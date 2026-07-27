#!/usr/bin/env python3
"""
compute_topic_intelligence.py — nightly intelligence calculations.

Reads the raw trend signals
  data/trends/wiki_pageviews.json   (demand — what people look up)
  data/trends/gdelt_coverage.json   (supply — what media publish)
plus data/topics.json, and produces data/trends/topic_intelligence.json:

  per topic:  global velocity, momentum label, top demand languages,
              top covering countries (media), volume stats
  per country: ranked "trending now" topics with component evidence

METHOD NOTES (also embedded in the output for the AI analyst to cite):
- Velocity = (mean of last 7 days − mean of prior 30 days) / prior mean,
  computed on each language series, then combined weighted by volume.
- Wikipedia pageviews are per LANGUAGE EDITION. Country attribution uses
  the documented heuristic weights below (speaker-population based).
  This is an approximation and is always labeled as such.
- GDELT source-country shares attribute coverage to where the OUTLET is
  based — a supply signal, kept separate from demand.
- A topic is "rising" when velocity > +0.30 with adequate volume;
  "falling" below −0.25. Thresholds are deliberately conservative.
"""

from __future__ import annotations

import json
import re
import sys
from datetime import date, timedelta
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
REGISTRY_PATH = REPO_ROOT / "data" / "topics.json"
WIKI_PATH = REPO_ROOT / "data" / "trends" / "wiki_pageviews.json"
GDELT_PATH = REPO_ROOT / "data" / "trends" / "gdelt_coverage.json"
OUTPUT_PATH = REPO_ROOT / "data" / "trends" / "topic_intelligence.json"

# Two-tier volume floors: INCLUDE_FLOOR admits smaller language editions
# (Swahili, Amharic, Hausa… have low absolute traffic but represent exactly
# the countries this platform must not ignore); RISING_FLOOR is the higher
# bar a series must clear before its velocity can flag a topic as "rising"
# (prevents 10-views-to-40-views noise from generating alerts).
INCLUDE_FLOOR = 25
RISING_FLOOR = 150
RISING_THRESHOLD = 0.30
FALLING_THRESHOLD = -0.25

# ---------------------------------------------------------------------------
# HEURISTIC language-edition → country weights (speaker-population based).
# Documented approximation, v1. English is the most diluted mapping and is
# down-weighted in country attribution accordingly.
# ---------------------------------------------------------------------------
LANG_COUNTRY_WEIGHTS: dict[str, dict[str, float]] = {
    "en": {"USA": .22, "IND": .16, "GBR": .08, "NGA": .07, "PHL": .05,
           "PAK": .05, "CAN": .04, "AUS": .03, "ZAF": .03, "KEN": .03,
           "GHA": .02, "UGA": .02, "TZA": .02, "IRL": .01, "NZL": .01},
    "fr": {"FRA": .35, "COD": .12, "DZA": .08, "MAR": .07, "CAN": .06,
           "CMR": .05, "CIV": .05, "TUN": .04, "SEN": .04, "BEL": .04,
           "MLI": .03, "BFA": .03, "HTI": .02, "CHE": .02},
    "es": {"MEX": .25, "COL": .11, "ESP": .10, "ARG": .10, "PER": .07,
           "VEN": .06, "CHL": .04, "ECU": .04, "GTM": .03, "USA": .05,
           "CUB": .02, "BOL": .02, "DOM": .02, "HND": .02, "PRY": .01,
           "SLV": .01, "NIC": .01, "CRI": .01, "PAN": .01, "URY": .01},
    "ar": {"EGY": .25, "DZA": .10, "SAU": .09, "IRQ": .09, "MAR": .08,
           "SDN": .07, "YEM": .06, "SYR": .05, "TUN": .04, "JOR": .03,
           "LBY": .03, "LBN": .02, "PSE": .02, "ARE": .02, "KWT": .01,
           "OMN": .01, "QAT": .01, "BHR": .01, "MRT": .01},
    "pt": {"BRA": .79, "AGO": .08, "MOZ": .06, "PRT": .05, "GNB": .01,
           "CPV": .005, "TLS": .003, "STP": .002},
    "ru": {"RUS": .68, "UKR": .10, "KAZ": .07, "BLR": .05, "UZB": .04,
           "KGZ": .03, "MDA": .03},
    "zh": {"CHN": .95, "SGP": .03, "MYS": .02},
    "hi": {"IND": .98, "NPL": .01, "FJI": .01},
    "bn": {"BGD": .60, "IND": .40},
    "id": {"IDN": .99, "TLS": .01},
    "sw": {"TZA": .40, "KEN": .35, "UGA": .10, "COD": .10, "RWA": .02,
           "BDI": .02, "MOZ": .01},
    "ha": {"NGA": .75, "NER": .20, "GHA": .02, "CMR": .02, "TCD": .01},
    "am": {"ETH": 1.0},
    "ur": {"PAK": .85, "IND": .15},
    "fa": {"IRN": .85, "AFG": .12, "TJK": .03},
    "tr": {"TUR": .97, "CYP": .03},
    "vi": {"VNM": 1.0},
    "th": {"THA": 1.0},
    "ja": {"JPN": 1.0},
    "de": {"DEU": .78, "AUT": .11, "CHE": .11},
    "uk": {"UKR": 1.0},
    "ko": {"KOR": 1.0},
}

