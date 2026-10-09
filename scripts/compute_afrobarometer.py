#!/usr/bin/env python3
"""
compute_afrobarometer.py — weighted news-source aggregates from Afrobarometer
Round 10 (38 countries, fieldwork 2024-2025).

INPUT (not in this repo — the dataset is Afrobarometer's to distribute):
  ~/Downloads/AB_R10.Merge Dataset_25Feb26.38ctry.release.sav
  Free download, no registration (checked 2026-10-08):
  afrobarometer.org → Data → Merged data → Round 10 →
  "AB_R10.Merge-Dataset_25Feb26.38ctry.release.sav.zip" (12.5 MB; the
  ENGLISH release — the "…release.Fr_.sav.zip" file is the French one).
  Unzip it and pass the .sav with --sav if it lives somewhere else.

WHAT IT COMPUTES, per country (withinwt_hh-weighted):
  radio / tv / social / online — % getting news from that source "a few
  times a week" or "every day" (Q65A / Q65B / Q65D / Q65E, codes 3-4).
  Denominator: every respondent except code -1 (Missing); "Don't know" and
  "Refused" stay in it. That is how Afrobarometer's own Summary of Results
  tables are built, and the guard below proves it on every run.
  year — fieldwork year(s) from DATEINTR, e.g. "2025" or "2024-2025".
  internet_weekly — % of adults using the internet "a few times a week" or
  more (Q90J). Not published as a figure; it backs the survey notes that
  explain when online-news use exceeds the World Bank/ITU internet figure
  (that one is a share of the WHOLE population, children included, while
  Afrobarometer interviews adults 18+ — Comoros and Guinea-Bissau, 2025).

WHY withinwt_hh, AND THE GUARD THAT PROVES IT:
  The file carries two within-country weights. withinwt_hh ("new AB
  withinwt") reproduces every cell of the published South Africa Summary of
  Results media tables exactly; withinwt_ea is off by up to 1.3 points and an
  unweighted count by up to 1.8 (tested 2026-10-08). The published cells are
  embedded below and the script aborts if they stop matching — so a changed
  file, a different weight or a different denominator cannot slip through.

CONSTRUCT NOTES (why labels matter):
  * "A few times a week or more" is close to, but not identical with,
    Reuters DNR's "used as a news source in the last week".
  * Round 10 asks about "Other Internet sources" (Q65E) as a separate item
    from social media (Q65D); the Atlas's "online" field is Q65E. Round 9's
    item was simply "Internet", so a Round 9 → Round 10 change in "online"
    partly reflects that sharper wording, not only behaviour.
  * Round 10 has no trust-in-news-media question comparable to DNR's, so
    trust stays unset, as it was for Round 9.

Output: a JSON dump next to the .sav for inspection, then paste-ready
AFRO_RADIO and NEWS_CONSUMPTION blocks. Nothing is written into the repo
automatically — integration into refresh_data.py is a deliberate, reviewed
step, and the round's ISO roster must be copied into AFROBAROMETER_R10 in
scripts/validate_atlas.py in the same commit.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import pyreadstat

SAV = Path.home() / "Downloads" / "AB_R10.Merge Dataset_25Feb26.38ctry.release.sav"

WEIGHT = "withinwt_hh"
VARS = ["COUNTRY", "DATEINTR", WEIGHT, "Q65A", "Q65B", "Q65D", "Q65E", "Q90J"]
FIELD_BY_VAR = {"Q65A": "radio", "Q65B": "tv", "Q65D": "social", "Q65E": "online"}

# Every COUNTRY value label in the Round 10 file (54, of which 38 hold data).
ISO3_BY_LABEL = {
    "Algeria": "DZA", "Angola": "AGO", "Benin": "BEN", "Botswana": "BWA",
    "Burkina Faso": "BFA", "Burundi": "BDI", "Cabo Verde": "CPV",
    "Cameroon": "CMR", "Central African Republic": "CAF", "Chad": "TCD",
    "Comoros": "COM", "Democratic Republic of the Congo": "COD",
    "Congo-Brazzaville": "COG", "Côte d'Ivoire": "CIV", "Djibouti": "DJI",
    "Egypt": "EGY", "Equatorial Guinea": "GNQ", "Eritrea": "ERI",
    "Eswatini": "SWZ", "Ethiopia": "ETH", "Gabon": "GAB", "Gambia, The": "GMB",
    "Ghana": "GHA", "Guinea": "GIN", "Guinea-Bissau": "GNB", "Kenya": "KEN",
    "Lesotho": "LSO", "Liberia": "LBR", "Libya": "LBY", "Madagascar": "MDG",
    "Malawi": "MWI", "Mali": "MLI", "Mauritania": "MRT", "Mauritius": "MUS",
    "Morocco": "MAR", "Mozambique": "MOZ", "Namibia": "NAM", "Niger": "NER",
    "Nigeria": "NGA", "Rwanda": "RWA", "São Tomé and Príncipe": "STP",
    "Senegal": "SEN", "Seychelles": "SYC", "Sierra Leone": "SLE",
    "Somalia": "SOM", "South Africa": "ZAF", "South Sudan": "SSD",
    "Sudan": "SDN", "Tanzania": "TZA", "Togo": "TGO", "Tunisia": "TUN",
    "Uganda": "UGA", "Zambia": "ZMB", "Zimbabwe": "ZWE",
}

# Published cells (%), Afrobarometer Round 10 Summary of Results, South
# Africa 2025 (Institute for Justice and Reconciliation, 22 May 2026), p. 83-84,
# "Total" column. code -> value, per question.
PUBLISHED_ZAF = {
    "Q65A": {0: 18.8, 3: 19.5, 4: 49.8},
    "Q65B": {0: 9.1, 3: 16.6, 4: 68.0},
    "Q65D": {0: 20.7, 3: 11.4, 4: 61.9},
    "Q65E": {0: 27.0, 3: 18.1, 4: 43.7},
}

EXPECTED_SCALE = {0.0: "Never", 3.0: "A few times a week", 4.0: "Every day"}


def weighted_pct(grp, var: str, codes: tuple[int, ...]) -> float | None:
    col = grp[[var, WEIGHT]].dropna()
    col = col[col[var] != -1]                        # drop "Missing" only
    total = col[WEIGHT].sum()
    if total <= 0:
        return None
    return 100.0 * col[col[var].isin(codes)][WEIGHT].sum() / total


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--sav", type=Path, default=SAV, help="path to the Round 10 .sav")
    ap.add_argument("--only", nargs="*", help="ISO3 codes to print (default: all)")
    ap.add_argument("--min-n", type=int, default=800,
                    help="minimum unweighted respondents per country (default 800)")
    args = ap.parse_args()

    if not args.sav.exists():
        print(f"Missing {args.sav} — download it first (see docstring).", file=sys.stderr)
        return 1

    df, meta = pyreadstat.read_sav(str(args.sav), usecols=VARS)

    # Guard 1: the answer scale is what the computation assumes.
    for var in [*FIELD_BY_VAR, "Q90J"]:
        labels = meta.variable_value_labels.get(var, {})
        for code, text in EXPECTED_SCALE.items():
            if labels.get(code) != text:
                print(f"SCALE MISMATCH on {var}: code {code} is {labels.get(code)!r}, "
                      f"expected {text!r} — aborting.", file=sys.stderr)
                return 1

    # Guard 2: every country in the file is one we can name.
    country_labels = meta.variable_value_labels["COUNTRY"]
    df["iso3"] = df["COUNTRY"].map(lambda c: ISO3_BY_LABEL.get(country_labels.get(c)))
    unknown = sorted({country_labels.get(c, c) for c in df.loc[df["iso3"].isna(), "COUNTRY"]})
    if unknown:
        print(f"UNMAPPED COUNTRIES {unknown} — add them to ISO3_BY_LABEL.", file=sys.stderr)
        return 1

    # Guard 3: reproduce Afrobarometer's own published South Africa tables.
    zaf = df[df["iso3"] == "ZAF"]
    for var, cells in PUBLISHED_ZAF.items():
        for code, published in cells.items():
            got = weighted_pct(zaf, var, (code,))
            if got is None or abs(round(got, 1) - published) > 0.051:
                print(f"PUBLISHED-TABLE MISMATCH: ZAF {var} code {code} computes {got} "
                      f"but the Summary of Results prints {published} — wrong file, "
                      f"weight or denominator; aborting.", file=sys.stderr)
                return 1

    out: dict[str, dict] = {}
    for iso3, grp in df.groupby("iso3"):
        n = len(grp)
        if n < args.min_n:
            continue
        years = sorted({d.year for d in grp["DATEINTR"].dropna()})
        rec: dict[str, object] = {
            "n": n,
            "year": str(years[0]) if len(years) == 1 else f"{years[0]}-{years[-1]}",
        }
        for var, field in {**FIELD_BY_VAR, "Q90J": "internet_weekly"}.items():
            pct = weighted_pct(grp, var, (3, 4))
            rec[field] = None if pct is None else round(pct, 1)
        out[str(iso3)] = rec

    dump = args.sav.parent / "afrobarometer_r10_aggregates.json"
    dump.write_text(json.dumps(out, indent=1, sort_keys=True), encoding="utf-8")
    print(f"# Wrote {dump} ({len(out)} countries). South Africa matches the "
          f"published Summary of Results tables.")
    print(f"# Roster for AFROBAROMETER_R10 in validate_atlas.py:\n# {' '.join(sorted(out))}\n")

    wanted = args.only if args.only else sorted(out)
    print("# AFRO_RADIO entries:")
    for iso3 in wanted:
        r = out.get(iso3)
        if r:
            print(f'    "{iso3}": ({r["radio"]}, "{label(r)}"),')
    print("\n# NEWS_CONSUMPTION entries (weekly-or-more use; no trust question):")
    for iso3 in wanted:
        r = out.get(iso3)
        if not r:
            print(f"    # {iso3}: not in Round 10 or below n threshold")
            continue
        print(f'    "{iso3}": {{"trust": None, "tv": {r["tv"]}, "online": {r["online"]}, '
              f'"social": {r["social"]}, "src": "{label(r)}"}},')
    return 0


def label(r: dict) -> str:
    return f"Afrobarometer Round 10 ({r['year']}), weighted microdata (n={r['n']:,})"


if __name__ == "__main__":
    sys.exit(main())
