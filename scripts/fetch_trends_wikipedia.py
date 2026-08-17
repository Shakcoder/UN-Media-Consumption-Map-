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
    --gate-only     re-run just the access-method anomaly gate over the
                    existing snapshot (see the GATE_* block below) and
                    rewrite its quarantine map — no series fetching.

Run with no flags and it behaves exactly as before (single-process full
fetch) — that is still the right way to run it by hand.

QUARANTINE (2026-08-17): the file also carries a top-level "quarantine" map
({qid: {lang: record}}) naming series whose traffic fails the access-method
anomaly gate — stored, still fetched daily, but excluded downstream from
attention shares / distinctive / rising by compute_topic_intelligence.py.
Design, calibration evidence and rejected alternatives: see the GATE_*
constants block below.
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


# ---------------------------------------------------------------------------
# ACCESS-METHOD ANOMALY GATE (2026-08-17) — the France-5G class of artifact.
#
# The 2026-08 audit found fr "5G" carrying ~4.9k "user" views/day for 120
# days straight — 5.2x the English article's traffic (healthy fr:en ratios
# run ~0.08), 99.3% of it mobile-web (the fr edition's own overall mix is
# ~33% desktop), with no French 5G news event behind it. The language
# weights then spilled that one series into 14 countries' profiles, making
# "5G" France's #1 "distinctive" topic at ~30% attention share. tr "Yapay
# zekâ" showed the same signature (4.3% desktop vs the tr edition's 25.3%)
# and owned 71% of Turkey's profile.
#
# The gate: cheap screens on the data already in the file pick out series
# big enough to distort a country profile, and only those few earn extra
# API calls that measure HOW the article is being read. Quarantine, never
# delete: a flagged series keeps its stored data (and keeps being fetched,
# so recovery is observable); compute_topic_intelligence.py excludes it
# from attention shares / distinctive / rising and reports the count.
#
# SCREENS (no API cost, ~5 candidates/day observed):
#   S1  non-en series whose 7-day mean is >= GATE_RATIO_VS_EN x the same
#       topic's en series (fr 5G: 5.2x; healthy series run far below 1).
#   S2  series carrying >= GATE_EDITION_DOMINANCE of its own edition's
#       total tracked attention (tr AI: 71%; the highest healthy value
#       observed is en ChatGPT at 33% — ChatGPT genuinely is the world's
#       #1 tracked topic in most editions).
#   Both require a 7-day mean >= GATE_MIN_MEAN: below that a series can't
#   meaningfully distort a profile, and access-split measurements on tiny
#   series are noise. (Known cost: a ~140/day artifact like hi "चुनाव" —
#   3.8% desktop against hi's 18.8% norm, clearly the same class — stays
#   published, bounded to its edition's small weight.)
#
# VERDICT (2 aggregate calls per edition + 1 per-article call, all cached
# per run): quarantine when the article's desktop share of user traffic
# over the last GATE_SPLIT_DAYS days is under GATE_REL_DESKTOP of the SAME
# edition's aggregate desktop share. Relative-to-own-edition matters: a
# fixed "under 10% desktop" cutoff would false-positive healthy series in
# mobile-first editions (hi "संयुक्त राष्ट्र" runs 9.0% desktop and is
# fine). Calibrated 2026-08-17 against live data:
#     artifacts:  fr 5G 0.02x its edition's norm, tr AI 0.17x
#     healthy:    hi UN 0.48x, ru Апатрид 0.55x, bn UN 0.57x,
#                 ar ChatGPT 0.62x, es Terremoto (Colombia-quake week)
#                 0.80x, tr Deprem 0.81x, es/en/vi ChatGPT 1.0-2.0x,
#                 ja 風力発電 (audit-verified organic burst) 3.08x
#   1/3 sits in that gap with ~1.7x margin on both sides.
#
# REJECTED DESIGNS (each tested on live data before rejection):
#   - automated/user lockstep as a per-series verdict: ja 風力発電 — an
#     audit-verified ORGANIC burst — shows automated at 6.5x user in its
#     post-burst tail (bots keep crawling after readers leave), so the 0.5
#     lockstep rule that works for single-day floods in the reading-list
#     fetcher false-positives here. Lockstep stays where it calibrates
#     cleanly: single-day, high-volume entries (fetch_trends_wiki_countries).
#   - absolute desktop-share threshold: see hi examples above.
#   - shape rules (flat-high, whipsaw): the 2026-08-12 eclipse legitimately
#     produced every "suspicious" shape; shape separates events from
#     baselines, not people from bots.
#   - a two-sided rule (also flagging desktop-degenerate series): ja
#     風力発電's tail is 97% desktop AND organic per the audit. The
#     documented artifact class is mobile-web floods; one-sided by design.
#
# FAIL-OPEN, WITH STICKY QUARANTINE: an API error while verifying a NEW
# candidate publishes it unchanged (a Wikimedia hiccup must never delete
# measured data); an API error while re-checking an EXISTING quarantined
# series keeps the quarantine (lifting requires positive evidence of
# health, and an error is not evidence). Lifts happen when a re-check
# measures a healthy split, or when the series falls below the screens —
# at which point it can no longer distort what the Atlas publishes.
# ---------------------------------------------------------------------------
GATE_MIN_MEAN = 150.0          # 7-day-mean floor for screening (and verdicts)
GATE_RATIO_VS_EN = 1.5         # S1: non-en mean >= 1.5x the topic's en mean
GATE_EDITION_DOMINANCE = 0.50  # S2: >= 50% of the edition's tracked total
GATE_EDITION_BASIS_FLOOR = 25.0  # series counted into an edition total (same
                                 # floor compute_topic_intelligence scores at)
