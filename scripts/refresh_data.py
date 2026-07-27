#!/usr/bin/env python3
"""
refresh_data.py — automated data refresh for the Global Media Consumption Atlas.

Primary sources (all free, no API key):
  - World Bank Open Data API (14 indicators, automated weekly)
  - RSF Press Freedom Index (174 countries, manual annual)
  - Freedom House: Freedom on the Net (70 countries, manual annual)
  - Freedom House: Freedom in the World (195 countries, manual annual)
  - Reuters Institute Digital News Report (46 of 48 markets, manual annual)
  - Afrobarometer (35 of 39 surveyed African countries, manual per wave)
  - Arab Barometer (Iraq only, real Wave VIII microdata — see 2026-07-22 note below)
  - DataReportal (smartphone penetration, manual annual)

Not yet integrated, pending free registration (see NEWS_CONSUMPTION's removal
note, 2026-07-22): Asian Barometer, Latinobarometro, Eurobarometer, World
Values Survey. Each would extend real news-consumption coverage once its
microdata is downloaded and computed the way Iraq's was — do not re-add a
country under one of these names without an actual downloaded file behind it.
"""

from __future__ import annotations

import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

REPO_ROOT = Path(__file__).resolve().parent.parent
STATIC_PATH = REPO_ROOT / "data" / "static_countries.json"
OUTPUT_PATH = REPO_ROOT / "data" / "countries.json"

# --------------------------------------------------------------------------
# World Bank indicator codes  (automated via API — 14 indicators)
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
    # Global Findex (World Bank): % of adults (15+) with a financial account —
    # incl. mobile money. A strong proxy for transactional digital adoption.
    "financial_account_pct": "FX.OWN.TOTL.ZS",
}

ISO3_TO_ISO2: dict[str, str] = {
    "AFG": "AF", "AGO": "AO", "ALB": "AL", "AND": "AD", "ARE": "AE",
    "ARG": "AR", "ARM": "AM", "ATG": "AG", "AUS": "AU", "AUT": "AT",
    "AZE": "AZ", "BDI": "BI", "BEL": "BE", "BEN": "BJ", "BFA": "BF",
    "BGD": "BD", "BGR": "BG", "BHR": "BH", "BHS": "BS", "BIH": "BA",
    "BLR": "BY", "BLZ": "BZ", "BOL": "BO", "BRA": "BR", "BRB": "BB",
    "BRN": "BN", "BTN": "BT", "BWA": "BW", "CAF": "CF", "CAN": "CA",
    "CHE": "CH", "CHL": "CL", "CHN": "CN", "CIV": "CI", "CMR": "CM",
    "COD": "CD", "COG": "CG", "COL": "CO", "COM": "KM", "CPV": "CV",
    "CRI": "CR", "CUB": "CU", "CYP": "CY", "CZE": "CZ", "DEU": "DE",
    "DJI": "DJ", "DMA": "DM", "DNK": "DK", "DOM": "DO", "DZA": "DZ",
    "ECU": "EC", "EGY": "EG", "ERI": "ER", "ESP": "ES", "EST": "EE",
    "ETH": "ET", "FIN": "FI", "FJI": "FJ", "FRA": "FR", "FSM": "FM",
    "GAB": "GA", "GBR": "GB", "GEO": "GE", "GHA": "GH", "GIN": "GN",
    "GMB": "GM", "GNB": "GW", "GNQ": "GQ", "GRC": "GR", "GRD": "GD",
    "GTM": "GT", "GUY": "GY", "HND": "HN", "HRV": "HR", "HTI": "HT",
    "HUN": "HU", "IDN": "ID", "IND": "IN", "IRL": "IE", "IRN": "IR",
    "IRQ": "IQ", "ISL": "IS", "ISR": "IL", "ITA": "IT", "JAM": "JM",
    "JOR": "JO", "JPN": "JP", "KAZ": "KZ", "KEN": "KE", "KGZ": "KG",
    "KHM": "KH", "KIR": "KI", "KNA": "KN", "KOR": "KR", "KWT": "KW",
    "LAO": "LA", "LBN": "LB", "LBR": "LR", "LBY": "LY", "LCA": "LC",
    "LIE": "LI", "LKA": "LK", "LSO": "LS", "LTU": "LT", "LUX": "LU",
    "LVA": "LV", "MAR": "MA", "MCO": "MC", "MDA": "MD", "MDG": "MG",
    "MDV": "MV", "MEX": "MX", "MHL": "MH", "MKD": "MK", "MLI": "ML",
    "MLT": "MT", "MMR": "MM", "MNE": "ME", "MNG": "MN", "MOZ": "MZ",
    "MRT": "MR", "MUS": "MU", "MWI": "MW", "MYS": "MY", "NAM": "NA",
    "NER": "NE", "NGA": "NG", "NIC": "NI", "NLD": "NL", "NOR": "NO",
    "NPL": "NP", "NRU": "NR", "NZL": "NZ", "OMN": "OM", "PAK": "PK",
    "PAN": "PA", "PER": "PE", "PHL": "PH", "PLW": "PW", "PNG": "PG",
    "POL": "PL", "PRK": "KP", "PRT": "PT", "PRY": "PY", "PSE": "PS",
    "QAT": "QA", "ROU": "RO", "RUS": "RU", "RWA": "RW", "SAU": "SA",
    "SDN": "SD", "SEN": "SN", "SGP": "SG", "SLB": "SB", "SLE": "SL",
    "SLV": "SV", "SMR": "SM", "SOM": "SO", "SRB": "RS", "SSD": "SS",
    "STP": "ST", "SUR": "SR", "SVK": "SK", "SVN": "SI", "SWE": "SE",
    "SWZ": "SZ", "SYC": "SC", "SYR": "SY", "TCD": "TD", "TGO": "TG",
    "THA": "TH", "TJK": "TJ", "TKM": "TM", "TLS": "TL", "TON": "TO",
    "TTO": "TT", "TUN": "TN", "TUR": "TR", "TUV": "TV", "TZA": "TZ",
    "UGA": "UG", "UKR": "UA", "URY": "UY", "USA": "US", "UZB": "UZ",
    "VAT": "VA", "VCT": "VC", "VEN": "VE", "VNM": "VN", "VUT": "VU",
    "WSM": "WS", "YEM": "YE", "ZAF": "ZA", "ZMB": "ZM", "ZWE": "ZW",
}

# ======================================================================
# HAND-CURATED SNAPSHOT TABLES — refreshed once per year per source
# ======================================================================

# --- DataReportal: smartphone penetration (2024) ---
# https://datareportal.com/reports
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

# --- RSF Press Freedom Index (fetched, not hand-typed) ---
# Until 2026-07-26 this file carried RSF_RANK_2025 / RSF_SCORE_2025 as two
# hand-transcribed dictionaries. Cross-checking them against RSF's own
# "previous edition" column showed 45 ranks that disagreed with RSF's record
# and a rank of 181 in a 180-country index — transcription drift, invisible
# because nothing could check it. The index now comes from RSF's published
# CSV via scripts/fetch_rsf.py, so refreshing it is one command and the
# numbers are whatever RSF published.
RSF_PATH = Path(__file__).resolve().parent.parent / "data" / "sources" / "rsf" / "rsf_index.json"


def _load_rsf() -> tuple[dict, int]:
    """Read the fetched RSF index. Fail loudly: silently dropping press
    freedom for 180 countries would be worse than stopping the refresh."""
    if not RSF_PATH.exists():
        raise SystemExit(
            f"Missing {RSF_PATH}.\n"
            "Run:  python3 scripts/fetch_rsf.py\n"
            "(downloads the current RSF World Press Freedom Index)")
    doc = json.loads(RSF_PATH.read_text(encoding="utf-8"))
    countries = doc.get("countries") or {}
    if len(countries) < 150:
        raise SystemExit(f"{RSF_PATH} holds only {len(countries)} countries — refusing to publish a truncated index.")
    return doc, int(doc["_meta"]["edition"])


RSF_INDEX, RSF_EDITION = _load_rsf()

# --- Freedom House: Freedom on the Net 2025 (internet-specific, 0–100) ---
# https://freedomhouse.org/country/scores?type=fotn
# FOTN only assesses a subset of countries (chosen for global significance
# and internet population) — 70 of our 195 are covered. Israel was rated in
# prior years but is not covered in the 2025 edition.
FREEDOM_HOUSE_FOTN_2025: dict[str, int] = {
    "AGO": 60, "ARE": 28, "ARG": 71, "ARM": 72, "AUS": 75,
    "AZE": 34, "BGD": 45, "BHR": 30, "BLR": 20, "BRA": 65,
    "CAN": 85, "CHL": 87, "CHN": 9, "COL": 64, "CRI": 86,
    "CUB": 21, "DEU": 74, "ECU": 63, "EGY": 28, "EST": 91,
    "ETH": 30, "FRA": 76, "GBR": 76, "GEO": 70, "GHA": 64,
    "HUN": 69, "IDN": 48, "IND": 51, "IRN": 13, "IRQ": 41,
    "ISL": 94, "ITA": 74, "JOR": 47, "JPN": 78, "KAZ": 37,
    "KEN": 58, "KGZ": 47, "KHM": 42, "KOR": 65, "LBN": 50,
    "LBY": 43, "LKA": 53, "MAR": 54, "MEX": 61, "MMR": 9,
    "MWI": 61, "MYS": 60, "NGA": 59, "NIC": 38, "NLD": 84,
    "PAK": 27, "PHL": 61, "RUS": 17, "RWA": 34, "SAU": 25,
    "SDN": 27, "SGP": 53, "SRB": 67, "THA": 39, "TUN": 59,
    "TUR": 31, "UGA": 52, "UKR": 62, "USA": 73, "UZB": 29,
    "VEN": 26, "VNM": 22, "ZAF": 73, "ZMB": 62, "ZWE": 50,
}

# --- Freedom House: Freedom in the World 2026 report (covers calendar year 2025; political freedom, 0–100) ---
# Covers ALL countries. Higher = more free.
# https://freedomhouse.org/report/freedom-world — data via Our World in Data
# (ourworldindata.org/grapher/freedom-score-fh), verified against 195 countries.
# PSE and VAT are NOT rated by Freedom House and are deliberately ABSENT here
# (removed 2026-07-21). Freedom House rates Gaza Strip and West Bank separately
# and issues no single Palestine score; it does not rate the Holy See at all.
# They previously carried a compiled estimate, but every downstream surface
# attributes this field to Freedom House by name — which misattributed a
# political judgement FH never made to a UN observer state. Per the project's
# own rule, "no reliable data" beats a bad estimate: they now render as no-data.
FREEDOM_HOUSE_FITW_2025: dict[str, int] = {
    "AFG": 8, "AGO": 28, "ALB": 69, "AND": 93, "ARE": 18,
    "ARG": 85, "ARM": 54, "ATG": 83, "AUS": 94, "AUT": 94,
    "AZE": 6, "BDI": 13, "BEL": 95, "BEN": 61, "BFA": 20,
    "BGD": 44, "BGR": 74, "BHR": 12, "BHS": 90, "BIH": 54,
    "BLR": 7, "BLZ": 87, "BOL": 69, "BRA": 73, "BRB": 94,
    "BRN": 27, "BTN": 69, "BWA": 75, "CAF": 5, "CAN": 97,
    "CHE": 96, "CHL": 95, "CHN": 9, "CIV": 46, "CMR": 15,
    "COD": 18, "COG": 17, "COL": 69, "COM": 41, "CPV": 92,
    "CRI": 91, "CUB": 9, "CYP": 90, "CZE": 95, "DEU": 95,
    "DJI": 24, "DMA": 92, "DNK": 97, "DOM": 67, "DZA": 31,
    "ECU": 64, "EGY": 18, "ERI": 3, "ESP": 91, "EST": 96,
    "ETH": 18, "FIN": 100, "FJI": 72, "FRA": 89, "FSM": 92,
    "GAB": 25, "GBR": 92, "GEO": 51, "GHA": 80, "GIN": 28,
    "GMB": 51, "GNB": 33, "GNQ": 5, "GRC": 85, "GRD": 89,
    "GTM": 48, "GUY": 74, "HND": 47, "HRV": 82, "HTI": 22,
    "HUN": 65, "IDN": 56, "IND": 62, "IRL": 98, "IRN": 10,
    "IRQ": 31, "ISL": 95, "ISR": 73, "ITA": 87, "JAM": 81,
    "JOR": 34, "JPN": 96, "KAZ": 23, "KEN": 49, "KGZ": 25,
    "KHM": 22, "KIR": 89, "KNA": 89, "KOR": 83, "KWT": 30,
    "LAO": 13, "LBN": 41, "LBR": 65, "LBY": 10, "LCA": 91,
    "LIE": 90, "LKA": 63, "LSO": 67, "LTU": 90, "LUX": 97,
    "LVA": 89, "MAR": 37, "MCO": 82, "MDA": 60, "MDG": 50,
    "MDV": 41, "MEX": 58, "MHL": 93, "MKD": 67, "MLI": 21,
    "MLT": 88, "MMR": 4, "MNE": 68, "MNG": 84, "MOZ": 42,
    "MRT": 38, "MUS": 87, "MWI": 68, "MYS": 53, "NAM": 73,
    "NER": 27, "NGA": 44, "NIC": 14, "NLD": 97, "NOR": 99,
    "NPL": 59, "NRU": 75, "NZL": 99, "OMN": 24, "PAK": 32,
    "PAN": 82, "PER": 66, "PHL": 58, "PLW": 92, "PNG": 61,
    "POL": 82, "PRK": 3, "PRT": 96, "PRY": 63, 
    "QAT": 25, "ROU": 83, "RUS": 12, "RWA": 21, "SAU": 9,
    "SDN": 1, "SEN": 70, "SGP": 48, "SLB": 74, "SLE": 61,
    "SLV": 42, "SMR": 97, "SOM": 8, "SRB": 53, "SSD": 0,
    "STP": 84, "SUR": 81, "SVK": 88, "SVN": 97, "SWE": 99,
    "SWZ": 17, "SYC": 81, "SYR": 10, "TCD": 15, "TGO": 37,
    "THA": 33, "TJK": 5, "TKM": 1, "TLS": 73, "TON": 79,
    "TTO": 83, "TUN": 42, "TUR": 32, "TUV": 93, "TZA": 28,
    "UGA": 33, "UKR": 51, "URY": 97, "USA": 81, "UZB": 12,
    "VCT": 90, "VEN": 13, "VNM": 20, "VUT": 82,
    "WSM": 84, "YEM": 10, "ZAF": 81, "ZMB": 53, "ZWE": 25,
}

