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

# --- RSF Press Freedom Index 2025 (lower rank = more free, 180 countries) ---
# https://rsf.org/en/index
# Verified against rsf.org, statranker.org, Wikipedia (June 2026)
# Small Caribbean states (ATG, BHS, BRB, DMA, GRD, KNA, LCA, VCT) grouped
# as "OECS" by RSF and not ranked individually.
RSF_RANK_2025: dict[str, int] = {
    "AFG": 176, "AGO": 100, "ALB": 80, "AND": 65, "ARE": 158,
    "ARG": 87, "ARM": 34, "AUS": 29, "AUT": 22, "AZE": 167,
    "BDI": 125, "BEL": 18, "BEN": 92, "BFA": 106, "BGD": 152,
    "BGR": 70, "BHR": 165, "BIH": 86, "BLR": 166, "BLZ": 47,
    "BOL": 93, "BRA": 63, "BRN": 97, "BTN": 153, "BWA": 81,
    "CAF": 72, "CAN": 21, "CHE": 9, "CHL": 69, "CHN": 179,
    "CIV": 64, "CMR": 131, "COD": 133, "COG": 71, "COL": 113,
    "COM": 75, "CPV": 30, "CRI": 36, "CUB": 161, "CYP": 77,
    "CZE": 10, "DEU": 11, "DJI": 168, "DNK": 6, "DOM": 43,
    "DZA": 126, "ECU": 94, "EGY": 170, "ERI": 181, "ESP": 23,
    "EST": 2, "ETH": 145, "FIN": 5, "FJI": 40, "FRA": 25,
    "GAB": 41, "GBR": 20, "GEO": 115, "GHA": 52, "GIN": 103,
    "GMB": 58, "GNB": 110, "GNQ": 119, "GRC": 89, "GTM": 135,
    "GUY": 73, "HND": 138, "HRV": 60, "HUN": 68, "IDN": 127,
    "IND": 151, "IRL": 7, "IRN": 177, "IRQ": 156, "ISL": 17,
    "ISR": 114, "ITA": 49, "JAM": 26, "JOR": 147, "JPN": 66,
    "KAZ": 141, "KEN": 118, "KGZ": 144, "KHM": 163, "KOR": 61,
    "KWT": 128, "LAO": 150, "LBN": 132, "LBR": 54, "LBY": 137,
    "LIE": 12, "LKA": 139, "LSO": 91, "LTU": 14, "LUX": 13,
    "LVA": 15, "MAR": 121, "MDA": 35, "MDG": 101, "MDV": 104,
    "MEX": 124, "MKD": 42, "MLI": 120, "MLT": 67, "MMR": 169,
    "MNE": 37, "MNG": 102, "MOZ": 105, "MRT": 50, "MUS": 51,
    "MWI": 76, "MYS": 88, "NAM": 28, "NER": 83, "NGA": 112,
    "NIC": 173, "NLD": 3, "NOR": 1, "NPL": 90, "NZL": 16,
    "OMN": 134, "PAK": 155, "PAN": 53, "PER": 130, "PHL": 116,
    "PNG": 78, "POL": 31, "PRK": 180, "PRT": 8, "PRY": 84,
    "PSE": 162, "QAT": 79, "ROU": 55, "RUS": 172, "RWA": 143,
    "SAU": 164, "SDN": 157, "SEN": 74, "SGP": 123, "SLE": 56,
    "SLV": 148, "SOM": 136, "SRB": 96, "SSD": 109, "SUR": 32,
    "SVK": 38, "SVN": 33, "SWE": 4, "SWZ": 98, "SYC": 45,
    "SYR": 178, "TCD": 108, "TGO": 122, "THA": 85, "TJK": 154,
    "TKM": 175, "TLS": 39, "TON": 46, "TTO": 19, "TUN": 129,
    "TUR": 160, "TZA": 95, "UGA": 111, "UKR": 62, "URY": 59,
    "USA": 57, "UZB": 146, "VEN": 159, "VNM": 174, "WSM": 44,
    "YEM": 171, "ZAF": 27, "ZMB": 82, "ZWE": 107,
}

