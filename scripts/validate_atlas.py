#!/usr/bin/env python3
"""
validate_atlas.py — comprehensive per-country data validation.

Run after any data change: `python3 scripts/validate_atlas.py`
Exit code 1 if any ERROR-level finding exists (warnings don't fail).

What it checks, per Shakti's 2026-07-22 acceptance criteria:
  1. FABRICATION GUARD — every news-consumption source label must match a
     whitelist of integrations that are actually backed by a real file,
     API, or published table, AND the country must be one that survey
     actually visited (SURVEY_COVERAGE below). An unlisted label is exactly
     how the June-2026 fabricated entries slipped through; a real label
     borrowed for a country the survey never fielded in is the same trick
     wearing a better disguise. Both are hard failures forever.
     Press-freedom numbers are additionally compared value-by-value with
     the fetched RSF index file, so they cannot be typed by hand at all.
  2. RANGE CHECKS — every percentage in [0, 100]; age cohorts sum to ~100;
     plausibility windows on median age, life expectancy, literacy,
     population, area, GDP per person, and the press/internet/political
     freedom scores.
  3. CROSS-FIELD CONSISTENCY — online news use far above internet
     penetration must carry a survey note explaining the sample skew;
     freedom statuses must match their scores' banding.
  4. CITATION PRESENCE — a published number with no matching entry in that
     country's sources{} block is an ERROR, not a warning.
  5. FILE INTEGRITY — no repeated keys in any data file (JSON silently
     keeps the last copy of a duplicated key), and countries.json holds
     exactly the country set that static_countries.json lists, so a country
     cannot quietly disappear from the site.
  6. COMPANION FILES — platform_web_shares.json shares sane and top
     platform consistent; ad_market.json figures within plausible bounds,
     each pointing at a source named in that file's own _meta.sources
     (growth-rate oddities are warnings, everything else is an error).

Output: human-readable report grouped ERROR / WARN / INFO, plus a
missing-data inventory (what is honestly absent, per field).
"""

from __future__ import annotations

import json
import re
import sys
from datetime import datetime
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

# --- 1b. Which countries each survey actually covers -------------------------
# A correct-looking label is not proof of anything: "Afrobarometer Round 9"
# attached to Iceland would sail past the whitelist above while being pure
# invention, because Afrobarometer has never worked outside Africa. Each roster
# below is therefore copied from the script that reads that survey's own
# microdata — never from memory — so it cannot describe a wave that does not
# exist. When a new wave lands, update the roster from the new script in the
# same commit as the new label.
#
# Afrobarometer Round 9 — the 39 keys of AFRO_RADIO_2023 in refresh_data.py.
# Every one was computed from the Round 9 file itself, so the list is the
# round's real country roster (the Atlas publishes news figures for 35 of
# them; the other four are covered by Reuters DNR instead).
AFROBAROMETER_R9 = frozenset("""
AGO BEN BFA BWA CIV CMR COG CPV ETH GAB GHA GIN GMB KEN LBR LSO MAR MDG MLI MOZ
MRT MUS MWI NAM NER NGA SDN SEN SLE STP SWZ SYC TGO TUN TZA UGA ZAF ZMB ZWE
""".split())

# Arab Barometer — COUNTRY_TO_A3 in compute_arabbarometer_w7.py / _w8.py, i.e.
# the country codes each wave's .sav file actually contains.
ARAB_BAROMETER_W7 = frozenset(
    "DZA EGY IRQ JOR KWT LBN LBY MAR MRT PSE SDN TUN".split())
ARAB_BAROMETER_W8 = frozenset(
    "IRQ JOR KWT LBN MAR MRT PSE TUN".split())

# Eurobarometer 102.2 — ISO2_TO_A3 in compute_eurobarometer.py, plus the four
# national samples that script deliberately skips because newer Reuters DNR
# figures already cover them (DE, GB, TR, RS). They belong in the roster: the
# survey did visit them, we just prefer the newer source. Cyprus-TCC and
# Kosovo are in the file too but are not UN member states, so no ISO here.
EUROBAROMETER_102_2 = frozenset("""
ALB AUT BEL BGR BIH CYP CZE DEU DNK ESP EST FIN FRA GBR GEO GRC HRV HUN IRL ITA
LTU LUX LVA MDA MKD MLT MNE NLD POL PRT ROU SRB SVK SVN SWE TUR
""".split())

# Asian Barometer Wave 6 — the SOURCES table in compute_asianbarometer.py.
# Wave 6 fieldwork covers more of Asia, but only these countries' files are
# published individually so far; add an ISO here only when its file is
# downloaded and wired into that script.
ASIAN_BAROMETER_W6 = frozenset("KHM MNG VNM".split())

# Latinobarometro 2024 — ISO_NUM_TO_A3 in compute_latinobarometro.py.
LATINOBAROMETRO_2024 = frozenset("""
ARG BOL BRA CHL COL CRI DOM ECU GTM HND MEX PAN PER PRY SLV URY VEN
""".split())

