#!/usr/bin/env python3
"""
fetch_trends_gdelt.py — daily GDELT news-coverage connector.

For every topic in data/topics.json, queries the GDELT 2.0 DOC API
(free, no key) for:
  1. mode=timelinevolraw  — daily global news article volume (media SUPPLY)
  2. mode=timelinesourcecountry — volume split by the country where the
     covering outlet is based (which countries' media cover this topic)

GDELT monitors news in 100+ languages with machine translation, so the
English query surfaces global coverage. This measures what media PUBLISH
(supply) — deliberately distinct from Wikipedia pageviews (demand).
compute_topic_intelligence.py keeps the two signals separate.

RATE LIMIT: GDELT allows ~1 request per 5 seconds per IP and returns a
plain-text notice (not JSON) when throttled. This script paces at
SLEEP seconds/call. Shared CI runner IPs (GitHub Actions) have been
observed hitting GDELT's limit immediately — evidently other tenants'
traffic on the same IP pool already consumes the budget — so retries are
kept short (fail fast, move to the next topic) rather than backing off
for minutes on a call that may never succeed this run.

RESILIENCE: writes a checkpoint every CHECKPOINT_EVERY topics, always
merged with the previous snapshot, so a mid-run kill (timeout) leaves a
file that is monotonically at least as complete as before — it can only
gain topics/freshness, never lose them. If GDELT is unreachable, this
signal simply stays "stale" or absent; the daily "Trending now" feature
depends only on Wikipedia data and is unaffected.

TIME BUDGET (reworked 2026-08-10 — the step was hitting its 50-minute cap
every day with only ~50 of 167 topics refreshed per cycle):
  * Topics are processed STALEST-FIRST using each topic's own
    volume_retrieved stamp, so whatever a timeout cuts off runs first
    tomorrow — the worst refresh interval is bounded (~4 days) instead of
    left to the luck of the old daily shuffle (which survives only as the
    tie-breaker for equal stamps).
  * The source-country mix is a 14-day mean and moves slowly, so it is
    re-fetched only when older than SOURCE_COUNTRY_REFRESH_DAYS — on most
    visits a topic now costs one call instead of two, roughly doubling how
    many topics fit in the budget.
--limit N caps the topics processed (TESTING ONLY).

Output: data/trends/gdelt_coverage.json (rolling snapshot; the volume
timeline covers the trailing TIMESPAN).
"""

from __future__ import annotations

import argparse
import json
import random
import re
import ssl
import sys
import time
import urllib.parse
import urllib.request
from datetime import date, timedelta
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
REGISTRY_PATH = REPO_ROOT / "data" / "topics.json"
OUTPUT_PATH = REPO_ROOT / "data" / "trends" / "gdelt_coverage.json"

USER_AGENT = "UN-Media-Atlas/1.0 (Global Content Intelligence Platform; research)"
TIMESPAN = "90d"          # volume timeline window
COUNTRY_TIMESPAN = "14d"  # source-country breakdown window
SLEEP = 6.5               # seconds between calls (GDELT limit: 1 per 5s)
MAX_BACKOFF_RETRIES = 2   # fail fast: better to cover more topics partially
BACKOFF_BASE = 12         # seconds; attempt N waits BACKOFF_BASE*(N+1)
CHECKPOINT_EVERY = 20     # topics between merged, safe-to-interrupt saves
SOURCE_COUNTRY_REFRESH_DAYS = 5  # reuse the 14d source-country mix this long


def _ssl_context() -> ssl.SSLContext:
    try:
        import certifi  # noqa: PLC0415
        return ssl.create_default_context(cafile=certifi.where())
    except ImportError:
        return ssl.create_default_context()


CTX = _ssl_context()


