#!/usr/bin/env python3
"""
fetch_trends_google.py — daily per-country trending search queries.

For every Atlas country, fetches the ~10 currently-trending Google searches in
that country (Google Trends "Trending Now" RSS, free, no key) and writes a
display-ready summary to data/trends/country_searches.json.

WHAT THIS MEASURES (and what it does not): what people in that country are
SEARCHING FOR right now. That is a demand signal from a different direction to
everything else in the trend engine: Wikipedia reading lists show what people
opened, GDELT shows what newsrooms published, and this shows what people went
looking for. It is search interest, not news interest — football clubs and
TV shows sit next to elections and disasters, and that is the honest picture.

TRAFFIC FIGURES ARE BUCKETS, NOT COUNTS. Google publishes "100+", "500+",
"20000+" and similar floors, never an exact number. They are stored verbatim
in `traffic` and as the integer floor in `traffic_min`, and must never be
presented as a measured search volume or summed across queries.

COVERAGE IS PARTIAL AND HONEST. Google supports this feed for roughly 120 of
195 countries. An unsupported country returns HTTP 400 with an HTML error
page instead of a feed; it gets an explicit {"unsupported": true} entry so
the site can say so rather than showing a blank. Nothing is ever estimated
in its place.

LICENSE / WHAT WE DELIBERATELY DO NOT COMMIT. Google's "Export, embed and
cite Trends data" guidance permits reuse with attribution ("Data source:
Google Trends"). Each RSS item also carries third-party news headlines,
publisher names and thumbnail images (ht:news_item, ht:picture). Those are
other people's copyrighted content, and this fetcher drops every one of them
on purpose. Only the derived facts are committed: the query text, the traffic
bucket, and the date. Do not add the headlines back in.

NO HISTORY EXISTS UPSTREAM. This is a snapshot endpoint: whatever is trending
at fetch time is all Google will ever tell us, and an unpolled day is lost
forever. So this script keeps its own rolling archive of the last
HISTORY_DAYS days per country, which is what makes "new today" and "trending
for N days" answerable at all. Never "clean up" the history block: it cannot
be rebuilt from the API.

Cadence: daily (trend-engine.yml). Runs FIRST in that workflow because it
talks to a different host from the Wikimedia steps and finishes in minutes,
so a throttled Wikimedia day can never starve it.

Resilience, matching the other trend fetchers:
  * a country whose fetch fails keeps its previous entry (never loses data);
  * progress is checkpointed to disk, so a timeout still commits partial work;
  * unsupported countries are re-probed only every UNSUPPORTED_RECHECK_DAYS
    days, so the daily run does not spend minutes re-confirming ~74 countries
    Google does not cover (they are picked up automatically when it does);
  * if nothing at all is fetched, previous data is preserved and the script
    exits non-zero so the breakage is visible instead of silently green.
"""

from __future__ import annotations

import json
import re
import sys
import time
import xml.etree.ElementTree as ET
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import requests

# Reuse the project's ISO3→ISO2 map so scripts can never drift on country
# identity (same convention as fetch_trends_wiki_countries.py).
sys.path.insert(0, str(Path(__file__).parent))
from refresh_data import ISO3_TO_ISO2  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
STATIC_PATH = ROOT / "data" / "static_countries.json"
OUTPUT_PATH = ROOT / "data" / "trends" / "country_searches.json"

FEED = "https://trends.google.com/trending/rss"
USER_AGENT = "UN-Media-Atlas/1.0 (Global Content Intelligence Platform; research)"
REQ_TIMEOUT = (5, 20)          # (connect, read) seconds
PACE_SECONDS = 0.7             # polite pacing between countries
RETRY_PACE_SECONDS = 3.0       # slower second pass over countries that errored
TOP_N = 10                     # queries kept per country (the feed returns ~10)
HISTORY_DAYS = 7               # rolling archive depth — see docstring
UNSUPPORTED_RECHECK_DAYS = 7   # how often to re-probe a country Google skips


def load_json(path: Path):
    with path.open(encoding="utf-8") as fh:
        return json.load(fh)


def parse_traffic(raw: str) -> int:
    """'20K+' / '20,000+' / '500+' -> integer floor. 0 when unparseable.

    Google has used both plain digits and K/M suffixes over the years, so both
    are handled rather than assuming today's format is permanent.
    """
    s = (raw or "").strip().replace(",", "").replace("+", "").upper()
    m = re.match(r"^(\d+(?:\.\d+)?)\s*([KM]?)$", s)
    if not m:
        return 0
    value = float(m.group(1))
    value *= {"": 1, "K": 1_000, "M": 1_000_000}[m.group(2)]
    return int(value)