# Label prefix -> roster. Reuters DNR and the World Values Survey are absent on
# purpose: DNR's market list is re-chosen every edition and the WVS script
# reads its countries out of the .sav at run time, so neither has a fixed
# roster this file could copy without guessing — and guessing one would be the
# very thing this check exists to prevent. Those two labels are checked by name
# only, so a wrong country under them is still possible; if a published roster
# for either becomes available, add it here.
SURVEY_COVERAGE = [
    (r"^Afrobarometer Round 9 ", AFROBAROMETER_R9),
    # the trailing space keeps "Wave VIII" from matching the "Wave VII" pattern
    (r"^Arab Barometer Wave VIII ", ARAB_BAROMETER_W8),
    (r"^Arab Barometer Wave VII ", ARAB_BAROMETER_W7),
    (r"^Eurobarometer 102\.2 ", EUROBAROMETER_102_2),
    (r"^Asian Barometer Wave 6 ", ASIAN_BAROMETER_W6),
    (r"^Latinobarometro 2024", LATINOBAROMETRO_2024),
]

# --- 1c. Which sources{} entry has to back each published number --------------
# (path inside the country record) -> key expected in that country's sources{}.
# A number the site prints with nothing in sources{} is untraceable, which is
# how invented figures survive review.
FIELD_CITATIONS = [
    (("population",), "population"),
    (("gdp_per_capita_usd",), "gdp_per_capita_usd"),
    (("area_km2",), "area_km2"),
    (("demographics", "median_age"), "median_age"),
    (("demographics", "age_0_14_pct"), "age_0_14_pct"),
    (("demographics", "age_15_64_pct"), "age_15_64_pct"),
    (("demographics", "age_65_plus_pct"), "age_65_plus_pct"),
    (("demographics", "urban_pct"), "urban_pct"),
    (("demographics", "literacy_pct"), "literacy_pct"),
    (("demographics", "life_expectancy"), "life_expectancy"),
    (("demographics", "electricity_pct"), "electricity_pct"),
    (("demographics", "edu_spending_gdp_pct"), "edu_spending_gdp_pct"),
    (("connectivity", "internet_pct"), "internet_pct"),
    (("connectivity", "mobile_per_100"), "mobile_per_100"),
    (("connectivity", "fixed_broadband_per_100"), "fixed_broadband_per_100"),
    (("connectivity", "smartphone_pct"), "smartphone_pct"),
    (("connectivity", "mobile_connectivity_index"), "mobile_connectivity_index"),
    (("connectivity", "financial_account_pct"), "financial_account_pct"),
    (("information_freedom", "press_freedom_rank"), "press_freedom_rank"),
    (("information_freedom", "press_freedom_score"), "press_freedom_rank"),
    (("information_freedom", "internet_freedom_score"), "internet_freedom"),
    (("information_freedom", "political_freedom_score"), "political_freedom"),
    (("information_freedom", "political_rights_score"), "political_freedom"),
    (("information_freedom", "civil_liberties_score"), "political_freedom"),
]
# population_year is not in the list: it is a label on the population figure,
# covered by the population citation, not a separate published number.

# Known gap, not an exemption anyone may widen. These ten countries carry a
# literacy rate that refresh_data.py copied forward from an older snapshot
# (the World Bank has published nothing newer) whose citation had already been
# lost, so the number is real but its sources{} entry is missing. They are
# listed here so that EVERY OTHER uncited literacy rate still fails, and are
# reported in the inventory at the bottom of the run. Delete an ISO the moment
# its citation is restored; never add one.
LITERACY_CITATION_GAP = frozenset(
    "BRB GRD HUN ISR LBY POL SVN TTO VCT YEM".split())


def pct_ok(v, lo=0.0, hi=100.0):
    return v is None or (isinstance(v, (int, float)) and lo <= v <= hi)


def survey_covers(label: str, iso: str) -> bool:
    """False only when we know the named survey never went to that country."""
    for pattern, roster in SURVEY_COVERAGE:
        if re.match(pattern, label):
            return iso in roster
    return True  # no roster on file for this source — label check stands alone


def field_value(rec: dict, path: tuple[str, ...]):
    """Follow a path like ("demographics", "urban_pct"); None if any step is."""
    cur = rec
    for key in path:
        if not isinstance(cur, dict):
            return None
        cur = cur.get(key)
    return cur


def is_number(v) -> bool:
    """True for a real published number. Booleans are ints in Python, and
    electoral_democracy is a bool, so they are excluded explicitly."""
    return isinstance(v, (int, float)) and not isinstance(v, bool)


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


def load_json(path: Path) -> dict:
    """Read a JSON file and ERROR on any repeated key, at any nesting level.

    Same hazard as the Python dict-literal one above, different file format:
    json.loads keeps only the LAST of two identical keys and says nothing. If a
    hand edit or a merge-conflict resolution leaves a country in the file
    twice, one of the two records — possibly the corrected one — becomes
    invisible to this validator, to the site, and to anyone reviewing the diff.
    """
    def flag_duplicates(pairs):
        seen: set[str] = set()
        for k, _ in pairs:
            if k in seen:
                ERRORS.append(
                    f"{path.name}: duplicate key {k!r} — the later copy silently "
                    f"replaces the earlier one, so one of the two records is "
                    f"invisible; keep exactly one")
            seen.add(k)
        return dict(pairs)

    return json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=flag_duplicates)