# Official Freedom House FIW 2026 detail: status (F/PF/NF), political-rights
# score (0-40), civil-liberties score (0-60), electoral-democracy designation.
# Source: official FH data files provided directly by Freedom House (July 2026).
# Kosovo/Taiwan excluded (non-UN); PSE/VAT not individually rated by FH.
FREEDOM_HOUSE_DETAIL_2026: dict[str, tuple[str, int, int, bool]] = {
    "AFG": ("NF", 1, 7, False), "AGO": ("NF", 10, 18, False), "ALB": ("PF", 28, 41, True),
    "AND": ("F", 38, 55, True), "ARE": ("NF", 5, 13, False), "ARG": ("F", 35, 50, True),
    "ARM": ("PF", 23, 31, True), "ATG": ("F", 32, 51, True), "AUS": ("F", 39, 55, True),
    "AUT": ("F", 38, 56, True), "AZE": ("NF", 0, 6, False), "BDI": ("NF", 2, 11, False),
    "BEL": ("F", 38, 57, True), "BEN": ("PF", 19, 42, False), "BFA": ("NF", 2, 18, False),
    "BGD": ("PF", 15, 29, False), "BGR": ("F", 30, 44, True), "BHR": ("NF", 2, 10, False),
    "BHS": ("F", 38, 52, True), "BIH": ("PF", 17, 37, False), "BLR": ("NF", 1, 6, False),
    "BLZ": ("F", 34, 53, True), "BOL": ("F", 30, 39, True), "BRA": ("F", 30, 43, True),
    "BRB": ("F", 37, 57, True), "BRN": ("NF", 7, 20, False), "BTN": ("F", 33, 36, True),
    "BWA": ("F", 31, 44, True), "CAF": ("NF", 1, 4, False), "CAN": ("F", 39, 58, True),
    "CHE": ("F", 39, 57, True), "CHL": ("F", 38, 57, True), "CHN": ("NF", -2, 11, False),
    "CIV": ("PF", 17, 29, False), "CMR": ("NF", 6, 9, False), "COD": ("NF", 4, 14, False),
    "COG": ("NF", 2, 15, False), "COL": ("F", 31, 38, True), "COM": ("PF", 16, 25, False),
    "CPV": ("F", 38, 54, True), "CRI": ("F", 38, 53, True), "CUB": ("NF", 0, 9, False),
    "CYP": ("F", 38, 52, True), "CZE": ("F", 37, 58, True), "DEU": ("F", 40, 55, True),
    "DJI": ("NF", 5, 19, False), "DMA": ("F", 37, 55, True), "DNK": ("F", 40, 57, True),
    "DOM": ("PF", 27, 40, True), "DZA": ("NF", 10, 21, False), "ECU": ("PF", 27, 37, True),
    "EGY": ("NF", 6, 12, False), "ERI": ("NF", 1, 2, False), "ESP": ("F", 37, 54, True),
    "EST": ("F", 39, 57, True), "ETH": ("NF", 8, 10, False), "FIN": ("F", 40, 60, True),
    "FJI": ("F", 28, 44, True), "FRA": ("F", 38, 51, True), "FSM": ("F", 37, 55, True),
    "GAB": ("NF", 5, 20, False), "GBR": ("F", 39, 53, True), "GEO": ("PF", 19, 32, False),
    "GHA": ("F", 35, 45, True), "GIN": ("NF", 6, 22, False), "GMB": ("PF", 22, 29, False),
    "GNB": ("PF", 7, 26, False), "GNQ": ("NF", 0, 5, False), "GRC": ("F", 35, 50, True),
    "GRD": ("F", 37, 52, True), "GTM": ("PF", 19, 29, False), "GUY": ("F", 29, 45, True),
    "HND": ("PF", 21, 26, False), "HRV": ("F", 34, 48, True), "HTI": ("NF", 5, 17, False),
    "HUN": ("PF", 24, 41, True), "IDN": ("PF", 28, 28, False), "IND": ("PF", 31, 31, True),
    "IRL": ("F", 40, 58, True), "IRN": ("NF", 4, 6, False), "IRQ": ("NF", 16, 15, False),
    "ISL": ("F", 38, 57, True), "ISR": ("F", 34, 39, True), "ITA": ("F", 35, 52, True),
    "JAM": ("F", 34, 47, True), "JOR": ("PF", 12, 22, False), "JPN": ("F", 40, 56, True),
    "KAZ": ("NF", 5, 18, False), "KEN": ("PF", 21, 28, False), "KGZ": ("NF", 4, 21, False),
    "KHM": ("NF", 4, 18, False), "KIR": ("F", 36, 53, True), "KNA": ("F", 35, 54, True),
    "KOR": ("F", 33, 50, True), "KWT": ("NF", 7, 23, False), "LAO": ("NF", 2, 11, False),
    "LBN": ("PF", 15, 26, False), "LBR": ("PF", 31, 34, True), "LBY": ("NF", 2, 8, False),
    "LCA": ("F", 38, 53, True), "LIE": ("F", 33, 57, True), "LKA": ("PF", 29, 34, True),
    "LSO": ("F", 31, 36, True), "LTU": ("F", 38, 52, True), "LUX": ("F", 38, 59, True),
    "LVA": ("F", 37, 52, True), "MAR": ("PF", 13, 24, False), "MCO": ("F", 25, 57, True),
    "MDA": ("PF", 25, 35, True), "MDG": ("PF", 16, 34, False), "MDV": ("PF", 19, 22, False),
    "MEX": ("PF", 26, 32, True), "MHL": ("F", 38, 55, True), "MKD": ("PF", 28, 39, True),
    "MLI": ("NF", 3, 18, False), "MLT": ("F", 35, 53, True), "MMR": ("NF", -2, 6, False),
    "MNE": ("PF", 26, 42, True), "MNG": ("F", 36, 48, True), "MOZ": ("PF", 13, 29, False),
    "MRT": ("PF", 15, 23, False), "MUS": ("F", 36, 51, True), "MWI": ("F", 30, 38, True),
    "MYS": ("PF", 22, 31, False), "NAM": ("F", 28, 45, True), "NER": ("NF", 3, 24, False),
    "NGA": ("PF", 20, 24, False), "NIC": ("NF", 2, 12, False), "NLD": ("F", 39, 58, True),
    "NOR": ("F", 39, 60, True), "NPL": ("PF", 27, 32, True), "NRU": ("F", 32, 43, True),
    "NZL": ("F", 40, 59, True), "OMN": ("NF", 6, 18, False), "PAK": ("PF", 12, 20, False),
    "PAN": ("F", 35, 47, True), "PER": ("PF", 27, 39, True), "PHL": ("PF", 25, 33, True),
    "PLW": ("F", 37, 55, True), "PNG": ("PF", 22, 39, False), "POL": ("F", 34, 48, True),
    "PRK": ("NF", 0, 3, False), "PRT": ("F", 39, 57, True), "PRY": ("PF", 26, 37, True),
    "QAT": ("NF", 7, 18, False), "ROU": ("F", 35, 48, True), "RUS": ("NF", 4, 8, False),
    "RWA": ("NF", 7, 14, False), "SAU": ("NF", 1, 8, False), "SDN": ("NF", -4, 5, False),
    "SEN": ("F", 30, 40, True), "SGP": ("PF", 19, 29, False), "SLB": ("F", 27, 47, True),
    "SLE": ("PF", 23, 38, True), "SLV": ("PF", 15, 27, False), "SMR": ("F", 39, 58, True),
    "SOM": ("NF", 2, 6, False), "SRB": ("PF", 18, 35, False), "SSD": ("NF", -4, 4, False),
    "STP": ("F", 35, 49, True), "SUR": ("F", 35, 46, True), "SVK": ("F", 35, 53, True),
    "SVN": ("F", 39, 58, True), "SWE": ("F", 40, 59, True), "SWZ": ("NF", 1, 16, False),
    "SYC": ("F", 35, 46, True), "SYR": ("NF", -2, 12, False), "TCD": ("NF", 1, 14, False),
    "TGO": ("PF", 11, 26, False), "THA": ("NF", 11, 22, False), "TJK": ("NF", 0, 5, False),
    "TKM": ("NF", 0, 1, False), "TLS": ("F", 33, 40, True), "TON": ("F", 29, 50, True),
    "TTO": ("F", 34, 49, True), "TUN": ("PF", 11, 31, False), "TUR": ("NF", 16, 16, False),
    "TUV": ("F", 37, 56, True), "TZA": ("NF", 6, 22, False), "UGA": ("NF", 10, 23, False),
    "UKR": ("PF", 22, 29, False), "URY": ("F", 40, 57, True), "USA": ("F", 32, 49, True),
    "UZB": ("NF", 2, 10, False), "VCT": ("F", 36, 54, True), "VEN": ("NF", 0, 13, False),
    "VNM": ("NF", 4, 16, False), "VUT": ("F", 32, 50, True), "WSM": ("F", 32, 52, True),
    "YEM": ("NF", 1, 9, False), "ZAF": ("F", 34, 47, True), "ZMB": ("PF", 22, 31, False),
    "ZWE": ("NF", 8, 17, False),
}

_FH_STATUS_WORDS = {"F": "Free", "PF": "Partly Free", "NF": "Not Free"}

def _freedom_status(score: int) -> str:
    """Fallback only, for the few countries without an official FH status
    (PSE, VAT). Everywhere else the official designation is used — FH derives
    status from PR/CL ratings, not the 0-100 total, so thresholds on the
    total mislabel countries near the boundaries."""
    if score >= 70:
        return "Free"
    if score >= 40:
        return "Partly Free"
    return "Not Free"

# Radio as a weekly news source (%), computed from Afrobarometer Round 9
# microdata (Q74A, weighted, values 3-4 = weekly or more). Radio is the
# leading news channel in much of Africa — a channel the digital-first
# sources miss entirely. 39 surveyed countries.
AFRO_RADIO_2023: dict[str, float] = {
    "AGO": 60.1, "BEN": 72.2, "BFA": 70.8, "BWA": 67.7, "CIV": 56.8,
    "CMR": 53.7, "COG": 59.0, "CPV": 48.8, "ETH": 44.9, "GAB": 51.0,
    "GHA": 79.6, "GIN": 72.0, "GMB": 67.7, "KEN": 85.1, "LBR": 78.9,
    "LSO": 72.0, "MAR": 44.9, "MDG": 65.0, "MLI": 72.8, "MOZ": 54.3,
    "MRT": 36.9, "MUS": 96.2, "MWI": 57.6, "NAM": 78.1, "NER": 52.9,
    "NGA": 65.0, "SDN": 45.1, "SEN": 68.8, "SLE": 67.3, "STP": 72.1,
    "SWZ": 67.0, "SYC": 81.2, "TGO": 75.4, "TUN": 39.1, "TZA": 74.4,
    "UGA": 78.8, "ZAF": 74.8, "ZMB": 66.2, "ZWE": 64.8,
}

