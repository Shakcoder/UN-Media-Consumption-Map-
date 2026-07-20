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

Run locally:  python3 scripts/check_source_editions.py
Exit code is always 0 (a "new edition" is news, not an error).
"""

from __future__ import annotations

import json
import re
import ssl
import sys
import urllib.request
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

# ---------------------------------------------------------------------------
# What the Atlas currently has integrated.
# WHEN YOU INTEGRATE A NEW EDITION: bump the year here in the same commit —
# that is what stops the watchdog from re-opening the issue forever.
# ---------------------------------------------------------------------------
INTEGRATED = {
    "rsf": 2025,          # RSF World Press Freedom Index
    "fh_fitw": 2026,      # Freedom House — Freedom in the World
    "fh_fotn": 2025,      # Freedom House — Freedom on the Net
    "dnr": 2026,          # Reuters Institute Digital News Report
    "gsma": 2024,         # GSMA Mobile Connectivity Index
    "afrobarometer": 9,   # Afrobarometer survey round (not a year)
    "wpp": 2024,          # UN DESA World Population Prospects (biennial)
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
        "check_url": "https://population.un.org/wpp/",
        "pattern": r"World Population Prospects (20\d\d)",
        "instructions": (
            "1. Open https://population.un.org/wpp/ and confirm the new revision (biennial).\n"
            "2. Download the median-age table (CSV).\n"
            "3. Update the median-age table/year labels in scripts/refresh_data.py.\n"
            "4. Bump the 'wpp' year in scripts/check_source_editions.py.\n"
            "5. Upload via GitHub → Add file → Upload files (one batch)."
        ),
    },
]


def _fetch(url: str, timeout: int = 25) -> tuple[int, str]:
    """Return (status_code, body_text). Never raises."""
    req = urllib.request.Request(url, headers={
        "User-Agent": "UN-Media-Atlas source watchdog (github.com; contact via repo issues)",
        "Accept": "text/html,application/xhtml+xml",
    })
    ctx = ssl.create_default_context()
    try:
        with urllib.request.urlopen(req, timeout=timeout, context=ctx) as resp:
            body = resp.read(400_000).decode("utf-8", errors="replace")
            return resp.status, body
    except urllib.error.HTTPError as e:
        return e.code, ""
    except Exception:
        return 0, ""


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
    findings = []

    for src in SOURCES:
        key = src["key"]
        have = INTEGRATED[key]

        if "probe_next_year_url" in src:
            # Try current+1 (and current+2 in case an edition was skipped)
            for candidate in (have + 1, have + 2):
                status, _ = _fetch(src["probe_next_year_url"].format(year=candidate))
                if status == 200:
                    findings.append((src, candidate))
                    break
            continue

        status, body = _fetch(src["check_url"])
        if (status != 200 or not body) and src.get("fallback_url"):
            status, body = _fetch(src["fallback_url"])
        if status != 200 or not body:
            print(f"[watchdog] {src['name']}: could not check ({status}) — will retry next run")
            continue
        newest = newest_edition_on_page(body, src["pattern"])
        if newest is None:
            print(f"[watchdog] {src['name']}: no edition number found on page — pattern may need updating")
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
            f"_Opened automatically by `.github/workflows/source-watchdog.yml`. "
            f"If this is a false alarm, close the issue; the watchdog will not reopen it for the same edition._"
        )
        out.append({"key": src["key"], "edition": newest, "title": title, "body": body})
        print(f"[watchdog] NEW EDITION: {src['name']} {newest}")

    Path("watchdog_findings.json").write_text(json.dumps(out, indent=2), encoding="utf-8")
    print(f"[watchdog] wrote watchdog_findings.json with {len(out)} finding(s)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
