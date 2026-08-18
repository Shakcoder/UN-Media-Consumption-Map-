#!/usr/bin/env python3
"""
update_attention_archive.py — long-term GLOBAL attention archive.

data/trends/wiki_pageviews.json stores 120 days of per-language daily
pageviews; the Topic Explorer's custom trend windows (topics.html, RANGE
VIEW block) can therefore reach back only ~4 months. This script maintains
data/trends/attention_archive.json: for every registry topic, ONE daily
integer — the topic's GLOBAL attention (its tracked language editions'
Wikipedia pageviews summed, user traffic, all access methods) — from
2024-01-01 to the newest published day. No per-language detail is stored;
that (and the access-method anomaly screening) exists only inside the live
120-day file, and the page says so.

TWO SECTIONS, ONE AXIS. Every topic's array runs day by day from
_meta.start to _meta.end, and the file is honest about the fact that the
two ends of that axis have different provenance:

  * the LIVE section (days from _meta.live_boundary on) is DERIVED from
    wiki_pageviews.json on every run: per calendar day, the sum of the
    non-quarantined series that reported it, null when none did. Because
    it is re-derived rather than fetched, it is equal BY CONSTRUCTION to
    what topics.html can compute from the live file — and a change in the
    anomaly gate's quarantine verdicts propagates into it the same day.
    The equality is still verified here and in validate_atlas.py, because
    a guarantee nobody checks is a guarantee that quietly dies.
  * the FROZEN section (days before live_boundary) was fetched once from
    the Wikimedia per-article API (--backfill) using the registry titles
    current on the build day, minus the series under quarantine on that
    day. As the live window slides forward, each day crossing out of it
    freezes with the last verdicts applied while it was inside. History
    is never refetched behind the boundary; a day the API had no data for
    stays null rather than being estimated.

MODES
  (no flags)   daily append — no network. Extends the axis to the live
               file's 'updated' date and re-derives the whole live-window
               section. Runs in trend-engine.yml right after the shard
               merge, so the two files always publish in lockstep.
  --backfill   the one-time (or rare re-run) history fetch: one request
               per topic-language pair covers the whole span, ~3,400
               requests total, throttled the way fetch_trends_wikipedia.py
               throttles (adaptive backoff on 429, few workers, honest
               User-Agent). Checkpoints as it goes so an interrupted run
               resumes instead of re-spending the request budget.

               Measured 2026-08-18: one residential IP gets roughly 500
               anonymous requests per hour out of this endpoint before
               every further request 429s — a full local backfill is a
               ~7-hour trickle no politeness setting can fix. So the
               fetch shards across GitHub runners exactly like the daily
               pageviews fetch does (each runner = its own IP = its own
               budget). Runner IPs are shared, so a shard may inherit a
               part-spent budget: failed pairs retry in rounds with
               growing pauses while the bucket refills. Via
               attention-archive-backfill.yml:
    --shard K N      fetch only every Nth pair (K of N, 1-based, from the
                     deterministically sorted pair list), writing the
                     per-pair checkpoint only — combine with --fetch-only.
    --fetch-only     stop after fetching (the checkpoint IS the output);
                     exits non-zero if any pair still failed after the
                     retry round, so a starved shard shows red.
    --assemble-from P1 P2 ...
                     no fetching: load shard checkpoints, require every
                     non-quarantined registry pair present (an incomplete
                     backfill aborts rather than silently under-counting
                     history), then assemble, golden-check and write the
                     archive exactly as the local path would.

The golden consistency check (also enforced by validate_atlas.py and
mirrored in the browser as __archiveGoldenTest() in topics.html): for
every day both files cover, the archive's value for a topic equals the sum
of that topic's non-quarantined series in wiki_pageviews.json — cell for
cell, null for null.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
import time
import urllib.parse
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, datetime, timedelta
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
REGISTRY_PATH = REPO_ROOT / "data" / "topics.json"
WIKI_PATH = REPO_ROOT / "data" / "trends" / "wiki_pageviews.json"
ARCHIVE_PATH = REPO_ROOT / "data" / "trends" / "attention_archive.json"

ARCHIVE_START = date(2024, 1, 1)   # the axis origin; never moves on append

# Same client discipline as fetch_trends_wikipedia.py — identify ourselves,
# few workers, back off on any 429 — but tuned for what this run IS: a
# one-off from a residential IP, not a daily shared-CI grind. Measured
# 2026-08-18 before tuning: the API happily serves this IP ~5 sequential
# requests per second, yet the daily fetcher's burst-then-backoff throttle
# (4 workers slamming at once, Retry-After honored up to 60s, gentle 0.9x
# decay) pinned itself near its ceiling after one early 429 wave and crawled
# at ~3 pairs/minute — a 19-hour self-inflicted backfill. The fix is to not
# burst in the first place: a token scheduler spaces request STARTS evenly
# (~7/s aggregate, whole run ~10 min), and the adaptive delay on top of it
# is honored per-request but capped and quick to decay.
USER_AGENT = "UN-Media-Atlas/1.0 (Global Content Intelligence Platform; research)"
WORKERS = 4
REQ_TIMEOUT = (5, 30)   # read timeout is generous: one response carries ~960 days
PACE_SECONDS = 0.14     # spacing between request starts, all workers combined

_throttle_lock = __import__("threading").Lock()
_throttle_delay = 0.0
_next_slot = 0.0
N_429 = 0        # visibility: progress lines report these, so a throttled
N_ERR = 0        # run says so instead of just being mysteriously slow


def _pace_wait() -> None:
    """Even request spacing across all workers (the anti-burst gate)."""
    global _next_slot
    with _throttle_lock:
        now = time.monotonic()
        slot = max(now, _next_slot)
        _next_slot = slot + PACE_SECONDS
    if slot > now:
        time.sleep(slot - now)


def _throttle_wait() -> None:
    _pace_wait()
    with _throttle_lock:
        d = _throttle_delay
    if d > 0:
        time.sleep(d)


def _throttle_hit(retry_after: float | None) -> None:
    global _throttle_delay, N_429
    with _throttle_lock:
        N_429 += 1
        _throttle_delay = min(max(_throttle_delay * 2, 1.0), 8.0)
        if retry_after:
            _throttle_delay = max(_throttle_delay, min(retry_after, 15.0))


def _throttle_ok() -> None:
    global _throttle_delay
    with _throttle_lock:
        _throttle_delay = max(_throttle_delay * 0.7 - 0.01, 0.0)


_session_store: dict[int, object] = {}


def _session():
    import threading
    import requests
    tid = threading.get_ident()
    if tid not in _session_store:
        s = requests.Session()
        s.headers["User-Agent"] = USER_AGENT
        _session_store[tid] = s
    return _session_store[tid]


def fetch_pair(lang: str, title: str, start: date, end: date) -> tuple[dict[str, int], str]:
    """One request for one article's whole span. Returns ({date: views}, status)
    with status 'ok', 'none' (clean 404 — the API holds no rows for this
    title, e.g. the article is newer than the span or was renamed), or
    'error' (network/throttle exhaustion — the caller decides; an error is
    NOT an empty series and must never be stored as one)."""
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
            if resp.status_code == 404:
                _throttle_ok()
                return {}, "none"
            if resp.status_code == 429:
                ra = resp.headers.get("Retry-After")
                _throttle_hit(float(ra) if ra and ra.isdigit() else None)
                time.sleep(2 * (attempt + 1))
                continue
            resp.raise_for_status()
            data = resp.json()
            _throttle_ok()
            return {
                f"{it['timestamp'][:4]}-{it['timestamp'][4:6]}-{it['timestamp'][6:8]}":
                    int(it["views"])
                for it in data.get("items", [])
            }, "ok"
        except Exception:
            if attempt == 2:
                return {}, "error"
            time.sleep(1 + attempt)
    return {}, "error"


# ---------------------------------------------------------------------------
# Shared derivation: what the live file says each topic's global day-sums are.
# This is THE definition the golden check holds the archive to.
# ---------------------------------------------------------------------------

def live_day_sums(wiki: dict, registry_qids: set[str]) -> dict[str, dict[str, int]]:
    """{qid: {iso_date: int}} — per calendar day, the sum of the topic's
    non-quarantined series values in wiki_pageviews.json. Days no series
    reported are simply absent (the archive stores them as null). Summed by
    DATE, never by array index: series start on different days."""
    quarantine = wiki.get("quarantine") or {}
    out: dict[str, dict[str, int]] = {}
    for qid, langs in wiki.get("series", {}).items():
        if qid not in registry_qids:
            continue
        q_langs = quarantine.get(qid) or {}
        sums: dict[str, int] = {}
        for lang, entry in langs.items():
            if lang in q_langs:
                continue
            start = datetime.strptime(entry["start"], "%Y-%m-%d").date()
            for i, v in enumerate(entry["values"]):
                if v is not None:
                    d = (start + timedelta(days=i)).isoformat()
                    sums[d] = sums.get(d, 0) + v
        out[qid] = sums
    return out


def golden_check(archive: dict, wiki: dict, registry_qids: set[str]) -> list[str]:
    """Cell-for-cell equality on every day both files cover. Returns problem
    descriptions (empty = the guarantee holds)."""
    problems: list[str] = []
    meta = archive.get("_meta") or {}
    try:
        a_start = date.fromisoformat(meta["start"])
        a_end = date.fromisoformat(meta["end"])
        w_end = date.fromisoformat(wiki["updated"])
    except (KeyError, ValueError) as exc:
        return [f"unusable date metadata ({exc})"]
    w_start = w_end - timedelta(days=int(wiki.get("window_days") or 120) - 1)
    lo, hi = max(a_start, w_start), min(a_end, w_end)
    if lo > hi:
        return ["archive and live file share no days at all"]
    expected = live_day_sums(wiki, registry_qids)
    a_topics = archive.get("topics") or {}
    if set(a_topics) != set(expected):
        only_a = sorted(set(a_topics) - set(expected))[:5]
        only_w = sorted(set(expected) - set(a_topics))[:5]
        problems.append(f"topic sets differ (archive-only {only_a}, live-only {only_w})")
    n_days = (hi - lo).days + 1
    for qid in sorted(set(a_topics) & set(expected)):
        arr = a_topics[qid]
        base = (lo - a_start).days
        for k in range(n_days):
            day = (lo + timedelta(days=k)).isoformat()
            have = arr[base + k] if 0 <= base + k < len(arr) else "OOB"
            want = expected[qid].get(day)
            if have != want:
                problems.append(f"{qid} {day}: archive {have!r} != live sum {want!r}")
                if len(problems) > 20:
                    problems.append("… further mismatches suppressed")
                    return problems
    return problems


def atomic_write(doc: dict) -> None:
    ARCHIVE_PATH.parent.mkdir(parents=True, exist_ok=True)
    tmp = ARCHIVE_PATH.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(doc, separators=(",", ":"), ensure_ascii=False) + "\n",
                   encoding="utf-8")
    os.replace(tmp, ARCHIVE_PATH)


def build_meta(start: date, end: date, live_start: date, built: str,
               excluded: list[str], n_topics: int) -> dict:
    return {
        "what": ("Per-topic GLOBAL daily attention: the topic's tracked Wikipedia "
                 "language editions summed to one integer per day (views/day, "
                 "user traffic, all access methods). No per-language detail is "
                 "stored here; that exists only in wiki_pageviews.json's live "
                 f"{int((end - live_start).days) + 1}-day window."),
        "source": "Wikimedia Pageviews per-article REST API",
        "license": "CC0 / public API",
        "signal_type": "demand (what people look up)",
        "start": start.isoformat(),
        "end": end.isoformat(),
        "built": built,
        "updated": date.today().isoformat(),
        "live_boundary": live_start.isoformat(),
        "sections": ("Days from live_boundary on are re-derived on every trend-engine "
                     "run as the per-day sum of the topic's non-quarantined series in "
                     "wiki_pageviews.json (equal to that file cell for cell — enforced "
                     "by validate_atlas.py). Days before live_boundary were fetched "
                     "once on the build date and are never refetched; each day that "
                     "slides out of the live window freezes with the last quarantine "
                     "verdicts applied while it was inside."),
        "caveats": [
            "Historical figures use the registry titles current on the build date: "
            "they measure attention to each topic's CURRENT article, so a page "
            "renamed since 2024 shows little or no data under its old name's days.",
            "The access-method anomaly gate (quarantine) has existed since "
            "2026-08-15; data before then was never screened by it and is "
            "published as fetched.",
            "A day's value sums whichever tracked editions reported that day; "
            "null means no tracked edition reported it (an API gap, never an "
            "estimate).",
            "Series under quarantine on the build date were excluded from the "
            "frozen section for their whole span (build_excluded_series below).",
        ],
        "build_excluded_series": excluded,
        "topics": n_topics,
        "days": (end - start).days + 1,
    }


def load_inputs() -> tuple[dict, dict, list]:
    registry = json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))
    wiki = json.loads(WIKI_PATH.read_text(encoding="utf-8"))
    if wiki.get("partial"):
        sys.exit("wiki_pageviews.json is a partial shard file — refusing to derive from it")
    return registry, wiki, registry["topics"]


# ---------------------------------------------------------------------------
# Daily append — no network. Runs in CI after the shard merge.
# ---------------------------------------------------------------------------

def append_mode() -> None:
    if not ARCHIVE_PATH.exists():
        sys.exit(f"{ARCHIVE_PATH} does not exist — run --backfill once to create it")
    registry, wiki, topics = load_inputs()
    archive = json.loads(ARCHIVE_PATH.read_text(encoding="utf-8"))
    meta = archive.get("_meta") or {}
    a_start = date.fromisoformat(meta["start"])
    a_end = date.fromisoformat(meta["end"])
    w_end = date.fromisoformat(wiki["updated"])
    w_start = w_end - timedelta(days=int(wiki.get("window_days") or 120) - 1)
    if w_end < a_end:
        sys.exit(f"live file ends {w_end}, archive already ends {a_end} — the live "
                 f"window moved backwards; refusing to truncate history")
    if w_end > a_end + timedelta(days=2):
        # gap days (engine down for a while) become nulls below — say so
        print(f"note: archive ends {a_end}, live file {w_end} — the days between "
              f"were never derived while current and will be filled from the live "
              f"window where it still covers them", flush=True)

    registry_qids = {t["qid"] for t in topics}
    expected = live_day_sums(wiki, registry_qids)
    n_days = (w_end - a_start).days + 1
    old = archive.get("topics") or {}

    dropped = sorted(set(old) - set(expected))
    added = sorted(set(expected) - set(old))
    for qid in dropped:
        print(f"note: {qid} left the registry/live file — its archive history is "
              f"removed with it (registry membership is the archive's universe)", flush=True)
    for qid in added:
        print(f"note: {qid} is new — archived from {w_start} on; days before that "
              f"stay null until a --backfill run fetches its history", flush=True)

    new_topics: dict[str, list] = {}
    for qid in sorted(expected):
        arr = list(old.get(qid) or [])
        arr += [None] * (n_days - len(arr))
        arr = arr[:n_days]
        # re-derive the whole live-window section from today's live file, so
        # quarantine verdicts (new, lifted, re-decided) propagate same-day
        base = (w_start - a_start).days
        sums = expected[qid]
        for k in range((w_end - w_start).days + 1):
            if base + k >= 0:
                arr[base + k] = sums.get((w_start + timedelta(days=k)).isoformat())
        new_topics[qid] = arr

    doc = {
        "_meta": build_meta(a_start, w_end, w_start, meta.get("built", "unknown"),
                            meta.get("build_excluded_series") or [], len(new_topics)),
        "topics": new_topics,
    }
    problems = golden_check(doc, wiki, registry_qids)
    if problems:
        for p in problems[:10]:
            print(f"GOLDEN-CHECK FAIL: {p}", flush=True)
        sys.exit("append aborted — the derived archive disagrees with its own source")
    atomic_write(doc)
    size_kb = ARCHIVE_PATH.stat().st_size / 1e3
    print(f"Archive appended: {meta['end']} -> {w_end} ({len(new_topics)} topics, "
          f"{n_days} days, {size_kb:.0f} KB; +{len(added)}/-{len(dropped)} topics). "
          f"Golden check passed.", flush=True)


# ---------------------------------------------------------------------------
# One-time backfill — the only mode that talks to the network.
# ---------------------------------------------------------------------------

def build_jobs(topics: list, quarantine: dict) -> list[tuple[str, str, str]]:
    """Every non-quarantined (qid, lang, title) pair, in a DETERMINISTIC
    order — the shard slices depend on every runner computing the same list."""
    jobs = [(t["qid"], lang, title)
            for t in topics
            for lang, title in t["titles"].items()
            if lang not in (quarantine.get(t["qid"]) or {})]
    jobs.sort(key=lambda j: (j[0], j[1]))
    return jobs


def load_checkpoint(path: Path, span: str, strict: bool = False) -> dict[str, dict]:
    """{qid/lang: {"t": title, "d": {date: views}, "s": status}} from a prior
    (possibly interrupted) run. A torn last line (kill mid-write) is dropped
    silently — that one pair is simply refetched. strict=True (assemble)
    refuses a checkpoint whose span differs instead of ignoring it."""
    done: dict[str, dict] = {}
    if not path.exists():
        if strict:
            sys.exit(f"ABORT: shard checkpoint {path} does not exist")
        return done
    with path.open(encoding="utf-8") as fh:
        header = fh.readline()
        try:
            ck_span = (json.loads(header) or {}).get("span")
        except json.JSONDecodeError:
            ck_span = None
        if ck_span != span:
            if strict:
                sys.exit(f"ABORT: {path} covers span {ck_span!r}, this run needs "
                         f"{span!r} — shards and assemble must share one snapshot")
            print("checkpoint is for a different span — starting fresh", flush=True)
            return {}
        for line in fh:
            try:
                rec = json.loads(line)
                done[rec["k"]] = rec
            except (json.JSONDecodeError, KeyError):
                continue
    return done


def backfill_fetch(checkpoint: Path, workers: int,
                   shard: tuple[int, int] | None) -> bool:
    """Fetch this shard's pairs into the checkpoint file. Returns True when
    every pair ended ok/none, False when failures remain after the retry."""
    registry, wiki, topics = load_inputs()
    quarantine = wiki.get("quarantine") or {}
    w_end = date.fromisoformat(wiki["updated"])
    span = f"{ARCHIVE_START.isoformat()}..{w_end.isoformat()}"

    excluded = sorted(f"{qid}/{lang}" for qid, langs in quarantine.items()
                      for lang in langs)
    jobs = build_jobs(topics, quarantine)
    shard_note = ""
    if shard:
        k, n = shard
        if not (1 <= k <= n):
            sys.exit(f"--shard {k} {n}: K must be within 1..N")
        jobs = jobs[k - 1::n]
        shard_note = f"shard {k}/{n}, "
    print(f"Backfill {span}: {len(jobs)} topic-language pairs ({shard_note}"
          f"{len(excluded)} quarantined series excluded: {', '.join(excluded)})",
          flush=True)

    done = load_checkpoint(checkpoint, span)
    reusable = {k: r for k, r in done.items() if r.get("s") in ("ok", "none")}
    todo = [(q, l, t) for q, l, t in jobs
            if not (reusable.get(f"{q}/{l}", {}).get("t") == t)]
    if len(todo) < len(jobs):
        print(f"  checkpoint: {len(jobs) - len(todo)} pairs reused, {len(todo)} to fetch",
              flush=True)
    checkpoint.parent.mkdir(parents=True, exist_ok=True)
    if not checkpoint.exists() or not done:
        checkpoint.write_text(json.dumps({"span": span}) + "\n", encoding="utf-8")

    ck_lock = __import__("threading").Lock()
    failures: list[tuple[str, str, str]] = []
    t0 = time.time()

    def run(job: tuple[str, str, str]) -> None:
        global N_ERR
        qid, lang, title = job
        data, status = fetch_pair(lang, title, ARCHIVE_START, w_end)
        rec = {"k": f"{qid}/{lang}", "t": title, "s": status, "d": data}
        if status == "error":
            with _throttle_lock:
                N_ERR += 1
            failures.append(job)
            return
        with ck_lock:
            with checkpoint.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
            reusable[rec["k"]] = rec

    # PATIENT RETRY ROUNDS (2026-08-18, learned from run 1): a shard shares
    # its runner IP's hourly request budget with whoever else used that IP —
    # ~28 pairs per shard still 429-starved after a single 30s-pause retry.
    # The budget REFILLS over minutes, so failed pairs are retried in rounds
    # with growing pauses (the adaptive delay is reset after each pause —
    # a refilled bucket deserves a fresh start). The wall-clock guard leaves
    # room for the artifact upload inside the job's 50-minute timeout.
    global _throttle_delay
    pauses = [30, 60, 120, 240, 300, 300]
    round_no = 0
    while todo:
        round_no += 1
        n_done = 0
        with ThreadPoolExecutor(max_workers=workers) as pool:
            futures = [pool.submit(run, j) for j in todo]
            for fut in as_completed(futures):
                fut.result()
                n_done += 1
                if n_done % 100 == 0:
                    rate = n_done / max(time.time() - t0, 1)
                    print(f"  …{n_done}/{len(todo)} pairs (round {round_no}, "
                          f"{rate:.1f} req/s, {N_429} throttle hits, "
                          f"{N_ERR} errors)", flush=True)
        todo, failures = failures, []
        if not todo:
            break
        if round_no > len(pauses) or time.time() - t0 > 40 * 60:
            break
        pause = pauses[round_no - 1]
        print(f"  round {round_no}: {len(todo)} pair(s) failed — waiting {pause}s "
              f"for the per-IP budget to refill, then retrying", flush=True)
        time.sleep(pause)
        with _throttle_lock:
            _throttle_delay = 0.0
    if todo:
        names = ", ".join(f"{q}/{l}" for q, l, _ in todo[:10])
        print(f"INCOMPLETE: {len(todo)} pair(s) still unfetched after retries "
              f"({names}…) — the checkpoint keeps what succeeded; rerun to "
              f"resume.", flush=True)
        return False
    return True


def backfill_assemble(checkpoints: list[Path]) -> None:
    """Assemble the archive from one or more shard checkpoints. Refuses to
    write anything unless EVERY non-quarantined registry pair is present —
    a partial archive would silently under-count those editions' history."""
    registry, wiki, topics = load_inputs()
    registry_qids = {t["qid"] for t in topics}
    quarantine = wiki.get("quarantine") or {}
    w_end = date.fromisoformat(wiki["updated"])
    w_start = w_end - timedelta(days=int(wiki.get("window_days") or 120) - 1)
    span = f"{ARCHIVE_START.isoformat()}..{w_end.isoformat()}"
    excluded = sorted(f"{qid}/{lang}" for qid, langs in quarantine.items()
                      for lang in langs)
    jobs = build_jobs(topics, quarantine)

    reusable: dict[str, dict] = {}
    for path in checkpoints:
        recs = load_checkpoint(path, span, strict=True)
        reusable.update({k: r for k, r in recs.items()
                         if r.get("s") in ("ok", "none")})
    missing = [(q, l) for q, l, t in jobs
               if reusable.get(f"{q}/{l}", {}).get("t") != t]
    if missing:
        names = ", ".join(f"{q}/{l}" for q, l in missing[:10])
        sys.exit(f"ABORT: {len(missing)} of {len(jobs)} pairs missing from the "
                 f"checkpoint(s) ({names}…). Nothing was written — rerun the "
                 f"failed shard(s), or the whole backfill.")
    print(f"Assembling {len(jobs)} pairs from {len(checkpoints)} checkpoint(s)",
          flush=True)

    # Per-topic day sums from the fetched pairs (frozen section semantics:
    # sum whichever pairs reported a day; no pair -> null).
    fetched_sums: dict[str, dict[str, int]] = {t["qid"]: {} for t in topics}
    for qid, lang, title in jobs:
        rec = reusable[f"{qid}/{lang}"]
        sums = fetched_sums[qid]
        for d, v in rec["d"].items():
            sums[d] = sums.get(d, 0) + v

    # Methodology cross-check BEFORE anything is written, at the only level
    # where "same measure?" is actually decidable: per PAIR per day. Where
    # both the fresh fetch and the live file hold a value for the same
    # series-day, the two numbers must agree — a wrong access/agent
    # parameter changes essentially every cell, so systematic disagreement
    # aborts. (Run 2, 2026-08-18, taught the distinction the hard way: the
    # first version compared per-TOPIC day sums and aborted on 13% "drift"
    # that was really the live file's own coverage gaps — days a throttled
    # run never stored for one of a topic's ~19 series make the topic sum
    # differ while every individually comparable value matches exactly;
    # a 19,291-cell per-pair comparison measured 0.0% real disagreement.)
    n_eq = n_diff = n_live_only = n_fresh_only = 0
    for qid, lang, title in jobs:
        fresh = reusable[f"{qid}/{lang}"]["d"]
        entry = (wiki.get("series", {}).get(qid) or {}).get(lang)
        live: dict[str, int] = {}
        if entry:
            try:
                s0 = datetime.strptime(str(entry.get("start")), "%Y-%m-%d").date()
            except ValueError:
                s0 = None
            if s0:
                for i, v in enumerate(entry.get("values") or []):
                    if v is not None:
                        live[(s0 + timedelta(days=i)).isoformat()] = v
        for day, v in live.items():
            f = fresh.get(day)
            if f is None:
                n_live_only += 1
            elif f == v:
                n_eq += 1
            else:
                n_diff += 1
        for k in range((w_end - w_start).days + 1):
            day = (w_start + timedelta(days=k)).isoformat()
            if day in fresh and day not in live:
                n_fresh_only += 1
    total_both = n_eq + n_diff
    print(f"  fetch-vs-live cross-check (per series-day): {n_eq} equal, "
          f"{n_diff} differ, {n_live_only} live-only, {n_fresh_only} "
          f"fresh-only (live-window days the live file's series lack — its "
          f"own throttling gaps; the overlap section keeps the live file's "
          f"values by design, and the daily engine heals those gaps "
          f"stalest-first)", flush=True)
    if total_both and n_diff / total_both > 0.05:
        sys.exit("ABORT: >5% of directly comparable series-day values "
                 "disagree with the live file — the fetch parameters do not "
                 "reproduce the published measure; nothing was written.")
    if n_live_only > 0.01 * max(total_both + n_live_only, 1):
        sys.exit("ABORT: >1% of the live file's series-day values are absent "
                 "from the fresh fetch — the fetch is dropping data it should "
                 "have retrieved; nothing was written.")

    # The axis: frozen section from the fetch, live section DERIVED from the
    # live file (the golden guarantee, and the state the daily append keeps).
    expected = live_day_sums(wiki, registry_qids)
    n_days = (w_end - ARCHIVE_START).days + 1
    boundary = (w_start - ARCHIVE_START).days
    archive_topics: dict[str, list] = {}
    for t in sorted(topics, key=lambda t: t["qid"]):
        qid = t["qid"]
        arr: list = [None] * n_days
        for d, v in fetched_sums[qid].items():
            i = (date.fromisoformat(d) - ARCHIVE_START).days
            if 0 <= i < boundary:
                arr[i] = v
        sums = expected.get(qid, {})
        for k in range((w_end - w_start).days + 1):
            if boundary + k >= 0:
                arr[boundary + k] = sums.get((w_start + timedelta(days=k)).isoformat())
        archive_topics[qid] = arr

    doc = {
        "_meta": build_meta(ARCHIVE_START, w_end, w_start,
                            date.today().isoformat(), excluded, len(archive_topics)),
        "topics": archive_topics,
    }
    problems = golden_check(doc, wiki, registry_qids)
    if problems:
        for p in problems[:10]:
            print(f"GOLDEN-CHECK FAIL: {p}", flush=True)
        sys.exit("backfill aborted before writing — the assembled archive "
                 "disagrees with the live file on shared days")
    atomic_write(doc)
    size_kb = ARCHIVE_PATH.stat().st_size / 1e3
    nulls = sum(1 for arr in archive_topics.values() for v in arr if v is None)
    print(f"Wrote {ARCHIVE_PATH} — {len(archive_topics)} topics x {n_days} days "
          f"({size_kb:.0f} KB, {nulls} null cells). Golden check passed. "
          f"The daily engine keeps it current from here.", flush=True)