# Median age of population, 2025 estimates. Source: UN DESA, World
# Population Prospects 2024 revision (CC BY 3.0 IGO) — the UN's own
# demographic standard. All 195 countries.
WPP_MEDIAN_AGE_2025: dict[str, float] = {
    "AFG": 17.3, "AGO": 16.6, "ALB": 37.3, "AND": 43.9, "ARE": 31.6,
    "ARG": 32.9, "ARM": 36.6, "ATG": 36.3, "AUS": 38.3, "AUT": 43.6,
    "AZE": 33.6, "BDI": 16.4, "BEL": 41.9, "BEN": 18.0, "BFA": 17.7,
    "BGD": 26.0, "BGR": 44.8, "BHR": 33.3, "BHS": 35.3, "BIH": 45.7,
    "BLR": 41.3, "BLZ": 26.9, "BOL": 25.2, "BRA": 34.8, "BRB": 39.4,
    "BRN": 32.7, "BTN": 30.5, "BWA": 23.4, "CAF": 14.5, "CAN": 40.6,
    "CHE": 42.9, "CHL": 36.9, "CHN": 40.1, "CIV": 18.3, "CMR": 18.0,
    "COD": 15.8, "COG": 18.6, "COL": 32.5, "COM": 20.6, "CPV": 29.0,
    "CRI": 35.2, "CUB": 42.2, "CYP": 38.6, "CZE": 43.8, "DEU": 45.5,
    "DJI": 24.9, "DMA": 36.3, "DNK": 41.3, "DOM": 28.3, "DZA": 28.6,
    "ECU": 29.3, "EGY": 24.5, "ERI": 19.2, "ESP": 45.9, "EST": 42.8,
    "ETH": 19.1, "FIN": 43.2, "FJI": 28.1, "FRA": 42.3, "FSM": 23.3,
    "GAB": 21.5, "GBR": 40.1, "GEO": 37.3, "GHA": 21.3, "GIN": 18.3,
    "GMB": 18.6, "GNB": 19.4, "GNQ": 20.9, "GRC": 46.8, "GRD": 34.4,
    "GTM": 23.4, "GUY": 26.2, "HND": 24.2, "HRV": 45.3, "HTI": 24.1,
    "HUN": 43.9, "IDN": 30.4, "IND": 28.8, "IRL": 39.0, "IRN": 34.0,
    "IRQ": 20.8, "ISL": 36.2, "ISR": 29.2, "ITA": 48.2, "JAM": 32.8,
    "JOR": 24.7, "JPN": 49.8, "KAZ": 29.7, "KEN": 20.0, "KGZ": 25.4,
    "KHM": 26.2, "KIR": 22.9, "KNA": 36.2, "KOR": 45.6, "KWT": 34.8,
    "LAO": 24.9, "LBN": 28.8, "LBR": 18.8, "LBY": 27.7, "LCA": 34.6,
    "LIE": 44.5, "LKA": 33.3, "LSO": 21.8, "LTU": 42.3, "LUX": 39.5,
    "LVA": 43.6, "MAR": 29.8, "MCO": 53.6, "MDA": 38.6, "MDG": 19.2,
    "MDV": 32.7, "MEX": 29.6, "MHL": 20.4, "MKD": 41.0, "MLI": 15.7,
    "MLT": 41.1, "MMR": 30.1, "MNE": 40.0, "MNG": 26.9, "MOZ": 16.5,
    "MRT": 17.4, "MUS": 37.8, "MWI": 18.1, "MYS": 31.0, "NAM": 21.3,
    "NER": 15.6, "NGA": 18.1, "NIC": 26.0, "NLD": 41.5, "NOR": 39.8,
    "NPL": 25.3, "NRU": 20.2, "NZL": 37.7, "OMN": 29.7, "PAK": 20.6,
    "PAN": 30.3, "PER": 30.2, "PHL": 26.1, "PLW": 38.5, "PNG": 22.8,
    "POL": 42.5, "PRK": 36.5, "PRT": 46.9, "PRY": 27.0, "PSE": 20.1,
    "QAT": 33.5, "ROU": 43.2, "RUS": 40.3, "RWA": 19.9, "SAU": 29.6,
    "SDN": 18.5, "SEN": 19.6, "SGP": 36.2, "SLB": 20.7, "SLE": 19.7,
    "SLV": 27.9, "SMR": 48.6, "SOM": 15.6, "SRB": 44.4, "SSD": 18.7,
    "STP": 19.5, "SUR": 28.6, "SVK": 42.3, "SVN": 44.7, "SWE": 40.3,
    "SWZ": 22.5, "SYC": 34.3, "SYR": 23.3, "TCD": 15.8, "TGO": 19.1,
    "THA": 40.6, "TJK": 22.2, "TKM": 26.9, "TLS": 21.7, "TON": 20.8,
    "TTO": 37.7, "TUN": 32.9, "TUR": 33.5, "TUV": 24.2, "TZA": 17.5,
    "UGA": 16.9, "UKR": 41.8, "URY": 36.4, "USA": 38.5, "UZB": 27.0,
    "VAT": 57.4, "VCT": 34.4, "VEN": 29.4, "VNM": 33.4, "VUT": 20.3,
    "WSM": 19.8, "YEM": 18.4, "ZAF": 28.7, "ZMB": 17.9, "ZWE": 18.1,
}

# GSMA Mobile Connectivity Index 2024 (0-100; higher = more enabling
# environment for mobile internet). Free dataset from
# mobileconnectivityindex.com (GSMA Intelligence). 172 countries.
GSMA_MCI_2024: dict[str, float] = {
    "AFG": 26.8, "AGO": 48.0, "ALB": 72.2, "ARE": 90.7, "ARG": 72.2,
    "ARM": 72.3, "AUS": 91.6, "AUT": 88.4, "AZE": 73.8, "BDI": 25.1,
    "BEL": 90.0, "BEN": 42.4, "BFA": 35.3, "BGD": 56.7, "BGR": 81.4,
    "BHR": 81.8, "BHS": 70.2, "BIH": 67.7, "BLR": 70.5, "BLZ": 64.2,
    "BOL": 62.2, "BRA": 77.1, "BRB": 65.5, "BRN": 74.6, "BTN": 64.4,
    "BWA": 64.4, "CAF": 22.3, "CAN": 88.2, "CHE": 91.2, "CHL": 79.7,
    "CHN": 83.5, "CIV": 50.6, "CMR": 49.0, "COD": 28.2, "COG": 40.8,
    "COL": 72.2, "COM": 34.1, "CPV": 60.0, "CRI": 73.0, "CYP": 86.7,
    "CZE": 87.4, "DEU": 92.0, "DNK": 93.4, "DOM": 70.3, "DZA": 57.9,
    "ECU": 68.8, "EGY": 65.9, "ESP": 90.9, "EST": 90.1, "ETH": 41.6,
    "FIN": 91.5, "FJI": 61.7, "FRA": 89.6, "GAB": 55.2, "GBR": 91.4,
    "GEO": 74.9, "GHA": 57.6, "GIN": 38.5, "GMB": 44.6, "GNB": 33.0,
    "GNQ": 43.5, "GRC": 84.1, "GTM": 64.8, "GUY": 63.9, "HND": 54.7,
    "HRV": 87.3, "HTI": 47.0, "HUN": 86.6, "IDN": 76.3, "IND": 69.2,
    "IRL": 91.1, "IRN": 65.4, "IRQ": 56.0, "ISL": 91.5, "ISR": 84.0,
    "ITA": 85.2, "JAM": 55.5, "JOR": 66.2, "JPN": 87.7, "KAZ": 76.9,
    "KEN": 56.8, "KGZ": 62.8, "KHM": 61.7, "KOR": 85.2, "KWT": 81.7,
    "LAO": 57.7, "LBN": 66.7, "LBR": 38.5, "LBY": 67.1, "LCA": 60.8,
    "LKA": 64.0, "LSO": 47.8, "LTU": 88.2, "LUX": 89.3, "LVA": 86.6,
    "MAR": 65.3, "MDA": 73.0, "MDG": 38.3, "MDV": 64.2, "MEX": 76.3,
    "MKD": 76.0, "MLI": 37.2, "MLT": 85.8, "MMR": 52.7, "MNE": 75.6,
    "MNG": 68.2, "MOZ": 40.6, "MRT": 42.8, "MUS": 73.0, "MWI": 39.8,
    "MYS": 80.3, "NAM": 56.3, "NER": 27.5, "NGA": 53.4, "NIC": 55.8,
    "NLD": 91.5, "NOR": 92.1, "NPL": 53.1, "NZL": 89.5, "OMN": 74.1,
    "PAK": 49.1, "PAN": 73.5, "PER": 72.3, "PHL": 71.5, "PNG": 47.6,
    "POL": 83.8, "PRT": 84.2, "PRY": 73.1, "QAT": 86.3, "ROU": 82.8,
    "RUS": 80.2, "RWA": 52.5, "SAU": 84.8, "SDN": 29.2, "SEN": 51.4,
    "SGP": 93.4, "SLB": 45.6, "SLE": 44.4, "SLV": 66.3, "SOM": 40.7,
    "SRB": 77.4, "SSD": 12.7, "SUR": 60.1, "SVK": 85.3, "SVN": 89.5,
    "SWE": 90.4, "SWZ": 57.1, "SYC": 74.0, "TCD": 26.9, "TGO": 47.9,
    "THA": 78.6, "TJK": 44.3, "TLS": 47.9, "TON": 64.2, "TTO": 69.3,
    "TUN": 66.6, "TUR": 77.9, "TZA": 46.8, "UGA": 45.5, "UKR": 71.3,
    "URY": 84.0, "USA": 91.3, "UZB": 67.8, "VCT": 62.0, "VEN": 59.8,
    "VNM": 79.5, "VUT": 59.0, "WSM": 64.3, "YEM": 28.4, "ZAF": 71.7,
    "ZMB": 44.2, "ZWE": 38.3,
}

# Primary compilers behind World Bank-republished indicators. The World Bank
# redistributes these under CC BY 4.0, which suits a public site better than
# ITU's own CC BY-NC-SA terms — same numbers, clean license. Credit both.
WB_DATA_ORIGINS = {
    "internet_pct": " (data originally compiled by ITU)",
    "mobile_per_100": " (data originally compiled by ITU)",
    "fixed_broadband_per_100": " (data originally compiled by ITU)",
    "literacy_pct": " (data originally compiled by UNESCO Institute for Statistics)",
    "edu_spending_gdp_pct": " (data originally compiled by UNESCO Institute for Statistics)",
    "financial_account_pct": " (Global Findex Database)",
}

# --- News consumption: ALL 50 countries ---
# Markets where the DNR 2026 sample is NOT nationally representative
# (online survey of mainly English-speaking / more urban, educated users —
# per the report's own methodology notes). Figures for these countries skew
# younger, urban, and connected; they are flagged in the output.
DNR_NON_REPRESENTATIVE = {"IND", "KEN", "NGA", "ZAF", "MAR"}

