#!/usr/bin/env python3
"""
fetch_rsf.py — download the RSF World Press Freedom Index from the source.

Why this exists
---------------
Until 2026-07-26 the RSF index lived as two hand-typed dictionaries inside
refresh_data.py (RSF_RANK_2025 / RSF_SCORE_2025 — 174 countries each,
transcribed by hand). That had two costs:

  1. Transcription error. Cross-checking the hand-typed 2025 table against
     RSF's own "Rank N-1" column in the 2026 file found 45 ranks that did
     not match RSF's own record of 2025, and 5 scores off by >0.5 points.
  2. An unmaintainable annual chore. The source watchdog opens an Issue
     every year saying "a new edition is out"; acting on it meant hand-
     editing ~350 numbers — exactly the kind of task a non-technical
     maintainer cannot safely do.

This script replaces both dictionaries with a fetch from RSF's own published
CSV, so refreshing the index is one command with no hand-typed numbers.

Usage
-----
    python3 scripts/fetch_rsf.py              # current year (2026)
    python3 scripts/fetch_rsf.py --year 2027  # next edition, when published

Writes data/sources/rsf/rsf_index.json, which refresh_data.py reads. If the
download fails the existing file is left untouched (never overwrite good
data with a failed fetch), and the exit code is non-zero.

Source: Reporters Without Borders (RSF), World Press Freedom Index.
        https://rsf.org/en/index — published CSV, one row per country.
        Free to use with attribution; the Atlas cites RSF on every figure.
"""

from __future__ import annotations

import argparse
import csv
import io
import json
import ssl
import sys
import urllib.error
import urllib.request
from datetime import date, timezone, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT_PATH = ROOT / "data" / "sources" / "rsf" / "rsf_index.json"

# RSF publishes each edition at a stable, predictable path.
CSV_URL = "https://rsf.org/sites/default/files/import_classement/{year}.csv"
INDEX_PAGE = "https://rsf.org/en/index"

# RSF's file is semicolon-delimited, comma-decimal, and Latin-1 encoded.
DELIMITER = ";"
ENCODING = "latin-1"

# RSF rates 180 countries/territories. Anything far from that means the
# format changed or we got an error page — refuse rather than write junk.
MIN_EXPECTED_ROWS = 150

# RSF codes some entries the Atlas does not carry as UN member states.
# They are kept in the file (harmless, traceable) but never joined blindly:
# refresh_data.py looks up by the Atlas's own ISO list.
NON_UN_CODES = {"HKG", "TWN", "XKX", "CSS", "CTU", "PSE"}


def _num(raw: str) -> float | None:
    """RSF writes decimals with a comma ('86,22'); empty cells mean no data."""
    raw = (raw or "").strip()
    if not raw:
        return None
    try:
        return float(raw.replace(",", "."))
    except ValueError:
        return None


def _int(raw: str) -> int | None:
    raw = (raw or "").strip()
    if not raw:
        return None
    try:
        return int(float(raw.replace(",", ".")))
    except ValueError:
        return None


def _ssl_context():
    """Same policy as refresh_data.py: certifi when available (fixes local
    macOS cert issues), system default elsewhere (CI runners are fine)."""
    try:
        import certifi
        return ssl.create_default_context(cafile=certifi.where())
    except ImportError:
        return ssl.create_default_context()


def fetch(year: int) -> str:
    url = CSV_URL.format(year=year)
    req = urllib.request.Request(url, headers={"User-Agent": "UN-Audience-Intelligence-Atlas/1.0 (data refresh)"})
    with urllib.request.urlopen(req, timeout=60, context=_ssl_context()) as resp:
        if resp.status != 200:
            raise RuntimeError(f"HTTP {resp.status} from {url}")
        return resp.read().decode(ENCODING, errors="replace")


def parse(raw_csv: str, year: int) -> dict:
    reader = csv.DictReader(io.StringIO(raw_csv), delimiter=DELIMITER)
    countries: dict[str, dict] = {}
    for row in reader:
        iso = (row.get("ISO") or "").strip().upper()
        if len(iso) != 3:
            continue
        score = _num(row.get(f"Score {year}") or row.get("Score") or "")
        rank = _int(row.get("Rank") or "")
        if score is None or rank is None:
            continue
        countries[iso] = {
            "rank": rank,
            "score": round(score, 2),
            "name_en": (row.get("Country_EN") or "").strip(),
            # RSF's five sub-indicators — richer than the single headline
            # score the Atlas showed before, and useful for explaining *why*
            # a market is rated as it is.
            "indicators": {
                "political": _num(row.get("Political Context") or ""),
                "economic": _num(row.get("Economic Context") or ""),
                "legal": _num(row.get("Legal Context") or ""),
                "social": _num(row.get("Social Context") or ""),
                "safety": _num(row.get("Safety") or ""),
            },
            # RSF's own record of the prior edition — lets the Atlas show
            # year-on-year movement without keeping a second hand-typed table.
            "prev": {
                "rank": _int(row.get("Rank N-1") or ""),
                "score": (lambda s: round(s, 2) if s is not None else None)(_num(row.get("Score N-1") or "")),
            },
            "non_un_member": iso in NON_UN_CODES,
        }

    if len(countries) < MIN_EXPECTED_ROWS:
        raise RuntimeError(
            f"only {len(countries)} usable rows parsed (expected ~180) — "
            "the RSF file format may have changed; refusing to write"
        )

    # Sanity gates: scores are 0–100, ranks are 1..n and unique.
    bad_scores = {i: c["score"] for i, c in countries.items() if not 0 <= c["score"] <= 100}
    if bad_scores:
        raise RuntimeError(f"scores outside 0–100: {bad_scores}")
    ranks = [c["rank"] for c in countries.values()]
    if len(set(ranks)) != len(ranks):
        dupes = sorted({r for r in ranks if ranks.count(r) > 1})
        raise RuntimeError(f"duplicate ranks in RSF file: {dupes}")

    return {
        "_meta": {
            "source": "Reporters Without Borders (RSF) — World Press Freedom Index",
            "edition": year,
            "source_url": INDEX_PAGE,
            "csv_url": CSV_URL.format(year=year),
            "retrieved": datetime.now(timezone.utc).date().isoformat(),
            "country_count": len(countries),
            "scale": "0–100, higher = more press freedom; rank 1 = most free",
            "note": (
                "Fetched from RSF's published CSV by scripts/fetch_rsf.py — no "
                "hand-typed figures. Sub-indicator scores (political, economic, "
                "legal, social, safety) are RSF's own five-context breakdown."
            ),
        },
        "countries": dict(sorted(countries.items())),
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--year", type=int, default=date.today().year,
                    help="index edition to fetch (default: current year)")
    args = ap.parse_args()

    for year in (args.year, args.year - 1):
        try:
            print(f"[rsf] fetching {year} edition …")
            payload = parse(fetch(year), year)
        except (urllib.error.URLError, urllib.error.HTTPError, RuntimeError) as exc:
            print(f"[rsf] {year}: {exc}")
            continue

        OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
        OUT_PATH.write_text(json.dumps(payload, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
        meta = payload["_meta"]
        print(f"[rsf] wrote {OUT_PATH.relative_to(ROOT)} — {meta['country_count']} countries, {meta['edition']} edition")
        return 0

    print("[rsf] FAILED — no edition could be fetched; existing data left untouched", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