def gdelt_call(params: dict[str, str]) -> dict | None:
    """One paced GDELT DOC API call. Returns parsed JSON or None."""
    url = "https://api.gdeltproject.org/api/v2/doc/doc?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    for attempt in range(MAX_BACKOFF_RETRIES):
        try:
            with urllib.request.urlopen(req, timeout=45, context=CTX) as resp:
                raw = resp.read().decode("utf-8", errors="replace")
            try:
                return json.loads(raw)
            except json.JSONDecodeError:
                # Throttle notice or transient HTML — short retry, then give up
                # on this call (a later topic gets its turn instead of one
                # call monopolizing the whole time budget).
                if attempt < MAX_BACKOFF_RETRIES - 1:
                    time.sleep(BACKOFF_BASE * (attempt + 1))
        except urllib.error.HTTPError as e:
            if e.code == 429 and attempt < MAX_BACKOFF_RETRIES - 1:
                time.sleep(BACKOFF_BASE * (attempt + 1))
            elif e.code != 429:
                time.sleep(3)
        except Exception:
            time.sleep(3)
    return None


def parse_volume(data: dict) -> list[dict]:
    """timelinevolraw -> [{date, articles}] daily points."""
    out = []
    for series in data.get("timeline", []):
        for pt in series.get("data", []):
            d = pt.get("date", "")
            if len(d) >= 8:
                out.append({"date": f"{d[:4]}-{d[4:6]}-{d[6:8]}",
                            "articles": pt.get("value", 0)})
    # collapse duplicate dates (intraday points) by summing
    agg: dict[str, int] = {}
    for p in out:
        agg[p["date"]] = agg.get(p["date"], 0) + p["articles"]
    return [{"date": d, "articles": v} for d, v in sorted(agg.items())]


def parse_source_countries(data: dict) -> dict[str, float]:
    """timelinesourcecountry -> {country_name: mean Volume Intensity}.

    Volume Intensity is the percentage of THAT country's own monitored news
    output matching the query — not the country's share of world coverage of
    the topic. A small media market that covers something obsessively scores
    higher than a large one publishing far more articles about it, so the
    figure must never be presented as "who covers this most".

    GDELT names its series "<Country> Volume Intensity" — strip the suffix so
    the downstream ISO3 lookup (compute_topic_intelligence.gdelt_iso3_lookup)
    receives plain country names. Without this every lookup fails silently and
    media_intensity_by_country comes out empty.
    """
    out: dict[str, float] = {}
    for series in data.get("timeline", []):
        name = series.get("series", "").strip()
        name = re.sub(r"\s+Volume Intensity$", "", name).strip()
        pts = [pt.get("value", 0) for pt in series.get("data", [])]
        if name and pts:
            out[name] = round(sum(pts) / len(pts), 4)
    return out


