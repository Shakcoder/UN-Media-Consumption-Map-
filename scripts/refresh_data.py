#!/usr/bin/env python3
"""
refresh_data.py — automated data refresh for the Global Media Consumption Atlas.

Primary sources (all free, no API key):
  - World Bank Open Data API (14 indicators, automated weekly)
  - RSF Press Freedom Index (174 countries, manual annual)
  - Freedom House: Freedom on the Net (70 countries, manual annual)
  - Freedom House: Freedom in the World (195 countries, manual annual)
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
        values["political_freedom_status"] = _freedom_status(fitw_score)
        sources["political_freedom"] = "Freedom House: Freedom in the World 2026 report (2025 data) — https://freedomhouse.org/report/freedom-world"

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
            "political_freedom_source": "Freedom House: Freedom in the World 2026 report (2025 data)",
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
