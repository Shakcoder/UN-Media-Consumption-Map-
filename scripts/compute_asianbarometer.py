#!/usr/bin/env python3
"""
compute_asianbarometer.py — news-source shares from Asian Barometer Wave 6.

INPUT (not in this repo — Asian Barometer data stays local per its terms):
  ~/Downloads/AsianBarometer/W6_12_Cambodia_20240819/W6_Cambodia_Release_20240819.sav
  ~/Downloads/AsianBarometer/W6_5_Mongolia/W6_Mongolia_Release_20241223.sav
  ~/Downloads/AsianBarometer/W6_11_Vietnam_Release_20250117.sav
  Free download after registration: asianbarometer.org → Data Release →
  Wave 6 → per-country files.

WHAT IT COMPUTES, per country (W-weighted):
  q53 — "Which one is the most important channel for you to find information
  about politics and government?" SINGLE choice: television / newspaper /
  internet and social media / radio / face-to-face / other.
  Shares are % naming each as the MOST IMPORTANT channel.

CONSTRUCT WARNING (kept on every entry, same rule as Arab Barometer):
a single-choice "most important channel" is NOT the multi-select "used
weekly" measure most Atlas entries use. Percentages are structurally lower
(they sum to ~100 across channels) and must never be compared head-to-head
with Reuters DNR weekly-reach figures. The note travels with the data.

Two further honesty constraints, both enforced below:
  * q53 offers a combined "Internet and social media" option, so online and
    social CANNOT be separated. We publish it as `online` and leave `social`
    as None rather than double-count one answer into two fields.
  * Wave 6 carries no trust-in-media question, so trust stays None.

Citation: Asian Barometer Survey Wave 6 (2023-2025), Hu Fu Center for East
Asia Democratic Studies, National Taiwan University — asianbarometer.org.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pyreadstat

BASE = Path.home() / "Downloads" / "AsianBarometer"

# Only countries whose Wave 6 file is published individually. Each entry is
# (ISO 3166-1 alpha-3, path, fieldwork year as released).
SOURCES = [
    ("KHM", BASE / "W6_12_Cambodia_20240819" / "W6_Cambodia_Release_20240819.sav", "2024"),
    ("MNG", BASE / "W6_5_Mongolia" / "W6_Mongolia_Release_20241223.sav", "2024"),
    ("VNM", BASE / "W6_11_Vietnam_Release_20250117.sav", "2025"),
]

# q53 codes — verified against each file's own value labels before use.
CODES = {"tv": 1.0, "newspaper": 2.0, "online": 3.0, "radio": 4.0}
EXPECTED_LABELS = {
    1.0: "television",
    2.0: "newspaper",
    3.0: "internet",
    4.0: "radio",
}

# Substantive answers only: 7 = don't understand, 8 = can't choose,
# 9 = decline, 0 = not applicable, -1 = missing.
NON_SUBSTANTIVE = {-1.0, 0.0, 7.0, 8.0, 9.0}

MIN_SAMPLE = 500


def _labels_match(labels: dict) -> bool:
    """Refuse to guess if the codebook shifted between releases."""
    for code, expect in EXPECTED_LABELS.items():
        got = str(labels.get(code, "")).lower()
        if expect not in got:
            print(f"  SCALE MISMATCH on q53 code {code}: expected ~'{expect}', got '{got}'", file=sys.stderr)
            return False
    return True


def main() -> int:
    out: dict[str, dict] = {}
    for iso3, path, year in SOURCES:
        if not path.exists():
            print(f"# skip {iso3}: missing {path}", file=sys.stderr)
            continue
        df, meta = pyreadstat.read_sav(str(path), usecols=["q53", "W"])
        labels = meta.variable_value_labels.get("q53", {})
        if not _labels_match(labels):
            print(f"# skip {iso3}: q53 value labels do not match the expected codebook", file=sys.stderr)
            continue

        sub = df.dropna(subset=["q53", "W"])
        sub = sub[~sub["q53"].isin(NON_SUBSTANTIVE)]
        wt = sub["W"].sum()
        if wt <= 0 or len(sub) < MIN_SAMPLE:
            print(f"# skip {iso3}: only {len(sub)} substantive responses (need {MIN_SAMPLE})", file=sys.stderr)
            continue

        rec = {"n": int(len(sub)), "year": year}
        for field, code in CODES.items():
            rec[field] = round(100.0 * sub[sub["q53"] == code]["W"].sum() / wt, 1)
        out[iso3] = rec

    if not out:
        print("No usable country files found — nothing written.", file=sys.stderr)
        return 1

    dump = BASE / "abs_w6_news_primary_channel.json"
    dump.write_text(json.dumps(out, indent=1, sort_keys=True), encoding="utf-8")
    print(f"# Wrote {dump} ({len(out)} countries).")
    print("# Paste-ready NEWS_CONSUMPTION entries (MOST IMPORTANT channel, single-choice):\n")
    for iso3 in sorted(out):
        r = out[iso3]
        print(
            f'    "{iso3}": {{"trust": None, "tv": {r["tv"]}, "online": {r["online"]}, '
            f'"social": None, "radio": {r["radio"]},\n'
            f'            "src": "Asian Barometer Wave 6 ({r["year"]}) microdata, weighted (n={r["n"]})",\n'
            f'            "note": "q53: single most-important news channel (not multi-select weekly use '
            f'— not directly comparable to other countries\' figures); the option combines internet and '
            f'social media, so social is not separable; no trust-in-media question in this wave"}},'
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