# Reuters Institute Digital News Report 2026 for markets they cover (46 of the
# 48 surveyed — Hong Kong and Taiwan excluded as non-UN-member entities),
# Afrobarometer for African markets, DataReportal 2024 for a few remaining
# markets DNR does not survey, and Arab Barometer Wave VIII for Iraq.
# Each entry: trust_pct, tv_pct, online_pct, social_pct, source label,
# optionally radio_pct and note (see the IRQ entry for the pattern).
NEWS_CONSUMPTION: dict[str, dict[str, Any]] = {
    # ---- Reuters Institute Digital News Report 2026 (46 markets) ----
    # Europe
    "GBR": {"trust": 30, "tv": 47, "online": 75, "social": 40, "src": "Reuters Institute DNR 2026"},
    "AUT": {"trust": 39, "tv": 57, "online": 71, "social": 40, "src": "Reuters Institute DNR 2026"},
    "BEL": {"trust": 39, "tv": 41, "online": 75, "social": 49, "src": "Reuters Institute DNR 2026"},
    "BGR": {"trust": 21, "tv": 58, "online": 75, "social": 58, "src": "Reuters Institute DNR 2026"},
    "HRV": {"trust": 29, "tv": 61, "online": 78, "social": 46, "src": "Reuters Institute DNR 2026"},
    "CZE": {"trust": 31, "tv": 60, "online": 81, "social": 44, "src": "Reuters Institute DNR 2026"},
    "DNK": {"trust": 55, "tv": 61, "online": 83, "social": 47, "src": "Reuters Institute DNR 2026"},
    "FIN": {"trust": 63, "tv": 61, "online": 87, "social": 45, "src": "Reuters Institute DNR 2026"},
    "FRA": {"trust": 29, "tv": 58, "online": 64, "social": 39, "src": "Reuters Institute DNR 2026"},
    "DEU": {"trust": 46, "tv": 59, "online": 67, "social": 36, "src": "Reuters Institute DNR 2026"},
    "GRC": {"trust": 18, "tv": 46, "online": 85, "social": 64, "src": "Reuters Institute DNR 2026"},
    "HUN": {"trust": 17, "tv": 40, "online": 83, "social": 62, "src": "Reuters Institute DNR 2026"},
    "IRL": {"trust": 42, "tv": 56, "online": 80, "social": 47, "src": "Reuters Institute DNR 2026"},
    "ITA": {"trust": 32, "tv": 62, "online": 69, "social": 45, "src": "Reuters Institute DNR 2026"},
    "NLD": {"trust": 49, "tv": 57, "online": 77, "social": 37, "src": "Reuters Institute DNR 2026"},
    "NOR": {"trust": 53, "tv": 53, "online": 87, "social": 43, "src": "Reuters Institute DNR 2026"},
    "POL": {"trust": 39, "tv": 56, "online": 77, "social": 52, "src": "Reuters Institute DNR 2026"},
    "PRT": {"trust": 51, "tv": 71, "online": 71, "social": 48, "src": "Reuters Institute DNR 2026"},
    "ROU": {"trust": 23, "tv": 58, "online": 72, "social": 48, "src": "Reuters Institute DNR 2026"},
    "SRB": {"trust": 22, "tv": 51, "online": 85, "social": 64, "src": "Reuters Institute DNR 2026"},
    "SVK": {"trust": 19, "tv": 52, "online": 71, "social": 50, "src": "Reuters Institute DNR 2026"},
    "ESP": {"trust": 33, "tv": 56, "online": 71, "social": 47, "src": "Reuters Institute DNR 2026"},
    "SWE": {"trust": 52, "tv": 61, "online": 87, "social": 47, "src": "Reuters Institute DNR 2026"},
    "CHE": {"trust": 42, "tv": 49, "online": 80, "social": 42, "src": "Reuters Institute DNR 2026"},
    "TUR": {"trust": 28, "tv": 53, "online": 71, "social": 49, "src": "Reuters Institute DNR 2026"},
    # Americas
    "USA": {"trust": 25, "tv": 56, "online": 77, "social": 45, "src": "Reuters Institute DNR 2026"},
    "ARG": {"trust": 26, "tv": 54, "online": 77, "social": 61, "src": "Reuters Institute DNR 2026"},
    "BRA": {"trust": 36, "tv": 44, "online": 76, "social": 53, "src": "Reuters Institute DNR 2026"},
    "CAN": {"trust": 37, "tv": 49, "online": 76, "social": 53, "src": "Reuters Institute DNR 2026"},
    "CHL": {"trust": 34, "tv": 54, "online": 76, "social": 59, "src": "Reuters Institute DNR 2026"},
    "COL": {"trust": 25, "tv": 38, "online": 78, "social": 60, "src": "Reuters Institute DNR 2026"},
    "MEX": {"trust": 31, "tv": 34, "online": 82, "social": 66, "src": "Reuters Institute DNR 2026"},
    "PER": {"trust": 32, "tv": 49, "online": 85, "social": 69, "src": "Reuters Institute DNR 2026"},
    # Asia-Pacific
    "AUS": {"trust": 43, "tv": 57, "online": 79, "social": 56, "src": "Reuters Institute DNR 2026"},
    "IND": {"trust": 39, "tv": 44, "online": 80, "social": 54, "src": "Reuters Institute DNR 2026"},
    "IDN": {"trust": 32, "tv": 42, "online": 83, "social": 64, "src": "Reuters Institute DNR 2026"},
    "JPN": {"trust": 41, "tv": 51, "online": 62, "social": 25, "src": "Reuters Institute DNR 2026"},
    "MYS": {"trust": 30, "tv": 36, "online": 84, "social": 69, "src": "Reuters Institute DNR 2026"},
    "PHL": {"trust": 28, "tv": 42, "online": 85, "social": 70, "src": "Reuters Institute DNR 2026"},
    "SGP": {"trust": 46, "tv": 40, "online": 87, "social": 59, "src": "Reuters Institute DNR 2026"},
    "KOR": {"trust": 30, "tv": 58, "online": 82, "social": 47, "src": "Reuters Institute DNR 2026"},
    "THA": {"trust": 47, "tv": 42, "online": 89, "social": 78, "src": "Reuters Institute DNR 2026"},
    # Africa
    "KEN": {"trust": 68, "tv": 66, "online": 91, "social": 74, "src": "Reuters Institute DNR 2026"},
    "MAR": {"trust": 28, "tv": 41, "online": 83, "social": 62, "src": "Reuters Institute DNR 2026"},
    "NGA": {"trust": 68, "tv": 59, "online": 94, "social": 79, "src": "Reuters Institute DNR 2026"},
    "ZAF": {"trust": 50, "tv": 56, "online": 89, "social": 74, "src": "Reuters Institute DNR 2026"},
    # ---- Afrobarometer Round 9 (2023) — 35 countries, computed from microdata ----
    # Weighted "weekly or more" usage (Q74 values 3-4) for TV/internet/social.
    # No comparable media-trust question in R9; trust intentionally left unset.
    "AGO": {"trust": None, "tv": 62.3, "online": 39.2, "social": 40.8, "src": "Afrobarometer Round 9 (2023)"},
    "BEN": {"trust": None, "tv": 33.2, "online": 27.0, "social": 34.6, "src": "Afrobarometer Round 9 (2023)"},
    "BFA": {"trust": None, "tv": 46.3, "online": 22.4, "social": 27.2, "src": "Afrobarometer Round 9 (2023)"},
    "BWA": {"trust": None, "tv": 41.1, "online": 37.0, "social": 47.3, "src": "Afrobarometer Round 9 (2023)"},
    "CIV": {"trust": None, "tv": 70.7, "online": 55.3, "social": 54.5, "src": "Afrobarometer Round 9 (2023)"},
    "CMR": {"trust": None, "tv": 73.9, "online": 63.7, "social": 67.1, "src": "Afrobarometer Round 9 (2023)"},
    "COG": {"trust": None, "tv": 57.0, "online": 40.9, "social": 41.9, "src": "Afrobarometer Round 9 (2023)"},
    "CPV": {"trust": None, "tv": 87.8, "online": 68.4, "social": 69.1, "src": "Afrobarometer Round 9 (2023)"},
    "ETH": {"trust": None, "tv": 37.0, "online": 19.3, "social": 20.2, "src": "Afrobarometer Round 9 (2023)"},
    "GAB": {"trust": None, "tv": 85.3, "online": 76.2, "social": 77.8, "src": "Afrobarometer Round 9 (2023)"},
    "GHA": {"trust": None, "tv": 71.4, "online": 41.9, "social": 43.2, "src": "Afrobarometer Round 9 (2023)"},
    "GIN": {"trust": None, "tv": 45.9, "online": 27.9, "social": 35.5, "src": "Afrobarometer Round 9 (2023)"},
    "GMB": {"trust": None, "tv": 57.7, "online": 47.5, "social": 61.4, "src": "Afrobarometer Round 9 (2023)"},
    "LBR": {"trust": None, "tv": 21.2, "online": 33.4, "social": 34.6, "src": "Afrobarometer Round 9 (2023)"},
    "LSO": {"trust": None, "tv": 41.6, "online": 31.2, "social": 41.9, "src": "Afrobarometer Round 9 (2023)"},
    "MDG": {"trust": None, "tv": 28.6, "online": 7.0, "social": 13.8, "src": "Afrobarometer Round 9 (2023)"},
    "MLI": {"trust": None, "tv": 50.2, "online": 30.2, "social": 38.8, "src": "Afrobarometer Round 9 (2023)"},
    "MOZ": {"trust": None, "tv": 45.3, "online": 25.7, "social": 26.9, "src": "Afrobarometer Round 9 (2023)"},
    "MRT": {"trust": None, "tv": 44.5, "online": 38.8, "social": 43.9, "src": "Afrobarometer Round 9 (2023)"},
    "MUS": {"trust": None, "tv": 96.4, "online": 82.0, "social": 80.9, "src": "Afrobarometer Round 9 (2023)"},
    "MWI": {"trust": None, "tv": 18.7, "online": 10.6, "social": 18.6, "src": "Afrobarometer Round 9 (2023)"},
    "NAM": {"trust": None, "tv": 50.2, "online": 49.1, "social": 49.6, "src": "Afrobarometer Round 9 (2023)"},
    "NER": {"trust": None, "tv": 17.3, "online": 17.4, "social": 23.6, "src": "Afrobarometer Round 9 (2023)"},
    "SDN": {"trust": None, "tv": 58.6, "online": 45.5, "social": 45.4, "src": "Afrobarometer Round 9 (2023)",
            "note": "Online-news use (45.5%, 2023 face-to-face survey) exceeds the internet-access figure because Sudan's World Bank/ITU internet series last reported in 2017 — a stale denominator, not a survey error. Treat the access figure as a lower bound."},
    "SEN": {"trust": None, "tv": 71.9, "online": 46.0, "social": 55.1, "src": "Afrobarometer Round 9 (2023)"},
    "SLE": {"trust": None, "tv": 14.9, "online": 27.2, "social": 33.4, "src": "Afrobarometer Round 9 (2023)"},
    "STP": {"trust": None, "tv": 75.9, "online": 57.1, "social": 55.9, "src": "Afrobarometer Round 9 (2023)"},
    "SWZ": {"trust": None, "tv": 67.6, "online": 62.1, "social": 61.9, "src": "Afrobarometer Round 9 (2023)"},
    "SYC": {"trust": None, "tv": 96.4, "online": 70.1, "social": 68.4, "src": "Afrobarometer Round 9 (2023)"},
    "TGO": {"trust": None, "tv": 49.8, "online": 39.7, "social": 49.7, "src": "Afrobarometer Round 9 (2023)"},
    "TUN": {"trust": None, "tv": 72.1, "online": 51.0, "social": 56.0, "src": "Afrobarometer Round 9 (2023)"},
    "TZA": {"trust": None, "tv": 47.3, "online": 19.0, "social": 20.4, "src": "Afrobarometer Round 9 (2023)"},
    "UGA": {"trust": None, "tv": 35.4, "online": 16.5, "social": 16.4, "src": "Afrobarometer Round 9 (2023)"},
    "ZMB": {"trust": None, "tv": 45.9, "online": 32.4, "social": 36.3, "src": "Afrobarometer Round 9 (2023)"},
    "ZWE": {"trust": None, "tv": 28.2, "online": 25.5, "social": 41.4, "src": "Afrobarometer Round 9 (2023)"},
    # DRC: REMOVED 2026-07-22. The old entry ("Estimate (DataReportal 2024)",
    # trust 47 / tv 38 / online 22 / social 18) had no checkable source —
    # DataReportal measures neither trust nor news-source mix. Same class as
    # the 15 fabricated entries removed earlier today, just labeled "estimate".
    # Afrobarometer Round 10 (releasing 2025-2026) is expected to cover DRC —
    # integrate the real figures when that lands.
    # ---- Arab Barometer Wave VIII (2023-2024), weighted from real microdata ----
    # Wave VIII is the only Arab Barometer edition with public data (Wave IX's
    # fieldwork runs through May 2026; nothing is released yet). Q421 asks
    # respondents their SINGLE primary source for breaking news — a different
    # question from the multi-select "used weekly" figures elsewhere in this
    # table, so it is not directly comparable across countries. No trust-in-media
    # question exists anywhere in Wave VIII's questionnaire, so "trust" is None.
    "IRQ": {"trust": None, "tv": 27.2, "online": None, "social": 45.3, "radio": 1.3,
            "src": "Arab Barometer Wave VIII (2023-2024) microdata",
            "note": "Q421: single primary news source (not multi-select weekly use — not directly comparable to other countries' figures); no trust-in-media question in this wave"},
    "KWT": {"trust": None, "tv": 18.2, "online": None, "social": 65.3, "radio": 1.0,
            "src": "Arab Barometer Wave VIII (2023-2024) microdata",
            "note": "Q421: single primary news source (not multi-select weekly use — not directly comparable to other countries' figures); no trust-in-media question in this wave"},
    "PSE": {"trust": None, "tv": 16.5, "online": None, "social": 70.1, "radio": 4.1,
            "src": "Arab Barometer Wave VIII (2023-2024) microdata",
            "note": "Q421: single primary news source (not multi-select weekly use — not directly comparable to other countries' figures); no trust-in-media question in this wave"},
    # ---- Arab Barometer Wave VII (2021-2022) — gap countries only ----
    # Computed by scripts/compute_arabbarometer_w7.py. Algeria is W7's one
    # true gap-fill: Libya already has WVS Wave 7 (2022) data with a richer
    # construct (weekly multi-select + trust), so it stays on WVS. Same Q421
    # primary-source construct and caveats as Wave VIII.
    "DZA": {"trust": None, "tv": 47.1, "online": None, "social": 33.3, "radio": 5.1,
            "src": "Arab Barometer Wave VII (2021-2022) microdata",
            "note": "Q421: single primary news source (not multi-select weekly use — not directly comparable to other countries' figures); no trust-in-media question in this wave"},
    # ---- Asian Barometer Wave 6, weighted microdata ----
    # Computed by scripts/compute_asianbarometer.py from the registered
    # download (asianbarometer.org). Same single-choice "most important
    # channel" construct as Arab Barometer, so the same caveat travels with
    # it. Only Cambodia is taken: Mongolia and Vietnam already carry WVS
    # Wave 7 entries, and mixing two constructs for one country would make
    # its figures incomparable with its own history.
    "KHM": {"trust": None, "tv": 13.2, "online": 63.3, "social": None, "radio": 5.5,
            "src": "Asian Barometer Wave 6 (2024) microdata, weighted (n=1,030)",
            "note": "q53: single most-important news channel (not multi-select weekly use — not directly comparable to other countries' figures); the answer option combines internet and social media, so social media is not separable; no trust-in-media question in this wave"},
    # ---- World Values Survey Wave 7 (2017-2022), weighted microdata ----
    # Computed by scripts/compute_wvs_news.py from the registered download
    # (raw .sav NOT in this repo — WVSA prohibits redistribution). Only
    # countries with no newer survey are listed; DNR/Afrobarometer/Arab
    # Barometer entries above always take precedence. Constructs differ
    # from DNR (see each entry's note) — never strip these notes.
    # Citation: Haerpfer et al. (eds.) 2022, WVS Round Seven v6.0,
    # doi:10.14281/18241.24
    "AND": {"trust": 36.9, "tv": 84.0, "online": 66.0, "social": 66.0, "radio": 42.0,
            "src": "World Values Survey Wave 7 (2018), weighted microdata (n=1,004)",
            "note": "WVS constructs: use = daily or weekly (vs DNR's 'past week'); trust = confidence in the press as an institution, not DNR's trust-in-news"},
    "ARM": {"trust": 12.1, "tv": 81.0, "online": 75.4, "social": 72.9, "radio": 18.1,
            "src": "World Values Survey Wave 7 (2021), weighted microdata (n=1,223)",
            "note": "WVS constructs: use = daily or weekly (vs DNR's 'past week'); trust = confidence in the press as an institution, not DNR's trust-in-news"},
    "BGD": {"trust": 71.6, "tv": 87.7, "online": 19.1, "social": 22.4, "radio": 12.3,
            "src": "World Values Survey Wave 7 (2018), weighted microdata (n=1,200)",
            "note": "WVS constructs: use = daily or weekly (vs DNR's 'past week'); trust = confidence in the press as an institution, not DNR's trust-in-news"},
    "BOL": {"trust": 25.3, "tv": 92.6, "online": 44.9, "social": 45.7, "radio": 59.7,
            "src": "World Values Survey Wave 7 (2017), weighted microdata (n=2,067)",
            "note": "WVS constructs: use = daily or weekly (vs DNR's 'past week'); trust = confidence in the press as an institution, not DNR's trust-in-news"},
    "CHN": {"trust": 68.5, "tv": 75.2, "online": 36.6, "social": 65.6, "radio": 16.8,
            "src": "World Values Survey Wave 7 (2018), weighted microdata (n=3,036)",
            "note": "WVS constructs: use = daily or weekly (vs DNR's 'past week'); trust = confidence in the press as an institution, not DNR's trust-in-news"},
    "CYP": {"trust": 36.2, "tv": 88.3, "online": 65.2, "social": 57.2, "radio": 59.3,
            "src": "World Values Survey Wave 7 (2019), weighted microdata (n=1,000)",
            "note": "WVS constructs: use = daily or weekly (vs DNR's 'past week'); trust = confidence in the press as an institution, not DNR's trust-in-news"},
    "ECU": {"trust": 36.4, "tv": 88.7, "online": 66.7, "social": 67.1, "radio": 51.7,
            "src": "World Values Survey Wave 7 (2018), weighted microdata (n=1,200)",
            "note": "WVS constructs: use = daily or weekly (vs DNR's 'past week'); trust = confidence in the press as an institution, not DNR's trust-in-news"},
    "EGY": {"trust": 9.5, "tv": 66.2, "online": 22.3, "social": 35.2, "radio": 14.1,
            "src": "World Values Survey Wave 7 (2018), weighted microdata (n=1,200)",
            "note": "WVS constructs: use = daily or weekly (vs DNR's 'past week'); trust = confidence in the press as an institution, not DNR's trust-in-news"},
    "GTM": {"trust": 20.2, "tv": 72.8, "online": 79.8, "social": 83.8, "radio": 46.8,
            "src": "World Values Survey Wave 7 (2020), weighted microdata (n=1,229)",
            "note": "WVS constructs: use = daily or weekly (vs DNR's 'past week'); trust = confidence in the press as an institution, not DNR's trust-in-news"},
    "IRN": {"trust": 60.6, "tv": 85.4, "online": 69.5, "social": 69.4, "radio": 32.9,
            "src": "World Values Survey Wave 7 (2020), weighted microdata (n=1,499)",
            "note": "WVS constructs: use = daily or weekly (vs DNR's 'past week'); trust = confidence in the press as an institution, not DNR's trust-in-news"},
    "JOR": {"trust": 32.8, "tv": 66.0, "online": 49.0, "social": 60.1, "radio": 16.9,
            "src": "World Values Survey Wave 7 (2018), weighted microdata (n=1,203)",
            "note": "WVS constructs: use = daily or weekly (vs DNR's 'past week'); trust = confidence in the press as an institution, not DNR's trust-in-news"},
    "KAZ": {"trust": 60.0, "tv": 80.4, "online": 61.8, "social": 47.5, "radio": 36.4,
            "src": "World Values Survey Wave 7 (2018), weighted microdata (n=1,276)",
            "note": "WVS constructs: use = daily or weekly (vs DNR's 'past week'); trust = confidence in the press as an institution, not DNR's trust-in-news"},
    "KGZ": {"trust": 45.2, "tv": 84.1, "online": 70.6, "social": 57.8, "radio": 34.3,
            "src": "World Values Survey Wave 7 (2020), weighted microdata (n=1,200)",
            "note": "WVS constructs: use = daily or weekly (vs DNR's 'past week'); trust = confidence in the press as an institution, not DNR's trust-in-news"},
    "LBN": {"trust": 20.4, "tv": 74.0, "online": 47.8, "social": 63.5, "radio": 24.3,
            "src": "World Values Survey Wave 7 (2018), weighted microdata (n=1,200)",
            "note": "WVS constructs: use = daily or weekly (vs DNR's 'past week'); trust = confidence in the press as an institution, not DNR's trust-in-news"},
    "LBY": {"trust": 11.5, "tv": 65.1, "online": 64.6, "social": 75.8, "radio": 30.1,
            "src": "World Values Survey Wave 7 (2022), weighted microdata (n=1,196)",
            "note": "WVS constructs: use = daily or weekly (vs DNR's 'past week'); trust = confidence in the press as an institution, not DNR's trust-in-news"},
    "MDV": {"trust": 25.9, "tv": 56.8, "online": 89.1, "social": 88.6, "radio": 26.2,
            "src": "World Values Survey Wave 7 (2021), weighted microdata (n=1,039)",
            "note": "WVS constructs: use = daily or weekly (vs DNR's 'past week'); trust = confidence in the press as an institution, not DNR's trust-in-news"},
    "MMR": {"trust": 57.2, "tv": 65.8, "online": 25.1, "social": 47.5, "radio": 34.1,
            "src": "World Values Survey Wave 7 (2020), weighted microdata (n=1,200)",
            "note": "WVS constructs: use = daily or weekly (vs DNR's 'past week'); trust = confidence in the press as an institution, not DNR's trust-in-news"},
    "MNG": {"trust": 35.8, "tv": 69.0, "online": 63.9, "social": 70.3, "radio": 26.9,
            "src": "World Values Survey Wave 7 (2020), weighted microdata (n=1,638)",
            "note": "WVS constructs: use = daily or weekly (vs DNR's 'past week'); trust = confidence in the press as an institution, not DNR's trust-in-news"},
    "NIC": {"trust": 18.4, "tv": 70.8, "online": 49.1, "social": 49.0, "radio": 37.2,
            "src": "World Values Survey Wave 7 (2020), weighted microdata (n=1,200)",
            "note": "WVS constructs: use = daily or weekly (vs DNR's 'past week'); trust = confidence in the press as an institution, not DNR's trust-in-news"},
    "NZL": {"trust": 27.9, "tv": 81.9, "online": 80.9, "social": 54.3, "radio": 73.6,
            "src": "World Values Survey Wave 7 (2020), weighted microdata (n=1,057)",
            "note": "WVS constructs: use = daily or weekly (vs DNR's 'past week'); trust = confidence in the press as an institution, not DNR's trust-in-news"},
    "PAK": {"trust": 56.2, "tv": 71.3, "online": 20.5, "social": 21.5, "radio": 10.5,
            "src": "World Values Survey Wave 7 (2018), weighted microdata (n=1,995)",
            "note": "WVS constructs: use = daily or weekly (vs DNR's 'past week'); trust = confidence in the press as an institution, not DNR's trust-in-news"},
    "RUS": {"trust": 33.0, "tv": 82.4, "online": 49.4, "social": 31.3, "radio": 38.3,
            "src": "World Values Survey Wave 7 (2017), weighted microdata (n=1,810)",
            "note": "WVS constructs: use = daily or weekly (vs DNR's 'past week'); trust = confidence in the press as an institution, not DNR's trust-in-news"},
    "TJK": {"trust": 61.2, "tv": 87.9, "online": 36.1, "social": 24.2, "radio": 34.1,
            "src": "World Values Survey Wave 7 (2020), weighted microdata (n=1,200)",
            "note": "WVS constructs: use = daily or weekly (vs DNR's 'past week'); trust = confidence in the press as an institution, not DNR's trust-in-news"},
    "UKR": {"trust": 31.4, "tv": 73.5, "online": 58.0, "social": 53.4, "radio": 31.8,
            "src": "World Values Survey Wave 7 (2020), weighted microdata (n=1,289)",
            "note": "WVS constructs: use = daily or weekly (vs DNR's 'past week'); trust = confidence in the press as an institution, not DNR's trust-in-news"},
    "URY": {"trust": 30.9, "tv": 71.1, "online": 72.2, "social": 65.4, "radio": 44.4,
            "src": "World Values Survey Wave 7 (2022), weighted microdata (n=1,000)",
            "note": "WVS constructs: use = daily or weekly (vs DNR's 'past week'); trust = confidence in the press as an institution, not DNR's trust-in-news"},
    "UZB": {"trust": 68.2, "tv": 85.5, "online": 83.2, "social": 70.7, "radio": 48.3,
            "src": "World Values Survey Wave 7 (2022), weighted microdata (n=1,250)",
            "note": "WVS constructs: use = daily or weekly (vs DNR's 'past week'); trust = confidence in the press as an institution, not DNR's trust-in-news"},
    "VEN": {"trust": 24.9, "tv": 64.6, "online": 55.6, "social": 56.9, "radio": 47.4,
            "src": "World Values Survey Wave 7 (2021), weighted microdata (n=1,190)",
            "note": "WVS constructs: use = daily or weekly (vs DNR's 'past week'); trust = confidence in the press as an institution, not DNR's trust-in-news"},
    "VNM": {"trust": 80.6, "tv": 89.0, "online": 75.2, "social": 78.2, "radio": 11.8,
            "src": "World Values Survey Wave 7 (2020), weighted microdata (n=1,200)",
            "note": "WVS constructs: use = daily or weekly (vs DNR's 'past week'); trust = confidence in the press as an institution, not DNR's trust-in-news"},
    # ---- Eurobarometer 102.2 (Oct-Nov 2024), weighted microdata ----
    # Computed by scripts/compute_eurobarometer.py from the registered GESIS
    # download (ZA8905; raw .sav stays local). Only countries with no other
    # survey are listed — EU members covered by Reuters DNR 2026 are skipped,
    # as are non-UN samples (Kosovo, Turkish Cypriot Community). Constructs
    # differ from DNR (general media use vs news use) — see each entry's note.
    # Citation: European Commission (2026), Eurobarometer 102.2, GESIS ZA8905
    # v1.0.0, doi:10.4232/1.14726.
    "ALB": {"trust": None, "tv": 94.5, "online": 71.0, "social": 77.5, "radio": 14.4,
            "src": "Eurobarometer 102.2 (Oct-Nov 2024), weighted microdata (n=1,009)",
            "note": "EB constructs: weekly use of each medium — general media use, not news-specific (except online = news on internet); trust is only asked per medium, so no single trust figure"},
    "BIH": {"trust": None, "tv": 97.5, "online": 69.8, "social": 75.0, "radio": 52.7,
            "src": "Eurobarometer 102.2 (Oct-Nov 2024), weighted microdata (n=1,000)",
            "note": "EB constructs: weekly use of each medium — general media use, not news-specific (except online = news on internet); trust is only asked per medium, so no single trust figure"},
    "EST": {"trust": None, "tv": 88.0, "online": 79.2, "social": 75.6, "radio": 74.6,
            "src": "Eurobarometer 102.2 (Oct-Nov 2024), weighted microdata (n=1,001)",
            "note": "EB constructs: weekly use of each medium — general media use, not news-specific (except online = news on internet); trust is only asked per medium, so no single trust figure"},
    "GEO": {"trust": None, "tv": 82.8, "online": 71.0, "social": 78.4, "radio": 11.8,
            "src": "Eurobarometer 102.2 (Oct-Nov 2024), weighted microdata (n=1,007)",
            "note": "EB constructs: weekly use of each medium — general media use, not news-specific (except online = news on internet); trust is only asked per medium, so no single trust figure"},
    "LTU": {"trust": None, "tv": 90.2, "online": 79.1, "social": 76.0, "radio": 63.3,
            "src": "Eurobarometer 102.2 (Oct-Nov 2024), weighted microdata (n=1,018)",
            "note": "EB constructs: weekly use of each medium — general media use, not news-specific (except online = news on internet); trust is only asked per medium, so no single trust figure"},
    "LUX": {"trust": None, "tv": 86.7, "online": 84.7, "social": 72.9, "radio": 71.2,
            "src": "Eurobarometer 102.2 (Oct-Nov 2024), weighted microdata (n=512)",
            "note": "EB constructs: weekly use of each medium — general media use, not news-specific (except online = news on internet); trust is only asked per medium, so no single trust figure"},
    "LVA": {"trust": None, "tv": 81.5, "online": 79.0, "social": 77.3, "radio": 64.3,
            "src": "Eurobarometer 102.2 (Oct-Nov 2024), weighted microdata (n=1,005)",
            "note": "EB constructs: weekly use of each medium — general media use, not news-specific (except online = news on internet); trust is only asked per medium, so no single trust figure"},
    "MDA": {"trust": None, "tv": 74.4, "online": 69.9, "social": 76.8, "radio": 29.0,
            "src": "Eurobarometer 102.2 (Oct-Nov 2024), weighted microdata (n=1,014)",
            "note": "EB constructs: weekly use of each medium — general media use, not news-specific (except online = news on internet); trust is only asked per medium, so no single trust figure"},
    "MKD": {"trust": None, "tv": 96.2, "online": 65.3, "social": 80.1, "radio": 39.1,
            "src": "Eurobarometer 102.2 (Oct-Nov 2024), weighted microdata (n=1,014)",
            "note": "EB constructs: weekly use of each medium — general media use, not news-specific (except online = news on internet); trust is only asked per medium, so no single trust figure"},
    "MLT": {"trust": None, "tv": 92.7, "online": 78.0, "social": 80.2, "radio": 62.3,
            "src": "Eurobarometer 102.2 (Oct-Nov 2024), weighted microdata (n=500)",
            "note": "EB constructs: weekly use of each medium — general media use, not news-specific (except online = news on internet); trust is only asked per medium, so no single trust figure"},
    "MNE": {"trust": None, "tv": 94.8, "online": 72.7, "social": 75.0, "radio": 60.3,
            "src": "Eurobarometer 102.2 (Oct-Nov 2024), weighted microdata (n=519)",
            "note": "EB constructs: weekly use of each medium — general media use, not news-specific (except online = news on internet); trust is only asked per medium, so no single trust figure"},
    "SVN": {"trust": None, "tv": 86.0, "online": 75.8, "social": 68.0, "radio": 79.9,
            "src": "Eurobarometer 102.2 (Oct-Nov 2024), weighted microdata (n=1,004)",
            "note": "EB constructs: weekly use of each medium — general media use, not news-specific (except online = news on internet); trust is only asked per medium, so no single trust figure"},
    # 2026-07-22: EGY, SAU, YEM, DZA, PAK, BGD, MMR, NPL, VEN, CHN, RUS, VNM,
    # IRN, AFG, UKR were REMOVED here. They carried source labels like "Arab
    # Barometer IX + DataReportal 2024" and "WVS Wave 7 + DataReportal 2024"
    # that do not hold up: the cited wave was either not yet publicly released
    # (Arab Barometer IX) or DataReportal does not measure trust/news-source
    # mix at all (it never has). No commit or note documents where these
    # numbers actually came from. Treat them as unverified, not as a "close
    # enough" estimate — restore only with a real, checkable source.
    # UPDATE 2026-07-22 (later same day): EGY, PAK, BGD, MMR, VEN, CHN,
    # RUS, VNM, IRN, UKR restored ABOVE with real WVS Wave 7 microdata.
    # Still unverified (no free survey found yet): SAU, YEM, DZA, NPL, AFG.
}