def fetch_country(iso2: str) -> list[dict] | None:
    """Return the country's trending queries, [] if unsupported, None on error.

    Google signals an unsupported geo with **HTTP 400 and an HTML error page**,
    not a 404 and not an empty feed (verified across TUV/VAT/CHN/ISL/LUX/MNG/
    SDN on 2026-08-10). Treating 400 as a transient error is the obvious trap:
    it puts ~74 permanently-unsupported countries into the retry queue every
    single day, which is minutes of wasted budget and an alarming-looking
    error count for something entirely normal.

    Deliberately narrow: only 400 means "not covered". 429/5xx and anything
    unrecognised stay transient, so a throttle or an outage can never be
    mistaken for Google dropping a country.
    """
    url = f"{FEED}?geo={iso2}"
    try:
        resp = requests.get(url, headers={"User-Agent": USER_AGENT},
                            timeout=REQ_TIMEOUT)
    except requests.RequestException:
        return None
    if resp.status_code == 400:
        return []          # Google does not cover this geo
    if resp.status_code != 200:
        return None        # 429 / 5xx / unknown → transient, retry later
    try:
        root = ET.fromstring(resp.content)
    except ET.ParseError:
        return []          # non-feed body = not covered either

    out: list[dict] = []
    for rank, item in enumerate(root.findall(".//item"), start=1):
        title = (item.findtext("title") or "").strip()
        if not title:
            continue
        # Namespaced ht:* children: matched by local name so a namespace-URI
        # change upstream cannot silently blank the traffic column.
        traffic = ""
        started = ""
        for child in item:
            local = child.tag.split("}")[-1]
            if local == "approx_traffic":
                traffic = (child.text or "").strip()
            elif local == "pubDate":
                started = (child.text or "").strip()
        # NOTE: ht:news_item / ht:picture / ht:picture_source are deliberately
        # NOT read here. See the license note in the module docstring.
        entry = {"query": title, "rank": rank}
        if traffic:
            entry["traffic"] = traffic
            entry["traffic_min"] = parse_traffic(traffic)
        if started:
            # "Mon, 10 Aug 2026 06:20:00 -0700" -> "2026-08-10"; best-effort,
            # the field is a nicety and never worth failing a country over.
            m = re.search(r"(\d{1,2})\s+(\w{3})\s+(\d{4})", started)
            if m:
                try:
                    entry["started"] = datetime.strptime(
                        f"{m.group(1)} {m.group(2)} {m.group(3)}", "%d %b %Y"
                    ).date().isoformat()
                except ValueError:
                    pass
        out.append(entry)
        if len(out) >= TOP_N:
            break
    return out


