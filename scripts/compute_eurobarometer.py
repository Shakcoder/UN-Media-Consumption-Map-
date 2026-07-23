#!/usr/bin/env python3
"""
compute_eurobarometer.py — weekly media reach from Eurobarometer 102.2 (2024).

INPUT (not in this repo — GESIS data stays local per its terms of use):
  ~/Downloads/ZA8905_v1-0-0.sav
  Free download after GESIS registration: search.gesis.org → Eurobarometer
  102.2 (ZA8905, doi:10.4232/1.14726) → Downloads → Datasets → SPSS.

WHAT IT COMPUTES, per country (w1-weighted):
  tv     — % using television WEEKLY or more (qe3_1 TV via set OR qe3_2 TV
           via internet, codes 1-3 on either)
  radio  — % using radio weekly or more (qe3_3 <= 3)
  online — % consuming NEWS on the internet weekly or more (qe3_6 <= 3;
           this item IS news-specific)
  social — % using online social networks weekly or more (qe3_7 <= 3)
  trust  — None. EB 102.2 measures trust per medium (qe4 battery: written
           press / radio / TV / websites / social networks, tend-to-trust
           binary). There is no single trust-in-news item, and cherry-picking
           one medium or averaging them would be construct invention.

CONSTRUCT NOTE (kept on every entry): qe3 measures GENERAL media use, not
news use (except qe3_6). Reach figures are therefore an upper bound on
news reach for tv/radio/social — flagged, not hidden. "Don't know" (8) is
excluded from the base; "never" (6) and "no access" (7) stay in the base
because unreached population is exactly what reach percentages are about.

SAMPLES DELIBERATELY SKIPPED:
  DE-E/DE-W, GB, TR, RS (already covered by Reuters DNR 2026 or newer),
  CY-TCC and RS-KM (not UN member states — outside the Atlas's 195).

Citation: European Commission, Brussels (2026). Eurobarometer 102.2 (2024).
GESIS, Cologne. ZA8905 data file v1.0.0, doi:10.4232/1.14726.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pyreadstat

SAV = Path.home() / "Downloads" / "ZA8905_v1-0-0.sav"

ISO2_TO_A3 = {
    "AL": "ALB", "AT": "AUT", "BA": "BIH", "BE": "BEL", "BG": "BGR",
    "CY": "CYP", "CZ": "CZE", "DK": "DNK", "EE": "EST", "ES": "ESP",
    "FI": "FIN", "FR": "FRA", "GE": "GEO", "GR": "GRC", "HR": "HRV",
    "HU": "HUN", "IE": "IRL", "IT": "ITA", "LT": "LTU", "LU": "LUX",
    "LV": "LVA", "MD": "MDA", "ME": "MNE", "MK": "MKD", "MT": "MLT",
    "NL": "NLD", "PL": "POL", "PT": "PRT", "RO": "ROU", "SE": "SWE",
    "SI": "SVN", "SK": "SVK",
    # skipped by design: DE-E, DE-W, GB, TR, RS (covered elsewhere),
    # CY-TCC, RS-KM (not UN member states)
}

VARS = ["isocntry", "w1", "qe3_1", "qe3_2", "qe3_3", "qe3_6", "qe3_7"]


def weekly_share(grp, cols: list[str]) -> float | None:
    """Weighted % with code <=3 on ANY of cols; DK (8) rows leave the base."""
    sub = grp[cols + ["w1"]].dropna()
    # a row is DK only if it is DK on every asked column
    dk = (sub[cols] == 8.0).all(axis=1)
    sub = sub[~dk]
    wt = sub["w1"].sum()
    if wt <= 0 or len(sub) < 300:
        return None
    hit = sub[(sub[cols] <= 3.0).any(axis=1)]["w1"].sum()
    return round(100.0 * hit / wt, 1)


def main() -> int:
    if not SAV.exists():
        print(f"Missing {SAV} — download it first (see docstring).", file=sys.stderr)
        return 1

    df, meta = pyreadstat.read_sav(str(SAV), usecols=VARS)

    # Guard: verify the frequency scale from the file's own labels.
    q = meta.variable_value_labels.get("qe3_1", {})
    if q.get(1.0) != "Everyday/ Almost everyday" or q.get(6.0) != "Never":
        print("SCALE MISMATCH on qe3_1 — aborting rather than guessing.", file=sys.stderr)
        return 1

    out: dict[str, dict] = {}
    for iso2, grp in df.groupby("isocntry"):
        iso3 = ISO2_TO_A3.get(str(iso2))
        if not iso3:
            continue                      # skipped sample (see docstring)
        rec = {
            "n": int(len(grp)),
            "tv": weekly_share(grp, ["qe3_1", "qe3_2"]),
            "radio": weekly_share(grp, ["qe3_3"]),
            "online": weekly_share(grp, ["qe3_6"]),
            "social": weekly_share(grp, ["qe3_7"]),
        }
        out[iso3] = rec

    dump = SAV.parent / "eb102_2_media_use.json"
    dump.write_text(json.dumps(out, indent=1, sort_keys=True), encoding="utf-8")
    print(f"# Wrote {dump} ({len(out)} countries).")
    print("# Paste-ready NEWS_CONSUMPTION entries (weekly use, w1-weighted):\n")
    for iso3 in sorted(out):
        r = out[iso3]
        print(
            f'    "{iso3}": {{"trust": None, "tv": {r["tv"]}, "online": {r["online"]}, '
            f'"social": {r["social"]}, "radio": {r["radio"]},\n'
            f'            "src": "Eurobarometer 102.2 (Oct-Nov 2024), weighted microdata (n={r["n"]:,})",\n'
            f'            "note": "EB constructs: weekly use of each medium — general media use, not news-specific '
            f'(except online = news on internet); trust is only asked per medium, so no single trust figure"}},'
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