# GDELT names countries in plain English; map the frequent ones to ISO3.
GDELT_NAME_TO_ISO3 = {
    "United States": "USA", "United Kingdom": "GBR", "India": "IND",
    "Nigeria": "NGA", "Canada": "CAN", "Australia": "AUS", "Germany": "DEU",
    "France": "FRA", "Spain": "ESP", "Italy": "ITA", "Brazil": "BRA",
    "Mexico": "MEX", "Argentina": "ARG", "China": "CHN", "Japan": "JPN",
    "South Korea": "KOR", "Indonesia": "IDN", "Malaysia": "MYS",
    "Philippines": "PHL", "Thailand": "THA", "Vietnam": "VNM",
    "Pakistan": "PAK", "Bangladesh": "BGD", "Russia": "RUS",
    "Ukraine": "UKR", "Turkey": "TUR", "Egypt": "EGY", "Saudi Arabia": "SAU",
    "United Arab Emirates": "ARE", "Israel": "ISR", "Iran": "IRN",
    "South Africa": "ZAF", "Kenya": "KEN", "Ghana": "GHA", "Ethiopia": "ETH",
    "Tanzania": "TZA", "Uganda": "UGA", "Zimbabwe": "ZWE", "Zambia": "ZMB",
    "New Zealand": "NZL", "Ireland": "IRL", "Netherlands": "NLD",
    "Belgium": "BEL", "Sweden": "SWE", "Norway": "NOR", "Denmark": "DNK",
    "Finland": "FIN", "Poland": "POL", "Austria": "AUT",
    "Switzerland": "CHE", "Portugal": "PRT", "Greece": "GRC",
    "Czech Republic": "CZE", "Czechia": "CZE", "Romania": "ROU",
    "Hungary": "HUN", "Colombia": "COL", "Peru": "PER", "Chile": "CHL",
    "Venezuela": "VEN", "Ecuador": "ECU", "Singapore": "SGP",
    "Sri Lanka": "LKA", "Nepal": "NPL", "Morocco": "MAR", "Algeria": "DZA",
    "Tunisia": "TUN", "Jordan": "JOR", "Lebanon": "LBN", "Iraq": "IRQ",
    "Qatar": "QAT", "Kuwait": "KWT",
}


def _mean(vals: list) -> float | None:
    xs = [v for v in vals if v is not None]
    return sum(xs) / len(xs) if xs else None


def _date_map(series: dict) -> dict:
    """{date: views} for one stored series, skipping days with no data."""
    start = date.fromisoformat(series["start"])
    return {
        start + timedelta(days=i): v
        for i, v in enumerate(series["values"])
        if v is not None
    }


