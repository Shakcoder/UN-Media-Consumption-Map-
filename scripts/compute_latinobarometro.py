#!/usr/bin/env python3
"""
compute_latinobarometro.py — measured social-platform use, Latinobarometro 2024.

INPUT (not in this repo — Latinobarometro data stays local per its terms):
  ~/Downloads/Latinobarometro/Latinobarometro_2024_Spss_eng_v20250817.sav
  Free download after registration: latinobarometro.org → Data → 2024 →
  SPSS zip (the zip ships both eng- and esp-labelled .sav files).

WHAT IT COMPUTES, per country (WT-weighted):
  % of adults who mention actively using each social/messaging service
  (S14M battery: Facebook, Snapchat, YouTube, X, WhatsApp, Instagram,
  TikTok, LinkedIn) plus % using none (S14M.10). Base = all respondents
  except explicit non-response (S14M.11).

WHY THIS LAYER EXISTS: the Atlas's "leading platform" fields were curated,
not measured. This battery is real measured platform usage — a different
construct from news consumption (it says nothing about NEWS use), so it
lives in its own `platform_use` field, never in news_consumption.

NOTE (2026-07-23): the 2024 wave does NOT carry the channel-of-news battery
("¿cómo se informa?") that earlier waves had, so news_consumption fields
cannot be filled from this wave. Check the 2023 wave for that battery.

Citation: Latinobarómetro 2024, Corporación Latinobarómetro, Santiago de
Chile — www.latinobarometro.org (free registration download).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pyreadstat

SAV = Path.home() / "Downloads" / "Latinobarometro" / "Latinobarometro_2024_Spss_eng_v20250817.sav"

# IDENPA is ISO 3166-1 numeric
ISO_NUM_TO_A3 = {
    32: "ARG", 68: "BOL", 76: "BRA", 152: "CHL", 170: "COL", 188: "CRI",
    214: "DOM", 218: "ECU", 222: "SLV", 320: "GTM", 340: "HND", 484: "MEX",
    591: "PAN", 600: "PRY", 604: "PER", 858: "URY", 862: "VEN",
}

PLATFORMS = {
    "S14M.1": "facebook", "S14M.2": "snapchat", "S14M.3": "youtube",
    "S14M.4": "x", "S14M.5": "whatsapp", "S14M.6": "instagram",
    "S14M.7": "tiktok", "S14M.8": "linkedin", "S14M.10": "none",
}
NONRESPONSE = "S14M.11"


def main() -> int:
    if not SAV.exists():
        print(f"Missing {SAV} — download it first (see docstring).", file=sys.stderr)
        return 1

    cols = ["IDENPA", "WT"] + list(PLATFORMS) + [NONRESPONSE]
    df, meta = pyreadstat.read_sav(str(SAV), usecols=cols)

    out: dict[str, dict] = {}
    for num, grp in df.groupby("IDENPA"):
        iso3 = ISO_NUM_TO_A3.get(int(num))
        if not iso3:
            print(f"# WARNING: unmapped IDENPA {num} — skipped", file=sys.stderr)
            continue
        base = grp[grp[NONRESPONSE] != 1.0]
        wt_total = base["WT"].sum()
        if wt_total <= 0 or len(base) < 500:
            continue
        rec = {"n": int(len(base))}
        for var, name in PLATFORMS.items():
            hit = base[base[var] == 1.0]["WT"].sum()
            rec[name] = round(100.0 * hit / wt_total, 1)
        out[iso3] = rec

    dump = SAV.parent / "latinobarometro2024_platform_use.json"
    dump.write_text(json.dumps(out, indent=1, sort_keys=True), encoding="utf-8")
    print(f"# Wrote {dump} ({len(out)} countries).")
    print("# Paste-ready PLATFORM_USE entries:\n")
    for iso3 in sorted(out):
        r = out[iso3]
        print(
            f'    "{iso3}": {{"whatsapp": {r["whatsapp"]}, "facebook": {r["facebook"]}, '
            f'"instagram": {r["instagram"]}, "tiktok": {r["tiktok"]}, "youtube": {r["youtube"]},\n'
            f'            "x": {r["x"]}, "snapchat": {r["snapchat"]}, "linkedin": {r["linkedin"]}, '
            f'"none": {r["none"]}, "n": {r["n"]}}},'
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
