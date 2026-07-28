#!/usr/bin/env python3
"""
check_source_editions.py — the Atlas's annual-source watchdog.

The Atlas mixes two kinds of data:
  • AUTOMATED sources (World Bank API weekly, Wikimedia/GDELT daily) — these
    refresh themselves and need no human attention.
  • ANNUAL flagship reports (RSF, Freedom House, Reuters DNR, GSMA MCI,
    Afrobarometer, UN WPP) — a human downloads the new edition once a year.

This script closes the gap for the second kind: it probes each flagship
source's website for evidence that a NEWER edition than the one integrated
has been published. When it finds one, it prints a machine-readable line
that the source-watchdog workflow turns into a GitHub Issue with
step-by-step (non-coder) refresh instructions.

It never changes data by itself — it only watches and reports.

It also watches ITSELF: a source whose site the script can no longer read
(moved page, redesign, bot-blocking) would otherwise drop out of coverage in
total silence — the workflow would stay green while nobody was watching that
report any more. Those sources are reported as their own GitHub Issue, which
tells the maintainer to check that one source by hand until the probe is fixed.

Run locally:  python3 scripts/check_source_editions.py
Exit code is always 0. Both "a new edition is out" and "I can no longer read
this site" are news for a human, not crashes — and they travel as Issues,
which the maintainer actually reads, rather than as a red run in the Actions
tab, which tells nobody WHICH source broke.
"""

from __future__ import annotations

import json
import re
import ssl
import sys
import time
import urllib.request
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

# A probe that fails once is usually a passing network hiccup; a probe that
# fails three times in a row, with pauses in between, means the site really is
# unreachable. Only the second case is worth opening an issue about.
PROBE_ATTEMPTS = 3
RETRY_WAIT_SECONDS = 8

# Worth retrying: 0 = never got a reply (DNS/TLS/timeout), 429 = "slow down",
# 5xx = the site's own error. A 403 (blocking robots) or 404 (page gone) is a
# settled answer — retrying it only burns runner minutes.
RETRY_STATUSES = {0, 429}

# ---------------------------------------------------------------------------
# What the Atlas currently has integrated.
# WHEN YOU INTEGRATE A NEW EDITION: bump the year here in the same commit —
# that is what stops the watchdog from re-opening the issue forever.
# ---------------------------------------------------------------------------
INTEGRATED = {
    "rsf": 2026,          # RSF World Press Freedom Index (fetch: scripts/fetch_rsf.py)
    "fh_fitw": 2026,      # Freedom House — Freedom in the World
    "fh_fotn": 2025,      # Freedom House — Freedom on the Net
    "dnr": 2026,          # Reuters Institute Digital News Report
    "gsma": 2024,         # GSMA Mobile Connectivity Index
    "afrobarometer": 9,   # Afrobarometer survey round (not a year)
    "wpp": 2024,          # UN DESA World Population Prospects (biennial)
    "ad_market": 2025,    # WPP Media TYNY / Dentsu year-end ad forecasts (December editions)
}

