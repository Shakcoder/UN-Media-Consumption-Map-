#!/usr/bin/env python3
"""
fetch_trends_wikipedia.py — daily Wikipedia pageviews connector.

For every topic in data/topics.json and every tracked language edition,
fetches daily pageview counts from the Wikimedia Pageviews REST API
(free, no key) and maintains a rolling window in
data/trends/wiki_pageviews.json.

First run backfills WINDOW_DAYS of history (~10-15 min for ~3,100 series).
Subsequent daily runs fetch the last MERGE_DAYS days per series — or back to
the oldest day that series is still missing, so days lost to a throttled run
are filled in on a later one — and merge (a few minutes).

Wikipedia pageviews measure information DEMAND (what people look up),
per language edition — country attribution happens later in
compute_topic_intelligence.py via documented language→country weights.

SHARDING (added 2026-08-10). Wikimedia's per-IP budget for anonymous CI
clients proved smaller than one runner can spend: the single-job fetch hit
its 85-minute cap every day and ~1,150 of ~3,100 series were stale and
climbing. The fix is to run several copies of this script in PARALLEL
GitHub jobs — each runner gets its own IP, so each gets its own budget:

    --shard K N     fetch only every Nth series (K of N, 1-based), taken
                    round-robin from the stalest-first work list, so each
                    shard is itself stalest-first and the staleness backlog
                    is spread evenly. Writes ONLY the series it fetched
                    (a partial file, marked "partial": true) to --out.
    --out PATH      where a shard writes its partial output.
    --merge P1 P2…  assemble mode: overlay the shard partials onto the
                    previous full snapshot, re-align every series to the
                    current window, and write the real wiki_pageviews.json.
                    Missing/empty partials are skipped with a warning —
                    a lost shard costs freshness, never data.
    --limit N       TESTING ONLY: cap the work list at N series.

Run with no flags and it behaves exactly as before (single-process full
fetch) — that is still the right way to run it by hand.
"""

from __future__ import annotations

import argparse
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


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Wikipedia pageviews fetcher")
    p.add_argument("--shard", nargs=2, type=int, metavar=("K", "N"),
                   help="fetch shard K of N (1-based) and write a partial file")
    p.add_argument("--out", type=Path,
                   help="output path for a shard's partial file")
    p.add_argument("--merge", nargs="*", type=Path, metavar="PARTIAL",
                   help="merge shard partials into the full snapshot and exit")
    p.add_argument("--limit", type=int,
                   help="TESTING ONLY: cap the work list at N series")
    return p.parse_args()


def current_window() -> tuple[date, date, list[str]]:
    """(full_start, end, all_dates) for today's run — shared by fetch+merge."""
    end = date.today() - timedelta(days=1)   # pageview data lags ~1 day
    full_start = end - timedelta(days=WINDOW_DAYS - 1)
    all_dates = [(full_start + timedelta(days=i)).isoformat()
                 for i in range(WINDOW_DAYS)]
    return full_start, end, all_dates


def realign(entry: dict, all_dates: list[str]) -> dict:
    """Re-key one stored series onto the current window's date axis."""
    pstart = datetime.strptime(entry["start"], "%Y-%m-%d").date()
    prev_map = {
        (pstart + timedelta(days=i)).isoformat(): v
        for i, v in enumerate(entry["values"])
        if v is not None
    }
    return {"start": all_dates[0], "values": [prev_map.get(d) for d in all_dates]}