# --------------------------------------------------------------------------
# Measured social-platform use — Latinobarometro 2024 (17 countries)
# --------------------------------------------------------------------------
# % of adults who mention actively using each service (S14M battery),
# WT-weighted, base excludes explicit non-response. Computed by
# scripts/compute_latinobarometro.py from the registered download (raw
# .sav stays local). This is PLATFORM USE, not news consumption — the
# 2024 wave dropped the channel-of-news battery, so news_consumption
# cannot be filled from it. A separate construct, a separate field.
# Citation: Latinobarómetro 2024, Corporación Latinobarómetro, Santiago.
PLATFORM_USE_2024: dict[str, dict[str, Any]] = {
    "ARG": {"whatsapp": 85.0, "facebook": 62.4, "instagram": 53.6, "tiktok": 25.3, "youtube": 53.2,
            "x": 15.2, "snapchat": 4.0, "linkedin": 6.3, "none": 9.4, "n": 1205},
    "BOL": {"whatsapp": 81.9, "facebook": 66.2, "instagram": 20.7, "tiktok": 44.3, "youtube": 39.7,
            "x": 7.7, "snapchat": 7.8, "linkedin": 2.3, "none": 14.4, "n": 1191},
    "BRA": {"whatsapp": 78.9, "facebook": 49.7, "instagram": 52.5, "tiktok": 28.4, "youtube": 41.1,
            "x": 6.5, "snapchat": 3.2, "linkedin": 5.8, "none": 14.4, "n": 1200},
    "CHL": {"whatsapp": 93.3, "facebook": 71.6, "instagram": 58.5, "tiktok": 46.9, "youtube": 63.7,
            "x": 19.0, "snapchat": 4.0, "linkedin": 5.8, "none": 4.2, "n": 1192},
    "COL": {"whatsapp": 85.2, "facebook": 69.5, "instagram": 34.0, "tiktok": 30.9, "youtube": 41.7,
            "x": 9.5, "snapchat": 5.8, "linkedin": 3.9, "none": 10.7, "n": 1200},
    "CRI": {"whatsapp": 90.5, "facebook": 76.7, "instagram": 46.4, "tiktok": 44.0, "youtube": 55.7,
            "x": 9.9, "snapchat": 8.6, "linkedin": 8.7, "none": 5.6, "n": 996},
    "DOM": {"whatsapp": 85.1, "facebook": 73.3, "instagram": 55.4, "tiktok": 50.9, "youtube": 59.5,
            "x": 11.4, "snapchat": 21.8, "linkedin": 3.9, "none": 9.5, "n": 999},
    "ECU": {"whatsapp": 88.4, "facebook": 83.6, "instagram": 50.4, "tiktok": 55.7, "youtube": 56.1,
            "x": 13.3, "snapchat": 10.3, "linkedin": 5.8, "none": 5.2, "n": 1199},
    "GTM": {"whatsapp": 71.9, "facebook": 66.5, "instagram": 21.6, "tiktok": 36.1, "youtube": 27.0,
            "x": 6.8, "snapchat": 8.1, "linkedin": 1.9, "none": 18.3, "n": 981},
    "HND": {"whatsapp": 77.7, "facebook": 66.4, "instagram": 24.7, "tiktok": 40.8, "youtube": 34.9,
            "x": 7.0, "snapchat": 10.7, "linkedin": 2.2, "none": 18.1, "n": 999},
    "MEX": {"whatsapp": 76.3, "facebook": 70.8, "instagram": 26.7, "tiktok": 27.3, "youtube": 44.6,
            "x": 12.8, "snapchat": 10.5, "linkedin": 2.5, "none": 14.4, "n": 1189},
    "PAN": {"whatsapp": 80.9, "facebook": 54.2, "instagram": 58.9, "tiktok": 44.6, "youtube": 46.3,
            "x": 13.8, "snapchat": 15.0, "linkedin": 4.9, "none": 12.9, "n": 993},
    "PER": {"whatsapp": 76.6, "facebook": 70.7, "instagram": 28.9, "tiktok": 39.0, "youtube": 46.7,
            "x": 6.8, "snapchat": 4.4, "linkedin": 5.2, "none": 17.5, "n": 1197},
    "PRY": {"whatsapp": 89.1, "facebook": 76.4, "instagram": 44.3, "tiktok": 47.2, "youtube": 53.3,
            "x": 9.6, "snapchat": 9.1, "linkedin": 2.7, "none": 8.6, "n": 1200},
    "SLV": {"whatsapp": 81.4, "facebook": 72.7, "instagram": 29.9, "tiktok": 43.0, "youtube": 47.1,
            "x": 10.9, "snapchat": 10.5, "linkedin": 4.0, "none": 12.6, "n": 998},
    "URY": {"whatsapp": 90.9, "facebook": 66.9, "instagram": 55.1, "tiktok": 31.6, "youtube": 60.1,
            "x": 15.1, "snapchat": 2.7, "linkedin": 7.9, "none": 5.1, "n": 1197},
    "VEN": {"whatsapp": 85.0, "facebook": 78.2, "instagram": 55.2, "tiktok": 54.8, "youtube": 39.7,
            "x": 15.0, "snapchat": 11.2, "linkedin": 2.1, "none": 8.2, "n": 1190},
}


