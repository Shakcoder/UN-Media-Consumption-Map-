#!/usr/bin/env python3
"""
fetch_trends_wikipedia.py — daily Wikipedia pageviews connector.

For every topic in data/topics.json and every tracked language edition,
fetches daily pageview counts from the Wikimedia Pageviews REST API
(free, no key) and maintains a rolling window in
data/trends/wiki_pageviews.json.

First run backfills WINDOW_DAYS of history (~10-15 min for ~3,100 series).
Subsequent daily runs fetch only the last MERGE_DAYS days per series and
merge (a few minutes).

Wikipedia pageviews measure information DEMAND (what people look up),
per language edition — country attribution happens later in
compute_topic_intelligence.py via documented language→country weights.
"""

from __future__ import annotations

import json
import os
import sys
import time
import urllib.parse
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, datetime, timedelta
from pathlib import Path

import requests

REPO_ROOT = Path(__file__).resolve().parent.parent
REGISTRY_PATH = REPO_ROOT / "data" / "topics.json"
OUTPUT_PATH = REPO_ROOT / "data" / "trends" / "wiki_pageviews.json"

USER_AGENT = "UN-Media-Atlas/1.0 (Global Content Intelligence Platform; research)"
WINDOW_DAYS = 120     # rolling history kept per series
MERGE_DAYS = 10       # incremental fetch depth on daily runs
WORKERS = 4           # parallel fetchers (modest: ~5-10 req/s aggregate)
REQ_TIMEOUT = (5, 15) # (connect, read) seconds

# Wikimedia throttles anonymous clients (especially cloud/CI IPs) to roughly
# hundreds of requests per hour. Two defenses:
# 1. DORMANT PRUNING — series averaging < DORMANT_MEAN views/day (65% of all
#    series, mostly small language editions) are refreshed only on Sundays;
#    they cannot affect results (compute's include floor is higher anyway).
# 2. ADAPTIVE THROTTLE — a shared delay grows on any 429 and decays on
#    success, so throughput self-tunes to whatever budget the IP has.
DORMANT_MEAN = 8.0
FULL_REFRESH = date.today().weekday() == 6   # Sunday: refresh everything

_throttle_lock = __import__("threading").Lock()
_throttle_delay = 0.0


def _throttle_wait() -> None:
    with _throttle_lock:
        d = _throttle_delay
    if d > 0:
        time.sleep(d)


def _throttle_hit(retry_after: float | None) -> None:
    global _throttle_delay
    with _throttle_lock:
        _throttle_delay = min(max(_throttle_delay * 2, 1.0), 20.0)
        if retry_after:
            _throttle_delay = max(_throttle_delay, min(retry_after, 60.0))


def _throttle_ok() -> None:
    global _throttle_delay
    with _throttle_lock:
        _throttle_delay = max(_throttle_delay * 0.9 - 0.01, 0.0)


_session_store: dict[int, requests.Session] = {}


def _session() -> requests.Session:
    """One connection-pooled session per worker thread."""
    import threading
    tid = threading.get_ident()
    if tid not in _session_store:
        s = requests.Session()
        s.headers["User-Agent"] = USER_AGENT
        _session_store[tid] = s
    return _session_store[tid]


def fetch_series(lang: str, title: str, start: date, end: date) -> dict[str, int]:
    """Daily views for one article. Returns {YYYY-MM-DD: views}. 404 -> {}."""
    article = urllib.parse.quote(title.replace(" ", "_"), safe="")
    url = (
        "https://wikimedia.org/api/rest_v1/metrics/pageviews/per-article/"
        f"{lang}.wikipedia/all-access/user/{article}/daily/"
        f"{start.strftime('%Y%m%d')}00/{end.strftime('%Y%m%d')}00"
    )
    for attempt in range(3):
        _throttle_wait()
        try:
            resp = _session().get(url, timeout=REQ_TIMEOUT)
            if resp.status_code == 404:    # no pageview data for this article
                _throttle_ok()
                return {}
            if resp.status_code == 429:    # throttled — adapt globally, retry
                ra = resp.headers.get("Retry-After")
                _throttle_hit(float(ra) if ra and ra.isdigit() else None)
                time.sleep(2 * (attempt + 1))
                continue
            resp.raise_for_status()
            data = resp.json()
            _throttle_ok()
            return {
                f"{it['timestamp'][:4]}-{it['timestamp'][4:6]}-{it['timestamp'][6:8]}":
                    it["views"]
                for it in data.get("items", [])
            }
        except Exception:
            if attempt == 2:
                return {}
            time.sleep(1 + attempt)
    return {}


