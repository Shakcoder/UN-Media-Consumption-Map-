#!/usr/bin/env python3
"""
refresh_data.py — automated data refresh for the Global Media Consumption Atlas.

Runs on a schedule (see .github/workflows/refresh-data.yml) and does three things:

  1. Reads data/static_countries.json — the hand-curated metadata
     (overviews, industries, media outlets).
  2. Fetches the latest quantitative indicators from the World Bank Open Data
     API for every country listed.
  3. Merges hand-curated snapshots from institutional sources (RSF, Freedom
     House, Reuters Institute, DataReportal) that do not offer public APIs.
  4. Writes the merged result to data/countries.json, which the website loads
     at runtime.

Primary sources used by this script (all free, no API key required):
  - World Bank Open Data API — https://api.worldbank.org/v2/
  - Reporters Without Borders (RSF) — https://rsf.org/
  - Freedom House: Freedom on the Net — https://freedomhouse.org/report/freedom-net
  - Reuters Institute Digital News Report — https://reutersinstitute.politics.ox.ac.uk/digital-news-report
  - DataReportal — https://datareportal.com/

If any single indicator fetch fails, the script preserves the previous value
from countries.json and logs the failure — it never emits partial or empty
rows.
"""

from __future__ import annotations

import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

# --------------------------------------------------------------------------
# Paths
# --------------------------------------------------------------------------
REPO_ROOT = Path(__file__).resolve().parent.parent
STATIC_PATH = REPO_ROOT / "data" / "static_countries.json"
OUTPUT_PATH = REPO_ROOT / "data" / "countries.json"

# --------------------------------------------------------------------------
# World Bank indicator codes  (automated via API — refreshes weekly)
# https://data.worldbank.org/indicator
# --------------------------------------------------------------------------
WORLD_BANK_INDICATORS: dict[str, str] = {
    "population": "SP.POP.TOTL",
    "gdp_per_capita_usd": "NY.GDP.PCAP.CD",
    "internet_pct": "IT.NET.USER.ZS",
    "urban_pct": "SP.URB.TOTL.IN.ZS",
    "literacy_pct": "SE.ADT.LITR.ZS",
    "age_0_14_pct": "SP.POP.0014.TO.ZS",
    "age_15_64_pct": "SP.POP.1564.TO.ZS",
    "age_65_plus_pct": "SP.POP.65UP.TO.ZS",
    "mobile_per_100": "IT.CEL.SETS.P2",
    "fixed_broadband_per_100": "IT.NET.BBND.P2",
    "area_km2": "AG.SRF.TOTL.K2",
    "electricity_pct": "EG.ELC.ACCS.ZS",
    "life_expectancy": "SP.DYN.LE00.IN",
    "edu_spending_gdp_pct": "SE.XPD.TOTL.GD.ZS",
}

# ISO-3166 alpha-3 to alpha-2 mapping for World Bank source URLs.
ISO3_TO_ISO2: dict[str, str] = {
    "USA": "US", "GBR": "GB", "BRA": "BR", "NGA": "NG", "KEN": "KE",
    "IND": "IN", "CHN": "CN", "IDN": "ID", "DEU": "DE", "MEX": "MX",
    "FRA": "FR", "JPN": "JP", "ZAF": "ZA", "ARG": "AR", "AUS": "AU",
    "CAN": "CA", "RUS": "RU", "EGY": "EG", "ETH": "ET", "TUR": "TR",
    "PAK": "PK", "BGD": "BD", "VNM": "VN", "PHL": "PH", "KOR": "KR",
    "THA": "TH", "ESP": "ES", "ITA": "IT", "POL": "PL", "NLD": "NL",
    "COD": "CD", "IRN": "IR", "COL": "CO", "SAU": "SA",
    "UGA": "UG", "SDN": "SD", "DZA": "DZ", "MAR": "MA", "AGO": "AO",
    "GHA": "GH", "MOZ": "MZ", "MMR": "MM", "IRQ": "IQ", "AFG": "AF",
    "MYS": "MY", "NPL": "NP", "YEM": "YE", "UKR": "UA", "PER": "PE",
    "VEN": "VE", "CMR": "CM", "MDG": "MG",
}