def main() -> None:
    p = argparse.ArgumentParser(description="Long-term global attention archive")
    p.add_argument("--backfill", action="store_true",
                   help="one-time history fetch from the Wikimedia per-article API")
    p.add_argument("--shard", nargs=2, type=int, metavar=("K", "N"),
                   help="backfill only pair-slice K of N (use with --fetch-only)")
    p.add_argument("--fetch-only", action="store_true",
                   help="backfill: stop after fetching; the checkpoint is the output")
    p.add_argument("--assemble-from", nargs="*", type=Path, metavar="CHECKPOINT",
                   help="backfill: skip fetching, assemble from these checkpoints")
    p.add_argument("--checkpoint", type=Path,
                   default=Path(tempfile.gettempdir()) / "attention_backfill_checkpoint.jsonl",
                   help="backfill resume/output file (never committed)")
    p.add_argument("--workers", type=int, default=WORKERS)
    args = p.parse_args()
    if args.assemble_from is not None:
        if not args.assemble_from:
            sys.exit("--assemble-from needs at least one checkpoint path")
        backfill_assemble(args.assemble_from)
    elif args.backfill:
        complete = backfill_fetch(args.checkpoint, args.workers,
                                  tuple(args.shard) if args.shard else None)
        if args.fetch_only:
            sys.exit(0 if complete else 1)
        if not complete:
            sys.exit("ABORT: fetch incomplete — nothing assembled or written; "
                     "rerun with the same --checkpoint to resume.")
        backfill_assemble([args.checkpoint])
    else:
        append_mode()


if __name__ == "__main__":
    main()
