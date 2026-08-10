#!/usr/bin/env python3
"""
build_mediacloud_collections.py — map Atlas countries to Media Cloud's
curated "<Country> - National" collections.

Run RARELY, by hand (needs MEDIACLOUD_API_KEY in the environment). It pages
through Media Cloud's public collection directory, keeps every collection
named exactly "<Something> - National", resolves <Something> to an Atlas
ISO3 code, and writes the mapping to data/sources/mediacloud_collections.json.

The mapping is COMMITTED so the daily fetcher never spends API quota (or
run time) on directory pagination — collections change rarely, countries
never. Re-run this script only if Media Cloud announces new national
collections or a country shows "no collection" that should have one.

Unmatched names in either direction are PRINTED, never guessed: a wrong
country mapping here would silently attribute one country's press to
another, which is worse than a gap.
"""

from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent
COUNTRIES_PATH = ROOT / "data" / "countries.json"
OUTPUT_PATH = ROOT / "data" / "sources" / "mediacloud_collections.json"

DIRECTORY = "https://search.mediacloud.org/api/sources/collections/"
USER_AGENT = "UN-Media-Atlas/1.0 (Global Content Intelligence Platform; research)"

# Media Cloud's naming vs the Atlas's — only entries verified by eye belong
# here. Left side: the "<Something>" from "<Something> - National", lowered.
ALIASES = {
    "united states": "USA", "united kingdom": "GBR", "russia": "RUS",
    "iran": "IRN", "syria": "SYR", "vietnam": "VNM", "viet nam": "VNM",
    "laos": "LAO", "bolivia": "BOL", "venezuela": "VEN", "tanzania": "TZA",
    "moldova": "MDA", "brunei": "BRN", "turkey": "TUR", "türkiye": "TUR",
    "czech republic": "CZE", "czechia": "CZE",
    "united arab emirates": "ARE", "saudi arabia": "SAU",
    "myanmar": "MMR", "burma": "MMR", "cape verde": "CPV", "cabo verde": "CPV",
    "east timor": "TLS", "timor-leste": "TLS", "timor leste": "TLS",
    "democratic republic of the congo": "COD", "congo - kinshasa": "COD",
    "congo, democratic republic of the": "COD",
    "republic of the congo": "COG", "congo - brazzaville": "COG",
    "ivory coast": "CIV", "côte d'ivoire": "CIV", "cote d'ivoire": "CIV",
    "south korea": "KOR", "korea, south": "KOR",
    "north korea": "PRK", "korea, north": "PRK",
    "micronesia": "FSM", "federated states of micronesia": "FSM",
    "eswatini": "SWZ", "swaziland": "SWZ",
    "north macedonia": "MKD", "macedonia": "MKD",
    "the gambia": "GMB", "gambia": "GMB", "the bahamas": "BHS", "bahamas": "BHS",
    "vatican city": "VAT", "holy see": "VAT",
    "são tomé and príncipe": "STP", "sao tome and principe": "STP",
    "saint kitts and nevis": "KNA", "saint vincent and the grenadines": "VCT",
    "saint lucia": "LCA", "palestine": "PSE", "west bank and gaza": "PSE",
    # Media Cloud's directory uses ISO-3166 FORMAL names — observed on the
    # first live harvest (2026-08-10):
    "bolivia, plurinational state of": "BOL",
    "congo, the democratic republic of the": "COD",
    "congo": "COG",                       # plain "Congo" = the republic; the
                                          # DRC has its own explicit entry
    "iran, islamic republic of": "IRN",
    "kyrgyzstan": "KGZ",
    "korea, republic of": "KOR",
    "korea, democratic people's republic of": "PRK",
    "lao people's democratic republic": "LAO",
    "macedonia, republic of": "MKD",
    "micronesia, federated states of": "FSM",
    "moldova, republic of": "MDA",
    "palestine, state of": "PSE",
    "russian federation": "RUS",
    "slovakia": "SVK",
    "somalia": "SOM",
    "tanzania, united republic of": "TZA",
    "venezuela, bolivarian republic of": "VEN",
    "holy see (vatican city state)": "VAT",
}


def main() -> int:
    key = os.environ.get("MEDIACLOUD_API_KEY", "").strip()
    if not key:
        print("ERROR: MEDIACLOUD_API_KEY is not set.", file=sys.stderr)
        return 1
    headers = {"Authorization": f"Token {key}", "User-Agent": USER_AGENT}

    countries = json.loads(COUNTRIES_PATH.read_text(encoding="utf-8"))
    countries.pop("_meta", None)
    name_to_iso: dict[str, str] = {}
    for iso, rec in countries.items():
        n = str(rec.get("name") or "").strip().lower()
        if n:
            name_to_iso[n] = iso
    name_to_iso.update(ALIASES)

    # Page through every collection whose name contains "National".
    results: list[dict] = []
    url, params = DIRECTORY, {"name": "National", "limit": 100}
    while url:
        r = requests.get(url, params=params, headers=headers, timeout=45)
        r.raise_for_status()
        page = r.json()
        results.extend(page.get("results") or [])
        url, params = page.get("next"), None   # `next` carries the query string

    mapping: dict[str, dict] = {}
    unmatched: list[str] = []
    for c in results:
        m = re.match(r"^(.+?)\s*-\s*National$", str(c.get("name") or ""))
        if not m:
            continue                     # "State & Local" etc. — not national
        country_name = m.group(1).strip().lower()
        iso = name_to_iso.get(country_name)
        if not iso:
            unmatched.append(c["name"])
            continue
        entry = {
            "id": c["id"],
            "name": c["name"],
            "source_count": c.get("source_count"),
        }
        # Two collections for one country: keep the larger outlet list, but
        # SAY so — a silent pick would be invisible forever.
        if iso in mapping:
            prev = mapping[iso]
            keep, drop = ((entry, prev)
                          if (entry.get("source_count") or 0) > (prev.get("source_count") or 0)
                          else (prev, entry))
            print(f"NOTE {iso}: two national collections — keeping "
                  f"{keep['name']!r} ({keep['source_count']} sources), dropping "
                  f"{drop['name']!r} ({drop['source_count']})")
            mapping[iso] = keep
        else:
            mapping[iso] = entry

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(json.dumps({
        "_meta": {
            "source": "Media Cloud collection directory",
            "source_url": DIRECTORY,
            "note": ("Mapping of Atlas ISO3 codes to Media Cloud's curated "
                     "'<Country> - National' collection IDs. Regenerate with "
                     "scripts/build_mediacloud_collections.py (needs "
                     "MEDIACLOUD_API_KEY); collections change rarely, so this "
                     "is committed rather than fetched daily."),
        },
        "collections": dict(sorted(mapping.items())),
    }, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")

    missing = sorted(set(countries) - set(mapping))
    print(f"Mapped {len(mapping)}/{len(countries)} countries "
          f"-> {OUTPUT_PATH}")
    if unmatched:
        print(f"Media Cloud names with no Atlas match ({len(unmatched)}): "
              f"{'; '.join(sorted(unmatched))}")
    if missing:
        print(f"Atlas countries with no national collection ({len(missing)}): "
              f"{' '.join(missing)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