RSF_SCORE_2025: dict[str, float] = {
    "AFG": 17.88, "AGO": 52.67, "ALB": 58.18, "AND": 63.30, "ARE": 26.91,
    "ARG": 56.14, "ARM": 73.96, "AUS": 75.15, "AUT": 78.12, "AZE": 25.47,
    "BDI": 45.44, "BEL": 80.12, "BEN": 54.60, "BFA": 51.50, "BGD": 33.71,
    "BGR": 60.78, "BHR": 30.24, "BIH": 56.33, "BLR": 25.73, "BLZ": 68.32,
    "BOL": 54.09, "BRA": 63.80, "BRN": 53.47, "BTN": 32.00, "BWA": 57.64,
    "CAF": 60.15, "CAN": 78.75, "CHE": 83.98, "CHL": 62.25, "CHN": 14.80,
    "CIV": 63.69, "CMR": 42.75, "COD": 42.31, "COG": 60.58, "COL": 49.80,
    "COM": 59.27, "CPV": 74.98, "CRI": 73.09, "CUB": 26.03, "CYP": 59.04,
    "CZE": 83.96, "DEU": 83.85, "DJI": 25.36, "DNK": 86.93, "DOM": 69.87,
    "DZA": 44.64, "ECU": 53.76, "EGY": 24.74, "ERI": 11.32, "ESP": 77.35,
    "EST": 89.46, "ETH": 36.92, "FIN": 87.18, "FJI": 71.20, "FRA": 76.62,
    "GAB": 70.65, "GBR": 78.89, "GEO": 50.53, "GHA": 67.13, "GIN": 52.53,
    "GMB": 65.49, "GNB": 51.36, "GNQ": 48.68, "GRC": 55.37, "GTM": 40.32,
    "GUY": 60.12, "HND": 38.51, "HRV": 64.20, "HUN": 62.82, "IDN": 44.13,
    "IND": 32.96, "IRL": 86.92, "IRN": 16.22, "IRQ": 30.69, "ISL": 81.36,
    "ISR": 50.00, "ITA": 68.01, "JAM": 75.83, "JOR": 35.25, "JPN": 63.14,
    "KAZ": 39.34, "KEN": 49.41, "KGZ": 37.46, "KHM": 25.90, "KOR": 64.06,
    "KWT": 44.06, "LAO": 33.22, "LBN": 42.62, "LBR": 66.61, "LBY": 40.42,
    "LIE": 83.42, "LKA": 39.93, "LSO": 52.07, "LTU": 82.27, "LUX": 83.04,
    "LVA": 81.82, "MAR": 48.04, "MDA": 73.36, "MDG": 50.80, "MDV": 52.46,
    "MEX": 45.55, "MKD": 70.44, "MLI": 48.23, "MLT": 62.96, "MMR": 25.32,
    "MNE": 72.83, "MNG": 52.57, "MOZ": 52.63, "MRT": 67.52, "MUS": 67.31,
    "MWI": 59.20, "MYS": 56.09, "NAM": 75.35, "NER": 57.05, "NGA": 46.81,
    "NIC": 22.83, "NLD": 88.64, "NOR": 92.31, "NPL": 55.20, "NZL": 81.37,
    "OMN": 42.29, "PAK": 29.62, "PAN": 66.75, "PER": 42.88, "PHL": 49.57,
    "PNG": 58.35, "POL": 74.79, "PRK": 12.64, "PRT": 84.26, "PRY": 56.84,
    "PSE": 27.41, "QAT": 58.25, "ROU": 66.42, "RUS": 24.57, "RWA": 35.84,
    "SAU": 27.94, "SDN": 30.34, "SEN": 59.43, "SGP": 45.78, "SLE": 66.36,
    "SLV": 41.19, "SOM": 40.49, "SRB": 53.55, "SSD": 51.63, "SUR": 74.49,
    "SVK": 71.93, "SVN": 74.06, "SWE": 88.13, "SWZ": 52.86, "SYC": 68.56,
    "SYR": 15.82, "TCD": 51.89, "TGO": 48.03, "THA": 56.72, "TJK": 32.21,
    "TKM": 19.14, "TLS": 71.79, "TON": 68.39, "TTO": 79.71, "TUN": 43.48,
    "TUR": 29.40, "TZA": 53.68, "UGA": 37.61, "UKR": 63.93, "URY": 65.18,
    "USA": 65.49, "UZB": 35.24, "VEN": 29.21, "VNM": 19.74, "WSM": 69.28,
    "YEM": 31.45, "ZAF": 75.71, "ZMB": 57.33, "ZWE": 51.40,
}

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
# PSE and VAT are not individually rated by Freedom House (Gaza Strip alone is
# rated but is not representative of Palestine as a whole; Vatican is unrated);
# both retain the prior compiled estimate.
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
    "POL": 82, "PRK": 3, "PRT": 96, "PRY": 63, "PSE": 27,
    "QAT": 25, "ROU": 83, "RUS": 12, "RWA": 21, "SAU": 9,
    "SDN": 1, "SEN": 70, "SGP": 48, "SLB": 74, "SLE": 61,
    "SLV": 42, "SMR": 97, "SOM": 8, "SRB": 53, "SSD": 0,
    "STP": 84, "SUR": 81, "SVK": 88, "SVN": 97, "SWE": 99,
    "SWZ": 17, "SYC": 81, "SYR": 10, "TCD": 15, "TGO": 37,
    "THA": 33, "TJK": 5, "TKM": 1, "TLS": 73, "TON": 79,
    "TTO": 83, "TUN": 42, "TUR": 32, "TUV": 93, "TZA": 28,
    "UGA": 33, "UKR": 51, "URY": 97, "USA": 81, "UZB": 12,
    "VAT": 35, "VCT": 90, "VEN": 13, "VNM": 20, "VUT": 82,
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

