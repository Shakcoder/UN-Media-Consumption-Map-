#!/usr/bin/env python3
"""
fetch_trends_bluesky.py — daily global Bluesky trending topics.

Fetches the topics currently trending across Bluesky (network-wide) and
writes an aggregate summary to data/trends/bluesky_trends.json.

WHAT THIS MEASURES (and what it does not): what the open social web is
talking about RIGHT NOW, globally. It is the Atlas's open-social signal,
carried because X/Twitter's data access closed in 2026 (see
docs/SOURCE_RESEARCH_2026-08.md §1) and Bluesky is the largest social
platform with an open, keyless API. Two hard caveats travel with every
surface that shows it:
  * GLOBAL ONLY — the endpoint has no country or language parameter, so
    this signal must NEVER appear on a country page as that country's own.
  * Bluesky's users are not the general population — this is a measured
    view of one (self-selected) network, not of public opinion.

POST COUNTS ARE FEED SIZES, NOT SHARES. `postCount` is the number of posts
gathered into that trend's feed — a magnitude indicator. Never present it
as a share of conversation or compare it as if platforms were equivalent.

AGGREGATES ONLY, BY DESIGN. Only the topic name, category, rank, post
count and dates are stored — never posts, never handles. That is what
makes committing this to a public repo clean: deletion obligations attach
to content and identities, and this file contains neither.

THE ENDPOINT IS OFFICIALLY "UNSPECCED". Bluesky publishes it under the
app.bsky.unspecced.* namespace, which they document as unstable — it may
change or vanish without notice. Defense: a shape guard below refuses to
write ANYTHING unless every field this integration depends on is present
and typed as expected, and exits non-zero so the workflow shows the
breakage. A silent upstream change can never publish garbage; the previous
day's file simply stands until a human looks.

NO HISTORY EXISTS UPSTREAM — same as the Google Trends feed, this is a
snapshot, so the file keeps its own rolling HISTORY_DAYS archive (which
powers the "new today" badge). It cannot be rebuilt if deleted.

Cadence: daily (trend-engine.yml, supply lane — a single request).
"""

from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent
OUTPUT_PATH = ROOT / "data" / "trends" / "bluesky_trends.json"

API = "https://public.api.bsky.app/xrpc/app.bsky.unspecced.getTrends"
USER_AGENT = "UN-Media-Atlas/1.0 (Global Content Intelligence Platform; research)"
REQ_TIMEOUT = (5, 20)
LIMIT = 25
HISTORY_DAYS = 7


def main() -> int:
    previous: dict = {}
    if OUTPUT_PATH.exists():
        try:
            previous = json.loads(OUTPUT_PATH.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            previous = {}

    try:
        resp = requests.get(API, params={"limit": LIMIT},
                            headers={"User-Agent": USER_AGENT},
                            timeout=REQ_TIMEOUT)
        resp.raise_for_status()
        raw = resp.json().get("trends")
    except Exception as exc:
        print(f"ERROR: Bluesky trends fetch failed ({exc}) — previous data "
              f"preserved.", file=sys.stderr)
        return 1

    # SHAPE GUARD — see docstring. Every field the Atlas depends on must be
    # present and correctly typed on every trend, or nothing is written.
    if not isinstance(raw, list) or not raw or not all(
            isinstance(t, dict)
            and str(t.get("topic") or "").strip()
            and str(t.get("displayName") or "").strip()
            and isinstance(t.get("postCount"), int) and t["postCount"] >= 0
            for t in raw):
        print("ERROR: Bluesky trends response shape changed (the endpoint is "
              "officially 'unspecced') — refusing to write; previous data "
              "preserved. Inspect the API response and update this fetcher.",
              file=sys.stderr)
        return 1

    now = datetime.now(timezone.utc)
    today_str = now.date().isoformat()
    keep_after = (now.date() - timedelta(days=HISTORY_DAYS)).isoformat()

    trends = []
    for rank, t in enumerate(raw[:LIMIT], start=1):
        entry: dict = {
            "topic": t["topic"].strip(),
            "display_name": t["displayName"].strip(),
            "rank": rank,
            "post_count": t["postCount"],
        }
        category = str(t.get("category") or "").strip()
        if category:
            entry["category"] = category
        if t.get("status") == "hot":
            entry["hot"] = True
        started = str(t.get("startedAt") or "")[:10]
        if started:
            entry["started"] = started
        trends.append(entry)

    # Roll the archive forward (names only — the aggregate discipline above
    # applies to the archive too), then badge what is genuinely new today.
    history = {d: names for d, names in (previous.get("history") or {}).items()
               if d > keep_after and d != today_str}
    # UNION with anything already captured today, never replace — same fix as
    # fetch_trends_google.py (2026-08-11 audit): the feed rotates all day, the
    # archive is unrebuildable, and a same-day rerun must add, not erase.
    prev_today = set((previous.get("history") or {}).get(today_str) or [])
    history[today_str] = sorted(prev_today | {t["display_name"] for t in trends})
    earlier = {n for d, names in history.items() if d != today_str for n in names}
    for t in trends:
        t["new"] = t["display_name"] not in earlier

    doc = {
        "_meta": {
            "source": "Bluesky public API (app.bsky.unspecced.getTrends)",
            "source_url": API,
            "license": ("Public, keyless API. Aggregates only are stored — "
                        "trend topics and counts, never posts or account "
                        "handles — so content-deletion obligations never "
                        "attach to this file."),
            "method_note": (
                "Topics trending across Bluesky network-wide at fetch time. "
                "GLOBAL only — no per-country split exists, so this must "
                "never be shown as any single country's signal. Bluesky "
                "users are not the general population. post_count is the "
                "size of that trend's feed: a magnitude, never a share. The "
                "endpoint namespace is officially 'unspecced' (unstable); "
                "the fetcher refuses to write on any shape change. The "
                "history block is this project's own rolling archive — the "
                "API keeps none."
            ),
            "history_days_kept": HISTORY_DAYS,
        },
        "retrieved_at": now.replace(microsecond=0).isoformat(),
        "date": today_str,
        "trends": trends,
        "history": dict(sorted(history.items())),
    }

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    tmp = OUTPUT_PATH.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(doc, ensure_ascii=False, indent=1) + "\n",
                   encoding="utf-8")
    os.replace(tmp, OUTPUT_PATH)
    n_new = sum(1 for t in trends if t.get("new"))
    print(f"Wrote {OUTPUT_PATH} — {len(trends)} global trends "
          f"({n_new} new today, {len(history)} archive days).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