SOURCES = [
    {
        "key": "rsf",
        "name": "RSF World Press Freedom Index",
        # rsf.org blocks non-browser requests (403), so the primary probe is the
        # Wikipedia article, which is updated within days of each edition.
        "check_url": "https://en.wikipedia.org/wiki/World_Press_Freedom_Index",
        "fallback_url": "https://rsf.org/en/index",
        "pattern": r"(20\d\d) World Press Freedom Index|World Press Freedom Index[^0-9]{0,20}(20\d\d)",
        "instructions": (
            "1. Open https://rsf.org/en/index and confirm the new edition is out.\n"
            "2. Download the new CSV (RSF publishes one per edition).\n"
            "3. In scripts/refresh_data.py, update the RSF score table and the year in its source labels.\n"
            "4. Bump the 'rsf' year in scripts/check_source_editions.py (INTEGRATED map).\n"
            "5. Upload the changed files via GitHub → Add file → Upload files (one batch)."
        ),
    },
    {
        "key": "fh_fitw",
        "name": "Freedom House — Freedom in the World",
        "check_url": "https://freedomhouse.org/report/freedom-world",
        "pattern": r"Freedom in the World (20\d\d)",
        "instructions": (
            "1. Open https://freedomhouse.org/report/freedom-world and confirm the new edition.\n"
            "2. Download the official 'All Data' XLSX (Country and Territory Ratings and Statuses).\n"
            "3. Replace the files in data/sources/freedom_house/ with the new ones.\n"
            "4. Update the FH tables/year labels in scripts/refresh_data.py.\n"
            "5. Bump the 'fh_fitw' year in scripts/check_source_editions.py.\n"
            "6. Upload everything via GitHub → Add file → Upload files (one batch)."
        ),
    },
    {
        "key": "fh_fotn",
        "name": "Freedom House — Freedom on the Net",
        "check_url": "https://freedomhouse.org/report/freedom-net",
        "pattern": r"Freedom on the Net (20\d\d)",
        "instructions": (
            "1. Open https://freedomhouse.org/report/freedom-net and confirm the new edition.\n"
            "2. Download the country-scores data file.\n"
            "3. Update the FOTN table/year labels in scripts/refresh_data.py.\n"
            "4. Bump the 'fh_fotn' year in scripts/check_source_editions.py.\n"
            "5. Upload via GitHub → Add file → Upload files (one batch)."
        ),
    },
    {
        "key": "dnr",
        "name": "Reuters Institute Digital News Report",
        # The next edition's landing page 404s until it exists — probe it directly.
        "probe_next_year_url": "https://reutersinstitute.politics.ox.ac.uk/digital-news-report/{year}",
        "instructions": (
            "1. Open the new edition's page and its country pages.\n"
            "2. Update the per-country DNR figures in scripts/refresh_data.py "
            "(trust, TV/online/social news use) and the year in its source labels.\n"
            "3. Bump the 'dnr' year in scripts/check_source_editions.py.\n"
            "4. Upload via GitHub → Add file → Upload files (one batch)."
        ),
    },
    {
        "key": "gsma",
        "name": "GSMA Mobile Connectivity Index",
        "check_url": "https://www.gsma.com/r/somic/",
        "fallback_url": "https://www.mobileconnectivityindex.com/",
        "pattern": r"State of Mobile Internet Connectivity (20\d\d)|(20\d\d) (?:Index|index|data)",
        "instructions": (
            "1. Open https://www.mobileconnectivityindex.com and check the latest data year.\n"
            "2. Download the new country scores (free download on the site).\n"
            "3. Update the MCI table/year labels in scripts/refresh_data.py.\n"
            "4. Bump the 'gsma' year in scripts/check_source_editions.py.\n"
            "5. Upload via GitHub → Add file → Upload files (one batch)."
        ),
    },
    {
        "key": "afrobarometer",
        "name": "Afrobarometer (survey round)",
        "check_url": "https://www.afrobarometer.org/surveys-and-methods/",
        "pattern": r"[Rr]ound (\d{1,2})",
        "instructions": (
            "1. Check https://www.afrobarometer.org/surveys-and-methods/ for the newest completed round.\n"
            "2. Register (free) and download the new round's merged microdata.\n"
            "3. Re-run the radio/news-source computation and update scripts/refresh_data.py.\n"
            "4. Bump the 'afrobarometer' round in scripts/check_source_editions.py.\n"
            "5. Upload via GitHub → Add file → Upload files (one batch)."
        ),
    },
    {
        "key": "wpp",
        "name": "UN DESA World Population Prospects",
        # population.un.org/wpp builds its page with JavaScript, so the revision
        # year is never in the HTML this script downloads. The Wikipedia article
        # lists every revision and is updated within days of a new one — the same
        # trick the RSF probe above uses.
        "check_url": "https://en.wikipedia.org/wiki/World_Population_Prospects",
        "fallback_url": "https://population.un.org/wpp/",
        "pattern": r"World Population Prospects (20\d\d)",
        "instructions": (
            "1. Open https://population.un.org/wpp/ and confirm the new revision (biennial).\n"
            "2. Download the median-age table (CSV).\n"
            "3. Update the median-age table/year labels in scripts/refresh_data.py.\n"
            "4. Bump the 'wpp' year in scripts/check_source_editions.py.\n"
            "5. Upload via GitHub → Add file → Upload files (one batch)."
        ),
    },
    {
        "key": "ad_market",
        "name": "Ad-market forecasts (WPP Media TYNY + Dentsu, December editions)",
        # Wikipedia is not reliable here; probe the trade press index instead.
        # Both publishers put the year in their year-end release headlines.
        "check_url": "https://www.dentsu.com/news-releases",
        "fallback_url": "https://www.wppmedia.com/",
        "pattern": r"[Aa]d [Ss]pend [Ff]orecasts?[^0-9]{0,40}(20\d\d)|This Year,? Next Year[^0-9]{0,40}(20\d\d)",
        "instructions": (
            "1. Each December, WPP Media ('This Year, Next Year') and Dentsu ('Global Ad Spend\n"
            "   Forecasts') publish free year-end summaries. Download both PDFs/press pages.\n"
            "2. Open data/ad_market.json — its _meta.how_to_update field walks through every step.\n"
            "3. Replace the figures with the new edition's numbers (keep the same field names),\n"
            "   update _meta.sources edition labels and the 'updated' date.\n"
            "4. Bump the 'ad_market' year in scripts/check_source_editions.py.\n"
            "5. Commit data/ad_market.json + scripts/check_source_editions.py in one batch.\n"
            "   No other file changes — the analyst reads ad_market.json directly."
        ),
    },
]