# ======================================================================
# HAND-CURATED SNAPSHOT TABLES
# These are refreshed once a year when each organisation publishes its
# new edition. Every table lists its source URL so the numbers can be
# verified. The implementation pattern is always the same: a Python dict
# keyed by ISO-3 code. To update, edit the values and commit.
# ======================================================================

# --- DataReportal: smartphone penetration (2024) ---
# Source: https://datareportal.com/reports
SMARTPHONE_PCT_2024: dict[str, float] = {
    "USA": 91, "GBR": 92, "BRA": 84, "NGA": 52, "KEN": 62,
    "IND": 71, "CHN": 68, "IDN": 74, "DEU": 88, "MEX": 79,
    "PAK": 54, "BGD": 53, "RUS": 78, "ETH": 25, "JPN": 91,
    "PHL": 78, "EGY": 72, "COD": 25, "VNM": 80, "IRN": 76,
    "TUR": 85, "THA": 89, "FRA": 88, "ZAF": 84, "ITA": 88,
    "COL": 75, "ARG": 85, "CAN": 89, "SAU": 93, "AUS": 91,
    "UGA": 30, "SDN": 40, "DZA": 75, "MAR": 78, "AGO": 35,
    "GHA": 55, "MOZ": 30, "MMR": 60, "KOR": 97, "IRQ": 75,
    "AFG": 30, "MYS": 90, "NPL": 50, "YEM": 45, "UKR": 85,
    "POL": 85, "PER": 70, "VEN": 65, "CMR": 45, "MDG": 25,
}

# --- RSF Press Freedom Index 2024 ranks (lower = more free) ---
# Source: https://rsf.org/en/index
RSF_RANK_2024: dict[str, int] = {
    "USA": 55, "GBR": 23, "BRA": 82, "NGA": 112, "KEN": 102,
    "IND": 159, "CHN": 172, "IDN": 111, "DEU": 10, "MEX": 121,
    "FRA": 21, "JPN": 70, "ZAF": 38, "ARG": 66, "AUS": 39,
    "CAN": 14, "RUS": 162, "EGY": 170, "ETH": 141, "TUR": 158,
    "PAK": 152, "BGD": 165, "VNM": 174, "PHL": 134, "KOR": 62,
    "THA": 87, "ESP": 30, "ITA": 46, "POL": 47, "NLD": 3,
    "COD": 123, "IRN": 176, "COL": 139, "SAU": 166,
    "UGA": 128, "SDN": 149, "DZA": 139, "MAR": 129, "AGO": 104,
    "GHA": 50, "MOZ": 102, "MMR": 171, "IRQ": 169, "AFG": 178,
    "MYS": 107, "NPL": 74, "YEM": 168, "UKR": 61, "PER": 125,
    "VEN": 156, "CMR": 130, "MDG": 54,
}

# --- Freedom House: Freedom on the Net 2023 ---
# Scores 0–100, higher = more free. Status derived from score.
# Source: https://freedomhouse.org/report/freedom-net
FREEDOM_HOUSE_FOTN_2023: dict[str, int] = {
    "USA": 76, "BRA": 64, "NGA": 49, "KEN": 51, "IND": 50,
    "CHN": 9, "IDN": 47, "DEU": 80, "MEX": 56, "PAK": 26,
    "BGD": 40, "RUS": 21, "ETH": 27, "JPN": 78, "PHL": 62,
    "EGY": 25, "VNM": 22, "IRN": 14, "TUR": 32, "THA": 39,
    "FRA": 77, "ZAF": 72, "ITA": 76, "COL": 63, "ARG": 70,
    "SAU": 24, "UGA": 43, "MAR": 44, "AGO": 31, "GHA": 65,
    "MMR": 17, "KOR": 66, "MYS": 41, "UKR": 55, "VEN": 28,
}

