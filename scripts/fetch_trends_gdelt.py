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
SLEEP seconds/call and backs off on throttle notices. A full run of
~167 topics × 2 calls ≈ 35 minutes — run it on a schedule, not in a hurry.

Output: data/trends/gdelt_coverage.json (rolling snapshot, overwritten
daily; the volume timeline covers the trailing TIMESPAN).
"""

from __future__ import annotations

import json
import ssl
import sys
import time
import urllib.parse
import urllib.request
from datetime import date
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
REGISTRY_PATH = REPO_ROOT / "data" / "topics.json"
OUTPUT_PATH = REPO_ROOT / "data" / "trends" / "gdelt_coverage.json"

USER_AGENT = "UN-Media-Atlas/1.0 (Global Content Intelligence Platform; research)"
TIMESPAN = "90d"          # volume timeline window
COUNTRY_TIMESPAN = "14d"  # source-country breakdown window
SLEEP = 6.5               # seconds between calls (GDELT limit: 1 per 5s)
MAX_BACKOFF_RETRIES = 4


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
                # Throttle notice or transient HTML — back off hard and retry.
                wait = 30 * (attempt + 1)
                print(f"    throttled/non-JSON, waiting {wait}s…", flush=True)
                time.sleep(wait)
        except urllib.error.HTTPError as e:
            if e.code == 429:
                wait = 30 * (attempt + 1)
                print(f"    HTTP 429, waiting {wait}s…", flush=True)
                time.sleep(wait)
            else:
                time.sleep(10)
        except Exception:
            time.sleep(10)
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
    """timelinesourcecountry -> {country_name: mean share of coverage}."""
    out: dict[str, float] = {}
    for series in data.get("timeline", []):
        name = series.get("series", "").strip()
        pts = [pt.get("value", 0) for pt in series.get("data", [])]
        if name and pts:
            out[name] = round(sum(pts) / len(pts), 4)
    return out


def main() -> None:
    registry = json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))
    topics = registry["topics"]

    # Previous snapshot — used as per-topic fallback when today's fetch fails,
    # so a rate-limited run can never erase good data.
    previous: dict[str, dict] = {}
    if OUTPUT_PATH.exists():
        previous = json.loads(OUTPUT_PATH.read_text(encoding="utf-8")).get("topics", {})

    results: dict[str, dict] = {}
    for i, t in enumerate(topics, 1):
        qid, label = t["qid"], t["label_en"]
        query = f'"{label}"' if " " in label else label

        vol_data = gdelt_call({
            "query": query, "mode": "timelinevolraw",
            "timespan": TIMESPAN, "format": "json",
        })
        time.sleep(SLEEP)

        country_data = gdelt_call({
            "query": query, "mode": "timelinesourcecountry",
            "timespan": COUNTRY_TIMESPAN, "format": "json",
        })
        time.sleep(SLEEP)

        entry: dict = {"label_en": label}
        if vol_data:
            entry["volume_daily"] = parse_volume(vol_data)
        if country_data:
            entry["source_countries"] = parse_source_countries(country_data)

        # per-topic fallback: keep yesterday's data rather than nothing
        prev_entry = previous.get(qid, {})
        if not entry.get("volume_daily") and prev_entry.get("volume_daily"):
            entry["volume_daily"] = prev_entry["volume_daily"]
            entry["volume_stale"] = True
        if not entry.get("source_countries") and prev_entry.get("source_countries"):
            entry["source_countries"] = prev_entry["source_countries"]
            entry["countries_stale"] = True

        results[qid] = entry

        if i % 10 == 0:
            print(f"  …{i}/{len(topics)} topics", flush=True)

    ok_vol = sum(1 for e in results.values()
                 if e.get("volume_daily") and not e.get("volume_stale"))
    ok_cty = sum(1 for e in results.values()
                 if e.get("source_countries") and not e.get("countries_stale"))

    # Global guard: if almost everything failed AND we have a previous good
    # snapshot, keep it untouched instead of committing a degraded file.
    if previous and ok_vol < max(3, len(topics) // 5):
        print(f"Only {ok_vol}/{len(topics)} topics fetched fresh — keeping the "
              f"previous snapshot untouched (likely rate-limited today).")
        return

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
    size_mb = OUTPUT_PATH.stat().st_size / 1e6
    print(f"Wrote {OUTPUT_PATH} ({size_mb:.1f} MB) — "
          f"volume OK for {ok_vol}/{len(topics)}, "
          f"source-country OK for {ok_cty}/{len(topics)}.")


if __name__ == "__main__":
    sys.exit(main())