# The footer of every "new edition" reminder. It has to spell out how the
# reminder ends, because the obvious move — closing it — used to silence that
# edition forever: publishers often announce an edition months before the data
# is downloadable, so the reminder closed as "not out yet" was the same reminder
# that should have fired when it really was out. The workflow now re-opens a
# closed reminder next month, and only two things stop it: integrating the
# edition (bumping INTEGRATED) or deliberately labelling it dismissed.
# The label is GitHub's built-in `wontfix` on purpose — it is already in every
# repository's label menu, so nobody has to create one to switch a reminder off.
CLOSING_A_NEW_EDITION_ISSUE = (
    "_Opened automatically by `.github/workflows/source-watchdog.yml`._\n\n"
    "**Is it not actually downloadable yet?** Some publishers announce an edition long "
    "before the data appears. Close this issue — the watchdog checks again next month and "
    "will remind you again, so an early announcement can never swallow the real one.\n\n"
    "**Once you have integrated the new edition**, change `\"{key}\"` in the `INTEGRATED` map "
    "at the top of `scripts/check_source_editions.py` to the new edition number. That is what "
    "ends the reminder for good.\n\n"
    "**Decided never to integrate this source?** Close this issue and tick the `wontfix` "
    "label on it — that is the only thing that silences this reminder permanently."
)


def _ssl_context() -> ssl.SSLContext:
    """HTTPS trust store.

    Uses certifi's list of trusted authorities when it happens to be installed
    (it comes along with many other packages) and Python's own otherwise. On a
    Mac where Python's "Install Certificates" step was never run, the plain
    default rejects every site and a local run would report all eight sources
    as unreadable — an alarming, entirely false picture.
    """
    try:
        import certifi
        return ssl.create_default_context(cafile=certifi.where())
    except Exception:
        return ssl.create_default_context()


def _fetch(url: str, timeout: int = 25) -> tuple[int, str]:
    """Return (status_code, body_text). Never raises."""
    req = urllib.request.Request(url, headers={
        "User-Agent": "UN-Media-Atlas source watchdog (github.com; contact via repo issues)",
        "Accept": "text/html,application/xhtml+xml",
    })
    ctx = _ssl_context()
    try:
        with urllib.request.urlopen(req, timeout=timeout, context=ctx) as resp:
            body = resp.read(400_000).decode("utf-8", errors="replace")
            return resp.status, body
    except urllib.error.HTTPError as e:
        return e.code, ""
    except Exception:
        return 0, ""


def fetch_with_retries(url: str) -> tuple[int, str]:
    """Fetch a page, retrying only the failures that might be temporary."""
    status, body = 0, ""
    for attempt in range(1, PROBE_ATTEMPTS + 1):
        status, body = _fetch(url)
        if status == 200 and body:
            return status, body
        if attempt == PROBE_ATTEMPTS or not (status in RETRY_STATUSES or status >= 500):
            return status, body
        time.sleep(RETRY_WAIT_SECONDS)
    return status, body


def why_unreadable(status: int) -> str:
    """Plain-English reason a probe failed, for the Issue a human will read."""
    if status == 0:
        return ("the site never answered — its address, its security certificate "
                "or the connection itself failed, on every attempt")
    if status == 403:
        return "the site refused the request (403); it is now blocking automated visitors"
    if status == 404:
        return "the page has moved or been deleted (404)"
    if status == 429:
        return "the site asked us to slow down (429) on every attempt"
    return f"the site answered with HTTP {status} on every attempt"


def newest_edition_on_page(body: str, pattern: str) -> int | None:
    """Largest plausible edition number the page mentions."""
    hits = []
    for m in re.findall(pattern, body):
        # patterns with alternation return tuples — take every non-empty group
        groups = m if isinstance(m, tuple) else (m,)
        hits.extend(int(g) for g in groups if g)
    hits = [h for h in hits if 1 <= h <= 2100]
    return max(hits) if hits else None