GATE_SPLIT_DAYS = 30           # window for the access-split measurement
GATE_REL_DESKTOP = 1.0 / 3.0   # verdict: desktop share < 1/3 of edition norm
GATE_MIN_SPLIT_VIEWS = 500     # user views needed in-window before a share
                               # is trusted (screened series carry ~4,500+)

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


def _gate_fetch(url: str) -> tuple[list | None, str]:
    """GET for the gate's extra calls. Returns (items, status) where status is
    'ok' (items is the list, possibly empty), 'none' (clean 404 — the API has
    no rows, i.e. a measured zero for per-article access splits), or 'error'
    (network/throttle exhaustion — the caller must fail open)."""
    for attempt in range(3):
        try:
            resp = _session().get(url, timeout=REQ_TIMEOUT)
            if resp.status_code == 200:
                return resp.json().get("items", []), "ok"
            if resp.status_code == 404:
                return None, "none"
            time.sleep(4 * (attempt + 1))   # 429/5xx — the gate is unhurried
        except Exception:
            time.sleep(2 * (attempt + 1))
    return None, "error"


def apply_anomaly_gate(series: dict, prev_quarantine: dict, end: date,
                       topics: list) -> tuple[dict, list[str]]:
    """
    The access-method anomaly gate (see the block comment above the GATE_*
    constants for the design, calibration evidence and rejected designs).

    Reads the full merged series map, screens it locally, verifies the few
    candidates against the Pageviews API's access-method split, and returns
    (quarantine_map, human-readable action lines). The map is persisted as
    the file's top-level "quarantine" key: {qid: {lang: record}}.

    Runs where the whole picture exists — the single-process fetch and the
    shard merge — never in a shard (a shard sees 1/N of the series, so its
    edition totals and en comparators would be nonsense).
    """
    titles = {t["qid"]: t.get("titles", {}) for t in topics}
    labels = {t["qid"]: t.get("label_en", t["qid"]) for t in topics}

    # 7-day means anchored to the window end, same convention as compute.
    window7 = {(end - timedelta(days=i)).isoformat() for i in range(7)}
    means: dict[tuple[str, str], float] = {}
    for qid, langs in series.items():
        if qid not in titles:
            continue                      # no longer in the registry
        for lang, entry in langs.items():
            start = datetime.strptime(entry["start"], "%Y-%m-%d").date()
            vals = [v for i, v in enumerate(entry["values"])
                    if v is not None
                    and (start + timedelta(days=i)).isoformat() in window7]
            if vals:
                means[(qid, lang)] = sum(vals) / len(vals)

    edition_total: dict[str, float] = {}
    for (qid, lang), m in means.items():
        if m >= GATE_EDITION_BASIS_FLOOR:
            edition_total[lang] = edition_total.get(lang, 0.0) + m

    def screen(qid: str, lang: str) -> str | None:
        """Why this series deserves the paid check — or None."""
        m = means.get((qid, lang))
        if m is None or m < GATE_MIN_MEAN:
            return None
        en = means.get((qid, "en"))
        if lang != "en" and en and en > 0 and m >= GATE_RATIO_VS_EN * en:
            return f"reads {m / en:.1f}x the en series"
        total = edition_total.get(lang, 0.0)
        if total > 0 and m / total >= GATE_EDITION_DOMINANCE:
            return f"carries {100 * m / total:.0f}% of the {lang} edition's tracked attention"
        return None

    # Candidates: everything screened now, plus everything currently
    # quarantined (so lifts are decided by measurement, not by omission).
    candidates = {k for k in means if screen(*k)}
    candidates |= {(q, l) for q, ls in prev_quarantine.items() for l in ls}

    split_start = end - timedelta(days=GATE_SPLIT_DAYS - 1)
    win = f"{split_start.strftime('%Y%m%d')}00/{end.strftime('%Y%m%d')}00"

    norm_cache: dict[str, float | None] = {}   # lang -> edition desktop share

    def edition_norm(lang: str) -> float | None:
        """The edition's own desktop share of user traffic — the reference a
        candidate is judged against. None = unavailable (fail open)."""
        if lang not in norm_cache:
            base = ("https://wikimedia.org/api/rest_v1/metrics/pageviews/"
                    f"aggregate/{lang}.wikipedia")
            desk, s1 = _gate_fetch(f"{base}/desktop/user/daily/{win}")
            time.sleep(0.5)
            alla, s2 = _gate_fetch(f"{base}/all-access/user/daily/{win}")
            time.sleep(0.5)
            if s1 == "ok" and s2 == "ok" and alla:
                total = sum(i.get("views", 0) for i in alla)
                norm_cache[lang] = (
                    sum(i.get("views", 0) for i in desk) / total if total else None)
            else:
                norm_cache[lang] = None
        return norm_cache[lang]

    out: dict[str, dict[str, dict]] = {}
    actions: list[str] = []

    def keep(qid: str, lang: str, rec: dict) -> None:
        out.setdefault(qid, {})[lang] = rec

    for qid, lang in sorted(candidates):
        prev = (prev_quarantine.get(qid) or {}).get(lang)
        name = f"{lang} '{titles.get(qid, {}).get(lang, '?')}' ({labels.get(qid, qid)})"
        why = screen(qid, lang)
        if why is None:
            if prev:
                actions.append(f"gate lift: {name} — below screening "
                               "thresholds, can no longer distort shares")
            continue

        title = titles.get(qid, {}).get(lang)
        entry = series.get(qid, {}).get(lang)
        if not title or not entry:
            continue
        # Denominator from our own stored all-access/user series — the same
        # thing the API would return, already on disk. Numerator only counts
        # days the denominator has, so partial windows can't skew the share.
        start = datetime.strptime(entry["start"], "%Y-%m-%d").date()
        have = {(start + timedelta(days=i)).strftime("%Y%m%d"): v
                for i, v in enumerate(entry["values"])
                if v is not None and split_start <= start + timedelta(days=i) <= end}
        user_sum = sum(have.values())
        norm = edition_norm(lang)
        if user_sum < GATE_MIN_SPLIT_VIEWS or not norm:
            if prev:
                keep(qid, lang, prev)     # sticky: an error is not evidence
                actions.append(f"gate recheck failed for {name} (edition norm "
                               "unavailable) — quarantine kept")
            else:
                actions.append(f"gate: {name} screened ({why}) but "
                               "unverifiable this run — published (fail-open)")
            continue
        art = urllib.parse.quote(title.replace(" ", "_"), safe="")
        items, status = _gate_fetch(
            "https://wikimedia.org/api/rest_v1/metrics/pageviews/per-article/"
            f"{lang}.wikipedia/desktop/user/{art}/daily/{win}")
        time.sleep(0.5)
        if status == "error":
            if prev:
                keep(qid, lang, prev)
                actions.append(f"gate recheck failed for {name} (desktop "
                               "series unavailable) — quarantine kept")
            else:
                actions.append(f"gate: {name} screened ({why}) but "
                               "unverifiable this run — published (fail-open)")
            continue
        # A clean 404 is a measured zero: the API stores no desktop rows at
        # all for an article people supposedly read thousands of times a day.
        desk_sum = sum(i.get("views", 0) for i in items
                       if str(i.get("timestamp", ""))[:8] in have) if status == "ok" else 0
        share = desk_sum / user_sum
        if share < GATE_REL_DESKTOP * norm:
            keep(qid, lang, {
                "reason": "access-split",
                "label_en": labels.get(qid, qid),
                "title": title,
                "screen": why,
                "mean_7d": round(means[(qid, lang)], 1),
                "desktop_share": round(share, 4),
                "edition_desktop_share": round(norm, 4),
                "window": f"{split_start.isoformat()}..{end.isoformat()}",
                "since": (prev or {}).get("since") or end.isoformat(),
                "checked": end.isoformat(),
                "note": ("user-classified traffic reading almost exclusively "
                         "via mobile-web, far outside this edition's own "
                         "access mix — the France-5G artifact signature. "
                         "Series stored and still fetched daily; excluded "
                         "from attention shares until the split recovers."),
            })
            if not prev:
                actions.append(
                    f"gate QUARANTINE: {name} — {why}; desktop share "
                    f"{100 * share:.1f}% vs edition norm {100 * norm:.1f}%")
        elif prev:
            actions.append(f"gate lift: {name} — access split recovered "
                           f"({100 * share:.1f}% desktop vs edition norm "
                           f"{100 * norm:.1f}%)")
    return out, actions


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
    p.add_argument("--gate-only", action="store_true",
                   help="run only the access-method anomaly gate over the "
                        "existing snapshot (no series fetching) and rewrite "
                        "its quarantine map — cheap, ~a dozen API calls")
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

    existing_doc: dict = {}
    if OUTPUT_PATH.exists():
        try:
            existing_doc = json.loads(OUTPUT_PATH.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as exc:
            print(f"WARNING: existing {OUTPUT_PATH.name} unreadable ({exc}) — "
                  f"merging shards onto an empty base", flush=True)
    existing = existing_doc.get("series", {})

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

    # The merge is the one place in the sharded path that sees every series
    # at once, so the anomaly gate runs here (a shard's view would make the
    # edition totals and en comparators nonsense).
    topics = json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))["topics"]
    quarantine, gate_actions = apply_anomaly_gate(
        merged, existing_doc.get("quarantine") or {}, end, topics)
    for line in gate_actions:
        print(f"  {line}", flush=True)

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    tmp = OUTPUT_PATH.with_suffix(".json.tmp")
    tmp.write_text(
        json.dumps({
            "source": "Wikimedia Pageviews API (user traffic, all access methods)",
            "license": "CC0 / public API",
            "signal_type": "demand (what people look up)",
            "updated": end.isoformat(),
            "window_days": WINDOW_DAYS,
            "quarantine": quarantine,
            "series": merged,
        }, separators=(",", ":"), ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    os.replace(tmp, OUTPUT_PATH)
    n_series = sum(len(v) for v in merged.values())
    n_quar = sum(len(v) for v in quarantine.values())
    print(f"Merged {len(partials)} partial(s): {n_overlaid} series refreshed, "
          f"{n_series} total ({n_quar} quarantined) in {OUTPUT_PATH}")


def gate_only() -> None:
    """Re-run just the anomaly gate over the existing snapshot (no fetching).

    For hand runs and for applying a gate change to already-stored data
    without waiting for the next daily cycle. Anchored to the snapshot's own
    'updated' date, so the verdicts describe the data actually on disk; the
    date is left untouched because no series data changed.
    """
    if not OUTPUT_PATH.exists():
        sys.exit(f"{OUTPUT_PATH} does not exist — nothing to gate")
    doc = json.loads(OUTPUT_PATH.read_text(encoding="utf-8"))
    if doc.get("partial"):
        sys.exit("refusing to gate a partial shard file")
    end = datetime.strptime(doc["updated"], "%Y-%m-%d").date()
    topics = json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))["topics"]
    quarantine, actions = apply_anomaly_gate(
        doc.get("series", {}), doc.get("quarantine") or {}, end, topics)
    for line in actions:
        print(f"  {line}", flush=True)
    ordered = {k: v for k, v in doc.items() if k not in ("quarantine", "series")}
    ordered["quarantine"] = quarantine
    ordered["series"] = doc.get("series", {})
    tmp = OUTPUT_PATH.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(ordered, separators=(",", ":"),
                              ensure_ascii=False) + "\n", encoding="utf-8")
    os.replace(tmp, OUTPUT_PATH)
    n_quar = sum(len(v) for v in quarantine.values())
    print(f"Gate pass complete — {n_quar} series quarantined "
          f"(data as of {doc['updated']}).")


