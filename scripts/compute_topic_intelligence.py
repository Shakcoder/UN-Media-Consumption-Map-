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
- GDELT's per-country figure is a coverage INTENSITY: the share of that
  country's OWN monitored news output that matches the topic, attributed to
  where the OUTLET is based. It is not a slice of world coverage — a small
  media market that covers a topic obsessively outranks a large one that
  publishes far more articles about it. Supply signal, kept separate from
  demand.
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
COUNTRIES_PATH = REPO_ROOT / "data" / "countries.json"
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

# A country profile is expressed as shares of that country's own attributed
# attention. With one or two qualifying topics that arithmetic says nothing:
# a single small-language series scraping INCLUDE_FLOOR becomes "this country
# cares about one thing, 100%". Below this many topics we report no profile
# rather than a share of one.
MIN_PROFILE_TOPICS = 3

# A point on the composite "global attention" line is only a global figure
# when the language editions that reported that day carry most of the topic's
# usual traffic. Below this share the day is left empty: editions differ in
# how far back their stored history reaches, and plotting a partial sum draws
# a hole in the data as a collapse in attention.
SERIES_COVERAGE_FLOOR = 0.5

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

# GDELT names countries in plain English, and ~150 of those names are spelled
# exactly as data/countries.json spells them — so the lookup is built from the
# atlas's own country list at run time and only GDELT's own spellings are
# listed here. Keeping the whole list by hand does not work: GDELT returns
# ~168 country names, a partial table drops the rest with no visible symptom,
# and the countries that fall off are disproportionately small and
# global-south markets — exactly the ones this platform exists to show.
GDELT_NAME_ALIASES = {
    "Bosnia-Herzegovina": "BIH",
    "Brunei": "BRN",
    "Cape Verde": "CPV",
    "Congo": "COG",             # GDELT lists the DRC separately, by full name
    "Czech Republic": "CZE",
    "East Timor": "TLS",
    "Gambia": "GMB",
    "Ivory Coast": "CIV",
    "Kyrgyzstan": "KGZ",
    "Laos": "LAO",
    "Macedonia": "MKD",
    "North Korea": "PRK",
    "Somalia": "SOM",
    "Syria": "SYR",
    "Taiwan": "TWN",
    "Turkey": "TUR",
    "United States": "USA",
    # Territories the atlas does not profile as countries. They still have
    # their own newsrooms, so they belong in a list of whose media cover a
    # topic rather than being silently discarded.
    "Guam": "GUM",
    "Hong Kong": "HKG",
    "Mayotte": "MYT",
}

# Names left unmapped on purpose, so the "unmapped source country" warning
# below stays a real alarm: Kosovo has no ISO 3166-1 code for the rest of the
# atlas to resolve, and "Volume Intensity" is GDELT's own label for coverage
# it could not attribute to any country.
GDELT_NAMES_UNMAPPABLE = {"Kosovo", "Volume Intensity"}