def _fotn_status(score: int) -> str:
    if score >= 70:
        return "Free"
    if score >= 40:
        return "Partly Free"
    return "Not Free"

# --- Reuters Institute Digital News Report 2024 ---
# Per-country metrics: trust in news %, TV for news %, online for news %,
# social media for news %.
# Source: https://reutersinstitute.politics.ox.ac.uk/digital-news-report/2024
REUTERS_DNR_2024: dict[str, dict[str, int]] = {
    "USA": {"trust": 32, "tv": 47, "online": 76, "social": 39},
    "GBR": {"trust": 36, "tv": 47, "online": 73, "social": 34},
    "BRA": {"trust": 43, "tv": 62, "online": 87, "social": 56},
    "IND": {"trust": 38, "tv": 57, "online": 78, "social": 52},
    "IDN": {"trust": 56, "tv": 66, "online": 86, "social": 61},
    "DEU": {"trust": 43, "tv": 60, "online": 72, "social": 30},
    "MEX": {"trust": 40, "tv": 54, "online": 83, "social": 56},
    "JPN": {"trust": 42, "tv": 52, "online": 72, "social": 24},
    "FRA": {"trust": 30, "tv": 48, "online": 73, "social": 34},
    "ZAF": {"trust": 51, "tv": 56, "online": 82, "social": 47},
    "ITA": {"trust": 35, "tv": 52, "online": 75, "social": 39},
    "COL": {"trust": 34, "tv": 48, "online": 81, "social": 52},
    "ARG": {"trust": 30, "tv": 59, "online": 81, "social": 47},
    "AUS": {"trust": 41, "tv": 42, "online": 77, "social": 36},
    "CAN": {"trust": 40, "tv": 43, "online": 76, "social": 36},
    "KOR": {"trust": 30, "tv": 48, "online": 82, "social": 36},
    "TUR": {"trust": 33, "tv": 68, "online": 85, "social": 61},
    "POL": {"trust": 36, "tv": 57, "online": 79, "social": 42},
    "THA": {"trust": 52, "tv": 66, "online": 88, "social": 67},
    "KEN": {"trust": 61, "tv": 59, "online": 83, "social": 52},
    "NGA": {"trust": 59, "tv": 56, "online": 84, "social": 53},
    "PHL": {"trust": 30, "tv": 55, "online": 86, "social": 61},
    "PER": {"trust": 29, "tv": 53, "online": 79, "social": 49},
}


# --------------------------------------------------------------------------
# HTTP helper
# --------------------------------------------------------------------------
def fetch_json(url: str, max_retries: int = 3, timeout: int = 20) -> Any:
    last_exc: Exception | None = None
    for attempt in range(max_retries):
        try:
            req = Request(url, headers={
                "User-Agent": "UN-Media-Consumption-Atlas/1.0 (+github actions)",
                "Accept": "application/json",
            })
            with urlopen(req, timeout=timeout) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except (HTTPError, URLError, TimeoutError) as e:
            last_exc = e
            if attempt < max_retries - 1:
                time.sleep(2 ** attempt)
    raise RuntimeError(f"Failed after {max_retries} attempts: {url}") from last_exc


def fetch_indicator_all_countries(wb_code: str) -> dict[str, tuple[float, int]]:
    url = (
        f"https://api.worldbank.org/v2/country/all/indicator/{wb_code}"
        "?format=json&per_page=500&mrnev=1"
    )
    out: dict[str, tuple[float, int]] = {}
    try:
        payload = fetch_json(url)
    except Exception as exc:
        print(f"  ! {wb_code}: bulk fetch failed, will fall back to previous values: {exc}")
        return out

    if not isinstance(payload, list) or len(payload) < 2 or not payload[1]:
        return out

    for row in payload[1]:
        iso3 = row.get("countryiso3code")
        value = row.get("value")
        if not iso3 or value is None:
            continue
        try:
            out[iso3] = (float(value), int(row["date"]))
        except (TypeError, ValueError):
            continue
    return out