def merge_partials(partials: list[Path]) -> None:
    """Overlay shard partials onto the previous snapshot and write the result.

    Each series was fetched by exactly one shard (round-robin partition), so
    the overlay is a plain union — no conflicts are possible. Series no shard
    reached (dormant weekday carries, or a shard that died early) keep their
    previous data, re-aligned to today's window: the same monotonic
    never-lose-data guarantee the single-process path has always had.
    """
    _, end, all_dates = current_window()

    existing: dict = {}
    if OUTPUT_PATH.exists():
        try:
            existing = json.loads(OUTPUT_PATH.read_text(encoding="utf-8")).get("series", {})
        except (json.JSONDecodeError, OSError) as exc:
            print(f"WARNING: existing {OUTPUT_PATH.name} unreadable ({exc}) — "
                  f"merging shards onto an empty base", flush=True)

    merged: dict[str, dict[str, dict]] = {
        qid: {lang: realign(e, all_dates) for lang, e in langs.items()}
        for qid, langs in existing.items()
    }

    n_overlaid = 0
    for path in partials:
        if not path.exists() or path.stat().st_size == 0:
            print(f"WARNING: shard partial {path} missing or empty — skipped "
                  f"(its series keep yesterday's data)", flush=True)
            continue
        try:
            part = json.loads(path.read_text(encoding="utf-8")).get("series", {})
        except (json.JSONDecodeError, OSError) as exc:
            print(f"WARNING: shard partial {path} unreadable ({exc}) — skipped",
                  flush=True)
            continue
        for qid, langs in part.items():
            for lang, entry in langs.items():
                merged.setdefault(qid, {})[lang] = realign(entry, all_dates)
                n_overlaid += 1

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    tmp = OUTPUT_PATH.with_suffix(".json.tmp")
    tmp.write_text(
        json.dumps({
            "source": "Wikimedia Pageviews API (user traffic, all access methods)",
            "license": "CC0 / public API",
            "signal_type": "demand (what people look up)",
            "updated": end.isoformat(),
            "window_days": WINDOW_DAYS,
            "series": merged,
        }, separators=(",", ":"), ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    os.replace(tmp, OUTPUT_PATH)
    n_series = sum(len(v) for v in merged.values())
    print(f"Merged {len(partials)} partial(s): {n_overlaid} series refreshed, "
          f"{n_series} total in {OUTPUT_PATH}")


def main(args: argparse.Namespace) -> None:
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
    full_start, end, all_dates = current_window()
    merge_start = end - timedelta(days=MERGE_DAYS - 1)

    def stored_mean(qid: str, lang: str) -> float | None:
        prev = existing.get(qid, {}).get(lang)
        if not prev:
            return None
        vals = [v for v in prev["values"] if v is not None]
        # An ALL-None series means "never successfully fetched", not
        # "zero-traffic article" — returning 0.0 here classified 29 real,
        # above-floor series (e.g. en 'Vocational education' at ~187
        # views/day upstream) as dormant, so weekday runs skipped them
        # forever and the hole self-perpetuated (2026-08-11 audit). None
        # sends them back through the non-incremental path, where
        # stalest-first ordering retries them at the front of every run.
        return (sum(vals) / len(vals)) if vals else None

    def stored_last_data(qid: str, lang: str) -> date | None:
        """Newest day this series actually holds data for (None = never fetched)."""
        prev = existing.get(qid, {}).get(lang)
        if not prev:
            return None
        pstart = datetime.strptime(prev["start"], "%Y-%m-%d").date()
        idx = [i for i, v in enumerate(prev["values"]) if v is not None]
        return pstart + timedelta(days=idx[-1]) if idx else None

    def fetch_start(qid: str, lang: str) -> date:
        """
        Oldest day to ask for when refreshing a series that already has data.

        A fixed MERGE_DAYS window can only ever heal the last few days: a day
        missed because Wikimedia was throttling falls out of that window
        tomorrow, and then nothing asks for it again — the hole simply rides
        the rolling window for four months. Since the Pageviews API returns
        any date range in ONE request, starting at the oldest day this series
        is missing costs no extra requests and makes an interrupted run
        self-healing.

        A day on which the article genuinely had no traffic is returned by the
        API as nothing at all, so it is indistinguishable from a missed day;
        such series just re-request their whole window each run, which is
        still a single request.
        """
        prev = existing.get(qid, {}).get(lang)
        if not prev:
            return full_start
        pstart = datetime.strptime(prev["start"], "%Y-%m-%d").date()
        have = {pstart + timedelta(days=i)
                for i, v in enumerate(prev["values"]) if v is not None}
        for i in range(WINDOW_DAYS):
            day = full_start + timedelta(days=i)
            if day not in have:
                return min(day, merge_start)
        return merge_start

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

    # STALEST FIRST (added 2026-07-26). Wikimedia rate-limits shared CI IPs
    # hard enough that this step regularly hits its 85-minute cap around
    # series ~800 of ~3,100. Because the work list was previously built in
    # registry order, the SAME leading series were refreshed every day and
    # the tail was never reached — by 2026-07-26 two-thirds of stored series
    # had been frozen since 2026-07-05 while the file still advertised
    # itself as updated daily.
    #
    # Ordering by "oldest data first" makes a truncated run self-healing:
    # whatever the timeout cuts off is exactly what runs first tomorrow, so
    # coverage rotates instead of starving. Never-fetched series (None) sort
    # first so a newly added topic is backfilled promptly.
    _EPOCH = date(1970, 1, 1)
    jobs.sort(key=lambda j: (stored_last_data(j[0], j[1]) or _EPOCH, j[0], j[1]))

    # Shard filter (see docstring): a round-robin slice of the stalest-first
    # list, so each shard is itself stalest-first and the backlog is spread
    # evenly across the parallel runners.
    partial_mode = bool(args.shard or args.out)
    if args.shard:
        k, n = args.shard
        if not (1 <= k <= n):
            sys.exit(f"--shard {k} {n}: K must be within 1..N")
        jobs = jobs[k - 1::n]
    if args.limit:
        jobs = jobs[:args.limit]

    total = len(jobs)
    oldest = stored_last_data(jobs[0][0], jobs[0][1]) if jobs else None
    shard_note = f"shard {args.shard[0]}/{args.shard[1]}, " if args.shard else ""
    print(f"Fetching {total} series ({shard_note}stalest first)"
          f"{f' (oldest stored data: {oldest})' if oldest else ''} "
          f"({'full Sunday refresh' if FULL_REFRESH else f'{len(carried)} dormant series carried forward'})",
          flush=True)

    def run_job(job: tuple[str, str, str, bool]) -> tuple[str, str, dict[str, int], bool]:
        qid, lang, title, incremental = job
        start = fetch_start(qid, lang) if incremental else full_start
        return qid, lang, fetch_series(lang, title, start, end), incremental

    out_path = args.out or OUTPUT_PATH

    def write_output(series: dict) -> None:
        # ATOMIC write: dump to a temp file, then os.replace() — so a timeout
        # kill mid-write can never leave a half-written (corrupt) JSON behind.
        out_path.parent.mkdir(parents=True, exist_ok=True)
        tmp = out_path.with_suffix(".json.tmp")
        doc = {
            "source": "Wikimedia Pageviews API (user traffic, all access methods)",
            "license": "CC0 / public API",
            "signal_type": "demand (what people look up)",
            "updated": end.isoformat(),
            "window_days": WINDOW_DAYS,
            "series": series,
        }
        if partial_mode:
            # A shard's file holds ONLY what it fetched this run — it must be
            # merged (--merge) onto the previous snapshot, never used directly.
            doc["partial"] = True
        tmp.write_text(
            json.dumps(doc, separators=(",", ":"), ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        os.replace(tmp, out_path)

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
    # In shard mode only the series THIS shard fetched are written out —
    # the merge step overlays them onto the previous snapshot. (Writing the
    # full seeded map from every shard would have each shard overwrite the
    # others' fresh series with stale copies.)
    fetched_out: dict[str, dict[str, dict]] = {}
    target = fetched_out if partial_mode else series_out

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
            entry = {"start": all_dates[0], "values": values}
            series_out[qid][lang] = entry
            if partial_mode:
                fetched_out.setdefault(qid, {})[lang] = entry

            n_done += 1
            if n_done % 100 == 0:
                print(f"  …{n_done}/{total} series", flush=True)
            if n_done % 250 == 0:
                # checkpoint: safe at any interruption point (see note above)
                write_output(target)

    if not partial_mode:
        # carry dormant series forward unchanged, re-aligned to the new window
        # (in shard mode the merge step does this for every untouched series)
        for qid, lang in carried:
            series_out[qid][lang] = realign(existing[qid][lang], all_dates)

    write_output(target)
    size_mb = out_path.stat().st_size / 1e6
    print(f"Wrote {out_path} ({size_mb:.1f} MB) — "
          f"{n_backfilled} backfilled, {n_fetched} updated series.")


if __name__ == "__main__":
    _args = parse_args()
    if _args.merge is not None:
        sys.exit(merge_partials(_args.merge))
    sys.exit(main(_args))
