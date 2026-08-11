#!/usr/bin/env python3
"""
compute_lapop_news.py — news-attention frequency, LAPOP AmericasBarometer 2023.

INPUT (not in this repo — LAPOP data stays local per its terms of use):
  ~/Downloads/LAPOP2023/{ISO}_2023_LAPOP_AmericasBarometer_v1.0_w.sav
  Free public download (no account): datasets.americasbarometer.org/database
  → "Free User" → search 2023. The terms require human-subjects protections
  and NOT sharing the data files with third parties — so the raw .sav files
  are never committed; only the weighted aggregates this script prints are
  published, with citation. (Same posture as WVS/Eurobarometer/the other
  barometers in this project.)

WHAT IT COMPUTES, per country (wt-weighted):
  gi0n — "About how often do you pay attention to the news, whether on TV,
  the radio, newspapers, or the internet?"
    daily_pct        = answered "Daily"
    weekly_plus_pct  = "Daily" or "A few times a week"
    never_pct        = "Never"
  Base = respondents 1..5; DK (888888), NR (988888) and N/A (999999)
  are excluded from the base.

THE CONSTRUCT, honestly: this is OVERALL news attention with every medium
lumped into one question. It can NEVER fill the per-channel
tv/radio/online/social_as_news_source_pct fields (doing so would invent a
construct), which is why it lives in its own `news_attention` field — the
same separate-field discipline as `platform_use`. For thirteen countries
(BHS BLZ CRI DOM GRD HTI HND JAM PAN PRY SLV SUR TTO) it is the first
measured news figure of any kind in the Atlas.

Citation: LAPOP Lab, AmericasBarometer 2023, Vanderbilt University —
www.vanderbilt.edu/lapop (free public datasets).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pyreadstat

BASE = Path.home() / "Downloads" / "LAPOP2023"

# Filename prefixes are ISO3 except Grenada, which LAPOP codes as GRE.
FILE_TO_ISO = {"GRE": "GRD"}

VALID = {1.0, 2.0, 3.0, 4.0, 5.0}


def main() -> int:
    files = sorted(BASE.glob("*_2023_LAPOP_AmericasBarometer_*.sav"))
    if not files:
        print(f"No LAPOP files in {BASE} — download them first (see docstring).",
              file=sys.stderr)
        return 1

    out: dict[str, dict] = {}
    skipped: list[str] = []
    for f in files:
        code = f.name.split("_")[0].upper()
        iso3 = FILE_TO_ISO.get(code, code)
        # Column-name case varies across country releases (gi0n / GI0N / GI0n),
        # so resolve the real names from the file's own metadata first.
        try:
            _, meta0 = pyreadstat.read_sav(str(f), metadataonly=True)
            by_lower = {c.lower(): c for c in meta0.column_names}
            gi, wtc = by_lower.get("gi0n"), by_lower.get("wt")
            if not gi or not wtc:
                skipped.append(f"{iso3} (no gi0n/wt column)")
                continue
            df, meta = pyreadstat.read_sav(str(f), usecols=[gi, wtc])
            df.columns = ["gi0n" if c == gi else "wt" for c in df.columns]
        except Exception as exc:
            skipped.append(f"{iso3} ({exc})")
            continue
        base = df[df["gi0n"].isin(VALID)]
        wt_total = base["wt"].sum()
        if wt_total <= 0 or len(base) < 500:
            skipped.append(f"{iso3} (base n={len(base)} too small)")
            continue
        w = lambda vals: 100.0 * base[base["gi0n"].isin(vals)]["wt"].sum() / wt_total
        out[iso3] = {
            "daily_pct": round(w({1.0}), 1),
            "weekly_plus_pct": round(w({1.0, 2.0}), 1),
            "never_pct": round(w({5.0}), 1),
            "n": int(len(base)),
        }

    dump = BASE / "lapop2023_news_attention.json"
    dump.write_text(json.dumps(out, indent=1, sort_keys=True), encoding="utf-8")
    print(f"# Wrote {dump} ({len(out)} countries)."
          + (f" Skipped: {'; '.join(skipped)}" if skipped else ""))
    print("# Paste-ready NEWS_ATTENTION_2023 entries:\n")
    for iso3 in sorted(out):
        r = out[iso3]
        print(f'    "{iso3}": {{"daily_pct": {r["daily_pct"]}, '
              f'"weekly_plus_pct": {r["weekly_plus_pct"]}, '
              f'"never_pct": {r["never_pct"]}, "n": {r["n"]}}},')
    return 0


if __name__ == "__main__":
    sys.exit(main())
