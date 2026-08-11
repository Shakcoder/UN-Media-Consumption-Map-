#!/usr/bin/env python3
"""
fetch_ooni_censorship.py — measured news-site censorship, per country.

For every Atlas country, asks OONI's aggregation API how the country's last
TRAILING_DAYS days of web-connectivity measurements against NEWS-category
sites came out (confirmed blocked / anomalous / ok), and writes a summary to
data/trends/ooni_censorship.json.

WHAT THIS IS: the only measured, citable evidence of internet censorship in
the Atlas — real network tests run from real devices inside each country by
OONI Probe volunteers, against the Citizen Lab NEWS test list. It sits next
to the RSF and Freedom House RANKINGS as their empirical companion: a
ranking says "restrictive"; this says "12,310 measurements confirmed news
sites blocked in the last four weeks".

THE EPISTEMICS ARE THE HARD PART — every surface must respect them:
  * OONI probes are run by VOLUNTEERS. Measurement volume reflects where
    volunteers are, not where censorship is. A country with zero
    measurements is UNKNOWN, never "not censored" — the file marks it
    no_measurements and the site says so in words.
  * confirmed_count is the strong signal (fingerprint-matched blocking).
    anomaly_count is weaker (consistent with blocking but also with flaky
    networks) — reported, never headlined.
  * Low-volume countries get counts only, never derived percentages: a
    "blocking rate" from 12 measurements would be noise dressed as fact
    (same floor discipline as the Media Cloud layer).

LICENSE — READ BEFORE REUSING THIS DATA COMMERCIALLY. OONI data is
CC BY-NC-SA 4.0 (non-commercial). Integrated 2026-08-11 under the Chief's
decision that the Atlas is a non-profit product and NC licences are
acceptable. If the Atlas ever becomes part of a paid or revenue-generating
offering, THIS LAYER MUST BE REMOVED (delete the workflow step, the data
file, and its surfaces — grep for "ooni"). The _meta block, the docs and
the site's licences paragraph all carry the same warning.

Cadence: daily (trend-engine.yml, press lane), one aggregation call per
country, stalest-first, budget-capped — the same resilience pattern as
every other fetcher here (checkpoints, seed-from-previous, fail loudly
when nothing at all could be fetched).
"""

from __future__ import annotations

import json
import os
import sys
import time
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).parent))
from refresh_data import ISO3_TO_ISO2  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
STATIC_PATH = ROOT / "data" / "static_countries.json"
OUTPUT_PATH = ROOT / "data" / "trends" / "ooni_censorship.json"

API = "https://api.ooni.io/api/v1/aggregation"
USER_AGENT = "UN-Media-Atlas/1.0 (Global Content Intelligence Platform; research)"
REQ_TIMEOUT = (5, 60)
TRAILING_DAYS = 28      # window length: thin volunteer coverage needs a month
LAG_DAYS = 1            # measurements land continuously; end yesterday
PACE_SECONDS = 1.2
MAX_CALLS = 205
TIME_BUDGET_MIN = 8
CHECKPOINT_EVERY = 25


