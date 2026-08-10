#!/usr/bin/env python3
"""
fetch_press_un_coverage.py — how much each country's OWN press covers the UN.

For every Atlas country, asks Media Cloud's curated "<Country> - National"
collection (mapping committed in data/sources/mediacloud_collections.json,
built by scripts/build_mediacloud_collections.py) one question per day:
of the stories your national outlets published in the measured week, how
many matched a United Nations phrase? Written to
data/trends/press_un_coverage.json.

WHY THIS SOURCE EARNS ITS PLACE: it is the only signal in the Atlas with a
defensible DENOMINATOR for national press attention. GDELT measures global
coverage volume; this measures share of each country's own press — "0.19%
of India's national-press stories last week mentioned the UN" is a
denominator-honest sentence no other integrated source can produce.
License standout (research sweep §2.3): Media Cloud's ToS explicitly
permits reproducing and distributing counts — exactly and only what this
file contains. Never store story text, URLs or titles here.

THE MEASURE IS A PHRASE-MATCH FLOOR. The query (versioned verbatim in
_meta.query) matches exact UN phrases in ~18 languages. Acronyms are
deliberately mostly excluded — "UN" is a word in French and Spanish,
"onu" is Turkish for "him/her" — so acronym-heavy press understates. A
floor, never an exhaustive count; every surface says so.

SMALL COLLECTIONS GET NO PERCENTAGE. A national collection with a handful
of outlets can publish a two-digit story count in a week; a share quoted
from that would be noise dressed as measurement. Below MIN_STORIES total
stories in the window the entry keeps its raw counts but sets
share_withheld — the site says "volume too low to quote a share" instead.

QUOTA HONESTY: one API call per country per run. A full daily sweep of
195 countries ≈ 1,365 calls/week against the free tier's 4,000. Pacing
adapts to 429s; the run stops cleanly at MAX_CALLS or TIME_BUDGET_MIN and
checkpoints, and countries are processed stalest-first, so a truncated run
self-heals tomorrow (same pattern as every other fetcher here).

Needs MEDIACLOUD_API_KEY in the environment (GitHub Actions secret; set
2026-08-10 from the UN media-partnerships team account). The key is never
printed and never written to disk.
"""

from __future__ import annotations

import json
import os
import sys
import time
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent
MAPPING_PATH = ROOT / "data" / "sources" / "mediacloud_collections.json"
OUTPUT_PATH = ROOT / "data" / "trends" / "press_un_coverage.json"

API = "https://search.mediacloud.org/api/search/count-over-time"
USER_AGENT = "UN-Media-Atlas/1.0 (Global Content Intelligence Platform; research)"
REQ_TIMEOUT = (5, 45)

WINDOW_DAYS = 7      # measured week
LAG_DAYS = 2         # Media Cloud ingestion settles; end the window early
MIN_STORIES = 100    # below this weekly total, no share is quoted
MAX_CALLS = 205      # hard per-run API budget (≈1,435/week of the 4,000)
TIME_BUDGET_MIN = 12 # stop cleanly before the workflow step's timeout
PACE_SECONDS = 1.2
CHECKPOINT_EVERY = 25

# The versioned phrase list. Exact quoted phrases only — see docstring.
UN_PHRASES = [
    "United Nations", "Nations Unies", "Naciones Unidas", "Nações Unidas",
    "Vereinte Nationen", "Nazioni Unite", "Verenigde Naties",
    "Организация Объединённых Наций", "ООН", "الأمم المتحدة", "联合国",
    "国連", "유엔", "Birleşmiş Milletler", "Perserikatan Bangsa-Bangsa",
    "Umoja wa Mataifa", "संयुक्त राष्ट्र", "سازمان ملل", "Liên Hợp Quốc",
    "สหประชาชาติ",
]
QUERY = " OR ".join(f'"{p}"' for p in UN_PHRASES)