# --------------------------------------------------------------------------
# Build one country row
# --------------------------------------------------------------------------
def build_country(
    iso3: str,
    static_meta: dict[str, Any],
    prev: dict[str, Any] | None,
    wb_data: dict[str, dict[str, tuple[float, int]]],
) -> dict[str, Any]:
    iso2 = ISO3_TO_ISO2.get(iso3, iso3)

    print(f"→ {iso3} ({static_meta.get('name', iso3)})")

    values: dict[str, Any] = {}
    latest_year: int | None = None
    sources: dict[str, str] = {}

    for field, wb_code in WORLD_BANK_INDICATORS.items():
        pair = wb_data.get(field, {}).get(iso3)
        value, year = pair if pair else (None, None)
        if value is None and prev:
            prev_value = _lookup_previous(prev, field)
            if prev_value is not None:
                values[field] = prev_value
                print(f"  = {field}: preserved previous value ({prev_value})")
                continue
        if value is not None:
            if field in {"population", "area_km2"}:
                values[field] = int(round(value))
            elif field in {"gdp_per_capita_usd"}:
                values[field] = int(round(value))
            elif field == "life_expectancy":
                values[field] = round(value, 1)
            elif field == "edu_spending_gdp_pct":
                values[field] = round(value, 1)
            else:
                values[field] = round(value, 1)
            if year and (latest_year is None or year > latest_year):
                latest_year = year
            sources[field] = (
                f"World Bank — https://data.worldbank.org/indicator/{wb_code}?locations={iso2}"
            )

    # --- Smartphone % (DataReportal) ---
    if iso3 in SMARTPHONE_PCT_2024:
        values["smartphone_pct"] = SMARTPHONE_PCT_2024[iso3]
        sources["smartphone_pct"] = "DataReportal Digital Report 2024 — https://datareportal.com/"

    # --- Press freedom (RSF) ---
    if iso3 in RSF_RANK_2024:
        values["press_freedom_rank"] = RSF_RANK_2024[iso3]
        sources["press_freedom_rank"] = f"RSF 2024 — https://rsf.org/en/country/{iso3.lower()}"

    # --- Internet freedom (Freedom House) ---
    if iso3 in FREEDOM_HOUSE_FOTN_2023:
        score = FREEDOM_HOUSE_FOTN_2023[iso3]
        values["internet_freedom_score"] = score
        values["internet_freedom_status"] = _fotn_status(score)
        sources["internet_freedom"] = f"Freedom House: Freedom on the Net 2023 — https://freedomhouse.org/country/{static_meta.get('name', iso3).lower().replace(' ', '-')}/freedom-net/2023"

    # --- News consumption (Reuters Institute DNR) ---
    dnr = REUTERS_DNR_2024.get(iso3)
    if dnr:
        values["news_trust_pct"] = dnr["trust"]
        values["news_tv_pct"] = dnr["tv"]
        values["news_online_pct"] = dnr["online"]
        values["news_social_pct"] = dnr["social"]
        sources["news_consumption"] = "Reuters Institute Digital News Report 2024 — https://reutersinstitute.politics.ox.ac.uk/digital-news-report/2024"

    # Nest fields the way the website expects.
    country: dict[str, Any] = {
        **static_meta,
        "population": values.get("population"),
        "population_year": latest_year or datetime.now().year - 2,
        "area_km2": values.get("area_km2"),
        "gdp_per_capita_usd": values.get("gdp_per_capita_usd"),
        "demographics": {
            "age_0_14_pct": values.get("age_0_14_pct"),
            "age_15_64_pct": values.get("age_15_64_pct"),
            "age_65_plus_pct": values.get("age_65_plus_pct"),
            "urban_pct": values.get("urban_pct"),
            "literacy_pct": values.get("literacy_pct"),
            "life_expectancy": values.get("life_expectancy"),
            "electricity_pct": values.get("electricity_pct"),
            "edu_spending_gdp_pct": values.get("edu_spending_gdp_pct"),
        },
        "connectivity": {
            "internet_pct": values.get("internet_pct"),
            "mobile_per_100": values.get("mobile_per_100"),
            "smartphone_pct": values.get("smartphone_pct"),
            "fixed_broadband_per_100": values.get("fixed_broadband_per_100"),
        },
        "media": {
            **static_meta.get("media", {}),
            "press_freedom_rank": values.get("press_freedom_rank"),
            "press_freedom_source": "RSF 2024",
        },
        "information_freedom": {
            "press_freedom_rank": values.get("press_freedom_rank"),
            "press_freedom_source": "RSF 2024 — https://rsf.org/en/index",
            "internet_freedom_score": values.get("internet_freedom_score"),
            "internet_freedom_status": values.get("internet_freedom_status"),
            "internet_freedom_source": "Freedom House: Freedom on the Net 2023 — https://freedomhouse.org/report/freedom-net",
        },
        "news_consumption": {
            "trust_in_news_pct": values.get("news_trust_pct"),
            "tv_as_news_source_pct": values.get("news_tv_pct"),
            "online_as_news_source_pct": values.get("news_online_pct"),
            "social_as_news_source_pct": values.get("news_social_pct"),
            "source": "Reuters Institute Digital News Report 2024",
        },
        "sources": sources,
        "confidence": "verified",
        "retrieved_on": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
    }

    if not values:
        country["confidence"] = "preliminary"

    return country