# --------------------------------------------------------------------------
# HTTP helpers
# --------------------------------------------------------------------------
def _ssl_context():
    """Certifi-based context when available (fixes local macOS cert issues);
    the system default elsewhere (GitHub Actions runners are fine as-is)."""
    import ssl
    try:
        import certifi
        return ssl.create_default_context(cafile=certifi.where())
    except ImportError:
        return ssl.create_default_context()


_CTX = _ssl_context()


def fetch_json(url: str, max_retries: int = 3, timeout: int = 90) -> Any:
    last_exc: Exception | None = None
    for attempt in range(max_retries):
        try:
            req = Request(url, headers={
                "User-Agent": "UN-Media-Consumption-Atlas/1.0 (+github actions)",
                "Accept": "application/json",
            })
            with urlopen(req, timeout=timeout, context=_CTX) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except (HTTPError, URLError, TimeoutError) as e:
            last_exc = e
            if attempt < max_retries - 1:
                time.sleep(2 ** attempt)
    raise RuntimeError(f"Failed after {max_retries} attempts: {url}") from last_exc


# Sparse indicators (censuses/surveys, not annual series) need a wider
# most-recent-value window to catch each country's latest real observation.
SPARSE_WINDOWS = {"SE.ADT.LITR.ZS": 30, "SE.XPD.TOTL.GD.ZS": 30}