# A series must have at least this many real days inside each window for its
# mean to mean anything. Wikimedia occasionally drops a day; a handful of
# gaps is fine, a mostly-empty window is not.
MIN_RECENT_DAYS = 4      # of the 7-day window
MIN_BASE_DAYS = 15       # of the 30-day baseline


def series_stats(series: dict, as_of: date) -> dict | None:
    """
    Velocity stats for one daily series, measured on CALENDAR DATES.

    Why dates and not array positions (fixed 2026-07-26): every stored series
    is WINDOW_DAYS long, but different series can end on different days — a
    fetch that times out leaves some series windowed weeks behind while
    others are current. Reading `values[-7:]` as "the last 7 days" therefore
    silently reported three-week-old numbers as this week's, for two-thirds
    of series, while the file's header still said it was updated today.

    Anchoring to `as_of` makes staleness self-declaring: a series with no
    data in the last 7 days returns None and is excluded rather than
    contributing stale figures to a "rising this week" panel.
    """
    dmap = _date_map(series)
    if not dmap:
        return None

    recent_days = [as_of - timedelta(days=i) for i in range(0, 7)]
    base_days = [as_of - timedelta(days=i) for i in range(7, 37)]
    recent_vals = [dmap[d] for d in recent_days if d in dmap]
    base_vals = [dmap[d] for d in base_days if d in dmap]

    if len(recent_vals) < MIN_RECENT_DAYS or len(base_vals) < MIN_BASE_DAYS:
        return None
    recent = _mean(recent_vals)
    base = _mean(base_vals)
    if recent is None or base is None or base <= 0:
        return None
    return {
        "mean_7d": round(recent, 1),
        "mean_30d_prior": round(base, 1),
        "velocity": round((recent - base) / base, 3),
        "last_data": max(dmap).isoformat(),
        "days_measured_7d": len(recent_vals),
    }