def write_output(results: dict) -> None:
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(
        json.dumps({
            "source": "GDELT 2.0 DOC API (news coverage, 100+ languages via machine translation)",
            "license": "open (attribution appreciated)",
            "signal_type": "supply (what media publish)",
            "updated": date.today().isoformat(),
            "volume_timespan": TIMESPAN,
            "country_timespan": COUNTRY_TIMESPAN,
            "topics": results,
        }, separators=(",", ":"), ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def main() -> None:
    ap = argparse.ArgumentParser(description="GDELT news-coverage fetcher")
    ap.add_argument("--limit", type=int,
                    help="TESTING ONLY: cap the number of topics processed")
    args = ap.parse_args()

    registry = json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))
    topics = list(registry["topics"])

    # Previous snapshot — the per-topic fallback when today's fetch fails, and
    # (since 2026-08-10) the carrier of the freshness stamps that drive the
    # processing order below.
    previous: dict[str, dict] = {}
    if OUTPUT_PATH.exists():
        previous = json.loads(OUTPUT_PATH.read_text(encoding="utf-8")).get("topics", {})

    # STALEST-FIRST (2026-08-10), replacing order-by-daily-shuffle. The
    # shuffle gave every topic a fair CHANCE at the ~40-50 slots a throttled
    # 50-minute budget really holds, but chance is not a guarantee — an
    # unlucky topic could starve for a week. Sorting by each topic's own
    # last-successful-fetch stamp bounds the worst case (~4 days), and
    # whatever a timeout cuts off is exactly what runs first tomorrow.
    # The shuffle survives as the tie-breaker so equal stamps (e.g. the
    # whole never-stamped backlog on this change's first day) rotate fairly
    # instead of falling into registry order.
    rng = random.Random(date.today().toordinal())
    rng.shuffle(topics)
    topics.sort(key=lambda t: (previous.get(t["qid"], {}).get("volume_retrieved") or ""))
    if args.limit:
        topics = topics[:args.limit]

    today_iso = date.today().isoformat()
    country_cutoff = (date.today()
                      - timedelta(days=SOURCE_COUNTRY_REFRESH_DAYS)).isoformat()

    # Seed results from `previous` (not empty) so every checkpoint — and a
    # timeout kill at any point — leaves a file at least as complete as
    # what existed before this run started.
    results: dict[str, dict] = {qid: dict(entry) for qid, entry in previous.items()}
    n_country_fetched = n_country_reused = 0
    for i, t in enumerate(topics, 1):
        qid, label = t["qid"], t["label_en"]
        query = f'"{label}"' if " " in label else label
        prev_entry = previous.get(qid, {})

        vol_data = gdelt_call({
            "query": query, "mode": "timelinevolraw",
            "timespan": TIMESPAN, "format": "json",
        })
        time.sleep(SLEEP)

        # The source-country mix is a 14-day mean — it moves slowly, and at
        # 6.5 s a call it used to double every topic's cost. Reuse it while
        # it is at most SOURCE_COUNTRY_REFRESH_DAYS old: deliberate reuse
        # within a declared freshness contract, NOT staleness — the
        # countries_stale flag stays reserved for fetches that failed.
        c_stamp = prev_entry.get("countries_retrieved") or ""
        country_data = None
        if c_stamp >= country_cutoff and prev_entry.get("source_countries"):
            n_country_reused += 1
        else:
            country_data = gdelt_call({
                "query": query, "mode": "timelinesourcecountry",
                "timespan": COUNTRY_TIMESPAN, "format": "json",
            })
            time.sleep(SLEEP)
            n_country_fetched += 1

        entry: dict = {"label_en": label}
        if vol_data:
            entry["volume_daily"] = parse_volume(vol_data)
            entry["volume_retrieved"] = today_iso
        if country_data:
            entry["source_countries"] = parse_source_countries(country_data)
            entry["countries_retrieved"] = today_iso

        # per-topic fallback: keep yesterday's data rather than nothing
        if not entry.get("volume_daily") and prev_entry.get("volume_daily"):
            entry["volume_daily"] = prev_entry["volume_daily"]
            entry["volume_stale"] = True
            if prev_entry.get("volume_retrieved"):
                entry["volume_retrieved"] = prev_entry["volume_retrieved"]
        if not entry.get("source_countries") and prev_entry.get("source_countries"):
            entry["source_countries"] = prev_entry["source_countries"]
            if c_stamp:
                entry["countries_retrieved"] = c_stamp
            if not (c_stamp >= country_cutoff):
                entry["countries_stale"] = True

        results[qid] = entry

        if i % 10 == 0:
            print(f"  …{i}/{len(topics)} topics", flush=True)
        if i % CHECKPOINT_EVERY == 0:
            write_output(results)   # safe: monotonically >= previous state

    write_output(results)
    ok_vol = sum(1 for e in results.values()
                 if e.get("volume_daily") and not e.get("volume_stale"))
    ok_cty = sum(1 for e in results.values()
                 if e.get("source_countries") and not e.get("countries_stale"))
    size_mb = OUTPUT_PATH.stat().st_size / 1e6
    print(f"Wrote {OUTPUT_PATH} ({size_mb:.1f} MB) — "
          f"volume fresh for {ok_vol}/{len(results)}, "
          f"source-country usable for {ok_cty}/{len(results)} "
          f"({n_country_fetched} country calls made, "
          f"{n_country_reused} reused within {SOURCE_COUNTRY_REFRESH_DAYS}d).")


if __name__ == "__main__":
    sys.exit(main())
