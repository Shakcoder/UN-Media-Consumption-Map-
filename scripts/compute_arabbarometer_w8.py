#!/usr/bin/env python3
"""
compute_arabbarometer_w8.py — news-source shares from Arab Barometer Wave VIII.

INPUT (not in this repo — Arab Barometer data stays local per its terms):
  ~/Downloads/ArabBarometer_WaveVIII_English_v2/ArabBarometer_WaveVIII_English_v3.sav
  Free download after a short form: arabbarometer.org → Survey Data →
  Data Downloads → Wave VIII → Data Sets.

WHAT IT COMPUTES, per country (WT-weighted):
  Q421 — "What is your primary source of information to follow the breaking
  news as events unfold?" SINGLE choice: in-person, telephone, newspapers,
  radio, television, social media. Shares are % naming each as PRIMARY.

CONSTRUCT WARNING (kept on every entry): a single-choice "primary source"
is NOT the multi-select "used weekly" measure most other Atlas entries use.
Percentages are structurally lower (they sum to ~100 across channels).
No trust-in-media question exists anywhere in Wave VIII — trust stays None.

Wave VIII countries: Iraq, Jordan, Kuwait, Lebanon, Mauritania, Morocco,
Palestine, Tunisia (2023-2024 fieldwork).

Citation: Arab Barometer Wave VIII (2023-2024), Arab Barometer,
Princeton NJ — arabbarometer.org.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pyreadstat

SAV = (Path.home() / "Downloads" / "ArabBarometer_WaveVIII_English_v2"
       / "ArabBarometer_WaveVIII_English_v3.sav")

COUNTRY_TO_A3 = {7.0: "IRQ", 8.0: "JOR", 9.0: "KWT", 10.0: "LBN",
                 12.0: "MRT", 13.0: "MAR", 15.0: "PSE", 21.0: "TUN"}

# Q421 codes (verified against the file's value labels at runtime)
CODES = {"tv": 5.0, "social": 6.0, "radio": 4.0, "newspapers": 3.0}


def main() -> int:
    if not SAV.exists():
        print(f"Missing {SAV} — download it first (see docstring).", file=sys.stderr)
        return 1

    df, meta = pyreadstat.read_sav(str(SAV), usecols=["COUNTRY", "WT", "Q421"])

    labels = meta.variable_value_labels.get("Q421", {})
    if (labels.get(5.0) != "Television" or labels.get(6.0) != "Social media"
            or labels.get(90.0) != "Other"):
        print("SCALE MISMATCH on Q421 — aborting rather than guessing.", file=sys.stderr)
        return 1

    out: dict[str, dict] = {}
    for code, grp in df.groupby("COUNTRY"):
        iso3 = COUNTRY_TO_A3.get(float(code))
        if not iso3:
            continue
        # Base: all respondents who named a source. Only 98 (don't know) and
        # 99 (refused) come out — code 90 is "Other", a real answer, and it
        # stays in the denominator. Wave VII numbers "Other" 7, so dropping 90
        # here would quietly give the two waves different bases for figures the
        # Atlas publishes side by side under the same construct note.
        sub = grp.dropna(subset=["Q421", "WT"])
        sub = sub[sub["Q421"] < 98.0]
        wt = sub["WT"].sum()
        if wt <= 0 or len(sub) < 500:
            continue
        rec = {"n": int(len(sub))}
        for field, c in CODES.items():
            rec[field] = round(100.0 * sub[sub["Q421"] == c]["WT"].sum() / wt, 1)
        out[iso3] = rec

    dump = SAV.parent / "ab_w8_news_primary_source.json"
    dump.write_text(json.dumps(out, indent=1, sort_keys=True), encoding="utf-8")
    print(f"# Wrote {dump} ({len(out)} countries).")
    print("# Paste-ready NEWS_CONSUMPTION entries (PRIMARY news source, single-choice):\n")
    for iso3 in sorted(out):
        r = out[iso3]
        print(
            f'    "{iso3}": {{"trust": None, "tv": {r["tv"]}, "online": None, '
            f'"social": {r["social"]}, "radio": {r["radio"]},\n'
            f'            "src": "Arab Barometer Wave VIII (2023-2024) microdata",\n'
            f'            "note": "Q421: single primary news source (not multi-select weekly use — '
            f'not directly comparable to other countries\' figures); no trust-in-media question in this wave"}},'
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