def fetch_indicator_all_countries(wb_code: str) -> dict[str, tuple[float, int]]:
    """Latest available value per country for one indicator.

    NOTE (2026-07-14): the API's mrnev (most-recent-non-empty) mode started
    returning HTTP 400 / timeouts for many indicators, so we fetch a recent
    window with plain mrv (which is stable), paginate, and pick each
    country's newest non-null value ourselves — this also preserves the TRUE
    year of each data point for citations, which gapfill would mask.
    """
    # PER_PAGE (2026-07-21): fetch every row in ONE request. The old value of
    # 300 needed up to 27 sequential pages for the 30-year sparse indicators;
    # when the World Bank API is slow (observed: 235s for one indicator, then
    # a page-23 failure) that pagination blew past the workflow timeout and
    # the whole refresh was cancelled. One big request is both far faster
    # (~3s vs ~4min for literacy) and immune to mid-pagination failure.
    # The loop below is kept as a safety net in case a future indicator
    # genuinely exceeds one page.
    PER_PAGE = 20000
    out: dict[str, tuple[float, int]] = {}
    page, pages = 1, 1
    while page <= pages:
        url = (
            f"https://api.worldbank.org/v2/country/all/indicator/{wb_code}"
            f"?format=json&per_page={PER_PAGE}&mrv={SPARSE_WINDOWS.get(wb_code, 12)}&page={page}"
        )
        try:
            payload = fetch_json(url)
        except Exception as exc:
            print(f"  ! {wb_code}: bulk fetch failed on page {page}: {exc}")
            return out
        if not isinstance(payload, list) or len(payload) < 2 or not payload[1]:
            break
        pages = int(payload[0].get("pages", 1))
        for row in payload[1]:
            iso3 = row.get("countryiso3code")
            value = row.get("value")
            if not iso3 or value is None:
                continue
            try:
                year = int(row["date"])
                if iso3 not in out or year > out[iso3][1]:
                    out[iso3] = (float(value), year)
            except (TypeError, ValueError):
                continue
        page += 1
        time.sleep(0.4)   # polite pacing between pages
    return out


# --------------------------------------------------------------------------
# Build one country row
# --------------------------------------------------------------------------
# CLDR's English language-name table doesn't cover every ISO 639-3 code that
# appears in its own territory data — without these, briefs would print raw
# codes ("haz", "apc") as if they were language names. Names follow ISO 639-3
# / Ethnologue usage. Add a line here if a new code ever shows up.
EXTRA_LANGUAGE_NAMES = {
    "abr": "Abron", "apc": "Levantine Arabic", "apd": "Sudanese Arabic",
    "bci": "Baoulé", "bsq": "Bassa", "bvb": "Bube", "bzj": "Belizean Creole",
    "cab": "Garifuna", "cak": "Kaqchikel", "cja": "Western Cham",
    "dnj": "Dan", "ffm": "Maasina Fulfulde", "fuq": "Central-Eastern Niger Fulfulde",
    "fuv": "Nigerian Fulfulde", "fvr": "Fur", "haz": "Hazaragi", "ife": "Ifè",
    "jml": "Jumli", "kck": "Kalanga", "kjg": "Khmu", "knf": "Mankanya",
    "kro": "Kru", "lep": "Lepcha", "lir": "Liberian English", "mam": "Mam",
    "mey": "Hassaniyya Arabic", "mfa": "Pattani Malay", "mnw": "Mon",
    "mop": "Mopan Maya", "mwk": "Kita Maninkakan", "mww": "Hmong Daw",
    "mxc": "Manyika", "ndc": "Ndau", "ngl": "Lomwe", "nod": "Northern Thai",
    "nse": "Nsenga", "prd": "Parsi-Dari", "puu": "Punu", "rkt": "Rangpuri",
    "sav": "Saafi-Saafi", "sef": "Cebaara Senoufo", "sou": "Southern Thai",
    "syl": "Sylheti", "toi": "Tonga", "tsj": "Tshangla", "tts": "Northeastern Thai",
    "uli": "Ulithian", "wni": "Ndzwani Comorian", "zdj": "Ngazidja Comorian",
}

# CLDR names a few languages with their TERRITORY's name, which reads as an
# error in a brief ("Produce in Tuvalu first"). These override CLDR.
LANGUAGE_NAME_OVERRIDES = {
    "tvl": "Tuvaluan",   # CLDR: "Tuvalu"
    "na": "Nauruan",     # CLDR: "Nauru"
    "toi": "Tonga (Zambia)",  # CLDR: "Tonga" — the Zambian Bantu language, not Tongan
}

CLDR_TERRITORY_URL = ("https://raw.githubusercontent.com/unicode-org/cldr-json/main/"
                      "cldr-json/cldr-core/supplemental/territoryInfo.json")
CLDR_LANG_NAMES_URL = ("https://raw.githubusercontent.com/unicode-org/cldr-json/main/"
                       "cldr-json/cldr-localenames-full/main/en/languages.json")


def fetch_cldr_languages() -> dict[str, list[dict[str, Any]]]:
    """Per-country language shares from Unicode CLDR (free, Unicode License V3).

    Returns {ISO2: [{"language": "Swahili", "code": "sw", "pct": 80.0,
                     "official": True}, ...]} — top languages by share of the
    population that speaks them (CLDR territory-language data). Empty dict on
    any failure so the weekly refresh never breaks because of this extra.
    """
    try:
        info = fetch_json(CLDR_TERRITORY_URL)
        names = fetch_json(CLDR_LANG_NAMES_URL)
    except Exception as exc:  # network hiccup → skip quietly, keep previous data
        print(f"  ! CLDR language fetch failed ({exc}) — keeping previous language data")
        return {}
    try:
        name_map = names["main"]["en"]["localeDisplayNames"]["languages"]
        territories = info["supplemental"]["territoryInfo"]
    except (KeyError, TypeError) as exc:
        print(f"  ! CLDR payload shape changed ({exc}) — keeping previous language data")
        return {}

    out: dict[str, list[dict[str, Any]]] = {}
    for iso2, tdata in territories.items():
        pops = tdata.get("languagePopulation")
        if not isinstance(pops, dict):
            continue
        rows = []
        for code, ldata in pops.items():
            try:
                pct = float(ldata.get("_populationPercent", 0))
            except (TypeError, ValueError):
                continue
            if pct < 1:                      # ignore sub-1% slivers
                continue
            status = ldata.get("_officialStatus", "")
            # "official_regional" (e.g. Spanish in US territories) is NOT a
            # country-level official language — counting it as one produced
            # "Spanish (official)" for the United States.
            is_official = status in ("official", "de_facto_official")
            # unmapped locale codes ("pa_Arab", "tts") → fall back to the base
            # language's name plus a script note, never leak raw codes
            name = LANGUAGE_NAME_OVERRIDES.get(code) or name_map.get(code) or EXTRA_LANGUAGE_NAMES.get(code)
            if not name:
                base = code.split("_")[0]
                name = name_map.get(base) or EXTRA_LANGUAGE_NAMES.get(base) or code
                if name != code and code.endswith("_Arab"):
                    name += " (Arabic script)"
            rows.append({
                "language": name,
                "code": code,
                "pct": round(pct, 1),
                "official": is_official,
            })
        rows.sort(key=lambda r: (-r["official"], -r["pct"]))
        if rows:
            out[iso2] = rows[:6]
    return out


# --------------------------------------------------------------------------
# CIA World Factbook (public domain) — media-landscape narrative
# --------------------------------------------------------------------------
# The Factbook's "Broadcast media" entry is the best free per-country
# DESCRIPTION of a media landscape (state vs. private TV/radio, satellite and
# cable reach). Ingested from the factbook.json mirror
# (github.com/factbook/factbook.json), which tracks the CIA site weekly.
# CIA Factbook content is a US-government work: public domain.
#
# The mirror keys files by GEC (FIPS) code, not ISO3 — the public-domain
# datasets/country-codes CSV provides the FIPS-to-ISO3 join.

FACTBOOK_TREE_URL = ("https://api.github.com/repos/factbook/factbook.json/"
                     "git/trees/master?recursive=1")
FACTBOOK_RAW_BASE = "https://raw.githubusercontent.com/factbook/factbook.json/master/"
COUNTRY_CODES_CSV_URL = ("https://raw.githubusercontent.com/datasets/"
                         "country-codes/main/data/country-codes.csv")


def _fetch_text(url: str, timeout: int = 30) -> str:
    req = Request(url, headers={
        "User-Agent": "UN-Media-Consumption-Atlas/1.0 (+github actions)",
    })
    with urlopen(req, timeout=timeout, context=_CTX) as resp:
        return resp.read().decode("utf-8")


def fetch_factbook_media(wanted_iso3: set[str]) -> dict[str, str]:
    """ISO3 → 'Broadcast media' text for every wanted country the mirror has.

    Returns {} on an infrastructure failure (tree or codes fetch) so the
    refresh keeps previous values instead of failing — the same
    degrade-gracefully rule the CLDR fetch follows. A single country's
    failure is silently skipped (its previous value survives via
    build_country's prev fallback).
    """
    import csv as _csv
    from io import StringIO

    try:
        fips_to_iso3: dict[str, str] = {}
        for r in _csv.DictReader(StringIO(_fetch_text(COUNTRY_CODES_CSV_URL))):
            fips = (r.get("FIPS") or "").strip()
            iso3 = (r.get("ISO3166-1-Alpha-3") or "").strip()
            if fips and iso3:
                fips_to_iso3[fips.lower()] = iso3

        tree = fetch_json(FACTBOOK_TREE_URL, max_retries=2, timeout=30)
        paths: dict[str, str] = {}
        for node in tree.get("tree", []):
            p = node.get("path", "")
            if p.endswith(".json") and "/" in p and not p.startswith("meta"):
                paths[p.rsplit("/", 1)[1][:-5]] = p
    except Exception as exc:
        print(f"  ! Factbook index fetch failed ({exc}) — keeping previous media-landscape notes")
        return {}

    out: dict[str, str] = {}
    fetched = 0
    for gec, path in sorted(paths.items()):
        iso3 = fips_to_iso3.get(gec)
        if iso3 not in wanted_iso3:
            continue
        try:
            data = fetch_json(FACTBOOK_RAW_BASE + path, max_retries=2, timeout=20)
            text = (((data.get("Communications") or {}).get("Broadcast media") or {})
                    .get("text") or "").strip()
            if text:
                # Keep it brief-friendly: cap ~700 chars on a clause boundary.
                if len(text) > 700:
                    cut = text[:700]
                    boundary = max(cut.rfind("; "), cut.rfind(". "))
                    if boundary > 200:
                        cut = cut[:boundary]
                    text = cut.rstrip(";. ") + " …"
                out[iso3] = text
        except Exception:
            pass          # single-country miss — previous value survives
        fetched += 1
        if fetched % 40 == 0:
            print(f"  · Factbook: {fetched} files checked, {len(out)} with media text")
        time.sleep(0.15)  # polite pacing for raw.githubusercontent
    return out