def main() -> None:
    registry = json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))
    topics = registry["topics"]

    existing: dict = {}
    if OUTPUT_PATH.exists():
        # Guard against a corrupt file (e.g. the process was SIGKILLed mid-write
        # before writes became atomic): start fresh rather than wedging the
        # pipeline permanently on a JSONDecodeError every day.
        try:
            existing = json.loads(OUTPUT_PATH.read_text(encoding="utf-8")).get("series", {})
        except (json.JSONDecodeError, OSError) as exc:
            print(f"WARNING: existing {OUTPUT_PATH.name} unreadable ({exc}) — rebuilding from scratch", flush=True)
            existing = {}

    # Pageview data lags ~1 day; end at yesterday.
    end = date.today() - timedelta(days=1)
    full_start = end - timedelta(days=WINDOW_DAYS - 1)
    merge_start = end - timedelta(days=MERGE_DAYS - 1)
    all_dates = [(full_start + timedelta(days=i)).isoformat()
                 for i in range(WINDOW_DAYS)]

    def stored_mean(qid: str, lang: str) -> float | None:
        prev = existing.get(qid, {}).get(lang)
        if not prev:
            return None
        vals = [v for v in prev["values"] if v is not None]
        return (sum(vals) / len(vals)) if vals else 0.0

    # Build the work list, then fetch in parallel. Dormant series (see note
    # at top) are skipped on weekdays: their stored history is carried
    # forward untouched and they refresh on the Sunday full pass.
    jobs: list[tuple[str, str, str, bool]] = []   # (qid, lang, title, incremental)
    carried: list[tuple[str, str]] = []
    for t in topics:
        for lang, title in t["titles"].items():
            m = stored_mean(t["qid"], lang)
            incremental = m is not None
            if incremental and not FULL_REFRESH and m < DORMANT_MEAN:
                carried.append((t["qid"], lang))
                continue
            jobs.append((t["qid"], lang, title, incremental))
    total = len(jobs)
    print(f"Fetching {total} series "
          f"({'full Sunday refresh' if FULL_REFRESH else f'{len(carried)} dormant series carried forward'})",
          flush=True)

    def run_job(job: tuple[str, str, str, bool]) -> tuple[str, str, dict[str, int], bool]:
        qid, lang, title, incremental = job
        start = merge_start if incremental else full_start
        return qid, lang, fetch_series(lang, title, start, end), incremental

    def write_output(series: dict) -> None:
        # ATOMIC write: dump to a temp file, then os.replace() — so a timeout
        # kill mid-write can never leave a half-written (corrupt) JSON behind.
        OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
        tmp = OUTPUT_PATH.with_suffix(".json.tmp")
        tmp.write_text(
            json.dumps({
                "source": "Wikimedia Pageviews API (user traffic, all access methods)",
                "license": "CC0 / public API",
                "signal_type": "demand (what people look up)",
                "updated": end.isoformat(),
                "window_days": WINDOW_DAYS,
                "series": series,
            }, separators=(",", ":"), ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        os.replace(tmp, OUTPUT_PATH)

    # IMPORTANT: seed series_out from `existing`, not empty dicts. If this run
    # gets killed by the workflow timeout partway through (observed in
    # practice — shared CI IPs get rate-limited harder than a home
    # connection), any topic not yet reached this run still keeps its
    # last-known-good data instead of vanishing. Every checkpoint and the
    # final output are therefore monotonically >= the prior state, never a
    # regression, however early the process is interrupted.
    series_out: dict[str, dict[str, dict]] = {
        t["qid"]: dict(existing.get(t["qid"], {})) for t in topics
    }
    n_fetched = n_backfilled = n_done = 0
    with ThreadPoolExecutor(max_workers=WORKERS) as pool:
        futures = [pool.submit(run_job, j) for j in jobs]
        for fut in as_completed(futures):
            qid, lang, fresh, incremental = fut.result()
            if incremental:
                prev = existing[qid][lang]
                pstart = datetime.strptime(prev["start"], "%Y-%m-%d").date()
                prev_map = {
                    (pstart + timedelta(days=i)).isoformat(): v
                    for i, v in enumerate(prev["values"])
                    if v is not None
                }
                prev_map.update(fresh)
                n_fetched += 1
            else:
                prev_map = fresh
                n_backfilled += 1

            values = [prev_map.get(d) for d in all_dates]  # None = no data that day
            series_out[qid][lang] = {"start": all_dates[0], "values": values}

            n_done += 1
            if n_done % 100 == 0:
                print(f"  …{n_done}/{total} series", flush=True)
            if n_done % 250 == 0:
                # checkpoint: safe at any interruption point (see note above)
                write_output(series_out)

    # carry dormant series forward unchanged, re-aligned to the new window
    for qid, lang in carried:
        prev = existing[qid][lang]
        pstart = datetime.strptime(prev["start"], "%Y-%m-%d").date()
        prev_map = {
            (pstart + timedelta(days=i)).isoformat(): v
            for i, v in enumerate(prev["values"])
            if v is not None
        }
        series_out[qid][lang] = {
            "start": all_dates[0],
            "values": [prev_map.get(dd) for dd in all_dates],
        }

    write_output(series_out)
    size_mb = OUTPUT_PATH.stat().st_size / 1e6
    print(f"Wrote {OUTPUT_PATH} ({size_mb:.1f} MB) — "
          f"{n_backfilled} backfilled, {n_fetched} updated series.")


if __name__ == "__main__":
    sys.exit(main())
