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
from datetime import date
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


def series_stats(values: list) -> dict | None:
    """Velocity stats for one daily series (most recent value last)."""
    if len(values) < 45:
        return None
    recent = _mean(values[-7:])
    base = _mean(values[-37:-7])
    if recent is None or base is None or base <= 0:
        return None
    return {
        "mean_7d": round(recent, 1),
        "mean_30d_prior": round(base, 1),
        "velocity": round((recent - base) / base, 3),
    }


def main() -> None:
    registry = json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))
    topics = {t["qid"]: t for t in registry["topics"]}
    wiki = json.loads(WIKI_PATH.read_text(encoding="utf-8"))
    gdelt = {}
    if GDELT_PATH.exists():
        gdelt = json.loads(GDELT_PATH.read_text(encoding="utf-8")).get("topics", {})

    topic_out: dict[str, dict] = {}
    country_scores: dict[str, dict[str, float]] = {}   # iso3 -> {qid: score}
    country_rising: dict[str, list] = {}               # iso3 -> rising topics

    for qid, langs in wiki.get("series", {}).items():
        meta = topics.get(qid)
        if not meta:
            continue

        lang_stats: dict[str, dict] = {}
        for lang, s in langs.items():
            st = series_stats(s["values"])
            if st and st["mean_7d"] >= INCLUDE_FLOOR:
                lang_stats[lang] = st
        if not lang_stats:
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
        top_media = sorted(
            ((GDELT_NAME_TO_ISO3.get(k), v) for k, v in src.items()
             if GDELT_NAME_TO_ISO3.get(k)),
            key=lambda kv: -kv[1])[:10]

        # compact global daily series (sum across tracked languages) so the
        # Topic Explorer can draw trend lines without the full raw dataset
        n_days = max(len(s["values"]) for s in langs.values())
        global_series = [0] * n_days
        for s in langs.values():
            for i, v in enumerate(s["values"]):
                if v is not None:
                    global_series[i] += v

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
            "series_start": next(iter(langs.values()))["start"],
            "global_series": global_series,
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
            "method_notes": {
                "velocity": "(mean last 7d − mean prior 30d) / prior mean, per language series, volume-weighted globally",
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


if __name__ == "__main__":
    main()