def build_country(
    iso3: str,
    static_meta: dict[str, Any],
    prev: dict[str, Any] | None,
    wb_data: dict[str, dict[str, tuple[float, int]]],
    cldr_langs: dict[str, list[dict[str, Any]]] | None = None,
    factbook_media: dict[str, str] | None = None,
) -> dict[str, Any]:
    iso2 = ISO3_TO_ISO2.get(iso3, iso3)
    print(f"→ {iso3} ({static_meta.get('name', iso3)})")

    values: dict[str, Any] = {}
    latest_year: int | None = None
    sources: dict[str, str] = {}

    # World Bank automated indicators
    for field, wb_code in WORLD_BANK_INDICATORS.items():
        pair = wb_data.get(field, {}).get(iso3)
        value, year = pair if pair else (None, None)
        if value is None and prev:
            prev_value = _lookup_previous(prev, field)
            if prev_value is not None:
                values[field] = prev_value
                prev_src = (prev.get("sources") or {}).get(field)
                if prev_src:
                    sources[field] = prev_src
                continue
        if value is not None:
            if field in {"population", "area_km2", "gdp_per_capita_usd"}:
                values[field] = int(round(value))
            else:
                values[field] = round(value, 1)
            if year and (latest_year is None or year > latest_year):
                latest_year = year
            origin = WB_DATA_ORIGINS.get(field, "")
            sources[field] = (
                f"World Bank{origin} — https://data.worldbank.org/indicator/{wb_code}?locations={iso2}"
            )

    # Smartphone % (DataReportal)
    if iso3 in SMARTPHONE_PCT_2024:
        values["smartphone_pct"] = SMARTPHONE_PCT_2024[iso3]
        sources["smartphone_pct"] = "DataReportal 2024 — https://datareportal.com/"

    # Press freedom (RSF) — from the fetched index file, never hand-typed
    rsf = RSF_INDEX["countries"].get(iso3)
    if rsf:
        values["press_freedom_rank"] = rsf["rank"]
        values["press_freedom_score"] = rsf["score"]
        values["press_freedom_edition"] = RSF_EDITION
        # RSF's five sub-scores explain WHY a market is rated as it is —
        # a legal-environment problem calls for different comms handling
        # than a safety-of-journalists problem.
        values["press_freedom_indicators"] = rsf.get("indicators")
        prev = (rsf.get("prev") or {}).get("rank")
        if prev:
            values["press_freedom_rank_prev"] = prev
        sources["press_freedom_rank"] = (
            f"RSF {RSF_EDITION} — https://rsf.org/en/country/{iso3.lower()}")

    # Internet freedom (Freedom House FOTN)
    fotn_score = FREEDOM_HOUSE_FOTN_2025.get(iso3)
    if fotn_score is not None:
        values["internet_freedom_score"] = fotn_score
        values["internet_freedom_status"] = _freedom_status(fotn_score)
        sources["internet_freedom"] = "Freedom House: Freedom on the Net 2025 — https://freedomhouse.org/country/scores?type=fotn"

    # Political freedom (Freedom House FITW — all countries)
    fitw_score = FREEDOM_HOUSE_FITW_2025.get(iso3)
    if fitw_score is not None:
        values["political_freedom_score"] = fitw_score
        detail = FREEDOM_HOUSE_DETAIL_2026.get(iso3)
        if detail:
            status_letter, pr, cl, electoral = detail
            values["political_freedom_status"] = _FH_STATUS_WORDS[status_letter]
            values["political_rights_score"] = pr        # 0-40
            values["civil_liberties_score"] = cl         # 0-60
            values["electoral_democracy"] = electoral
            sources["political_freedom"] = "Freedom House: Freedom in the World 2026 — official data files provided by Freedom House (July 2026) — https://freedomhouse.org/report/freedom-world"
        else:
            values["political_freedom_status"] = _freedom_status(fitw_score)
            sources["political_freedom"] = "Freedom House: Freedom in the World 2026 report (2025 data) — https://freedomhouse.org/report/freedom-world"

    # News consumption (Reuters DNR / regional barometers / WVS)
    nc = NEWS_CONSUMPTION.get(iso3)
    if nc:
        values["news_trust_pct"] = nc["trust"]
        values["news_tv_pct"] = nc["tv"]
        values["news_online_pct"] = nc["online"]
        values["news_social_pct"] = nc["social"]
        sources["news_consumption"] = f"{nc['src']} — https://reutersinstitute.politics.ox.ac.uk/digital-news-report/2026" if "Reuters" in nc["src"] else nc["src"]
        if iso3 in DNR_NON_REPRESENTATIVE and "Reuters" in nc["src"]:
            values["news_survey_note"] = ("Survey sample is online and mainly English-speaking/urban — "
                                          "not nationally representative; figures skew younger and more connected "
                                          "(per DNR 2026 methodology).")
        elif nc.get("note"):
            values["news_survey_note"] = nc["note"]

    # Radio (Afrobarometer R9 microdata — independent of the dicts above,
    # because DNR reports radio only per-brand, not as a single reach figure)
    radio_source_label = None
    radio = AFRO_RADIO_2023.get(iso3)
    if radio is not None:
        values["news_radio_pct"] = radio
        radio_source_label = "Afrobarometer Round 9 (2023)"
        sources["news_radio"] = "Afrobarometer Round 9 (2023), computed from weighted microdata — https://www.afrobarometer.org/data/"
    elif nc and nc.get("radio") is not None:
        values["news_radio_pct"] = nc["radio"]
        radio_source_label = nc["src"]
        sources["news_radio"] = nc["src"]

    # Median age (UN DESA WPP 2024)
    ma = WPP_MEDIAN_AGE_2025.get(iso3)
    if ma is not None:
        values["median_age"] = ma
        sources["median_age"] = "UN DESA, World Population Prospects 2024 (2025 estimate) — https://population.un.org/wpp/"

    # Mobile Connectivity Index (GSMA)
    mci = GSMA_MCI_2024.get(iso3)
    if mci is not None:
        values["mobile_connectivity_index"] = mci
        sources["mobile_connectivity_index"] = "GSMA Mobile Connectivity Index 2024 — https://www.mobileconnectivityindex.com/"

    # Language shares (Unicode CLDR territory-language data) — which languages
    # actually reach this country's population, with official status.
    languages_detail = (cldr_langs or {}).get(iso2)
    if languages_detail:
        sources["languages_detail"] = ("Unicode CLDR territory-language data (Unicode License V3) — "
                                       "https://github.com/unicode-org/cldr-json")
    elif prev and prev.get("languages_detail"):
        languages_detail = prev["languages_detail"]          # keep last good copy
        prev_src = (prev.get("sources") or {}).get("languages_detail")
        if prev_src:
            sources["languages_detail"] = prev_src

    # Measured platform use (Latinobarometro 2024, 17 LatAm countries)
    platform_use = PLATFORM_USE_2024.get(iso3)
    if platform_use:
        sources["platform_use"] = (
            "Latinobarometro 2024, weighted microdata (S14M battery; % of adults actively using each service) — "
            "https://www.latinobarometro.org/"
        )

    # Media-landscape narrative (CIA World Factbook, public domain)
    landscape_note = (factbook_media or {}).get(iso3)
    if landscape_note:
        sources["media_landscape"] = (
            "CIA World Factbook, Broadcast media (public domain; auto-ingested weekly "
            "via the factbook.json mirror) — https://www.cia.gov/the-world-factbook/"
        )
    elif isinstance(prev, dict):
        # Defensive: `prev` comes from the previous countries.json, which a
        # killed or concurrent run could have left malformed. One odd record
        # must not abort a refresh that is 170 countries in — carry nothing
        # forward for that country instead.
        prev_media = prev.get("media")
        landscape_note = prev_media.get("landscape_note") if isinstance(prev_media, dict) else None
        if landscape_note:
            prev_sources = prev.get("sources")
            prev_src = prev_sources.get("media_landscape") if isinstance(prev_sources, dict) else None
            if prev_src:
                sources["media_landscape"] = prev_src

    # Assemble the country object
    country: dict[str, Any] = {
        **static_meta,
        "population": values.get("population"),
        "population_year": latest_year or datetime.now().year - 2,
        "area_km2": values.get("area_km2"),
        "gdp_per_capita_usd": values.get("gdp_per_capita_usd"),
        "demographics": {
            "median_age": values.get("median_age"),
            "median_age_source": "UN DESA WPP 2024 (2025 estimate)" if values.get("median_age") is not None else None,
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
            "mobile_connectivity_index": values.get("mobile_connectivity_index"),
            "mobile_connectivity_index_source": "GSMA Mobile Connectivity Index 2024" if values.get("mobile_connectivity_index") is not None else None,
            "financial_account_pct": values.get("financial_account_pct"),
        },
        "languages_detail": languages_detail or None,
        "platform_use": ({**platform_use, "source": "Latinobarometro 2024", "year": 2024}
                         if platform_use else None),
        "media": {
            **static_meta.get("media", {}),
            "landscape_note": landscape_note,
            "landscape_note_source": "CIA World Factbook" if landscape_note else None,
            "press_freedom_rank": values.get("press_freedom_rank"),
            "press_freedom_score": values.get("press_freedom_score"),
            # edition comes from the fetched index, so it can never drift
            # out of step with the numbers it labels
            "press_freedom_source": f"RSF {RSF_EDITION}",
        },
        "information_freedom": {
            "press_freedom_rank": values.get("press_freedom_rank"),
            "press_freedom_score": values.get("press_freedom_score"),
            "press_freedom_source": f"RSF {RSF_EDITION} — https://rsf.org/en/index",
            "press_freedom_edition": RSF_EDITION,
            "press_freedom_indicators": values.get("press_freedom_indicators"),
            "press_freedom_rank_prev": values.get("press_freedom_rank_prev"),
            "internet_freedom_score": values.get("internet_freedom_score"),
            "internet_freedom_status": values.get("internet_freedom_status"),
            "internet_freedom_source": "Freedom House: Freedom on the Net 2025",
            "political_freedom_score": values.get("political_freedom_score"),
            "political_freedom_status": values.get("political_freedom_status"),
            "political_rights_score": values.get("political_rights_score"),
            "civil_liberties_score": values.get("civil_liberties_score"),
            "electoral_democracy": values.get("electoral_democracy"),
            "political_freedom_source": "Freedom House: Freedom in the World 2026 — official FH data files (July 2026)",
        },
        "news_consumption": {
            "trust_in_news_pct": values.get("news_trust_pct"),
            "tv_as_news_source_pct": values.get("news_tv_pct"),
            "online_as_news_source_pct": values.get("news_online_pct"),
            "social_as_news_source_pct": values.get("news_social_pct"),
            "radio_as_news_source_pct": values.get("news_radio_pct"),
            "radio_source": radio_source_label,
            "survey_note": values.get("news_survey_note"),
            "source": nc["src"] if nc else None,
        },
        "sources": sources,
        "confidence": "verified" if values else "preliminary",
        "retrieved_on": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
    }

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

    print("Fetching Unicode CLDR language data (two requests)...")
    cldr_langs = fetch_cldr_languages()
    print(f"  · language shares for {len(cldr_langs)} territories")

    print("Fetching CIA World Factbook media-landscape notes (~200 small requests)...")
    factbook_media = fetch_factbook_media(set(static.keys()))
    print(f"  · Broadcast-media text for {len(factbook_media)} countries")

    result: dict[str, Any] = {}
    for iso3, meta in sorted(static.items()):
        result[iso3] = build_country(iso3, meta, previous.get(iso3), wb_data, cldr_langs, factbook_media)

    world_pop_row = wb_data.get("population", {}).get("WLD")
    result["_meta"] = {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "country_count": len([k for k in result if not k.startswith("_")]),
        # World Bank world total — the denominator for the "% of world
        # population" stat (summing 195 countries slightly exceeds older
        # hardcoded totals, which produced a "101%" display bug).
        "world_population": world_pop_row[0] if world_pop_row else None,
        "schema_version": 2,
        "data_sources": [
            "World Bank Open Data API (15 indicators incl. Global Findex financial-account ownership, automated weekly; ICT indicators originally compiled by ITU, education/literacy by UNESCO Institute for Statistics — CC BY 4.0)",
            "Unicode CLDR territory-language data (per-country language shares & official status, automated weekly — Unicode License V3)",
            "UN DESA World Population Prospects 2024 (median age, 195 countries)",
            "GSMA Mobile Connectivity Index 2024 (172 countries)",
            "RSF Press Freedom Index 2025 (174 countries)",
            "Freedom House: Freedom on the Net 2025 (70 countries)",
            "Freedom House: Freedom in the World 2026 — official FH data files incl. PR/CL scores & electoral democracy (193 countries)",
            "Reuters Institute Digital News Report 2026 (46 markets; non-representative samples flagged for IND/KEN/NGA/ZAF/MAR)",
            "Afrobarometer Round 9 microdata (news sources incl. radio, 35-39 African countries, weighted)",
            "DataReportal 2024 (smartphone penetration estimates, 50 countries)",
            "Arab Barometer Wave VIII (Iraq, Kuwait, Palestine — real weighted microdata, computed by scripts/compute_arabbarometer_w8.py)",
            "Arab Barometer Wave VII, 2021-2022 (Algeria — real weighted microdata, computed by scripts/compute_arabbarometer_w7.py)",
            "World Values Survey Wave 7 v6.0 (28 countries — weighted microdata computed by scripts/compute_wvs_news.py; doi:10.14281/18241.24; constructs differ from DNR and are labeled per country)",
            "Latinobarometro 2024 (17 countries — measured social-platform use, weighted microdata computed by scripts/compute_latinobarometro.py; platform use is a separate construct from news consumption)",
            "Eurobarometer 102.2, Oct-Nov 2024 (12 countries — weekly media use, weighted microdata computed by scripts/compute_eurobarometer.py; GESIS ZA8905, doi:10.4232/1.14726)",
            "Trend engine: Wikimedia Pageviews API (CC0) + GDELT 2.0 (daily, 167 topics, 22 languages)",
            "CIA World Factbook, Broadcast media entries (public domain, auto-ingested weekly via the factbook.json mirror)",
            "Statcounter GlobalStats (social web-traffic referral shares, 195 countries, automated weekly, 3-month average — web-referral measure only; app-first platforms like WhatsApp/TikTok are not visible to it)",
            "WPP Media 'This Year, Next Year' Dec 2025 + Dentsu Global Ad Spend Forecasts Dec 2025 (regional ad-market signals, annual hand-update in data/ad_market.json)",
            "Curated country profiles cross-referenced with national sources",
            "Reference tools (linked, not ingested): UNESCO World Trends in Freedom of Expression, Pew Research Center, Edison Research, OECD Data, Meta Ad Library, Google Ads Transparency Center",
        ],
    }

    # ATOMIC write (same policy as fetch_trends_wikipedia.py): serialise to a
    # temp file in the same directory, then os.replace(). A direct write_text
    # leaves the published countries.json truncated if the process is killed
    # or the disk fills mid-write — and anything reading it in that window
    # (the site, the validator, the next run) sees a half-written file.
    tmp = OUTPUT_PATH.with_suffix(".json.tmp")
    tmp.write_text(
        json.dumps(result, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    os.replace(tmp, OUTPUT_PATH)
    print(f"\nWrote {OUTPUT_PATH} with {result['_meta']['country_count']} countries.")
    print(f"Data sources: {len(result['_meta']['data_sources'])}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
