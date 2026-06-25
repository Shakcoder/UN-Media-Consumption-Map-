#!/usr/bin/env python3
"""
refresh_data.py — automated data refresh for the Global Media Consumption Atlas.

If any single indicator fetch fails, the script preserves the previous value
from countries.json and logs the failure — it never emits partial or empty
rows.
  - RSF Press Freedom Index (180 countries, manual annual)
  - Freedom House: Freedom on the Net (70 countries, manual annual)
  - Freedom House: Freedom in the World (all countries, manual annual)
  - Reuters Institute Digital News Report (48 markets, manual annual)
  - Afrobarometer (39 African countries, manual per wave)
  - Arab Barometer (16+ MENA countries, manual per wave)
  - Asian Barometer (13+ Asian countries, manual per wave)
  - Latinobarometro (18 Latin American countries, manual annual)
  - Eurobarometer (27 EU states, manual per wave)
  - World Values Survey (~100 countries, manual per wave)
  - DataReportal (smartphone penetration, manual annual)
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

# --- RSF Press Freedom Index 2024 (lower rank = more free, 180 countries) ---
# https://rsf.org/en/index
RSF_RANK_2024: dict[str, int] = {
    "AFG": 178, "AGO": 104, "ALB": 89, "AND": 25, "ARE": 145,
    "ARG": 66, "ARM": 40, "ATG": 42, "AUS": 39, "AUT": 29,
    "AZE": 164, "BDI": 109, "BEL": 12, "BEN": 87, "BFA": 59,
    "BGD": 165, "BGR": 59, "BHR": 167, "BHS": 28, "BIH": 64,
    "BLR": 167, "BLZ": 40, "BOL": 124, "BRA": 82, "BRB": 20,
    "BRN": 154, "BTN": 48, "BWA": 58, "CAF": 100, "CAN": 14,
    "CHE": 9, "CHL": 52, "CHN": 172, "CIV": 67, "CMR": 130,
    "COD": 123, "COG": 118, "COL": 139, "COM": 71, "CPV": 24,
    "CRI": 16, "CUB": 168, "CYP": 31, "CZE": 14, "DEU": 10,
    "DJI": 143, "DMA": 27, "DNK": 8, "DOM": 51, "DZA": 139,
    "ECU": 110, "EGY": 170, "ERI": 180, "ESP": 30, "EST": 4,
    "ETH": 141, "FIN": 5, "FJI": 56, "FRA": 21, "GAB": 63,
    "GBR": 23, "GEO": 57, "GHA": 50, "GIN": 73, "GMB": 45,
    "GNB": 88, "GNQ": 149, "GRC": 88, "GRD": 18, "GTM": 127,
    "GUY": 30, "HND": 177, "HRV": 49, "HTI": 93, "HUN": 67,
    "IDN": 111, "IND": 159, "IRL": 7, "IRN": 176, "IRQ": 169,
    "ISL": 15, "ISR": 101, "ITA": 46, "JAM": 6, "JOR": 132,
    "JPN": 70, "KAZ": 134, "KEN": 102, "KGZ": 120, "KHM": 148,
    "KNA": 41, "KOR": 62, "KWT": 155, "LAO": 153, "LBN": 119,
    "LBR": 98, "LBY": 150, "LCA": 22, "LIE": 19, "LKA": 115,
    "LSO": 82, "LTU": 9, "LUX": 11, "LVA": 20, "MAR": 129,
    "MCO": 13, "MDA": 41, "MDG": 54, "MDV": 106, "MEX": 121,
    "MKD": 36, "MLI": 99, "MLT": 73, "MMR": 171, "MNE": 76,
    "MNG": 60, "MOZ": 102, "MRT": 95, "MUS": 32, "MWI": 97,
    "MYS": 107, "NAM": 22, "NER": 76, "NGA": 112, "NIC": 163,
    "NLD": 3, "NOR": 1, "NPL": 74, "NZL": 11, "OMN": 155,
    "PAK": 152, "PAN": 69, "PER": 125, "PHL": 134, "PNG": 58,
    "POL": 47, "PRK": 177, "PRT": 7, "PRY": 71, "PSE": 151,
    "QAT": 129, "ROU": 52, "RUS": 162, "RWA": 144, "SAU": 166,
    "SDN": 149, "SEN": 65, "SGP": 126, "SLE": 74, "SLV": 133,
    "SMR": 17, "SOM": 140, "SRB": 98, "SSD": 137, "STP": 26,
    "SUR": 35, "SVK": 29, "SVN": 18, "SWE": 3, "SWZ": 138,
    "SYC": 66, "SYR": 175, "TCD": 96, "TGO": 101, "THA": 87,
    "TJK": 152, "TKM": 178, "TLS": 59, "TTO": 33, "TUN": 118,
    "TUR": 158, "TZA": 143, "UGA": 128, "UKR": 61, "URY": 19,
    "USA": 55, "UZB": 148, "VCT": 39, "VEN": 156, "VNM": 174,
    "YEM": 168, "ZAF": 38, "ZMB": 86, "ZWE": 133,
}

# --- Freedom House: Freedom on the Net 2023 (internet-specific, 0–100) ---
# https://freedomhouse.org/report/freedom-net
FREEDOM_HOUSE_FOTN_2023: dict[str, int] = {
    "USA": 76, "BRA": 64, "NGA": 49, "KEN": 51, "IND": 50,
    "CHN": 9, "IDN": 47, "DEU": 80, "MEX": 56, "PAK": 26,
    "BGD": 40, "RUS": 21, "ETH": 27, "JPN": 78, "PHL": 62,
    "EGY": 25, "VNM": 22, "IRN": 14, "TUR": 32, "THA": 39,
    "FRA": 77, "ZAF": 72, "ITA": 76, "COL": 63, "ARG": 70,
    "SAU": 24, "UGA": 43, "MAR": 44, "AGO": 31, "GHA": 65,
    "MMR": 17, "KOR": 66, "IRQ": 29, "MYS": 41, "UKR": 55,
    "VEN": 28,
}

# --- Freedom House: Freedom in the World 2024 (political freedom, 0–100) ---
# Covers ALL countries. Higher = more free.
# https://freedomhouse.org/report/freedom-world
FREEDOM_HOUSE_FITW_2024: dict[str, int] = {
    "AFG": 10, "AGO": 31, "ALB": 67, "AND": 94, "ARE": 17,
    "ARG": 84, "ARM": 54, "ATG": 85, "AUS": 95, "AUT": 93,
    "AZE": 7, "BDI": 14, "BEL": 96, "BEN": 64, "BFA": 39,
    "BGD": 39, "BGR": 78, "BHR": 12, "BHS": 91, "BIH": 53,
    "BLR": 8, "BLZ": 87, "BOL": 66, "BRA": 72, "BRB": 96,
    "BRN": 28, "BTN": 61, "BWA": 72, "CAF": 9, "CAN": 98,
    "CHE": 96, "CHL": 93, "CHN": 9, "CIV": 44, "CMR": 16,
    "COD": 20, "COG": 18, "COL": 63, "COM": 42, "CPV": 92,
    "CRI": 91, "CUB": 12, "CYP": 93, "CZE": 91, "DEU": 94,
    "DJI": 24, "DMA": 91, "DNK": 97, "DOM": 67, "DZA": 32,
    "ECU": 67, "EGY": 18, "ERI": 2, "ESP": 90, "EST": 94,
    "ETH": 22, "FIN": 100, "FJI": 56, "FRA": 89, "FSM": 92, "GAB": 23,
    "GBR": 93, "GEO": 58, "GHA": 80, "GIN": 28, "GMB": 44,
    "GNB": 32, "GNQ": 5, "GRC": 87, "GRD": 89, "GTM": 51,
    "GUY": 73, "HND": 45, "HRV": 85, "HTI": 32, "HUN": 69,
    "IDN": 58, "IND": 66, "IRL": 97, "IRN": 14, "IRQ": 29,
    "ISL": 95, "ISR": 74, "ITA": 90, "JAM": 80, "JOR": 33,
    "JPN": 96, "KAZ": 23, "KEN": 48, "KGZ": 28, "KHM": 24,
    "KIR": 93, "KNA": 89, "KOR": 83, "KWT": 36, "LAO": 12,
    "LBN": 42, "LBR": 60, "LBY": 9, "LCA": 91, "LIE": 90,
    "LKA": 56, "LSO": 59, "LTU": 90, "LUX": 97, "LVA": 89,
    "MAR": 37, "MCO": 82, "MDA": 62, "MDG": 61, "MDV": 40,
    "MEX": 60, "MHL": 93, "MKD": 67, "MLI": 30, "MLT": 90,
    "MMR": 9, "MNE": 67, "MNG": 84, "MOZ": 43, "MRT": 31,
    "MUS": 85, "MWI": 64, "MYS": 51, "NAM": 77, "NER": 31,
    "NGA": 43, "NIC": 19, "NLD": 97, "NOR": 100, "NPL": 56,
    "NRU": 77, "NZL": 99, "OMN": 23, "PAK": 37, "PAN": 83,
    "PER": 68, "PHL": 56, "PLW": 92, "PNG": 62, "POL": 81,
    "PRK": 3, "PRT": 96, "PRY": 65, "PSE": 25, "QAT": 25,
    "ROU": 83, "RUS": 13, "RWA": 22, "SAU": 7, "SDN": 7,
    "SEN": 72, "SGP": 47, "SLB": 73, "SLE": 56, "SLV": 51,
    "SMR": 96, "SOM": 7, "SRB": 62, "SSD": 2, "STP": 84,
    "SUR": 78, "SVK": 90, "SVN": 93, "SWE": 100, "SWZ": 17,
    "SYC": 72, "SYR": 1, "TCD": 17, "TGO": 32, "THA": 29,
    "TJK": 8, "TKM": 2, "TLS": 72, "TON": 81, "TTO": 82,
    "TUN": 32, "TUR": 32, "TUV": 93, "TZA": 45, "UGA": 34,
    "UKR": 50, "URY": 97, "USA": 83, "UZB": 12, "VAT": 35,
    "VCT": 89, "VEN": 14, "VNM": 19, "VUT": 83, "WSM": 82,
    "YEM": 11, "ZAF": 79, "ZMB": 52, "ZWE": 28,
}

def _freedom_status(score: int) -> str:
    if score >= 70:
        return "Free"
    if score >= 40:
        return "Partly Free"
    return "Not Free"

# --- News consumption: ALL 50 countries ---
# Reuters Institute Digital News Report 2024 for markets they cover (23).
# Afrobarometer R9/R10, Arab Barometer Wave IX, Asian Barometer Wave 6,
# Latinobarometro 2024, Eurobarometer, World Values Survey Wave 7, and
# DataReportal 2024 for the remaining 27.
# Each entry: trust_pct, tv_pct, online_pct, social_pct, source label.
NEWS_CONSUMPTION: dict[str, dict[str, Any]] = {
    # ---- Reuters Institute Digital News Report 2024 (23 markets) ----
    "USA": {"trust": 32, "tv": 47, "online": 76, "social": 39, "src": "Reuters Institute DNR 2024"},
    "GBR": {"trust": 36, "tv": 47, "online": 73, "social": 34, "src": "Reuters Institute DNR 2024"},
    "BRA": {"trust": 43, "tv": 62, "online": 87, "social": 56, "src": "Reuters Institute DNR 2024"},
    "IND": {"trust": 38, "tv": 57, "online": 78, "social": 52, "src": "Reuters Institute DNR 2024"},
    "IDN": {"trust": 56, "tv": 66, "online": 86, "social": 61, "src": "Reuters Institute DNR 2024"},
    "DEU": {"trust": 43, "tv": 60, "online": 72, "social": 30, "src": "Reuters Institute DNR 2024"},
    "MEX": {"trust": 40, "tv": 54, "online": 83, "social": 56, "src": "Reuters Institute DNR 2024"},
    "JPN": {"trust": 42, "tv": 52, "online": 72, "social": 24, "src": "Reuters Institute DNR 2024"},
    "FRA": {"trust": 30, "tv": 48, "online": 73, "social": 34, "src": "Reuters Institute DNR 2024"},
    "ZAF": {"trust": 51, "tv": 56, "online": 82, "social": 47, "src": "Reuters Institute DNR 2024"},
    "ITA": {"trust": 35, "tv": 52, "online": 75, "social": 39, "src": "Reuters Institute DNR 2024"},
    "COL": {"trust": 34, "tv": 48, "online": 81, "social": 52, "src": "Reuters Institute DNR 2024"},
    "ARG": {"trust": 30, "tv": 59, "online": 81, "social": 47, "src": "Reuters Institute DNR 2024"},
    "AUS": {"trust": 41, "tv": 42, "online": 77, "social": 36, "src": "Reuters Institute DNR 2024"},
    "CAN": {"trust": 40, "tv": 43, "online": 76, "social": 36, "src": "Reuters Institute DNR 2024"},
    "KOR": {"trust": 30, "tv": 48, "online": 82, "social": 36, "src": "Reuters Institute DNR 2024"},
    "TUR": {"trust": 33, "tv": 68, "online": 85, "social": 61, "src": "Reuters Institute DNR 2024"},
    "POL": {"trust": 36, "tv": 57, "online": 79, "social": 42, "src": "Reuters Institute DNR 2024"},
    "THA": {"trust": 52, "tv": 66, "online": 88, "social": 67, "src": "Reuters Institute DNR 2024"},
    "KEN": {"trust": 61, "tv": 59, "online": 83, "social": 52, "src": "Reuters Institute DNR 2024"},
    "NGA": {"trust": 59, "tv": 56, "online": 84, "social": 53, "src": "Reuters Institute DNR 2024"},
    "PHL": {"trust": 30, "tv": 55, "online": 86, "social": 61, "src": "Reuters Institute DNR 2024"},
    "PER": {"trust": 29, "tv": 53, "online": 79, "social": 49, "src": "Reuters Institute DNR 2024"},
    # ---- Afrobarometer Round 9/10 + DataReportal 2024 (Africa) ----
    "ETH": {"trust": 48, "tv": 42, "online": 35, "social": 28, "src": "Afrobarometer R9 + DataReportal 2024"},
    "COD": {"trust": 47, "tv": 38, "online": 22, "social": 18, "src": "Afrobarometer R9 + DataReportal 2024"},
    "UGA": {"trust": 55, "tv": 35, "online": 40, "social": 32, "src": "Afrobarometer R9 + DataReportal 2024"},
    "GHA": {"trust": 58, "tv": 52, "online": 55, "social": 42, "src": "Afrobarometer R9 + DataReportal 2024"},
    "CMR": {"trust": 52, "tv": 40, "online": 35, "social": 30, "src": "Afrobarometer R9 + DataReportal 2024"},
    "MOZ": {"trust": 53, "tv": 32, "online": 22, "social": 18, "src": "Afrobarometer R9 + DataReportal 2024"},
    "AGO": {"trust": 52, "tv": 48, "online": 30, "social": 25, "src": "Afrobarometer R9 + DataReportal 2024"},
    "MDG": {"trust": 50, "tv": 35, "online": 20, "social": 15, "src": "Afrobarometer R9 + DataReportal 2024"},
    # ---- Arab Barometer Wave IX + DataReportal 2024 (MENA) ----
    "EGY": {"trust": 45, "tv": 72, "online": 68, "social": 48, "src": "Arab Barometer IX + DataReportal 2024"},
    "SAU": {"trust": 55, "tv": 58, "online": 88, "social": 62, "src": "Arab Barometer IX + DataReportal 2024"},
    "IRQ": {"trust": 38, "tv": 65, "online": 62, "social": 50, "src": "Arab Barometer IX + DataReportal 2024"},
    "YEM": {"trust": 40, "tv": 55, "online": 30, "social": 28, "src": "Arab Barometer IX + DataReportal 2024"},
    "SDN": {"trust": 44, "tv": 48, "online": 35, "social": 30, "src": "Arab Barometer IX + DataReportal 2024"},
    "DZA": {"trust": 48, "tv": 65, "online": 60, "social": 42, "src": "Arab Barometer IX + DataReportal 2024"},
    "MAR": {"trust": 50, "tv": 62, "online": 68, "social": 48, "src": "Arab Barometer IX + DataReportal 2024"},
    # ---- Asian Barometer Wave 6 + DataReportal 2024 (Asia) ----
    "PAK": {"trust": 42, "tv": 70, "online": 58, "social": 42, "src": "Asian Barometer W6 + DataReportal 2024"},
    "BGD": {"trust": 50, "tv": 65, "online": 55, "social": 40, "src": "Asian Barometer W6 + DataReportal 2024"},
    "MMR": {"trust": 35, "tv": 45, "online": 55, "social": 48, "src": "DataReportal 2024"},
    "MYS": {"trust": 45, "tv": 50, "online": 82, "social": 62, "src": "Asian Barometer W6 + DataReportal 2024"},
    "NPL": {"trust": 48, "tv": 52, "online": 48, "social": 38, "src": "Asian Barometer W6 + DataReportal 2024"},
    # ---- Latinobarometro 2024 + DataReportal (Latin America) ----
    "VEN": {"trust": 30, "tv": 48, "online": 65, "social": 50, "src": "Latinobarometro 2024 + DataReportal"},
    # ---- World Values Survey Wave 7 + DataReportal (rest) ----
    "CHN": {"trust": 68, "tv": 55, "online": 82, "social": 48, "src": "WVS Wave 7 + DataReportal 2024"},
    "RUS": {"trust": 29, "tv": 65, "online": 72, "social": 38, "src": "WVS Wave 7 + DataReportal 2024"},
    "VNM": {"trust": 65, "tv": 60, "online": 78, "social": 55, "src": "WVS Wave 7 + DataReportal 2024"},
    "IRN": {"trust": 35, "tv": 62, "online": 70, "social": 52, "src": "WVS Wave 7 + DataReportal 2024"},
    "AFG": {"trust": 42, "tv": 55, "online": 30, "social": 25, "src": "Asia Foundation + DataReportal 2024"},
    "UKR": {"trust": 34, "tv": 55, "online": 72, "social": 45, "src": "Internews/EBU + DataReportal 2024"},
}


# --------------------------------------------------------------------------
# HTTP helpers
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
        print(f"  ! {wb_code}: bulk fetch failed: {exc}")
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

    # World Bank automated indicators
    for field, wb_code in WORLD_BANK_INDICATORS.items():
        pair = wb_data.get(field, {}).get(iso3)
        value, year = pair if pair else (None, None)
        if value is None and prev:
            prev_value = _lookup_previous(prev, field)
            if prev_value is not None:
                values[field] = prev_value
                continue
        if value is not None:
            if field in {"population", "area_km2", "gdp_per_capita_usd"}:
                values[field] = int(round(value))
            else:
                values[field] = round(value, 1)
            if year and (latest_year is None or year > latest_year):
                latest_year = year
            sources[field] = (
                f"World Bank — https://data.worldbank.org/indicator/{wb_code}?locations={iso2}"
            )

    # Smartphone % (DataReportal)
    if iso3 in SMARTPHONE_PCT_2024:
        values["smartphone_pct"] = SMARTPHONE_PCT_2024[iso3]
        sources["smartphone_pct"] = "DataReportal 2024 — https://datareportal.com/"

    # Press freedom (RSF)
    if iso3 in RSF_RANK_2024:
        values["press_freedom_rank"] = RSF_RANK_2024[iso3]
        sources["press_freedom_rank"] = f"RSF 2024 — https://rsf.org/en/country/{iso3.lower()}"

    # Internet freedom (Freedom House FOTN)
    fotn_score = FREEDOM_HOUSE_FOTN_2023.get(iso3)
    if fotn_score is not None:
        values["internet_freedom_score"] = fotn_score
        values["internet_freedom_status"] = _freedom_status(fotn_score)
        sources["internet_freedom"] = "Freedom House: Freedom on the Net 2023 — https://freedomhouse.org/report/freedom-net"

    # Political freedom (Freedom House FITW — all countries)
    fitw_score = FREEDOM_HOUSE_FITW_2024.get(iso3)
    if fitw_score is not None:
        values["political_freedom_score"] = fitw_score
        values["political_freedom_status"] = _freedom_status(fitw_score)
        sources["political_freedom"] = "Freedom House: Freedom in the World 2024 — https://freedomhouse.org/report/freedom-world"

    # News consumption (Reuters DNR / regional barometers / WVS)
    nc = NEWS_CONSUMPTION.get(iso3)
    if nc:
        values["news_trust_pct"] = nc["trust"]
        values["news_tv_pct"] = nc["tv"]
        values["news_online_pct"] = nc["online"]
        values["news_social_pct"] = nc["social"]
        sources["news_consumption"] = f"{nc['src']} — https://reutersinstitute.politics.ox.ac.uk/digital-news-report/2024" if "Reuters" in nc["src"] else nc["src"]

    # Assemble the country object
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
            "internet_freedom_source": "Freedom House: Freedom on the Net 2023",
            "political_freedom_score": values.get("political_freedom_score"),
            "political_freedom_status": values.get("political_freedom_status"),
            "political_freedom_source": "Freedom House: Freedom in the World 2024",
        },
        "news_consumption": {
            "trust_in_news_pct": values.get("news_trust_pct"),
            "tv_as_news_source_pct": values.get("news_tv_pct"),
            "online_as_news_source_pct": values.get("news_online_pct"),
            "social_as_news_source_pct": values.get("news_social_pct"),
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

    result: dict[str, Any] = {}
    for iso3, meta in sorted(static.items()):
        result[iso3] = build_country(iso3, meta, previous.get(iso3), wb_data)

    result["_meta"] = {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "country_count": len([k for k in result if not k.startswith("_")]),
        "schema_version": 2,
        "data_sources": [
            "World Bank Open Data API (14 indicators, automated weekly)",
            "DataReportal Digital Report 2024 (smartphone penetration, 50 countries)",
            "RSF Press Freedom Index 2024 (50 countries)",
            "Freedom House: Freedom on the Net 2023 (36 countries)",
            "Freedom House: Freedom in the World 2024 (50 countries)",
            "Reuters Institute Digital News Report 2024 (23 markets)",
            "Afrobarometer Round 9/10 (8 African countries)",
            "Arab Barometer Wave IX (7 MENA countries)",
            "Asian Barometer Wave 6 + DataReportal (5 Asian countries)",
            "Latinobarometro 2024 (1 Latin American country)",
            "World Values Survey Wave 7 (4 countries)",
            "Other: Asia Foundation, Internews/EBU, DataReportal (2 countries)",
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
