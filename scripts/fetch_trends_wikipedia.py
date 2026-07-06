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
        try:
            resp = _session().get(url, timeout=REQ_TIMEOUT)
            if resp.status_code == 404:    # no pageview data for this article
                return {}
            if resp.status_code == 429:    # throttled — back off and retry
                time.sleep(5 * (attempt + 1))
                continue
            resp.raise_for_status()
            data = resp.json()
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
        existing = json.loads(OUTPUT_PATH.read_text(encoding="utf-8")).get("series", {})

    # Pageview data lags ~1 day; end at yesterday.
    end = date.today() - timedelta(days=1)
    full_start = end - timedelta(days=WINDOW_DAYS - 1)
    merge_start = end - timedelta(days=MERGE_DAYS - 1)
    all_dates = [(full_start + timedelta(days=i)).isoformat()
                 for i in range(WINDOW_DAYS)]

    # Build the full work list, then fetch in parallel. A stalled socket
    # only blocks one worker for REQ_TIMEOUT seconds instead of the run.
    jobs: list[tuple[str, str, str, bool]] = []   # (qid, lang, title, incremental)
    for t in topics:
        for lang, title in t["titles"].items():
            incremental = bool(existing.get(t["qid"], {}).get(lang))
            jobs.append((t["qid"], lang, title, incremental))
    total = len(jobs)

    def run_job(job: tuple[str, str, str, bool]) -> tuple[str, str, dict[str, int], bool]:
        qid, lang, title, incremental = job
        start = merge_start if incremental else full_start
        return qid, lang, fetch_series(lang, title, start, end), incremental

    def write_output(series: dict) -> None:
        OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
        OUTPUT_PATH.write_text(
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

    series_out: dict[str, dict[str, dict]] = {t["qid"]: {} for t in topics}
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
            if n_done % 500 == 0:
                # checkpoint: completed series survive an interrupted run;
                # a rerun fetches the rest incrementally
                write_output({q: l for q, l in series_out.items() if l})

    write_output(series_out)
    size_mb = OUTPUT_PATH.stat().st_size / 1e6
    print(f"Wrote {OUTPUT_PATH} ({size_mb:.1f} MB) — "
          f"{n_backfilled} backfilled, {n_fetched} updated series.")


if __name__ == "__main__":
    sys.exit(main())