def main() -> int:
    findings = []     # (source, edition number seen on the site)
    unreadable = []   # (source, plain-English reason) — watchdog is blind here

    for src in SOURCES:
        key = src["key"]
        have = INTEGRATED[key]

        if "probe_next_year_url" in src:
            # Try current+1 (and current+2 in case an edition was skipped)
            found = False
            broken = None
            for candidate in (have + 1, have + 2):
                status, _ = fetch_with_retries(src["probe_next_year_url"].format(year=candidate))
                if status == 200:
                    findings.append((src, candidate))
                    found = True
                    break
                # 404 is the expected answer for an edition that isn't out yet.
                # Anything else means the probe itself stopped working.
                if status != 404 and broken is None:
                    broken = status
            if found:
                continue
            if broken is None:
                print(f"[watchdog] {src['name']}: up to date (integrated {have}, "
                      f"{have + 1} not published yet)")
            else:
                reason = why_unreadable(broken)
                unreadable.append((src, reason))
                print(f"[watchdog] CANNOT CHECK: {src['name']} — {reason}")
            continue

        status, body = fetch_with_retries(src["check_url"])
        if (status != 200 or not body) and src.get("fallback_url"):
            status, body = fetch_with_retries(src["fallback_url"])
        if status != 200 or not body:
            reason = why_unreadable(status)
            unreadable.append((src, reason))
            print(f"[watchdog] CANNOT CHECK: {src['name']} — {reason}")
            continue
        newest = newest_edition_on_page(body, src["pattern"])
        # A page that LOADS but carries no edition number is the common failure
        # here — a site reorganises and the year moves to another page. The
        # fallback used to be tried only when the fetch itself failed, so that
        # case went straight to "cannot check" without ever looking at the
        # alternative URL the source entry provides for exactly this purpose.
        if newest is None and src.get("fallback_url"):
            alt_status, alt_body = fetch_with_retries(src["fallback_url"])
            if alt_status == 200 and alt_body:
                alt_newest = newest_edition_on_page(alt_body, src["pattern"])
                if alt_newest is not None:
                    newest = alt_newest
        if newest is None:
            reason = ("the page loaded, but no edition number could be read from it — "
                      "either the site has been redesigned, or it now writes its text "
                      "with JavaScript, which this script cannot run")
            unreadable.append((src, reason))
            print(f"[watchdog] CANNOT CHECK: {src['name']} — no edition number on the page")
            continue
        if newest > have:
            findings.append((src, newest))
        else:
            print(f"[watchdog] {src['name']}: up to date (integrated {have}, page shows {newest})")

    # Machine-readable output for the workflow step
    out = []
    for src, newest in findings:
        title = f"New edition available: {src['name']} ({newest})"
        body = (
            f"The source watchdog detected that **{src['name']} {newest}** appears to be published, "
            f"while the Atlas currently integrates edition **{INTEGRATED[src['key']]}**.\n\n"
            f"### How to refresh (no coding needed beyond edits described)\n{src['instructions']}\n\n"
            f"{CLOSING_A_NEW_EDITION_ISSUE.format(key=src['key'])}"
        )
        out.append({"kind": "new_edition", "key": src["key"], "edition": newest,
                    "title": title, "body": body})
        print(f"[watchdog] NEW EDITION: {src['name']} {newest}")

    for src, reason in unreadable:
        title = f"Watchdog cannot check: {src['name']}"
        where = src.get("check_url") or src.get("probe_next_year_url", "").format(
            year=INTEGRATED[src["key"]] + 1)
        body = (
            f"The source watchdog could not work out which edition of **{src['name']}** is "
            f"current: {reason}.\n\n"
            f"**Until this is repaired, nothing is watching this source** — a new edition "
            f"could come out and no reminder would ever appear. The Atlas keeps serving the "
            f"edition it already has (**{INTEGRATED[src['key']]}**), correctly labelled, so no "
            f"published figure is wrong; the risk is only that it quietly gets old.\n\n"
            f"### What to do now (no coding)\n"
            f"Open the source yourself — {where} — and see whether an edition newer than "
            f"**{INTEGRATED[src['key']]}** has been published. If it has, follow these steps:\n\n"
            f"{src['instructions']}\n\n"
            f"Put a note in your calendar to repeat that check once a year until the watchdog "
            f"is fixed.\n\n"
            f"### To make the watchdog see this source again (needs someone technical)\n"
            f"In `scripts/check_source_editions.py`, find the `{src['key']}` entry in the "
            f"`SOURCES` list and point `check_url` at a page that still shows the edition "
            f"number in plain HTML (a Wikipedia article often works when the publisher's own "
            f"site does not — see the `rsf` and `wpp` entries), then adjust `pattern` to match "
            f"it. Test with `python3 scripts/check_source_editions.py`.\n\n"
            f"_Opened automatically by `.github/workflows/source-watchdog.yml`. Closing this "
            f"issue is fine — if the source is still unreadable at the next monthly run, the "
            f"watchdog opens it again, so the blind spot cannot be forgotten. To stop the "
            f"reminders permanently, close it and tick the `wontfix` label._"
        )
        out.append({"kind": "cannot_check", "key": src["key"], "title": title, "body": body})

    Path("watchdog_findings.json").write_text(json.dumps(out, indent=2), encoding="utf-8")
    print(f"[watchdog] wrote watchdog_findings.json with {len(out)} finding(s): "
          f"{len(findings)} new edition(s), {len(unreadable)} source(s) that could not be checked")
    return 0


if __name__ == "__main__":
    sys.exit(main())