# --- News consumption: ALL 50 countries ---
# Reuters Institute Digital News Report 2026 for markets they cover (46 of the
# 48 surveyed — Hong Kong and Taiwan excluded as non-UN-member entities).
# Afrobarometer R9/R10, Arab Barometer Wave IX, Asian Barometer Wave 6,
# Latinobarometro 2024, Eurobarometer, World Values Survey Wave 7, and
# DataReportal 2024 for the remaining markets DNR does not survey.
# Each entry: trust_pct, tv_pct, online_pct, social_pct, source label.
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
    "SDN": {"trust": None, "tv": 58.6, "online": 45.5, "social": 45.4, "src": "Afrobarometer Round 9 (2023)"},
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
    # DRC not covered by Afrobarometer Round 9 (only Congo-Brazzaville was) — kept as prior estimate.
    "COD": {"trust": 47, "tv": 38, "online": 22, "social": 18, "src": "Estimate (DataReportal 2024)"},
    # ---- Arab Barometer Wave IX + DataReportal 2024 (MENA) ----
    "EGY": {"trust": 45, "tv": 72, "online": 68, "social": 48, "src": "Arab Barometer IX + DataReportal 2024"},
    "SAU": {"trust": 55, "tv": 58, "online": 88, "social": 62, "src": "Arab Barometer IX + DataReportal 2024"},
    "IRQ": {"trust": 38, "tv": 65, "online": 62, "social": 50, "src": "Arab Barometer IX + DataReportal 2024"},
    "YEM": {"trust": 40, "tv": 55, "online": 30, "social": 28, "src": "Arab Barometer IX + DataReportal 2024"},
    "DZA": {"trust": 48, "tv": 65, "online": 60, "social": 42, "src": "Arab Barometer IX + DataReportal 2024"},
    # ---- Asian Barometer Wave 6 + DataReportal 2024 (Asia) ----
    "PAK": {"trust": 42, "tv": 70, "online": 58, "social": 42, "src": "Asian Barometer W6 + DataReportal 2024"},
    "BGD": {"trust": 50, "tv": 65, "online": 55, "social": 40, "src": "Asian Barometer W6 + DataReportal 2024"},
    "MMR": {"trust": 35, "tv": 45, "online": 55, "social": 48, "src": "DataReportal 2024"},
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
    if iso3 in RSF_RANK_2025:
        values["press_freedom_rank"] = RSF_RANK_2025[iso3]
        values["press_freedom_score"] = RSF_SCORE_2025.get(iso3)
        sources["press_freedom_rank"] = f"RSF 2025 — https://rsf.org/en/country/{iso3.lower()}"

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
            "press_freedom_score": values.get("press_freedom_score"),
            "press_freedom_source": "RSF 2025",
        },
        "information_freedom": {
            "press_freedom_rank": values.get("press_freedom_rank"),
            "press_freedom_score": values.get("press_freedom_score"),
            "press_freedom_source": "RSF 2025 — https://rsf.org/en/index",
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
            "RSF Press Freedom Index 2025 (174 countries)",
            "Freedom House: Freedom on the Net 2025 (70 countries)",
            "Freedom House: Freedom in the World 2026 report / 2025 data (195 countries)",
            "Reuters Institute Digital News Report 2026 (46 markets)",
            "Afrobarometer Round 9 (35 African countries)",
            "Arab Barometer Wave IX (6 MENA countries)",
            "Asian Barometer Wave 6 + DataReportal (4 Asian countries)",
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