def gdelt_iso3_lookup() -> dict[str, str]:
    """GDELT country name → ISO3, resolved against the atlas's country list."""
    lookup = dict(GDELT_NAME_ALIASES)
    try:
        countries = json.loads(COUNTRIES_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return lookup
    for iso3, rec in countries.items():
        if isinstance(rec, dict) and rec.get("name"):
            lookup.setdefault(rec["name"], iso3)
    return lookup


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


def news_articles_7d(entry: dict, run_day: date) -> tuple[int | None, dict | None]:
    """
    Articles published in the 7 COMPLETE days before run_day — or nothing.

    Two ways this count can lie about its own window, both refused here:

    - GDELT rate-limits hard, and when a topic's fetch fails
      fetch_trends_gdelt.py keeps the previous snapshot and marks it
      volume_stale. Those timelines run weeks behind while the file header
      says it was updated today, so counting them publishes a fortnight-old
      week as "the last 7 days".
    - The newest point is the morning the fetch ran — a few hours of news,
      not a day. Counting it shortens every week by about a seventh, and
      makes topics fetched on different days incomparable.

    Anything short of seven complete days returns None. topics.html and the
    analyst both hide a null figure, which is the honest outcome: fewer
    topics carry a coverage count, and the ones that do mean what they say.
    """
    if entry.get("volume_stale"):
        return None, None
    end = run_day - timedelta(days=1)
    start = end - timedelta(days=6)
    by_day: dict[date, int] = {}
    for p in entry.get("volume_daily") or []:
        try:
            d = date.fromisoformat(str(p.get("date", "")))
        except ValueError:
            continue
        if start <= d <= end:
            by_day[d] = p.get("articles", 0)
    if len(by_day) < 7:
        return None, None
    return (sum(by_day.values()),
            {"start": start.isoformat(), "end": end.isoformat()})


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
    gdelt_iso3 = gdelt_iso3_lookup()
    unmapped_media: dict[str, int] = {}                # GDELT name -> topics seen in
    run_day = date.today()

    # How long a history the demand file keeps; the composite attention line
    # below covers exactly this window so the Topic Explorer's "last N days"
    # heading stays true if the window is ever changed.
    window_days = int(wiki.get("window_days") or 120)

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
        news_7d, news_window = news_articles_7d(g, run_day)
        src = g.get("source_countries", {})
        # tolerate both clean names and legacy "<Country> Volume Intensity"
        # series names from GDELT snapshots fetched before the suffix fix
        src = {re.sub(r"\s+Volume Intensity$", "", k).strip(): v for k, v in src.items()}
        top_media = sorted(
            ((gdelt_iso3[k], v) for k, v in src.items() if k in gdelt_iso3),
            key=lambda kv: -kv[1])[:10]
        for k in src:
            if k not in gdelt_iso3 and k not in GDELT_NAMES_UNMAPPABLE:
                unmapped_media[k] = unmapped_media.get(k, 0) + 1

        # Compact global daily series (sum across tracked languages) so the
        # Topic Explorer can draw trend lines without the full raw dataset.
        # Summed BY CALENDAR DATE, not by array index: series can start on
        # different days, so index-summing silently added Monday's views to
        # another edition's Thursday.
        #
        # A day is only plotted when the editions that reported it carry at
        # least SERIES_COVERAGE_FLOOR of the topic's usual traffic. Editions
        # hold different amounts of history: when a large edition's stored
        # window reaches back only three weeks, summing the earlier months
        # without it shows four months of attention at a fraction of its real
        # level, then a cliff upwards. Days below the floor are emitted as
        # null, which the sparkline draws as a break in the line, not a fall.
        typical = {l: (_mean(list(_date_map(s).values())) or 0.0)
                   for l, s in langs.items()}
        total_typical = sum(typical.values())
        by_date: dict[date, int] = {}
        reported_typical: dict[date, float] = {}
        for l, s in langs.items():
            for d, v in _date_map(s).items():
                by_date[d] = by_date.get(d, 0) + v
                reported_typical[d] = reported_typical.get(d, 0.0) + typical[l]
        series_start = as_of - timedelta(days=window_days - 1)
        window = [series_start + timedelta(days=i) for i in range(window_days)]
        floor = SERIES_COVERAGE_FLOOR * total_typical
        global_series = [
            by_date[d] if d in by_date and reported_typical[d] >= floor else None
            for d in window
        ]

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
            # the exact days that count covers, so nothing downstream has to
            # assume "7 days" ends today
            "news_articles_7d_window": news_window,
            # NOT a share of the world's coverage of this topic: each value is
            # the percentage of THAT country's own monitored news output that
            # matches the topic (GDELT calls it Volume Intensity). The field
            # name spells this out because read as a global share it puts
            # small, intensely-covering markets where the biggest news
            # producers should be — Ghana above France on a 5G question.
            "media_intensity_by_country": [
                {"iso3": c, "pct_of_country_news_volume": v} for c, v in top_media],
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
    # Countries with fewer than MIN_PROFILE_TOPICS qualifying topics are held
    # out of the baseline as well as out of the output: a profile that is one
    # topic at 100% would drag that topic's global average up and make every
    # other country look less interested in it than it is.
    share_by_country: dict[str, dict[str, float]] = {}
    for iso3, scores in country_scores.items():
        if len(scores) < MIN_PROFILE_TOPICS:
            continue
        total = sum(scores.values()) or 1.0
        share_by_country[iso3] = {q: s / total for q, s in scores.items()}
    tmp: dict[str, list[float]] = {}
    for shares in share_by_country.values():
        for q, sh in shares.items():
            tmp.setdefault(q, []).append(sh)
    global_share = {q: sum(v) / len(share_by_country) for q, v in tmp.items()}

    # per-country: top interest topics + distinctive interests + rising list
    country_out: dict[str, dict] = {}
    n_thin_profiles = 0
    for iso3, scores in country_scores.items():
        rising = sorted(
            country_rising.get(iso3, []),
            key=lambda r: -(r["velocity"] * r["weight"]))[:10]
        # dedupe rising by topic, keep strongest
        seen, rising_dedup = set(), []
        for r in rising:
            if r["qid"] not in seen:
                seen.add(r["qid"])
                rising_dedup.append(r)

        if iso3 not in share_by_country:
            # Too few measurable topics to divide attention between. Say so
            # rather than reporting the one series that happened to clear the
            # floor as the whole of what this audience cares about.
            n_thin_profiles += 1
            country_out[iso3] = {
                "top_topics": [],
                "distinctive_topics": [],
                "rising_topics": rising_dedup,
                "no_profile_reason": (
                    f"only {len(scores)} topic(s) cleared the measurement floor for "
                    "this country — too few to express attention as shares"
                ),
            }
            continue

        shares = share_by_country[iso3]
        top = sorted(scores.items(), key=lambda kv: -kv[1])[:15]
        distinctive = sorted(
            ((q, sh, sh / global_share[q]) for q, sh in shares.items()
             if sh >= 0.01 and global_share.get(q, 0) > 0),
            key=lambda x: -x[2])[:10]
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
                "topics_with_news_volume": sum(
                    1 for t in topic_out.values() if t["news_articles_7d"] is not None),
                "countries_without_profile": n_thin_profiles,
                "note": (
                    "Velocity windows are anchored to measured_as_of by calendar date. "
                    "Series with no data in that 7-day window are excluded rather than "
                    "contributing older figures; a large series_stale_excluded count means "
                    "the daily fetch has not been completing (see docs/AUTOMATION.md). "
                    "News volume is reported only for topics whose GDELT timeline covers "
                    "the seven complete days before the run, so topics_with_news_volume is "
                    "normally well below topics_scored."
                ),
            },
            "method_notes": {
                "velocity": "(mean last 7d − mean prior 30d) / prior mean, per language series, volume-weighted globally; windows are calendar-dated against measured_as_of",
                "country_attribution": "HEURISTIC: language-edition demand mapped to countries by speaker-population weights; approximation, not measurement",
                "demand_vs_supply": "Wikipedia pageviews = demand (what people look up); GDELT = supply (what media publish); never merged",
                "media_intensity_by_country": "pct_of_country_news_volume is GDELT 'Volume Intensity': the percentage of THAT COUNTRY'S OWN monitored news output matching the topic — NOT its share of world coverage. A small media market that covers the topic intensively outranks a large one publishing far more articles on it; read it as editorial focus, never as volume or concentration.",
                "news_articles_7d": "GDELT article count over the 7 complete days before the run date (see news_articles_7d_window); null for topics whose timeline could not be refreshed, rather than reporting an older week as this one",
                "global_series": "daily sum of tracked Wikipedia language editions across the demand window ending measured_as_of; a day is null when the editions reporting it carry less than half the topic's usual traffic, i.e. the data is missing rather than the attention",
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
    n_news = sum(1 for t in topic_out.values() if t["news_articles_7d"] is not None)
    print(f"  news volume reported for {n_news}/{len(topic_out)} topics "
          f"(the rest could not be refreshed from GDELT in time for a complete week); "
          f"{n_thin_profiles} countries have too few measurable topics for a profile.")
    if unmapped_media:
        # Not fatal, but every unmapped name is a country missing from the
        # "whose media cover this" lists. Add it to GDELT_NAME_ALIASES.
        worst = sorted(unmapped_media.items(), key=lambda kv: -kv[1])[:10]
        print("  WARNING: GDELT source countries with no ISO3 match (dropped from media "
              "lists): " + ", ".join(f"{n} ({c} topics)" for n, c in worst))
    if n_series_stale > n_series_fresh:
        print("  WARNING: most series are stale — the daily Wikipedia fetch is not "
              "completing. Topic momentum is being computed from a minority of the "
              "tracked universe. See docs/AUTOMATION.md → 'trend engine falls behind'.")


if __name__ == "__main__":
    main()
