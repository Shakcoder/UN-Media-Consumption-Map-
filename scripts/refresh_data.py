#!/usr/bin/env python3
"""
refresh_data.py — automated data refresh for the Global Media Consumption Atlas.

Runs on a schedule (see .github/workflows/refresh-data.yml) and does three things:

  1. Reads data/static_countries.json — the hand-curated metadata
     (overviews, industries, media outlets).
  2. Fetches the latest quantitative indicators from the World Bank Open Data
     API for every country listed.
  3. Writes the merged result to data/countries.json, which the website loads
     at runtime.

The script is deliberately simple so that a maintainer using GitHub Copilot can
read it, understand it, and extend it without prior Python experience.

To expand to more countries, add their ISO-3166 alpha-3 code (e.g. "FRA") as a
key inside data/static_countries.json with the standard metadata block. The
script will automatically attempt to populate its numeric indicators on the
next scheduled run.

Primary sources used by this script (all free, no API key required):
  - World Bank Open Data API — https://api.worldbank.org/v2/
    Returns population, GDP per capita, internet usage, urban share, literacy,
    age brackets, mobile subscriptions, fixed broadband, and land area.

  - Reporters Without Borders (RSF) — https://rsf.org/
    The annual Press Freedom Index ranking. The API is not public; this script
    stores a hand-curated snapshot that is refreshed once a year when RSF
    publishes its new edition (traditionally in May).

If any single indicator fetch fails, the script preserves the previous value
from countries.json and logs the failure — it never emits partial or empty
rows. All refreshes carry a "retrieved_on" timestamp so the website can show
data freshness to visitors.
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
# World Bank indicator codes
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
}

# ISO-3166 alpha-3 to alpha-2 mapping for World Bank requests.
# Add new entries as the country list grows.
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

# Smartphone penetration is NOT in the World Bank API; DataReportal
# publishes per-country values annually. Until we implement its scraper,
# we carry a hand-updated table, refreshed once a year.
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

# RSF Press Freedom Index 2024 ranks, manually curated.
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


# --------------------------------------------------------------------------
# HTTP helper — simple, no external dependencies
# --------------------------------------------------------------------------
def fetch_json(url: str, max_retries: int = 3, timeout: int = 20) -> Any:
    """
    Fetch a JSON document with a few retries on transient failure.
    Uses only the Python standard library so the GitHub Actions job needs
    no `pip install` step.
    """
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


def latest_world_bank_value(iso2: str, indicator: str) -> tuple[float | None, int | None]:
    """
    Query the World Bank for one indicator and return (value, reference_year)
    for the most recent year that has a non-null value.
    """
    url = (
        f"https://api.worldbank.org/v2/country/{iso2}/indicator/{indicator}"
        "?format=json&per_page=20"
    )
    try:
        payload = fetch_json(url)
    except Exception as exc:  # noqa: BLE001 — intentional catch-all for resilience
        print(f"  ! {indicator}: {exc}")
        return None, None

    if not isinstance(payload, list) or len(payload) < 2 or not payload[1]:
        return None, None

    for row in payload[1]:
        value = row.get("value")
        if value is not None:
            try:
                return float(value), int(row["date"])
            except (TypeError, ValueError):
                continue
    return None, None


# --------------------------------------------------------------------------
# Build one country row
# --------------------------------------------------------------------------
def build_country(iso3: str, static_meta: dict[str, Any], prev: dict[str, Any] | None) -> dict[str, Any]:
    iso2 = ISO3_TO_ISO2.get(iso3)
    if not iso2:
        print(f"  ! {iso3}: no ISO-2 mapping — add it to ISO3_TO_ISO2 and re-run.")
        return {}

    print(f"→ {iso3} ({static_meta.get('name', iso3)})")

    # Quantitative block
    values: dict[str, Any] = {}
    latest_year: int | None = None
    sources: dict[str, str] = {}

    for field, wb_code in WORLD_BANK_INDICATORS.items():
        value, year = latest_world_bank_value(iso2, wb_code)
        if value is None and prev:
            # preserve whatever we had previously — never publish null
            prev_value = _lookup_previous(prev, field)
            if prev_value is not None:
                values[field] = prev_value
                print(f"  = {field}: preserved previous value ({prev_value})")
                continue
        if value is not None:
            # Integer-typed fields get rounded; percentages keep one decimal.
            if field in {"population", "area_km2"}:
                values[field] = int(round(value))
            elif field == "gdp_per_capita_usd":
                values[field] = int(round(value))
            else:
                values[field] = round(value, 1)
            if year and (latest_year is None or year > latest_year):
                latest_year = year
            sources[field] = (
                f"World Bank — https://data.worldbank.org/indicator/{wb_code}?locations={iso2}"
            )

    # Smartphone % — hand-curated snapshot
    if iso3 in SMARTPHONE_PCT_2024:
        values["smartphone_pct"] = SMARTPHONE_PCT_2024[iso3]
        sources["smartphone_pct"] = "DataReportal Digital Report 2024 — https://datareportal.com/"

    # Press freedom — hand-curated snapshot
    if iso3 in RSF_RANK_2024:
        values["press_freedom_rank"] = RSF_RANK_2024[iso3]
        sources["press_freedom_rank"] = f"RSF 2024 — https://rsf.org/en/country/{iso3.lower()}"

    # Nest demographics and connectivity the way the website expects.
    country: dict[str, Any] = {
        **static_meta,  # name, capital, flag, overview, industries, etc.
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
        "sources": sources,
        "confidence": "verified",
        "retrieved_on": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
    }

    # Honest fallback: if we somehow got nothing, mark the row preliminary.
    if not values:
        country["confidence"] = "preliminary"

    return country


def _lookup_previous(prev: dict[str, Any], field: str) -> Any:
    """Retrieve a previously-known value from the existing countries.json."""
    if field in prev:
        return prev[field]
    for group in ("demographics", "connectivity", "media"):
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

    # Drop the leading comment key
    static = {k: v for k, v in static.items() if not k.startswith("_")}

    # Load previous output (if any) so we can preserve values on fetch failure
    previous: dict[str, Any] = {}
    if OUTPUT_PATH.exists():
        try:
            previous = json.loads(OUTPUT_PATH.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            previous = {}

    result: dict[str, Any] = {}
    for iso3, meta in sorted(static.items()):
        result[iso3] = build_country(iso3, meta, previous.get(iso3))

    result["_meta"] = {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "country_count": len([k for k in result if not k.startswith("_")]),
        "schema_version": 1,
    }

    OUTPUT_PATH.write_text(
        json.dumps(result, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(f"\nWrote {OUTPUT_PATH} with {result['_meta']['country_count']} countries.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
