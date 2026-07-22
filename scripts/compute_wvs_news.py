#!/usr/bin/env python3
"""
compute_wvs_news.py — weighted news-consumption aggregates from WVS Wave 7.

INPUT (not in this repo — WVSA prohibits redistributing the raw dataset):
  ~/Downloads/WVS7_spss/WVS_Cross-National_Wave_7_spss_v6_0.sav
  Free download after registration: worldvaluessurvey.org → Data Download →
  Wave 7 → "WVS Cross-National Wave 7 spss v6 0.zip" (STANDARD version, not
  "Inverted scales"). This script verifies the scale direction from the
  file's own embedded value labels and aborts if they don't match, so the
  inverted file cannot silently produce reversed numbers.

WHAT IT COMPUTES, per country (W_WEIGHT-weighted, missing codes excluded):
  tv / radio / online / social  — % using that source DAILY or WEEKLY
                                  (Q202 / Q203 / Q206 / Q207 <= 2)
  trust                         — % with "a great deal" or "quite a lot" of
                                  confidence in THE PRESS (Q66 <= 2)
  year                          — fieldwork year (max A_YEAR per country)

CONSTRUCT NOTES (why labels matter):
  * "Daily or weekly use" is close to, but not identical with, Reuters DNR's
    "used as a news source in the last week".
  * Q66 measures confidence in the press as an INSTITUTION — a different
    question from DNR's "you can trust most news most of the time". The
    integration labels it as such and must keep doing so.

Citation (required by WVSA):
  Haerpfer, C., Inglehart, R., Moreno, A., Welzel, C., Kizilova, K.,
  Diez-Medrano J., M. Lagos, P. Norris, E. Ponarin & B. Puranen (eds.). 2022.
  World Values Survey: Round Seven – Country-Pooled Datafile Version 6.0.
  Madrid & Vienna: JD Systems Institute & WVSA Secretariat.
  doi:10.14281/18241.24

Output: prints a ready-to-paste NEWS_CONSUMPTION block (only for countries
you pass with --only, or all 66) plus a JSON dump next to the .sav for
inspection. Nothing is written into the repo automatically — integration
into refresh_data.py is a deliberate, reviewed step.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import pyreadstat

SAV = Path.home() / "Downloads" / "WVS7_spss" / "WVS_Cross-National_Wave_7_spss_v6_0.sav"

VARS = ["B_COUNTRY_ALPHA", "A_YEAR", "W_WEIGHT",
        "Q66", "Q202", "Q203", "Q206", "Q207"]

FIELD_BY_VAR = {"Q202": "tv", "Q203": "radio", "Q206": "online", "Q207": "social"}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", nargs="*", help="ISO3 codes to print (default: all)")
    ap.add_argument("--min-n", type=int, default=800,
                    help="minimum unweighted respondents per country (default 800)")
    args = ap.parse_args()

    if not SAV.exists():
        print(f"Missing {SAV} — download it first (see docstring).", file=sys.stderr)
        return 1

    df, meta = pyreadstat.read_sav(str(SAV), usecols=VARS)

    # Guard: verify scale direction from the file's own labels (the
    # "Inverted scales" release would flip every result).
    q202 = meta.variable_value_labels.get("Q202", {})
    if q202.get(1.0) != "Daily" or q202.get(5.0) != "Never":
        print("SCALE MISMATCH: this looks like the INVERTED release — aborting.", file=sys.stderr)
        return 1
    q66 = meta.variable_value_labels.get("Q66", {})
    if q66.get(1.0) != "A great deal":
        print("SCALE MISMATCH on Q66 — aborting.", file=sys.stderr)
        return 1

    out: dict[str, dict] = {}
    for iso3, grp in df.groupby("B_COUNTRY_ALPHA"):
        n = len(grp)
        if n < args.min_n:
            continue
        year = int(grp["A_YEAR"].max())
        rec: dict[str, object] = {"n": n, "year": year}
        for var, field in {**FIELD_BY_VAR, "Q66": "trust"}.items():
            col = grp[[var, "W_WEIGHT"]].dropna()
            col = col[col[var] > 0]                     # drop missing codes (<0)
            wt_total = col["W_WEIGHT"].sum()
            if wt_total <= 0 or len(col) < args.min_n // 2:
                rec[field] = None
                continue
            hit = col[col[var] <= 2.0]["W_WEIGHT"].sum()  # daily+weekly / great deal+quite a lot
            rec[field] = round(100.0 * hit / wt_total, 1)
        out[str(iso3)] = rec

    dump = SAV.parent / "wvs7_news_aggregates.json"
    dump.write_text(json.dumps(out, indent=1, sort_keys=True), encoding="utf-8")
    print(f"# Wrote {dump} ({len(out)} countries).")
    print("# Paste-ready NEWS_CONSUMPTION entries "
          "(daily+weekly use; trust = confidence in the press):\n")

    wanted = args.only if args.only else sorted(out)
    for iso3 in wanted:
        r = out.get(iso3)
        if not r:
            print(f"    # {iso3}: not in WVS7 or below n threshold")
            continue
        print(
            f'    "{iso3}": {{"trust": {r["trust"]}, "tv": {r["tv"]}, '
            f'"online": {r["online"]}, "social": {r["social"]}, "radio": {r["radio"]},\n'
            f'            "src": "World Values Survey Wave 7 ({r["year"]}), weighted microdata (n={r["n"]:,})",\n'
            f'            "note": "WVS constructs: use = daily or weekly (vs DNR\'s \'past week\'); '
            f'trust = confidence in the press as an institution, not DNR\'s trust-in-news"}},'
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