def check_country_roster(countries: dict, meta: dict) -> None:
    """countries.json must hold exactly the countries static_countries.json lists.

    A refresh bug or a bad merge can drop a block of countries from the
    generated file. Nothing else notices: the site simply stops showing them,
    and the coverage counts below would happily report "126 of 195" against a
    file that no longer has 195 countries in it.
    """
    static_path = ROOT / "data" / "static_countries.json"
    if not static_path.exists():
        ERRORS.append("data/static_countries.json is missing — the country roster "
                      "cannot be checked, so a lost country would go unnoticed")
        return
    static = load_json(static_path)
    expected = {k for k in static if not k.startswith("_")}
    lost = sorted(expected - set(countries))
    extra = sorted(set(countries) - expected)
    if lost:
        ERRORS.append(f"countries.json is missing {len(lost)} country/countries that "
                      f"static_countries.json defines: {' '.join(lost)}")
    if extra:
        ERRORS.append(f"countries.json has {len(extra)} country/countries that "
                      f"static_countries.json does not define: {' '.join(extra)}")
    declared = meta.get("country_count")
    if declared is not None and declared != len(countries):
        ERRORS.append(f"_meta.country_count says {declared} but the file holds "
                      f"{len(countries)} countries")


def main() -> int:
    check_duplicate_dict_keys()
    d = load_json(ROOT / "data" / "countries.json")
    countries = {k: v for k, v in d.items() if not k.startswith("_")}
    check_country_roster(countries, d.get("_meta") or {})

    # Press-freedom figures are fetched, never typed, so the fetched file is
    # the truth they must agree with.
    rsf_path = ROOT / "data" / "sources" / "rsf" / "rsf_index.json"
    rsf_index = (load_json(rsf_path).get("countries") or {}) if rsf_path.exists() else None
    if rsf_index is None:
        WARNS.append("data/sources/rsf/rsf_index.json missing — press-freedom values "
                     "can only be range-checked, not compared with their source")

    n_with_news = 0
    uncited_literacy: list[str] = []
    for iso, c in sorted(countries.items()):
        name = c.get("name", iso)
        nc = c.get("news_consumption") or {}
        dem = c.get("demographics") or {}
        conn = c.get("connectivity") or {}
        inf = c.get("information_freedom") or {}
        sources = c.get("sources") or {}

        # A record with no sources{} block at all would otherwise skip most of
        # the citation checks below — the worst corruption passing as the
        # cleanest record.
        if "sources" not in c:
            ERRORS.append(f"{iso} {name}: no sources{{}} block at all — every published "
                          f"figure has to name where it came from")

        # --- fabrication guard ---
        src = nc.get("source")
        if src:
            n_with_news += 1
            if not any(re.match(p, src) for p in NEWS_SOURCE_WHITELIST):
                ERRORS.append(f"{iso} {name}: news source label not in whitelist: {src!r}")
            elif not survey_covers(src, iso):
                ERRORS.append(f"{iso} {name}: {src!r} never surveyed {iso} — that survey's "
                              f"country roster has no {iso} in it, so these figures have no "
                              f"microdata behind them")
            if not sources.get("news_consumption"):
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
            elif not survey_covers(rsrc, iso):
                ERRORS.append(f"{iso} {name}: radio figure cites {rsrc!r}, but that survey's "
                              f"country roster has no {iso} in it")
            if not sources.get("news_radio"):
                ERRORS.append(f"{iso} {name}: radio value present but no citation in sources{{}}")

        # --- platform_use fabrication guard ---
        pu = c.get("platform_use")
        if pu:
            psrc = pu.get("source")
            if not psrc or not any(re.match(p, psrc) for p in PLATFORM_USE_SOURCE_WHITELIST):
                ERRORS.append(f"{iso} {name}: platform_use source not in whitelist: {psrc!r}")
            elif not survey_covers(psrc, iso):
                ERRORS.append(f"{iso} {name}: platform_use cites {psrc!r}, but that survey's "
                              f"country roster has no {iso} in it")
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

        # Headline profile numbers. The windows are deliberately wide — they
        # are here to catch a dropped minus sign, a units change at the World
        # Bank, or a figure that slid 1000x, not to second-guess real data.
        # For scale: the smallest UN member has ~9,500 people, the largest
        # ~1.46bn; Nauru is 20 km2 and Russia 17.1m; GDP per person runs from
        # about $230 (Burundi) to about $288,000 (Monaco).
        for label, v, lo, hi in [
            ("population", c.get("population"), 500, 2_000_000_000),
            ("area_km2", c.get("area_km2"), 1, 20_000_000),
            ("gdp_per_capita_usd", c.get("gdp_per_capita_usd"), 50, 400_000),
            ("population_year", c.get("population_year"), 2015, datetime.now().year + 1),
        ]:
            if v is not None and not (is_number(v) and lo <= v <= hi):
                ERRORS.append(f"{iso} {name}: {label}={v} is outside the possible range "
                              f"[{lo}, {hi}]")

        # Freedom scores. These are hand-updated once a year from the Freedom
        # House and RSF releases, and the analyst treats a low press-freedom
        # score as a restricted market, so a typo here quietly changes the
        # advice the site gives. Freedom House political-rights points can be
        # slightly negative (its discretionary question subtracts up to 4).
        for label, v, lo, hi in [
            ("internet_freedom_score", inf.get("internet_freedom_score"), 0, 100),
            ("press_freedom_score", inf.get("press_freedom_score"), 0, 100),
            ("political_freedom_score", inf.get("political_freedom_score"), -4, 100),
            ("political_rights_score", inf.get("political_rights_score"), -4, 40),
            ("civil_liberties_score", inf.get("civil_liberties_score"), 0, 60),
        ]:
            if v is not None and not (is_number(v) and lo <= v <= hi):
                ERRORS.append(f"{iso} {name}: {label}={v} is outside its published scale "
                              f"[{lo}, {hi}]")

        # Press freedom must equal the fetched RSF index, entry for entry: the
        # figures are read out of RSF's own CSV by scripts/fetch_rsf.py, so any
        # difference means someone edited the published copy by hand.
        rank, pscore = inf.get("press_freedom_rank"), inf.get("press_freedom_score")
        if rsf_index is not None and (rank is not None or pscore is not None):
            rsf_rec = rsf_index.get(iso)
            if rsf_rec is None:
                ERRORS.append(f"{iso} {name}: has press-freedom figures but the fetched RSF "
                              f"index has no entry for {iso}")
            else:
                if rank != rsf_rec.get("rank"):
                    ERRORS.append(f"{iso} {name}: press_freedom_rank {rank} does not match the "
                                  f"fetched RSF index ({rsf_rec.get('rank')})")
                if pscore != rsf_rec.get("score"):
                    ERRORS.append(f"{iso} {name}: press_freedom_score {pscore} does not match the "
                                  f"fetched RSF index ({rsf_rec.get('score')})")
        if rank is not None and rsf_index is not None and not (1 <= rank <= len(rsf_index)):
            ERRORS.append(f"{iso} {name}: press_freedom_rank {rank} but the RSF index only "
                          f"ranks {len(rsf_index)} countries")
        # The country profile prints its press-freedom figures from media{},
        # while the analyst reads information_freedom{} — they must agree.
        med = c.get("media") or {}
        for f in ("press_freedom_rank", "press_freedom_score"):
            if f in med and med.get(f) != inf.get(f):
                ERRORS.append(f"{iso} {name}: media.{f}={med.get(f)} but "
                              f"information_freedom.{f}={inf.get(f)} — the profile and the "
                              f"analyst would show different numbers")

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

        # --- citation presence for every published number ---
        for path, key in FIELD_CITATIONS:
            v = field_value(c, path)
            if not is_number(v) or sources.get(key):
                continue
            if path[-1] == "literacy_pct" and iso in LITERACY_CITATION_GAP:
                uncited_literacy.append(iso)
                continue
            ERRORS.append(f"{iso} {name}: {'.'.join(path)}={v} is published with no entry in "
                          f"sources{{}} (expected sources[{key!r}]) — an uncitable number "
                          f"cannot be told apart from an invented one")
        if (c.get("media") or {}).get("landscape_note") and not sources.get("media_landscape"):
            WARNS.append(f"{iso} {name}: landscape_note without citation")

    # --- companion files ---
    pws_path = ROOT / "data" / "platform_web_shares.json"
    if pws_path.exists():
        pws = load_json(pws_path)
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

    # Extended TV-station lists (Wikipedia lists gated through Wikidata) — an
    # optional layer, so absence is a warning; a malformed entry is an error.
    tv_path = ROOT / "data" / "tv_stations.json"
    if tv_path.exists():
        tv = load_json(tv_path)
        tv_countries = {k: v for k, v in tv.items() if not k.startswith("_")}
        n_stations = 0
        for iso, rec in sorted(tv_countries.items()):
            if iso not in countries:
                ERRORS.append(f"tv_stations {iso}: not a country the Atlas carries")
                continue
            stations = rec.get("stations") or []
            if not stations:
                ERRORS.append(f"tv_stations {iso}: entry with no stations — an empty "
                              f"entry should simply be absent")
            if not re.search(r"https?://", str(rec.get("source") or "")):
                ERRORS.append(f"tv_stations {iso}: source line carries no URL — the "
                              f"per-country citation must link the page it came from")
            if "retrieved" not in str(rec.get("source") or ""):
                ERRORS.append(f"tv_stations {iso}: source line names no retrieval date")
            for s in stations:
                n_stations += 1
                if not (s.get("name") or "").strip():
                    ERRORS.append(f"tv_stations {iso}: station with an empty name")
                if "—" in str(s.get("name", "")) or "–" in str(s.get("name", "")):
                    ERRORS.append(f"tv_stations {iso}: em/en dash in station name "
                                  f"{s.get('name')!r} — the database carries none by rule")
        INFOS.append(f"extended TV-station coverage: {len(tv_countries)}/{len(countries)} "
                     f"countries, {n_stations} stations")
    else:
        WARNS.append("tv_stations.json missing — extended TV-station layer not built yet")

    # Per-country most-read Wikipedia pages (Wikimedia top-per-country, daily)
    # — an optional trend layer, so absence is a warning; a malformed entry is
    # an error. Withheld entries are legitimate (Wikimedia's privacy list /
    # volume threshold) and are counted, not flagged.
    cr_path = ROOT / "data" / "trends" / "country_reading.json"
    if cr_path.exists():
        cr = load_json(cr_path)
        n_read = n_withheld = 0
        for iso, rec in sorted((cr.get("countries") or {}).items()):
            if iso not in countries:
                ERRORS.append(f"country_reading {iso}: not a country the Atlas carries")
                continue
            if rec.get("withheld"):
                n_withheld += 1
                if not str(rec.get("note") or "").strip():
                    ERRORS.append(f"country_reading {iso}: withheld entry with no note — "
                                  f"the site must be able to say why nothing is shown")
                continue
            n_read += 1
            arts = rec.get("articles") or []
            if not arts:
                ERRORS.append(f"country_reading {iso}: entry with no articles — an empty "
                              f"entry should be withheld or absent")
            if not re.search(r"https?://", str(rec.get("source") or "")):
                ERRORS.append(f"country_reading {iso}: source line carries no URL — the "
                              f"per-country citation must link the endpoint it came from")
            if "retrieved" not in str(rec.get("source") or ""):
                ERRORS.append(f"country_reading {iso}: source line names no retrieval date")
            if not re.match(r"^\d{4}-\d{2}-\d{2}$", str(rec.get("date") or "")):
                ERRORS.append(f"country_reading {iso}: missing or malformed date "
                              f"{rec.get('date')!r}")
            for a in arts:
                if not str(a.get("title") or "").strip():
                    ERRORS.append(f"country_reading {iso}: article with an empty title")
                v = a.get("views_ceil")
                if not (isinstance(v, int) and v > 0):
                    ERRORS.append(f"country_reading {iso}: views_ceil {v!r} for "
                                  f"{a.get('title')!r} is not a positive integer")
            mix = rec.get("language_mix") or {}
            mix_total = sum(v for v in mix.values() if isinstance(v, (int, float)))
            # 102, not 100.5: shares are independently rounded integers, so a
            # legitimate mix can sum to 101-102 (same margin as the
            # platform_web_shares check above).
            if mix_total > 102:
                ERRORS.append(f"country_reading {iso}: language mix sums "
                              f"{round(mix_total, 1)} > 102 — beyond rounding error")
        INFOS.append(f"per-country reading lists: {n_read}/{len(countries)} countries "
                     f"with data, {n_withheld} withheld by Wikimedia (privacy/threshold)")
    else:
        WARNS.append("trends/country_reading.json missing — per-country reading layer "
                     "not built yet")

    # Per-country trending searches (Google Trends "Trending Now" RSS, daily)
    # — an optional trend layer, so absence is a warning; a malformed entry is
    # an error. Unsupported entries are legitimate (Google publishes no feed
    # for ~74 countries) and are counted, not flagged. Traffic buckets are
    # floors ("500+") stored verbatim plus a parsed integer floor; the check
    # accepts any non-negative floor rather than re-parsing the bucket.
    cs_path = ROOT / "data" / "trends" / "country_searches.json"
    if cs_path.exists():
        cs = load_json(cs_path)
        n_search = n_unsupported = 0
        for iso, rec in sorted((cs.get("countries") or {}).items()):
            if iso not in countries:
                ERRORS.append(f"country_searches {iso}: not a country the Atlas carries")
                continue
            if rec.get("unsupported"):
                n_unsupported += 1
                if not str(rec.get("note") or "").strip():
                    ERRORS.append(f"country_searches {iso}: unsupported entry with no "
                                  f"note — the site must be able to say why nothing is shown")
                if not re.match(r"^\d{4}-\d{2}-\d{2}$", str(rec.get("checked") or "")):
                    ERRORS.append(f"country_searches {iso}: unsupported entry with no "
                                  f"checked date — the weekly re-probe depends on it")
                continue
            n_search += 1
            qs = rec.get("queries") or []
            if not qs:
                ERRORS.append(f"country_searches {iso}: entry with no queries — an "
                              f"empty entry should be unsupported or absent")
            if not re.search(r"https?://", str(rec.get("source") or "")):
                ERRORS.append(f"country_searches {iso}: source line carries no URL — the "
                              f"per-country citation must link the feed it came from")
            if "retrieved" not in str(rec.get("source") or ""):
                ERRORS.append(f"country_searches {iso}: source line names no retrieval date")
            if not re.match(r"^\d{4}-\d{2}-\d{2}$", str(rec.get("date") or "")):
                ERRORS.append(f"country_searches {iso}: missing or malformed date "
                              f"{rec.get('date')!r}")
            for q in qs:
                if not str(q.get("query") or "").strip():
                    ERRORS.append(f"country_searches {iso}: query with empty text")
                rank = q.get("rank")
                if not (isinstance(rank, int) and rank > 0):
                    ERRORS.append(f"country_searches {iso}: rank {rank!r} for "
                                  f"{q.get('query')!r} is not a positive integer")
                tm = q.get("traffic_min")
                if tm is not None and not (isinstance(tm, int) and tm >= 0):
                    ERRORS.append(f"country_searches {iso}: traffic_min {tm!r} for "
                                  f"{q.get('query')!r} is not a non-negative integer")
            hist = rec.get("history") or {}
            for hday, hqueries in hist.items():
                if not re.match(r"^\d{4}-\d{2}-\d{2}$", str(hday)):
                    ERRORS.append(f"country_searches {iso}: history key {hday!r} is "
                                  f"not a date")
                if not (isinstance(hqueries, list) and hqueries
                        and all(str(x).strip() for x in hqueries)):
                    ERRORS.append(f"country_searches {iso}: history for {hday} is not "
                                  f"a non-empty list of queries")
        INFOS.append(f"trending searches: {n_search}/{len(countries)} countries with "
                     f"data, {n_unsupported} not covered by Google Trends")
    else:
        WARNS.append("trends/country_searches.json missing — trending-searches layer "
                     "not built yet")

    # Global Bluesky trending topics (open-social pulse) — optional layer.
    # GLOBAL only by design: there is deliberately no per-country structure
    # here, and none may ever be invented for it. Aggregates only: a "posts"
    # or "handles" field appearing would mean the fetcher started storing
    # content, which the license posture forbids — hard error.
    bt_path = ROOT / "data" / "trends" / "bluesky_trends.json"
    if bt_path.exists():
        bt = load_json(bt_path)
        bts = bt.get("trends") or []
        if not re.match(r"^\d{4}-\d{2}-\d{2}$", str(bt.get("date") or "")):
            ERRORS.append("bluesky_trends: missing or malformed date")
        if not bts:
            ERRORS.append("bluesky_trends: no trends — an empty file should not "
                          "be published")
        for t in bts:
            if not str(t.get("display_name") or "").strip():
                ERRORS.append("bluesky_trends: trend with empty display_name")
            rank = t.get("rank")
            if not (isinstance(rank, int) and rank > 0):
                ERRORS.append(f"bluesky_trends: rank {rank!r} for "
                              f"{t.get('display_name')!r} is not a positive integer")
            pc = t.get("post_count")
            if not (isinstance(pc, int) and pc >= 0):
                ERRORS.append(f"bluesky_trends: post_count {pc!r} for "
                              f"{t.get('display_name')!r} is not a non-negative integer")
            for forbidden in ("posts", "handles", "authors", "text"):
                if forbidden in t:
                    ERRORS.append(f"bluesky_trends: {t.get('display_name')!r} carries "
                                  f"{forbidden!r} — aggregates only, never content")
        for hday, names in (bt.get("history") or {}).items():
            if not re.match(r"^\d{4}-\d{2}-\d{2}$", str(hday)):
                ERRORS.append(f"bluesky_trends: history key {hday!r} is not a date")
            if not (isinstance(names, list) and names
                    and all(str(x).strip() for x in names)):
                ERRORS.append(f"bluesky_trends: history for {hday} is not a "
                              f"non-empty list of names")
        INFOS.append(f"Bluesky pulse: {len(bts)} global trends, dated {bt.get('date')}")
    else:
        WARNS.append("trends/bluesky_trends.json missing — open-social pulse "
                     "not built yet")

    # UN-in-the-national-press shares (Media Cloud) — optional layer. The
    # honesty floor is machine-enforced here: a share may exist ONLY when the
    # window's total volume clears _meta.min_stories, and a withheld entry
    # must carry its explanation. Counts only — story text/titles/URLs in
    # this file would violate the license posture and are hard errors.
    pu_path = ROOT / "data" / "trends" / "press_un_coverage.json"
    if pu_path.exists():
        pu = load_json(pu_path)
        pu_floor = ((pu.get("_meta") or {}).get("min_stories")) or 100
        n_share = n_lowvol = 0
        for iso, rec in sorted((pu.get("countries") or {}).items()):
            if iso not in countries:
                ERRORS.append(f"press_un {iso}: not a country the Atlas carries")
                continue
            for forbidden in ("stories", "titles", "urls", "text", "headlines"):
                if forbidden in rec:
                    ERRORS.append(f"press_un {iso}: carries {forbidden!r} — counts "
                                  f"only, never story content")
            w = rec.get("window") or {}
            if not (re.match(r"^\d{4}-\d{2}-\d{2}$", str(w.get("start") or ""))
                    and re.match(r"^\d{4}-\d{2}-\d{2}$", str(w.get("end") or ""))):
                ERRORS.append(f"press_un {iso}: missing or malformed window")
            tot, un = rec.get("stories_total"), rec.get("stories_un")
            if not (isinstance(tot, int) and tot >= 0 and isinstance(un, int)
                    and 0 <= un <= tot):
                ERRORS.append(f"press_un {iso}: story counts malformed "
                              f"(total {tot!r}, un {un!r})")
            share = rec.get("share_pct")
            if share is not None:
                n_share += 1
                if rec.get("share_withheld"):
                    ERRORS.append(f"press_un {iso}: both share_pct and "
                                  f"share_withheld set — pick one")
                if not (is_number(share) and 0 <= share <= 100):
                    ERRORS.append(f"press_un {iso}: share_pct {share!r} out of range")
                if isinstance(tot, int) and tot < pu_floor:
                    ERRORS.append(f"press_un {iso}: share quoted from only {tot} "
                                  f"stories — below the {pu_floor}-story floor")
            elif rec.get("share_withheld"):
                n_lowvol += 1
                if not str(rec.get("low_volume_note") or "").strip():
                    ERRORS.append(f"press_un {iso}: withheld share with no note — "
                                  f"the site must be able to say why")
            else:
                ERRORS.append(f"press_un {iso}: neither share_pct nor "
                              f"share_withheld — entry is unusable")
            if not re.search(r"https?://", str(rec.get("source") or "")):
                ERRORS.append(f"press_un {iso}: source line carries no URL")
            if "retrieved" not in str(rec.get("source") or ""):
                ERRORS.append(f"press_un {iso}: source line names no retrieval date")
            if not isinstance((rec.get("collection") or {}).get("id"), int):
                ERRORS.append(f"press_un {iso}: collection id missing — the "
                              f"citation must name which outlet list measured this")
        INFOS.append(f"national-press UN share: {n_share}/{len(countries)} countries "
                     f"with a share, {n_lowvol} withheld (low volume)")
    else:
        WARNS.append("trends/press_un_coverage.json missing — national-press "
                     "layer not built yet")

    # OONI measured censorship — optional layer. The honesty invariants are
    # machine-enforced: counts must reconcile, a zero-measurement country
    # must carry the no_measurements flag AND its unknown-not-open note, and
    # no derived rate/percentage field may ever appear (counts only).
    oo_path = ROOT / "data" / "trends" / "ooni_censorship.json"
    if oo_path.exists():
        oo = load_json(oo_path)
        n_meas = n_conf = n_unk = 0
        for iso, rec in sorted((oo.get("countries") or {}).items()):
            if iso not in countries:
                ERRORS.append(f"ooni {iso}: not a country the Atlas carries")
                continue
            for forbidden in ("rate", "pct", "share", "percentage", "blocking_rate"):
                for k in rec:
                    if forbidden in k.lower():
                        ERRORS.append(f"ooni {iso}: derived field {k!r} — counts only, "
                                      f"a rate from thin volunteer data would be invented")
            w = rec.get("window") or {}
            if not (re.match(r"^\d{4}-\d{2}-\d{2}$", str(w.get("start") or ""))
                    and re.match(r"^\d{4}-\d{2}-\d{2}$", str(w.get("end") or ""))):
                ERRORS.append(f"ooni {iso}: missing or malformed window")
            m_, c_, a_ = rec.get("measurements"), rec.get("confirmed"), rec.get("anomalies")
            if not all(isinstance(x, int) and x >= 0 for x in (m_, c_, a_)):
                ERRORS.append(f"ooni {iso}: counts malformed ({m_!r}/{c_!r}/{a_!r})")
            elif c_ + (a_ or 0) > m_:
                ERRORS.append(f"ooni {iso}: confirmed+anomalies exceed measurements")
            if m_ == 0:
                n_unk += 1
                if not rec.get("no_measurements") or not str(rec.get("note") or "").strip():
                    ERRORS.append(f"ooni {iso}: zero measurements without the "
                                  f"no_measurements flag and its unknown-status note")
            else:
                n_meas += 1
                if c_ and c_ > 0:
                    n_conf += 1
            if not re.search(r"https?://", str(rec.get("source") or "")):
                ERRORS.append(f"ooni {iso}: source line carries no URL")
            if "retrieved" not in str(rec.get("source") or ""):
                ERRORS.append(f"ooni {iso}: source line names no retrieval date")
        INFOS.append(f"OONI censorship: {n_meas}/{len(countries)} countries with "
                     f"measurements, {n_conf} with confirmed blocking, {n_unk} unknown "
                     f"(no volunteer coverage)")
    else:
        WARNS.append("trends/ooni_censorship.json missing — censorship-evidence "
                     "layer not built yet")

    am_path = ROOT / "data" / "ad_market.json"
    if am_path.exists():
        am = load_json(am_path)
        # These figures are hand-copied out of the WPP Media and Dentsu
        # year-end PDFs each December by someone who is not a coder, and the
        # analyst quotes them straight into briefs. The checks below catch the
        # realistic mistake — a number typed with an extra digit, or pointing
        # at a source label that does not exist in this file.
        known_sources = set(((am.get("_meta") or {}).get("sources") or {}))
        world = am.get("global") or {}
        world_bn = world.get("ad_revenue_2025_usd_bn")
        if world_bn is not None and not (is_number(world_bn) and 100 <= world_bn <= 5000):
            ERRORS.append(f"ad_market global: world ad revenue {world_bn} bn is outside any "
                          f"plausible total (100-5000 bn)")
            world_bn = None
        if not pct_ok(world.get("digital_share_2026_pct")):
            ERRORS.append(f"ad_market global: digital share "
                          f"{world.get('digital_share_2026_pct')} out of [0,100]")
        for f in ("growth_2025_pct", "growth_2026_forecast_pct"):
            g = world.get(f)
            if g is not None and not (-30 <= g <= 40):
                WARNS.append(f"ad_market global: implausible {f} {g}%")
        for f, key in (("revenue_source", "ad_revenue_2025_usd_bn"),
                       ("digital_share_source", "digital_share_2026_pct")):
            if world.get(key) is not None and world.get(f) not in known_sources:
                ERRORS.append(f"ad_market global: {key} cites {world.get(f)!r}, which is not one "
                              f"of the sources named in _meta.sources")

        for section in ("regions", "markets"):
            for mkt, rec in (am.get(section) or {}).items():
                if section == "markets" and mkt not in countries:
                    ERRORS.append(f"ad_market: unknown market key {mkt}")
                spend = rec.get("ad_spend_2026_usd_bn")
                if spend is not None:
                    if not is_number(spend) or spend <= 0:
                        ERRORS.append(f"ad_market {mkt}: ad spend {spend} bn is not a positive number")
                    elif world_bn is not None and spend > world_bn:
                        ERRORS.append(f"ad_market {mkt}: ad spend {spend} bn is larger than the whole "
                                      f"world's {world_bn} bn — check for a mistyped digit")
                g = rec.get("growth_2026_pct")
                if g is not None and not (-30 <= g <= 40):
                    WARNS.append(f"ad_market {mkt}: implausible growth {g}%")
                if (spend is not None or g is not None) and rec.get("source") not in known_sources:
                    ERRORS.append(f"ad_market {mkt}: cites source {rec.get('source')!r}, which is not "
                                  f"one of the sources named in _meta.sources")

    # --- missing-data inventory (honest absence, not errors) ---
    missing_news = sorted(iso for iso, c in countries.items()
                          if not (c.get("news_consumption") or {}).get("source"))
    missing_rsf = sorted(iso for iso, c in countries.items()
                         if (c.get("information_freedom") or {}).get("press_freedom_score") is None)
    missing_lit = sorted(iso for iso, c in countries.items()
                         if (c.get("demographics") or {}).get("literacy_pct") is None)
    # Counted against the countries actually in the file, never against a
    # hardcoded 195: if countries went missing, these lines have to show it
    # rather than quietly reporting coverage of a file that no longer exists.
    total = len(countries)
    INFOS.append(f"countries in file: {total}")
    INFOS.append(f"news-consumption survey coverage: {n_with_news}/{total}; missing: {' '.join(missing_news)}")
    INFOS.append(f"RSF press-freedom coverage: {total - len(missing_rsf)}/{total}; missing: {' '.join(missing_rsf)}")
    INFOS.append(f"literacy coverage: {total - len(missing_lit)}/{total} (World Bank/UIS never surveys some high-income countries)")
    if uncited_literacy:
        INFOS.append(f"literacy figures still carrying no citation ({len(uncited_literacy)}): "
                     f"{' '.join(sorted(uncited_literacy))} — known gap, see LITERACY_CITATION_GAP")

    # --- text-hygiene sweep (WARN only) -------------------------------------
    # Upstream text (chiefly the CIA Factbook media notes) occasionally arrives
    # with double spaces, curly quotes or stray HTML entities. The ingest now
    # normalises them, but a source can change shape; this makes any recurrence
    # visible without ever blocking a refresh over cosmetics.
    import unicodedata as _ud
    hygiene = 0

    def _scan(o, path):
        nonlocal hygiene
        if isinstance(o, dict):
            for k, v in o.items():
                _scan(v, f"{path}.{k}")
        elif isinstance(o, list):
            for i, v in enumerate(o):
                _scan(v, f"{path}[{i}]")
        elif isinstance(o, str):
            problems = []
            if "  " in o:
                problems.append("double space")
            if "\u00a0" in o:
                problems.append("non-breaking space")
            # N'Ko (ߒߞߏ) is a real script whose romanised name genuinely
            # carries this apostrophe — a straight quote would misspell it.
            if any(c in o for c in "\u2018\u2019\u201c\u201d") and o != "N\u2019Ko":
                problems.append("curly quote")
            if re.search(r"&[a-z]+;|&#\d+;", o):
                problems.append("HTML entity")
            if "\ufffd" in o:
                problems.append("replacement char (mojibake)")
            if o != o.strip():
                problems.append("edge whitespace")
            if problems and hygiene < 12:
                WARNS.append(f"text hygiene at {path[1:]}: {', '.join(problems)} — {o[:60]!r}")
            if problems:
                hygiene += 1

    _scan(d, "")
    if hygiene:
        INFOS.append(f"text-hygiene notes: {hygiene} field(s) with cosmetic issues (warnings above; not errors)")

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