def main() -> int:
    static = json.loads(STATIC_PATH.read_text(encoding="utf-8"))
    iso3s = sorted(k for k in static if not k.startswith("_") and k in ISO3_TO_ISO2)

    previous: dict = {}
    if OUTPUT_PATH.exists():
        try:
            previous = json.loads(OUTPUT_PATH.read_text(encoding="utf-8")).get("countries", {})
        except (json.JSONDecodeError, OSError) as exc:
            print(f"WARNING: existing {OUTPUT_PATH.name} unreadable ({exc}) — rebuilding", flush=True)

    until = date.today() - timedelta(days=LAG_DAYS)
    since = until - timedelta(days=TRAILING_DAYS - 1)
    retrieved = date.today().isoformat()

    # Stalest-first: a truncated run self-heals tomorrow.
    iso3s.sort(key=lambda i: ((previous.get(i) or {}).get("retrieved") or "", i))

    out: dict[str, dict] = json.loads(json.dumps(previous)) if previous else {}

    def write_output() -> None:
        measured = sum(1 for r in out.values() if not r.get("no_measurements"))
        confirmed_anywhere = sum(1 for r in out.values() if (r.get("confirmed") or 0) > 0)
        doc = {
            "_meta": {
                "source": "OONI aggregation API (web_connectivity, Citizen Lab NEWS list)",
                "source_url": API,
                "license": (
                    "CC BY-NC-SA 4.0 — NON-COMMERCIAL. Integrated 2026-08-11 for "
                    "the Atlas as a non-profit product (Chief's decision). If the "
                    "Atlas ever becomes part of a paid or revenue-generating "
                    "offering, this layer must be removed — see the fetcher "
                    "docstring for the removal checklist."
                ),
                "method_note": (
                    f"Volunteer-run OONI Probe measurements of NEWS-category "
                    f"sites over a trailing {TRAILING_DAYS}-day window. "
                    "confirmed = fingerprint-matched blocking (the strong "
                    "signal); anomalies are consistent-with-blocking but "
                    "weaker and are never headlined. Measurement volume "
                    "follows volunteer presence, NOT censorship: a country "
                    "with no measurements is unknown, never clean. No rates "
                    "or percentages are derived — counts only, with the "
                    "measurement total always alongside."
                ),
                "window_days": TRAILING_DAYS,
                "generated_at": datetime.now(timezone.utc)
                                .replace(microsecond=0).isoformat(),
                "coverage": {
                    "countries_with_measurements": measured,
                    "countries_with_confirmed_blocking": confirmed_anywhere,
                    "countries_total": len(iso3s),
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
    n_calls = n_fresh = n_empty = n_errors = 0

    for i, iso3 in enumerate(iso3s, 1):
        if n_calls >= MAX_CALLS or (time.monotonic() - t0) / 60 > TIME_BUDGET_MIN:
            print(f"Budget reached at {i - 1}/{len(iso3s)} — stopping cleanly; "
                  f"stalest-first covers the rest tomorrow.", flush=True)
            break

        result = None
        for attempt in range(3):
            try:
                n_calls += 1
                resp = requests.get(API, params={
                    "probe_cc": ISO3_TO_ISO2[iso3], "test_name": "web_connectivity",
                    "category_code": "NEWS",
                    "since": since.isoformat(), "until": until.isoformat(),
                }, headers={"User-Agent": USER_AGENT}, timeout=REQ_TIMEOUT)
                if resp.status_code == 429:
                    pace = min(pace * 2, 30.0)
                    time.sleep(10 * (attempt + 1))
                    continue
                resp.raise_for_status()
                result = resp.json().get("result")
                pace = max(pace * 0.9, PACE_SECONDS)
                break
            except requests.RequestException:
                time.sleep(3 * (attempt + 1))
        time.sleep(pace)

        if not isinstance(result, dict):
            n_errors += 1              # previous entry, if any, stays
            continue

        total = int(result.get("measurement_count") or 0)
        entry: dict = {
            "window": {"start": since.isoformat(), "end": until.isoformat()},
            "measurements": total,
            "confirmed": int(result.get("confirmed_count") or 0),
            "anomalies": int(result.get("anomaly_count") or 0),
            "ok": int(result.get("ok_count") or 0),
            "failures": int(result.get("failure_count") or 0),
            "retrieved": retrieved,
            "source": (f"OONI aggregation API | web_connectivity vs Citizen Lab "
                       f"NEWS list, {since.isoformat()} to {until.isoformat()} | "
                       f"{API}?probe_cc={ISO3_TO_ISO2[iso3]}&test_name=web_connectivity"
                       f"&category_code=NEWS | retrieved {retrieved}"),
        }
        if total == 0:
            entry["no_measurements"] = True
            entry["note"] = ("No OONI measurements from this country in the "
                            "window — volunteer coverage, not evidence of an "
                            "open internet.")
            n_empty += 1
        out[iso3] = entry
        n_fresh += 1

        if i % CHECKPOINT_EVERY == 0:
            write_output()
        if i % 40 == 0:
            print(f"  · {i}/{len(iso3s)} — {n_fresh} fresh, {n_empty} without "
                  f"measurements, {n_errors} errored, pace {pace:.1f}s", flush=True)

    if n_fresh == 0 and previous:
        print("ERROR: no country returned data — previous file preserved; check "
              "the OONI API and the response shape.", file=sys.stderr)
        return 1

    write_output()
    print(f"Wrote {OUTPUT_PATH} — {n_fresh} countries refreshed "
          f"({n_empty} with no measurements in the window, {n_errors} errored, "
          f"{n_calls} calls).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