def main() -> int:
    static = load_json(STATIC_PATH)
    iso3s = sorted(k for k in static if len(k) == 3 and k in ISO3_TO_ISO2)

    previous_doc = load_json(OUTPUT_PATH) if OUTPUT_PATH.exists() else {}
    previous = (previous_doc.get("countries") or {}) if previous_doc else {}

    today = datetime.now(timezone.utc).date()
    today_str = today.isoformat()
    retrieved = today_str
    keep_after = (today - timedelta(days=HISTORY_DAYS)).isoformat()

    # Seed from the previous run so a country that fails today keeps yesterday's
    # entry (and its archive) instead of vanishing from the file.
    out: dict[str, dict] = json.loads(json.dumps(previous)) if previous else {}

    n_fresh = 0
    n_unsupported = 0
    n_skipped = 0            # unsupported, not due for a re-probe today
    carried: set[str] = set()

    def write_output() -> None:
        supported = sum(1 for r in out.values() if not r.get("unsupported"))
        doc = {
            "_meta": {
                "generated_at": datetime.now(timezone.utc)
                                .replace(microsecond=0).isoformat(),
                "source": "Google Trends (Trending Now RSS)",
                "source_url": FEED,
                "attribution": "Data source: Google Trends",
                "license": (
                    "Google Trends data, reusable with attribution per Google's "
                    "'Export, embed and cite Trends data' guidance. Only derived "
                    "facts (query, traffic bucket, date) are stored — the feed's "
                    "third-party news headlines and images are never committed."
                ),
                "method_note": (
                    "The ~10 searches trending in each country at fetch time, from "
                    "Google Trends' Trending Now RSS feed. Traffic figures are "
                    "Google's own buckets (\"100+\", \"20K+\"): floors, not measured "
                    "volumes, and they must never be summed or compared across "
                    "countries as if they were counts. Coverage is roughly 120 of "
                    "195 countries; the rest are marked unsupported rather than "
                    "left blank. This measures search interest of any kind, not "
                    "news interest specifically. The endpoint publishes no history, "
                    "so the per-country history block below is this project's own "
                    "rolling archive and cannot be rebuilt if deleted."
                ),
                "history_days_kept": HISTORY_DAYS,
                "coverage": {
                    "countries_with_data": supported,
                    "countries_unsupported": sum(
                        1 for r in out.values() if r.get("unsupported")),
                    "countries_total": len(iso3s),
                },
            },
            "countries": dict(sorted(out.items())),
        }
        OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
        with OUTPUT_PATH.open("w", encoding="utf-8") as fh:
            json.dump(doc, fh, ensure_ascii=False, indent=1)
            fh.write("\n")

    def due_for_recheck(iso3: str) -> bool:
        rec = previous.get(iso3) or {}
        if not rec.get("unsupported"):
            return True
        checked = rec.get("checked")
        if not checked:
            return True
        try:
            age = (today - datetime.strptime(checked, "%Y-%m-%d").date()).days
        except ValueError:
            return True
        return age >= UNSUPPORTED_RECHECK_DAYS

    def process(iso3: str) -> str:
        nonlocal n_fresh, n_unsupported
        queries = fetch_country(ISO3_TO_ISO2[iso3])

        if queries is None:                       # transient error
            if iso3 in previous:
                carried.add(iso3)
            return "error"

        if not queries:                           # Google does not cover this geo
            out[iso3] = {
                "unsupported": True,
                "note": ("Google Trends does not publish a trending-searches feed "
                         "for this country."),
                "checked": retrieved,
            }
            n_unsupported += 1
            return "unsupported"

        # Roll the archive forward: previous days, minus anything older than
        # the window, plus today. Written before `new`/`days_seen` are computed
        # so both are derived from the same picture.
        prev_rec = previous.get(iso3) or {}
        history = {d: q for d, q in (prev_rec.get("history") or {}).items()
                   if d > keep_after and d != today_str}
        history[today_str] = [q["query"] for q in queries]

        earlier = {q for d, qs in history.items() if d != today_str for q in qs}
        for q in queries:
            q["new"] = q["query"] not in earlier
            q["days_seen"] = sum(1 for qs in history.values() if q["query"] in qs)

        out[iso3] = {
            "date": today_str,
            "queries": queries,
            "history": dict(sorted(history.items())),
            "source": (f"Google Trends (Trending Now RSS) | trending searches "
                       f"{today_str} | {FEED}?geo={ISO3_TO_ISO2[iso3]} | "
                       f"retrieved {retrieved}"),
        }
        n_fresh += 1
        return "ok"

    errored: list[str] = []
    for i, iso3 in enumerate(iso3s):
        if not due_for_recheck(iso3):
            n_skipped += 1
            continue
        if process(iso3) == "error":
            errored.append(iso3)
        if (i + 1) % 25 == 0:
            print(f"  · {i + 1}/{len(iso3s)} countries — {n_fresh} fresh, "
                  f"{n_unsupported} unsupported, {n_skipped} skipped, "
                  f"{len(carried)} carried, {len(errored)} errored", flush=True)
        if (i + 1) % 50 == 0:
            write_output()      # checkpoint: safe at any interruption point
        time.sleep(PACE_SECONDS)

    # SECOND PASS — same reasoning as the Wikimedia fetcher: a throttle window
    # that swallowed a country in the main sweep has usually passed by now.
    if errored:
        print(f"Retrying {len(errored)} errored countries at "
              f"{RETRY_PACE_SECONDS:.0f}s pacing…", flush=True)
        still_missing = []
        for iso3 in errored:
            time.sleep(RETRY_PACE_SECONDS)
            if process(iso3) == "error" and iso3 not in out:
                still_missing.append(iso3)
        if still_missing:
            print(f"WARNING: no data obtained this run for {len(still_missing)} "
                  f"countries: {' '.join(still_missing)} — absent from the file "
                  f"until a later run succeeds.", flush=True)

    if n_fresh == 0 and previous:
        # Nothing fetched at all (feed down, shape change, or a hard block on
        # the runner's IP). Every previously-good entry is preserved; skip the
        # write to avoid a churn-only commit, and fail loudly.
        print("ERROR: no country returned trending searches — previous data "
              "preserved; check the Trends RSS endpoint and the response shape.",
              file=sys.stderr)
        return 1

    write_output()
    size_kb = OUTPUT_PATH.stat().st_size / 1e3
    print(f"Wrote {OUTPUT_PATH} ({size_kb:.0f} kB) — {n_fresh} fresh, "
          f"{n_unsupported} unsupported, {n_skipped} unsupported-skipped, "
          f"{len(carried)} carried forward.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