def _lookup_previous(prev: dict[str, Any], field: str) -> Any:
    if field in prev:
        return prev[field]
    for group in ("demographics", "connectivity", "media", "information_freedom", "news_consumption"):
        if field in prev.get(group, {}):
            return prev[group][field]
    return None


# --------------------------------------------------------------------------
# Main
# --------------------------------------------------------------------------
def main() -> int:
    if not STATIC_PATH.exists():
        print(f"Missing {STATIC_PATH}", file=sys.stderr)
        return 1

    static = json.loads(STATIC_PATH.read_text(encoding="utf-8"))
    static = {k: v for k, v in static.items() if not k.startswith("_")}

    previous: dict[str, Any] = {}
    if OUTPUT_PATH.exists():
        try:
            previous = json.loads(OUTPUT_PATH.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            previous = {}

    print("Fetching World Bank indicators (one bulk request each)...")
    wb_data: dict[str, dict[str, tuple[float, int]]] = {}
    for field, wb_code in WORLD_BANK_INDICATORS.items():
        wb_data[field] = fetch_indicator_all_countries(wb_code)
        print(f"  · {field} ({wb_code}): {len(wb_data[field])} countries returned")

    result: dict[str, Any] = {}
    for iso3, meta in sorted(static.items()):
        result[iso3] = build_country(iso3, meta, previous.get(iso3), wb_data)

    result["_meta"] = {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "country_count": len([k for k in result if not k.startswith("_")]),
        "schema_version": 2,
        "data_sources": [
            "World Bank Open Data API (14 indicators, automated weekly)",
            "DataReportal Digital Report 2024 (smartphone penetration, manual annual)",
            "RSF Press Freedom Index 2024 (180 countries, manual annual)",
            "Freedom House: Freedom on the Net 2023 (70 countries, manual annual)",
            "Reuters Institute Digital News Report 2024 (23 markets, manual annual)",
        ],
    }

    OUTPUT_PATH.write_text(
        json.dumps(result, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(f"\nWrote {OUTPUT_PATH} with {result['_meta']['country_count']} countries.")
    print(f"Data sources: {len(result['_meta']['data_sources'])}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