def main() -> None:
    registry = json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))
    topics = {t["qid"]: t for t in registry["topics"]}
    if not WIKI_PATH.exists():
        # first-ever run, or the fetch step failed before producing anything:
        # exit cleanly so the workflow's commit step doesn't fail the night
        print(f"NOTE: {WIKI_PATH.name} not found — nothing to compute yet. "
              "The next successful pageview fetch will populate it.")
        sys.exit(0)
    wiki = json.loads(WIKI_PATH.read_text(encoding="utf-8"))
    gdelt = {}
    if GDELT_PATH.exists():
        try:
            gdelt_doc = json.loads(GDELT_PATH.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            gdelt_doc = {}
        # STALENESS GUARD: if the GDELT fetch has been failing for a week,
        # presenting its last snapshot as "news articles in the last 7 days"
        # would be silently wrong. Drop the supply signal instead.
        from datetime import date as _date, timedelta as _td
        upd = str(gdelt_doc.get("updated", ""))
        try:
            fresh = (_date.today() - _date.fromisoformat(upd)) <= _td(days=7)
        except ValueError:
            fresh = False
        if fresh:
            gdelt = gdelt_doc.get("topics", {})
        else:
            print(f"WARNING: gdelt_coverage.json is stale (updated={upd or 'unknown'}) — omitting news-coverage figures this run")

    topic_out: dict[str, dict] = {}
    country_scores: dict[str, dict[str, float]] = {}   # iso3 -> {qid: score}
    country_rising: dict[str, list] = {}               # iso3 -> rising topics

    # The measurement anchor: the day the demand file says its window ends.
    # Every velocity below is computed against THIS date, so a series that
    # stopped updating cannot pass its old numbers off as current.
    try:
        as_of = date.fromisoformat(str(wiki.get("updated", "")))
    except ValueError:
        as_of = date.today()
        print(f"WARNING: wiki_pageviews.json has no usable 'updated' date — anchoring to today ({as_of})")

    n_series_fresh = n_series_stale = 0
    stale_topics: list[str] = []

    for qid, langs in wiki.get("series", {}).items():
        meta = topics.get(qid)
        if not meta:
            continue

        lang_stats: dict[str, dict] = {}
        for lang, s in langs.items():
            st = series_stats(s, as_of)
            if st is None:
                n_series_stale += 1
                continue
            n_series_fresh += 1
            if st["mean_7d"] >= INCLUDE_FLOOR:
                lang_stats[lang] = st
        if not lang_stats:
            # Either genuinely low-traffic everywhere, or every series for
            # this topic is stale. Record the latter so the count of
            # "topics we cannot currently speak to" is visible rather than
            # silently absent from the output.
            if all(series_stats(s, as_of) is None for s in langs.values()):
                stale_topics.append(qid)
            continue

        # volume-weighted global velocity (only series above the rising floor
        # participate, so tiny editions can't dominate the global number)
        big = {l: st for l, st in lang_stats.items() if st["mean_7d"] >= RISING_FLOOR}
        basis = big or lang_stats
        wsum = sum(st["mean_7d"] for st in basis.values())
        g_velocity = sum(st["velocity"] * st["mean_7d"] for st in basis.values()) / wsum

        label = ("rising" if g_velocity > RISING_THRESHOLD
                 else "falling" if g_velocity < FALLING_THRESHOLD
                 else "steady")

        # GDELT supply context
        g = gdelt.get(qid, {})
        vol = g.get("volume_daily", [])
        news_7d = sum(p["articles"] for p in vol[-7:]) if vol else None
        src = g.get("source_countries", {})
        # tolerate both clean names and legacy "<Country> Volume Intensity"
        # series names from GDELT snapshots fetched before the suffix fix
        src = {re.sub(r"\s+Volume Intensity$", "", k).strip(): v for k, v in src.items()}
        top_media = sorted(
            ((GDELT_NAME_TO_ISO3.get(k), v) for k, v in src.items()
             if GDELT_NAME_TO_ISO3.get(k)),
            key=lambda kv: -kv[1])[:10]

        # Compact global daily series (sum across tracked languages) so the
        # Topic Explorer can draw trend lines without the full raw dataset.
        # Summed BY CALENDAR DATE, not by array index: series can start on
        # different days, so index-summing silently added Monday's views to
        # another edition's Thursday.
        by_date: dict[date, int] = {}
        for s in langs.values():
            for d, v in _date_map(s).items():
                by_date[d] = by_date.get(d, 0) + v
        series_start = min(by_date) if by_date else as_of
        n_days = (max(by_date) - series_start).days + 1 if by_date else 0
        global_series = [by_date.get(series_start + timedelta(days=i), 0)
                         for i in range(n_days)]

        topic_out[qid] = {
            "label_en": meta["label_en"],
            "category": meta["category"],
            "global_velocity": round(g_velocity, 3),
            "momentum": label,
            "demand_by_language": {
                l: {"weekly_daily_avg_views": st["mean_7d"],
                    "velocity": st["velocity"]}
                for l, st in sorted(lang_stats.items(),
                                    key=lambda kv: -kv[1]["mean_7d"])[:8]
            },
            "news_articles_7d": news_7d,
            "top_covering_media_countries": [
                {"iso3": c, "coverage_share_pct": v} for c, v in top_media],
            "series_start": series_start.isoformat(),
            "global_series": global_series,
            # the newest day of real demand data behind this topic's figures
            "as_of": max(st["last_data"] for st in lang_stats.values()),
        }

        # country attribution (documented heuristic)
        for lang, st in lang_stats.items():
            for iso3, w in LANG_COUNTRY_WEIGHTS.get(lang, {}).items():
                score = w * st["mean_7d"]
                country_scores.setdefault(iso3, {})
                country_scores[iso3][qid] = country_scores[iso3].get(qid, 0) + score
                if st["velocity"] > RISING_THRESHOLD and st["mean_7d"] >= RISING_FLOOR:
                    country_rising.setdefault(iso3, []).append({
                        "qid": qid, "label_en": meta["label_en"],
                        "velocity": st["velocity"], "via_language": lang,
                        "weight": w,
                    })

    # Global baseline share per topic (average of its share across countries).
    # Used for "distinctive interests": share ÷ global share, TF-IDF-style —
    # a perennially popular topic (share high EVERYWHERE) scores ~1 and drops
    # out, while a topic a country cares about unusually much scores >>1.
    share_by_country: dict[str, dict[str, float]] = {}
    for iso3, scores in country_scores.items():
        total = sum(scores.values()) or 1.0
        share_by_country[iso3] = {q: s / total for q, s in scores.items()}
    tmp: dict[str, list[float]] = {}
    for shares in share_by_country.values():
        for q, sh in shares.items():
            tmp.setdefault(q, []).append(sh)
    global_share = {q: sum(v) / len(share_by_country) for q, v in tmp.items()}

    # per-country: top interest topics + distinctive interests + rising list
    country_out: dict[str, dict] = {}
    for iso3, scores in country_scores.items():
        shares = share_by_country[iso3]
        top = sorted(scores.items(), key=lambda kv: -kv[1])[:15]
        distinctive = sorted(
            ((q, sh, sh / global_share[q]) for q, sh in shares.items()
             if sh >= 0.01 and global_share.get(q, 0) > 0),
            key=lambda x: -x[2])[:10]
        rising = sorted(
            country_rising.get(iso3, []),
            key=lambda r: -(r["velocity"] * r["weight"]))[:10]
        # dedupe rising by topic, keep strongest
        seen, rising_dedup = set(), []
        for r in rising:
            if r["qid"] not in seen:
                seen.add(r["qid"])
                rising_dedup.append(r)
        country_out[iso3] = {
            "top_topics": [
                {"qid": q, "label_en": topics[q]["label_en"],
                 "attention_share_pct": round(100 * shares[q], 1)}
                for q, s in top],
            "distinctive_topics": [
                {"qid": q, "label_en": topics[q]["label_en"],
                 "attention_share_pct": round(100 * sh, 1),
                 "vs_global_avg": round(ratio, 1)}
                for q, sh, ratio in distinctive if ratio >= 1.5],
            "rising_topics": rising_dedup,
        }

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(
        json.dumps({
            "generated": date.today().isoformat(),
            # What the numbers below actually measure, and how much of the
            # tracked universe was current enough to measure at all. The
            # Topic Explorer and the analyst both surface this rather than
            # implying full coverage.
            "measured_as_of": as_of.isoformat(),
            "coverage": {
                "series_current": n_series_fresh,
                "series_stale_excluded": n_series_stale,
                "topics_scored": len(topic_out),
                "topics_stale_excluded": len(stale_topics),
                "note": (
                    "Velocity windows are anchored to measured_as_of by calendar date. "
                    "Series with no data in that 7-day window are excluded rather than "
                    "contributing older figures; a large series_stale_excluded count means "
                    "the daily fetch has not been completing (see docs/AUTOMATION.md)."
                ),
            },
            "method_notes": {
                "velocity": "(mean last 7d − mean prior 30d) / prior mean, per language series, volume-weighted globally; windows are calendar-dated against measured_as_of",
                "country_attribution": "HEURISTIC: language-edition demand mapped to countries by speaker-population weights; approximation, not measurement",
                "demand_vs_supply": "Wikipedia pageviews = demand (what people look up); GDELT = supply (what media publish); never merged",
                "include_floor_daily_views": INCLUDE_FLOOR,
                "rising_floor_daily_views": RISING_FLOOR,
                "rising_threshold": RISING_THRESHOLD,
            },
            "topics": topic_out,
            "countries": country_out,
        }, indent=1, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    n_rising = sum(1 for t in topic_out.values() if t["momentum"] == "rising")
    print(f"Wrote {OUTPUT_PATH} — {len(topic_out)} topics scored "
          f"({n_rising} rising globally), {len(country_out)} countries profiled.")
    print(f"  measured as of {as_of}: {n_series_fresh} current series, "
          f"{n_series_stale} stale series excluded, {len(stale_topics)} topics unscorable today.")
    if n_series_stale > n_series_fresh:
        print("  WARNING: most series are stale — the daily Wikipedia fetch is not "
              "completing. Topic momentum is being computed from a minority of the "
              "tracked universe. See docs/AUTOMATION.md → 'trend engine falls behind'.")


if __name__ == "__main__":
    main()