def main(args: argparse.Namespace) -> None:
    registry = json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))
    topics = registry["topics"]

    existing_doc: dict = {}
    if OUTPUT_PATH.exists():
        # Guard against a corrupt file (e.g. the process was SIGKILLed mid-write
        # before writes became atomic): start fresh rather than wedging the
        # pipeline permanently on a JSONDecodeError every day.
        try:
            existing_doc = json.loads(OUTPUT_PATH.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as exc:
            print(f"WARNING: existing {OUTPUT_PATH.name} unreadable ({exc}) — rebuilding from scratch", flush=True)
    existing = existing_doc.get("series", {})
    # Checkpoints carry the previous run's quarantine verdicts forward
    # unchanged; the gate re-decides them just before the final write.
    quarantine: dict = existing_doc.get("quarantine") or {}

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
            # No quarantine key either: gate verdicts are only made where the
            # full series map exists (the merge, or a single-process run).
            doc["partial"] = True
        else:
            doc["quarantine"] = quarantine
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
        # Full picture assembled — re-decide the anomaly-gate verdicts.
        quarantine, gate_actions = apply_anomaly_gate(
            series_out, quarantine, end, topics)
        for line in gate_actions:
            print(f"  {line}", flush=True)

    write_output(target)
    size_mb = out_path.stat().st_size / 1e6
    print(f"Wrote {out_path} ({size_mb:.1f} MB) — "
          f"{n_backfilled} backfilled, {n_fetched} updated series.")


if __name__ == "__main__":
    _args = parse_args()
    if _args.merge is not None:
        sys.exit(merge_partials(_args.merge))
    if _args.gate_only:
        sys.exit(gate_only())
    sys.exit(main(_args))
