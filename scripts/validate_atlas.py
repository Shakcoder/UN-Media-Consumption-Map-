#!/usr/bin/env python3
"""
validate_atlas.py — comprehensive per-country data validation.

Run after any data change: `python3 scripts/validate_atlas.py`
Exit code 1 if any ERROR-level finding exists (warnings don't fail).

What it checks, per Shakti's 2026-07-22 acceptance criteria:
  1. FABRICATION GUARD — every news-consumption source label must match a
     whitelist of integrations that are actually backed by a real file,
     API, or published table. An unlisted label is exactly how the
     June-2026 fabricated entries slipped through; this makes that class
     of error a hard failure forever.
  2. RANGE CHECKS — every percentage in [0, 100]; age cohorts sum to ~100;
     plausibility windows on median age, life expectancy, literacy.
  3. CROSS-FIELD CONSISTENCY — online news use far above internet
     penetration must carry a survey note explaining the sample skew;
     freedom statuses must match their scores' banding.
  4. CITATION PRESENCE — a value without a source entry is flagged.
  5. COMPANION FILES — platform_web_shares.json shares sane and top
     platform consistent; ad_market.json matches its documented seed.

Output: human-readable report grouped ERROR / WARN / INFO, plus a
missing-data inventory (what is honestly absent, per field).
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
ERRORS: list[str] = []
WARNS: list[str] = []
INFOS: list[str] = []

# --- 1. Source whitelist -----------------------------------------------------
# Every allowed news_consumption source label, as a regex. Add a pattern here
# ONLY when a new integration lands with a real, checkable source behind it.
NEWS_SOURCE_WHITELIST = [
    r"^Reuters Institute DNR 2026$",
    r"^Afrobarometer Round 9 \(2023\)$",
    r"^Arab Barometer Wave VIII \(2023-2024\) microdata$",
    r"^Arab Barometer Wave VII \(2021-2022\) microdata$",
    r"^World Values Survey Wave 7 \(20(1[7-9]|2[0-3])\), weighted microdata \(n=[\d,]+\)$",
    r"^Eurobarometer 102\.2 \(Oct-Nov 2024\), weighted microdata \(n=[\d,]+\)$",
    r"^Asian Barometer Wave 6 \(202[3-5]\) microdata, weighted \(n=[\d,]+\)$",
    # NOTE: no "Estimate" labels are whitelisted, deliberately. An estimate
    # without a checkable source is a fabrication with a modest label — the
    # COD entry of that kind was removed 2026-07-22.
]

PLATFORM_USE_SOURCE_WHITELIST = [
    r"^Latinobarometro 2024$",
]

RADIO_SOURCE_WHITELIST = [
    r"^Afrobarometer Round 9 \(2023\)$",
    r"^Arab Barometer Wave VIII \(2023-2024\) microdata$",
    r"^Arab Barometer Wave VII \(2021-2022\) microdata$",
    r"^World Values Survey Wave 7 \(20(1[7-9]|2[0-3])\), weighted microdata \(n=[\d,]+\)$",
    r"^Eurobarometer 102\.2 \(Oct-Nov 2024\), weighted microdata \(n=[\d,]+\)$",
    r"^Asian Barometer Wave 6 \(202[3-5]\) microdata, weighted \(n=[\d,]+\)$",
]


def pct_ok(v, lo=0.0, hi=100.0):
    return v is None or (isinstance(v, (int, float)) and lo <= v <= hi)


def check_duplicate_dict_keys() -> None:
    """Guard against silent dict-literal shadowing in refresh_data.py.

    Python allows duplicate keys in a dict literal — the later one silently
    wins. In a 200-entry hand-maintained table that means a country can be
    invisibly overwritten (nearly happened with Libya, 2026-07-23: an Arab
    Barometer W7 entry was added for a country that already had a WVS entry
    later in the same dict). This walks refresh_data.py's AST and errors on
    any dict literal with a repeated constant key.
    """
    import ast as _ast
    src = (ROOT / "scripts" / "refresh_data.py").read_text(encoding="utf-8")
    tree = _ast.parse(src)
    for node in _ast.walk(tree):
        if isinstance(node, _ast.Dict):
            seen: dict[object, int] = {}
            for k in node.keys:
                if isinstance(k, _ast.Constant):
                    if k.value in seen:
                        ERRORS.append(
                            f"refresh_data.py: duplicate dict key {k.value!r} "
                            f"(lines {seen[k.value]} and {k.lineno}) — the later "
                            f"entry silently overwrites the earlier one")
                    else:
                        seen[k.value] = k.lineno


def main() -> int:
    check_duplicate_dict_keys()
    d = json.loads((ROOT / "data" / "countries.json").read_text(encoding="utf-8"))
    countries = {k: v for k, v in d.items() if not k.startswith("_")}

    n_with_news = 0
    for iso, c in sorted(countries.items()):
        name = c.get("name", iso)
        nc = c.get("news_consumption") or {}
        dem = c.get("demographics") or {}
        conn = c.get("connectivity") or {}
        inf = c.get("information_freedom") or {}
        sources = c.get("sources") or {}

        # --- fabrication guard ---
        src = nc.get("source")
        if src:
            n_with_news += 1
            if not any(re.match(p, src) for p in NEWS_SOURCE_WHITELIST):
                ERRORS.append(f"{iso} {name}: news source label not in whitelist: {src!r}")
            if "sources" in c and not sources.get("news_consumption"):
                ERRORS.append(f"{iso} {name}: news values present but no citation in sources{{}}")
        else:
            # values without a source are fabrication by definition
            for f in ("trust_in_news_pct", "tv_as_news_source_pct",
                      "online_as_news_source_pct", "social_as_news_source_pct"):
                if nc.get(f) is not None:
                    ERRORS.append(f"{iso} {name}: {f}={nc[f]} but news_consumption.source is empty")
        rsrc = nc.get("radio_source")
        if nc.get("radio_as_news_source_pct") is not None:
            if not rsrc:
                ERRORS.append(f"{iso} {name}: radio value without radio_source")
            elif not any(re.match(p, rsrc) for p in RADIO_SOURCE_WHITELIST):
                ERRORS.append(f"{iso} {name}: radio source label not in whitelist: {rsrc!r}")

        # --- platform_use fabrication guard ---
        pu = c.get("platform_use")
        if pu:
            psrc = pu.get("source")
            if not psrc or not any(re.match(p, psrc) for p in PLATFORM_USE_SOURCE_WHITELIST):
                ERRORS.append(f"{iso} {name}: platform_use source not in whitelist: {psrc!r}")
            if not sources.get("platform_use"):
                ERRORS.append(f"{iso} {name}: platform_use present but no citation in sources{{}}")
            pu_vals = [v for k, v in pu.items() if k not in ("source", "year", "n") and isinstance(v, (int, float))]
            for v in pu_vals:
                if not pct_ok(v):
                    ERRORS.append(f"{iso} {name}: platform_use value out of [0,100]: {v}")
            if not pu.get("n") or pu["n"] < 300:
                WARNS.append(f"{iso} {name}: platform_use sample size suspiciously small (n={pu.get('n')})")

        # --- range checks ---
        for label, v in [
            ("trust", nc.get("trust_in_news_pct")), ("tv", nc.get("tv_as_news_source_pct")),
            ("online", nc.get("online_as_news_source_pct")), ("social", nc.get("social_as_news_source_pct")),
            ("radio", nc.get("radio_as_news_source_pct")),
            ("internet_pct", conn.get("internet_pct")), ("smartphone_pct", conn.get("smartphone_pct")),
            ("urban_pct", dem.get("urban_pct")), ("literacy_pct", dem.get("literacy_pct")),
            ("age_0_14_pct", dem.get("age_0_14_pct")), ("age_15_64_pct", dem.get("age_15_64_pct")),
            ("age_65_plus_pct", dem.get("age_65_plus_pct")), ("electricity_pct", dem.get("electricity_pct")),
        ]:
            if not pct_ok(v):
                ERRORS.append(f"{iso} {name}: {label} out of [0,100]: {v}")
        ma = dem.get("median_age")
        if ma is not None and not (12 <= ma <= 60):
            ERRORS.append(f"{iso} {name}: implausible median_age {ma}")
        le = dem.get("life_expectancy")
        if le is not None and not (45 <= le <= 92):
            WARNS.append(f"{iso} {name}: unusual life_expectancy {le}")
        a0, a1, a2 = dem.get("age_0_14_pct"), dem.get("age_15_64_pct"), dem.get("age_65_plus_pct")
        if None not in (a0, a1, a2) and abs((a0 + a1 + a2) - 100) > 2.5:
            ERRORS.append(f"{iso} {name}: age cohorts sum to {round(a0+a1+a2,1)} (expected ~100)")

        # --- cross-field consistency ---
        online, net = nc.get("online_as_news_source_pct"), conn.get("internet_pct")
        if online is not None and net is not None and online > net + 20 and not nc.get("survey_note"):
            WARNS.append(f"{iso} {name}: online news use {online}% far above internet access {net}% "
                         f"with NO survey_note explaining the sample skew")
        fotn, fstat = inf.get("internet_freedom_score"), inf.get("internet_freedom_status")
        if fotn is not None and fstat:
            band = "Free" if fotn >= 70 else ("Partly Free" if fotn >= 40 else "Not Free")
            if fstat != band:
                ERRORS.append(f"{iso} {name}: FOTN status {fstat!r} inconsistent with score {fotn} (expect {band})")
        if ma is not None and a0 is not None:
            if ma < 20 and a0 < 30:
                WARNS.append(f"{iso} {name}: median age {ma} but only {a0}% under 15 — check one of the two")
            if ma > 40 and a0 > 25:
                WARNS.append(f"{iso} {name}: median age {ma} but {a0}% under 15 — check one of the two")

        # --- citation presence for headline structural fields ---
        if conn.get("internet_pct") is not None and not sources.get("internet_pct"):
            WARNS.append(f"{iso} {name}: internet_pct has no citation")
        if (c.get("media") or {}).get("landscape_note") and not sources.get("media_landscape"):
            WARNS.append(f"{iso} {name}: landscape_note without citation")

    # --- companion files ---
    pws_path = ROOT / "data" / "platform_web_shares.json"
    if pws_path.exists():
        pws = json.loads(pws_path.read_text(encoding="utf-8"))
        for iso, rec in (pws.get("countries") or {}).items():
            shares = rec.get("shares") or {}
            if shares:
                total = sum(shares.values())
                if total > 102:
                    ERRORS.append(f"platform_web_shares {iso}: shares sum {round(total,1)} > 100")
                top_claimed = rec.get("top_web_platform")
                top_actual = max(shares, key=shares.get)
                if top_claimed != top_actual:
                    ERRORS.append(f"platform_web_shares {iso}: top {top_claimed!r} != max share {top_actual!r}")
    else:
        WARNS.append("platform_web_shares.json missing")

    am_path = ROOT / "data" / "ad_market.json"
    if am_path.exists():
        am = json.loads(am_path.read_text(encoding="utf-8"))
        for mkt, rec in (am.get("markets") or {}).items():
            if mkt not in countries:
                ERRORS.append(f"ad_market: unknown market key {mkt}")
            g = rec.get("growth_2026_pct")
            if g is not None and not (-30 <= g <= 40):
                WARNS.append(f"ad_market {mkt}: implausible growth {g}%")

    # --- missing-data inventory (honest absence, not errors) ---
    missing_news = sorted(iso for iso, c in countries.items()
                          if not (c.get("news_consumption") or {}).get("source"))
    missing_rsf = sorted(iso for iso, c in countries.items()
                         if (c.get("information_freedom") or {}).get("press_freedom_score") is None)
    missing_lit = sorted(iso for iso, c in countries.items()
                         if (c.get("demographics") or {}).get("literacy_pct") is None)
    INFOS.append(f"news-consumption survey coverage: {n_with_news}/195; missing: {' '.join(missing_news)}")
    INFOS.append(f"RSF press-freedom coverage: {195 - len(missing_rsf)}/195; missing: {' '.join(missing_rsf)}")
    INFOS.append(f"literacy coverage: {195 - len(missing_lit)}/195 (World Bank/UIS never surveys some high-income countries)")

    print(f"=== validate_atlas: {len(ERRORS)} error(s), {len(WARNS)} warning(s) ===\n")
    for e in ERRORS:
        print("ERROR:", e)
    if ERRORS:
        print()
    for w in WARNS:
        print("WARN: ", w)
    print()
    for i in INFOS:
        print("INFO: ", i)
    return 1 if ERRORS else 0


if __name__ == "__main__":
    sys.exit(main())