def main() -> int:
    key = os.environ.get("MEDIACLOUD_API_KEY", "").strip()
    if not key:
        print("ERROR: MEDIACLOUD_API_KEY is not set — cannot fetch. (In CI it "
              "comes from the repo secret; locally, export it first.)",
              file=sys.stderr)
        return 1
    headers = {"Authorization": f"Token {key}", "User-Agent": USER_AGENT}

    mapping = json.loads(MAPPING_PATH.read_text(encoding="utf-8"))["collections"]

    previous: dict = {}
    if OUTPUT_PATH.exists():
        try:
            previous = json.loads(OUTPUT_PATH.read_text(encoding="utf-8")).get("countries", {})
        except (json.JSONDecodeError, OSError) as exc:
            print(f"WARNING: existing {OUTPUT_PATH.name} unreadable ({exc}) — rebuilding", flush=True)

    end = date.today() - timedelta(days=LAG_DAYS)
    start = end - timedelta(days=WINDOW_DAYS - 1)
    retrieved = date.today().isoformat()

    # Stalest-first, same as every fetcher here: a truncated run self-heals.
    iso3s = sorted(mapping, key=lambda i: ((previous.get(i) or {}).get("retrieved") or "", i))

    out: dict[str, dict] = json.loads(json.dumps(previous)) if previous else {}

    def write_output() -> None:
        measured = sum(1 for r in out.values() if r.get("share_pct") is not None)
        withheld = sum(1 for r in out.values() if r.get("share_withheld"))
        doc = {
            "_meta": {
                "source": "Media Cloud (curated national collections)",
                "source_url": "https://search.mediacloud.org/",
                "license": ("Media Cloud ToS explicitly permits reproducing and "
                            "distributing platform outputs such as counts and "
                            "time series — this file contains counts only, "
                            "never story text, titles or URLs."),
                "query": QUERY,
                "method_note": (
                    "Share of each country's national-press stories matching "
                    "one of the UN phrases in _meta.query, over a trailing "
                    f"{WINDOW_DAYS}-day window ending {LAG_DAYS} days back "
                    "(ingestion settles). A PHRASE-MATCH FLOOR: acronyms are "
                    "deliberately mostly excluded (\"UN\" is a word in French "
                    "and Spanish; \"onu\" is Turkish), so acronym-heavy press "
                    "understates. Collections are Media Cloud's curated "
                    "national outlet lists; below "
                    f"{MIN_STORIES} total stories in the window no share is "
                    "quoted (share_withheld instead). Story counts are "
                    "publication counts in monitored outlets, not readership."
                ),
                "window_days": WINDOW_DAYS,
                "lag_days": LAG_DAYS,
                "min_stories": MIN_STORIES,
                "generated_at": datetime.now(timezone.utc)
                                .replace(microsecond=0).isoformat(),
                "coverage": {
                    "countries_with_share": measured,
                    "countries_share_withheld_low_volume": withheld,
                    "countries_total": len(mapping),
                },
            },
            "countries": dict(sorted(out.items())),
        }
        OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
        tmp = OUTPUT_PATH.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(doc, ensure_ascii=False, indent=1) + "\n",
                       encoding="utf-8")
        os.replace(tmp, OUTPUT_PATH)

    t0 = time.monotonic()
    pace = PACE_SECONDS
    n_calls = n_fresh = n_withheld_now = n_errors = 0

    for i, iso3 in enumerate(iso3s, 1):
        if n_calls >= MAX_CALLS:
            print(f"Call budget ({MAX_CALLS}) reached — stopping cleanly; "
                  f"stalest-first covers the rest tomorrow.", flush=True)
            break
        if (time.monotonic() - t0) / 60 > TIME_BUDGET_MIN:
            print(f"Time budget ({TIME_BUDGET_MIN} min) reached — stopping "
                  f"cleanly; stalest-first covers the rest tomorrow.", flush=True)
            break

        coll = mapping[iso3]
        data = None
        for attempt in range(3):
            try:
                n_calls += 1
                resp = requests.get(API, params={
                    "q": QUERY, "start": start.isoformat(), "end": end.isoformat(),
                    "cs": str(coll["id"]), "platform": "onlinenews-mediacloud",
                }, headers=headers, timeout=REQ_TIMEOUT)
                if resp.status_code == 429:
                    pace = min(pace * 2, 30.0)
                    time.sleep(10 * (attempt + 1))
                    continue
                resp.raise_for_status()
                data = resp.json().get("count_over_time", {}).get("counts")
                pace = max(pace * 0.9, PACE_SECONDS)
                break
            except requests.RequestException:
                time.sleep(3 * (attempt + 1))
        time.sleep(pace)

        if not isinstance(data, list):
            n_errors += 1          # previous entry, if any, stays untouched
            continue

        stories_un = sum(int(d.get("count") or 0) for d in data)
        stories_total = sum(int(d.get("total_count") or 0) for d in data)
        # The API omits days with no stories at all (observed on 20 tiny
        # collections, 2026-08-10), so the daily array is padded to the full
        # window with explicit zeros — sparse days are real zeros, and a
        # 7-day window should always LOOK like 7 days.
        by_date = {str(d.get("date"))[:10]: d for d in data}
        entry: dict = {
            "window": {"start": start.isoformat(), "end": end.isoformat()},
            "stories_total": stories_total,
            "stories_un": stories_un,
            "daily": [
                {"date": (start + timedelta(days=n)).isoformat(),
                 "un": int((by_date.get((start + timedelta(days=n)).isoformat()) or {}).get("count") or 0),
                 "total": int((by_date.get((start + timedelta(days=n)).isoformat()) or {}).get("total_count") or 0)}
                for n in range(WINDOW_DAYS)
            ],
            "collection": {"id": coll["id"], "name": coll["name"],
                           "source_count": coll.get("source_count")},
            "retrieved": retrieved,
            "source": (f"Media Cloud national collection ‘{coll['name']}’ "
                       f"(id {coll['id']}) | UN-phrase share of stories "
                       f"{start.isoformat()} to {end.isoformat()} | "
                       f"https://search.mediacloud.org/ | retrieved {retrieved}"),
        }
        if stories_total >= MIN_STORIES:
            entry["share_pct"] = round(100 * stories_un / stories_total, 2)
        else:
            entry["share_withheld"] = True
            entry["low_volume_note"] = (
                f"Only {stories_total} stories monitored in this window "
                f"(below the {MIN_STORIES}-story floor) — too few to quote a "
                f"share honestly.")
            n_withheld_now += 1
        out[iso3] = entry
        n_fresh += 1

        if i % CHECKPOINT_EVERY == 0:
            write_output()
        if i % 25 == 0:
            print(f"  · {i}/{len(iso3s)} countries — {n_fresh} fresh, "
                  f"{n_withheld_now} low-volume, {n_errors} errored, "
                  f"{n_calls} calls, pace {pace:.1f}s", flush=True)

    if n_fresh == 0 and previous:
        print("ERROR: no country returned data — previous file preserved; "
              "check the key, the endpoint, and the response shape.",
              file=sys.stderr)
        return 1

    write_output()
    print(f"Wrote {OUTPUT_PATH} — {n_fresh} countries refreshed "
          f"({n_withheld_now} low-volume withheld, {n_errors} errored, "
          f"{n_calls} API calls).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
