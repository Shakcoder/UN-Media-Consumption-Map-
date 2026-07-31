#!/usr/bin/env python3
"""
fetch_tv_stations.py — build data/tv_stations.json: major TV stations per country.

Why this exists (and why it works the way it does)
--------------------------------------------------
DGC asked (2026-07-31) for the prominent TV stations of every country, drawn
from Wikipedia's regional station lists, kept current automatically, cited,
and layered UNDER the Atlas's existing hand-curated top_tv line (never
replacing it).

The naive approach - scraping the regional list pages straight into the
Atlas - fails this project's evidence bar. Wikipedia itself tags several of
those pages {{unreferenced}} and incomplete; they mix defunct stations and
foreign cable feeds into national lists (Azerbaijan's five entries included
Cartoon Network; Rwanda's only entry was ESPN Africa); and each page formats
differently, so a scraper would break silently when any of them is edited.

So the pipeline splits the job in two:

  1. RECALL - Wikipedia pages supply candidate names. For every country we
     harvest link targets from (a) its canonical pages ("List of television
     stations in X", "Television in X"), (b) the nine regional seed pages DGC
     pointed at, and (c) any {{Main|List of ...}} pages those seeds point to.
  2. PRECISION - every candidate must pass through its Wikidata record to
     survive: the record must say the station belongs to that country
     (kills foreign cable feeds), must carry no dissolved/end date (kills
     defunct stations), and must be typed as a television/broadcast entity
     (kills regulators, owners, and stray prose links). Wikidata is CC0, so
     the emitted data is cleanly licensed; the Wikipedia page consulted per
     country is named in that country's citation.

Ranking is by Wikidata sitelink count (how many language Wikipedias carry an
article on the station) - a PRESENCE proxy, not a viewership measure. No free
source measures audience share per station worldwide, and this project does
not invent figures, so the output is labeled "major stations", never "most
watched". The curated top_tv line (cross-checked against the CIA World
Factbook) remains the Atlas's statement of which stations lead.

Usage
-----
    python3 scripts/fetch_tv_stations.py                 # all 195 countries
    python3 scripts/fetch_tv_stations.py --countries KEN,BRA,IND   # debug
    python3 scripts/fetch_tv_stations.py --max-stations 12

Safety: if the result is implausibly thin (fewer countries covered than
MIN_COUNTRIES_COVERED, or fewer stations than MIN_TOTAL_STATIONS), nothing is
written and the exit code is non-zero - never overwrite good data with a bad
fetch. A country whose fresh harvest comes back empty keeps its previous
entry (marked carried_from_previous) rather than losing coverage to a flaky
page edit.

Sources: en.wikipedia.org page text (station-list pages; CC BY-SA 4.0,
         attributed per country) and wikidata.org entity records (CC0).
"""

from __future__ import annotations

import argparse
import json
import re
import ssl
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT_PATH = ROOT / "data" / "tv_stations.json"
COUNTRIES_PATH = ROOT / "data" / "countries.json"
STATIC_PATH = ROOT / "data" / "static_countries.json"

WIKI_API = "https://en.wikipedia.org/w/api.php"
WIKIDATA_API = "https://www.wikidata.org/w/api.php"
WDQS = "https://query.wikidata.org/sparql"
USER_AGENT = ("UN-Audience-Atlas/1.0 "
              "(https://github.com/Shakcoder/UN-Media-Consumption-Map-)")

# The nine regional pages DGC asked for (2026-07-31), harvested as seeds and
# kept as the validation set. Europe's page carries no stations itself (it
# links "Television in X" articles), which the canonical-title harvest covers.
SEED_PAGES = [
    "List of television stations in Africa",
    "List of digital television channels in Australia",
    "List of television stations in West Asia",
    "List of television stations in Southeast Asia",
    "List of television stations in East Asia",
    "List of European television stations",
    "Lists of television stations in North America",
    "List of local television stations in South America",
]

# Countries whose Wikipedia page titles differ from the Atlas's formal names.
TITLE_ALIASES = {
    "BOL": ["Bolivia"], "BRN": ["Brunei"], "CIV": ["Ivory Coast", "Côte d'Ivoire"],
    "COD": ["the Democratic Republic of the Congo", "DR Congo"],
    "COG": ["the Republic of the Congo", "Congo"],
    "CPV": ["Cape Verde", "Cabo Verde"], "CZE": ["the Czech Republic", "Czechia"],
    "FSM": ["the Federated States of Micronesia", "Micronesia"],
    "GBR": ["the United Kingdom"], "GMB": ["the Gambia"], "IRN": ["Iran"],
    "KOR": ["South Korea"], "LAO": ["Laos"], "MDA": ["Moldova"],
    "MMR": ["Myanmar", "Burma"], "NLD": ["the Netherlands"],
    "PHL": ["the Philippines"], "PRK": ["North Korea"], "RUS": ["Russia"],
    "SYR": ["Syria"], "TZA": ["Tanzania"], "USA": ["the United States"],
    "VEN": ["Venezuela"], "VNM": ["Vietnam"], "ARE": ["the United Arab Emirates"],
    "MHL": ["the Marshall Islands"], "SLB": ["the Solomon Islands"],
    "MDV": ["the Maldives"], "BHS": ["the Bahamas"], "COM": ["the Comoros"],
    "DOM": ["the Dominican Republic"], "CAF": ["the Central African Republic"],
    "TLS": ["East Timor", "Timor-Leste"], "TUR": ["Turkey", "Türkiye"],
    "VAT": ["Vatican City", "the Vatican City"], "PSE": ["Palestine", "the State of Palestine"],
}

# A few countries whose canonical list page uses a non-guessable title.
EXTRA_TITLES = {
    "USA": ["List of United States over-the-air television networks"],
    "GBR": ["List of television stations in the United Kingdom"],
    "AUS": ["List of digital television channels in Australia"],
}

# Accept an item when at least one of its P31 classes reads as an actual
# broadcaster/station/channel/network. Kills regulators, holding companies,
# stray prose links ("digital television transition in India"), and history
# articles that merely mention television.
CLASS_OK = re.compile(
    r"(?:television|tv|broadcast\w*|media) (?:station|channel|network|service|"
    r"company|organi[sz]ation|corporation)|broadcaster|^television$", re.I)

# Second chance for the Wikidata typing lottery: many real national
# broadcasters carry only a generic class ("state-owned enterprise" is all
# Côte d'Ivoire's RTI has). Accept those when the item's own name is
# unmistakably a TV org - unless the name is shaped like an article topic.
NAME_TV = re.compile(r"\btv\b|television|télévision|televisão|televisión|broadcast", re.I)
NAME_NOT_STATION = re.compile(r"transition|history|media of|list of|award|festival|ministry", re.I)

MIN_COUNTRIES_COVERED = 100     # refuse to write anything thinner than this
MIN_TOTAL_STATIONS = 500

SLEEP_PAGE = 0.2                # politeness between page fetches
SLEEP_BATCH = 0.5               # politeness between batched API calls

try:
    import certifi
    _CTX = ssl.create_default_context(cafile=certifi.where())
except ImportError:  # pragma: no cover
    _CTX = ssl.create_default_context()


def http_json(url: str, params: dict) -> dict:
    full = url + "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(full, headers={"User-Agent": USER_AGENT})
    for attempt in (1, 2, 3):
        try:
            with urllib.request.urlopen(req, timeout=90, context=_CTX) as resp:
                return json.load(resp)
        except (urllib.error.URLError, TimeoutError) as e:
            if attempt == 3:
                raise
            time.sleep(2 * attempt)
    return {}


def fetch_wikitext(title: str) -> str | None:
    data = http_json(WIKI_API, {
        "action": "parse", "page": title, "prop": "wikitext",
        "redirects": 1, "format": "json", "formatversion": 2})
    if "error" in data:
        return None
    return data.get("parse", {}).get("wikitext")


LINK_RE = re.compile(r"\[\[([^\[\]|#]+)(?:\|[^\[\]]*)?\]\]")
MAIN_TPL_RE = re.compile(r"\{\{\s*(?:Main|See also)\s*\|\s*([^{}|]+?)\s*(?:\|[^{}]*)?\}\}", re.I)
HEADER_RE = re.compile(r"^(=,{0}=+) *([^=]+?) *=+$".replace(",{0}", ""), re.M)

SKIP_TARGET = re.compile(
    r"^(File|Image|Category|Template|Wikipedia|Help|Portal|Special|Talk):"
    r"|^Lists? of |^Television in |^Media (?:of|in) |^Radio in ", re.I)


def harvest_links(wikitext: str) -> tuple[list[str], list[str]]:
    """Link targets on list-item or table lines - where stations live.

    Returns (station_candidates, sub_list_pages). Some countries' canonical
    page is only an INDEX of narrower lists (India's links per-language
    channel lists); those "List of ..." targets come back separately so the
    caller can follow them one level down when the direct harvest is thin.
    """
    out: list[str] = []
    sub: list[str] = []
    for line in wikitext.splitlines():
        s = line.strip()
        if not (s.startswith(("*", "#", "|", "!")) ):
            continue
        for m in LINK_RE.finditer(s):
            target = m.group(1).strip()
            if not target:
                continue
            if re.match(r"^Lists? of .*(?:television|TV)", target, re.I):
                sub.append(target)
            elif not SKIP_TARGET.search(target):
                out.append(target)
    return out, sub


def harvest_main_list_pages(wikitext: str) -> list[str]:
    """{{Main|List of television stations in X}} pointers inside seed pages."""
    out = []
    for m in MAIN_TPL_RE.finditer(wikitext):
        t = m.group(1).strip()
        if re.match(r"^List of television", t, re.I):
            out.append(t)
    return out


def split_seed_by_country(wikitext: str, name_to_iso: dict[str, str]) -> dict[str, list[str]]:
    """Assign each seed-page section's links to the country the header names."""
    per: dict[str, list[str]] = {}
    current_isos: list[str] = []
    for line in wikitext.splitlines():
        h = re.match(r"^=+ *([^=]+?) *=+$", line.strip())
        if h:
            header = h.group(1).strip()
            header = re.sub(r"\[\[|\]\]", "", header).split("|")[-1]
            current_isos = []
            # "Republic of the Congo and Democratic Republic of Congo"
            for part in re.split(r"\s+and\s+", header):
                iso = name_to_iso.get(_norm(part))
                if iso:
                    current_isos.append(iso)
            continue
        if not current_isos:
            continue
        s = line.strip()
        if s.startswith(("*", "#", "|", "!")):
            for m in LINK_RE.finditer(s):
                target = m.group(1).strip()
                if target and not SKIP_TARGET.search(target):
                    for iso in current_isos:
                        per.setdefault(iso, []).append(target)
    return per


def _norm(name: str) -> str:
    import unicodedata
    # Fold diacritics first: the Africa page's "Côte d'Ivoire" and "São Tomé
    # and Príncipe" headers must match their plain-ASCII aliases.
    name = "".join(ch for ch in unicodedata.normalize("NFKD", name)
                   if not unicodedata.combining(ch))
    n = name.casefold().strip()
    n = re.sub(r"^(the|republic of|kingdom of|state of|federal republic of|"
               r"people's republic of|democratic republic of)\s+", "", n)
    n = n.replace("&", "and")
    n = re.sub(r"[^a-z0-9 ]", "", n)
    return re.sub(r"\s+", " ", n)


def canonicalize_titles(titles: list[str]) -> dict[str, str]:
    """Resolve enwiki redirects so renamed articles still reach Wikidata."""
    mapping: dict[str, str] = {}
    for i in range(0, len(titles), 50):
        chunk = titles[i:i + 50]
        data = http_json(WIKI_API, {
            "action": "query", "titles": "|".join(chunk), "redirects": 1,
            "format": "json", "formatversion": 2})
        q = data.get("query", {})
        redirect = {r["from"]: r["to"] for r in q.get("redirects", [])}
        normalized = {n["from"]: n["to"] for n in q.get("normalized", [])}
        for t in chunk:
            t2 = normalized.get(t, t)
            mapping[t] = redirect.get(t2, t2)
        time.sleep(SLEEP_BATCH)
    return mapping


def fetch_entities(titles: list[str]) -> dict[str, dict]:
    """Wikidata records for enwiki titles: claims + sitelink count + label."""
    out: dict[str, dict] = {}
    for i in range(0, len(titles), 50):
        chunk = titles[i:i + 50]
        data = http_json(WIKIDATA_API, {
            "action": "wbgetentities", "sites": "enwiki",
            "titles": "|".join(chunk), "props": "claims|sitelinks|labels",
            "languages": "en", "format": "json", "formatversion": 2})
        for qid, ent in (data.get("entities") or {}).items():
            if qid.startswith("-"):
                continue
            title = (ent.get("sitelinks", {}).get("enwiki") or {}).get("title")
            if title:
                out[title] = ent
        time.sleep(SLEEP_BATCH)
    return out


def claim_ids(ent: dict, prop: str) -> list[str]:
    vals = []
    for c in ent.get("claims", {}).get(prop, []):
        dv = (c.get("mainsnak", {}).get("datavalue") or {}).get("value")
        if isinstance(dv, dict) and "id" in dv:
            vals.append(dv["id"])
    return vals


def has_claim(ent: dict, prop: str) -> bool:
    return bool(ent.get("claims", {}).get(prop))


def fetch_class_labels(qids: set[str]) -> dict[str, str]:
    out: dict[str, str] = {}
    ids = sorted(qids)
    for i in range(0, len(ids), 50):
        chunk = ids[i:i + 50]
        data = http_json(WIKIDATA_API, {
            "action": "wbgetentities", "ids": "|".join(chunk),
            "props": "labels", "languages": "en",
            "format": "json", "formatversion": 2})
        for qid, ent in (data.get("entities") or {}).items():
            out[qid] = (ent.get("labels", {}).get("en") or {}).get("value", "")
        time.sleep(SLEEP_BATCH)
    return out


def fetch_iso_to_qid() -> dict[str, str]:
    q = 'SELECT ?c ?iso WHERE { ?c wdt:P298 ?iso . }'
    data = http_json(WDQS, {"query": q, "format": "json"})
    out = {}
    for b in data["results"]["bindings"]:
        out[b["iso"]["value"]] = b["c"]["value"].rsplit("/", 1)[-1]
    return out


def scrub(s: str) -> str:
    """The database carries no em/en dashes by project rule."""
    return s.replace("—", "-").replace("–", "-").strip()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--countries", help="comma-separated ISO3 subset (debug)")
    ap.add_argument("--max-stations", type=int, default=12)
    args = ap.parse_args()

    countries = json.loads(COUNTRIES_PATH.read_text(encoding="utf-8"))
    countries = {k: v for k, v in countries.items() if not k.startswith("_")}
    static = json.loads(STATIC_PATH.read_text(encoding="utf-8"))

    subset = set(args.countries.split(",")) if args.countries else None

    previous: dict = {}
    if OUT_PATH.exists():
        try:
            previous = json.loads(OUT_PATH.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            previous = {}

    # --- name lookup tables -------------------------------------------------
    name_to_iso: dict[str, str] = {}
    titles_per_iso: dict[str, list[str]] = {}
    for iso, meta in countries.items():
        names = [meta["name"]] + TITLE_ALIASES.get(iso, [])
        for n in names:
            name_to_iso[_norm(n)] = iso
        titles_per_iso[iso] = []
        for n in names:
            titles_per_iso[iso] += [f"List of television stations in {n}",
                                    f"Television in {n}"]
        titles_per_iso[iso] += EXTRA_TITLES.get(iso, [])

    print("Resolving country QIDs from Wikidata (one query)...")
    iso_to_qid = fetch_iso_to_qid()
    missing_qid = [i for i in countries if i not in iso_to_qid]
    if missing_qid:
        print(f"  ! no Wikidata QID for: {', '.join(missing_qid)} (they will be skipped)")

    # --- harvest ------------------------------------------------------------
    candidates: dict[str, list[str]] = {iso: [] for iso in countries}
    page_used: dict[str, str] = {}

    print("Harvesting the regional seed pages...")
    seed_follow: dict[str, list[str]] = {}
    for seed in SEED_PAGES:
        wt = fetch_wikitext(seed)
        time.sleep(SLEEP_PAGE)
        if not wt:
            print(f"  ! seed page missing: {seed}")
            continue
        per = split_seed_by_country(wt, name_to_iso)
        n_links = sum(len(v) for v in per.values())
        print(f"  · {seed}: {len(per)} countries, {n_links} links")
        for iso, links in per.items():
            candidates[iso] += links
            page_used.setdefault(iso, seed)
        for t in harvest_main_list_pages(wt):
            iso = None
            m = re.match(r"List of television stations in (.+)", t, re.I)
            if m:
                iso = name_to_iso.get(_norm(m.group(1)))
            if iso:
                seed_follow.setdefault(iso, []).append(t)

    print("Harvesting per-country pages...")
    for n, (iso, meta) in enumerate(sorted(countries.items()), 1):
        if subset and iso not in subset:
            continue
        tried = list(dict.fromkeys(seed_follow.get(iso, []) + titles_per_iso[iso]))
        for title in tried:
            wt = fetch_wikitext(title)
            time.sleep(SLEEP_PAGE)
            if not wt:
                continue
            links, sub_pages = harvest_links(wt)
            # An index-shaped page (like India's) lists narrower lists rather
            # than stations; follow a bounded handful of them one level down.
            if len(links) < 5 and sub_pages:
                for sp in list(dict.fromkeys(sub_pages))[:6]:
                    sub_wt = fetch_wikitext(sp)
                    time.sleep(SLEEP_PAGE)
                    if sub_wt:
                        sub_links, _ = harvest_links(sub_wt)
                        links += sub_links
            if links:
                candidates[iso] += links
                page_used[iso] = title      # the richest source wins the citation
                break
        if n % 25 == 0:
            print(f"  · {n}/{len(countries)} countries harvested")

    # --- resolve and gate ---------------------------------------------------
    all_titles = sorted({t for links in candidates.values() for t in links})
    print(f"Canonicalizing {len(all_titles)} distinct link targets...")
    canon = canonicalize_titles(all_titles)

    resolved_titles = sorted(set(canon.values()))
    print(f"Fetching {len(resolved_titles)} Wikidata records...")
    entities = fetch_entities(resolved_titles)

    class_qids: set[str] = set()
    for ent in entities.values():
        class_qids.update(claim_ids(ent, "P31"))
    print(f"Fetching labels for {len(class_qids)} entity classes...")
    class_label = fetch_class_labels(class_qids)

    retrieved = datetime.now(timezone.utc).date().isoformat()
    result: dict = {}
    stats = {"covered": 0, "stations": 0, "carried": 0}
    recall_misses: list[str] = []

    for iso, meta in sorted(countries.items()):
        if subset and iso not in subset:
            if iso in previous and not iso.startswith("_"):
                result[iso] = previous[iso]     # debug runs keep other countries
            continue
        country_qid = iso_to_qid.get(iso)
        seen: set[str] = set()
        kept: list[dict] = []
        for raw in candidates[iso]:
            title = canon.get(raw, raw)
            ent = entities.get(title)
            if not ent:
                continue
            qid = ent.get("id")
            if not qid or qid in seen:
                continue
            seen.add(qid)
            if country_qid and country_qid not in claim_ids(ent, "P17"):
                continue                        # foreign feed or wrong country
            if has_claim(ent, "P576") or has_claim(ent, "P582"):
                continue                        # defunct
            label = (ent.get("labels", {}).get("en") or {}).get("value") or title
            class_hit = any(CLASS_OK.search(class_label.get(c, ""))
                            for c in claim_ids(ent, "P31"))
            name_hit = NAME_TV.search(label) and not NAME_NOT_STATION.search(label)
            if not (class_hit or name_hit):
                continue                        # not recognizably a TV/broadcast entity
            kept.append({
                "name": scrub(label),
                "article": title.replace(" ", "_"),
                "sitelinks": len(ent.get("sitelinks", {})),
            })
        kept.sort(key=lambda s: (-s["sitelinks"], s["name"]))
        kept = kept[:args.max_stations]

        if kept:
            page = page_used.get(iso, "List of television stations (regional pages)")
            url = "https://en.wikipedia.org/wiki/" + urllib.parse.quote(page.replace(" ", "_"))
            result[iso] = {
                "name": meta["name"],
                "stations": kept,
                "source": (f"Wikipedia station lists + Wikidata records, "
                           f"retrieved {retrieved} | {url}"),
            }
            stats["covered"] += 1
            stats["stations"] += len(kept)
        elif iso in previous and previous[iso].get("stations"):
            result[iso] = dict(previous[iso], carried_from_previous=True)
            stats["carried"] += 1
            stats["covered"] += 1
            stats["stations"] += len(previous[iso]["stations"])

        # Recall check against the hand-curated line (validation, not a gate).
        top_tv = ((static.get(iso) or {}).get("media") or {}).get("top_tv", "")
        if top_tv and iso in result:
            have = {s["name"].casefold() for s in result[iso]["stations"]}
            for cur in [c.strip() for c in top_tv.split(",") if c.strip()]:
                if not any(cur.casefold() in h or h in cur.casefold() for h in have):
                    recall_misses.append(f"{iso}: curated '{cur}' not in harvest")

    if subset:
        for iso in sorted(subset):
            entry = result.get(iso)
            if not entry:
                print(f"  {iso}: NOTHING SURVIVED THE GATE")
                continue
            names = ", ".join(f"{s['name']}({s['sitelinks']})" for s in entry["stations"])
            print(f"  {iso}: {names}")
            print(f"       source: {entry['source']}")

    # --- guards -------------------------------------------------------------
    # Floors apply to the MERGED result (fresh + carried + subset-preserved),
    # so a --countries backfill of a few countries can still write, while a
    # full run that comes back thin still refuses.
    stats["covered"] = sum(1 for k, v in result.items()
                           if not k.startswith("_") and v.get("stations"))
    stats["stations"] = sum(len(v.get("stations", [])) for k, v in result.items()
                            if not k.startswith("_"))
    if stats["covered"] < MIN_COUNTRIES_COVERED or stats["stations"] < MIN_TOTAL_STATIONS:
        print(f"REFUSING to write: coverage {stats['covered']} countries / "
              f"{stats['stations']} stations is below the floor "
              f"({MIN_COUNTRIES_COVERED}/{MIN_TOTAL_STATIONS}). "
              f"The existing file is left untouched.", file=sys.stderr)
        return 1

    result["_meta"] = {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "countries_covered": stats["covered"],
        "stations_total": stats["stations"],
        "carried_from_previous": stats["carried"],
        "max_stations_per_country": args.max_stations,
        "method": ("Candidate names harvested from Wikipedia station-list pages "
                   "(regional seeds + per-country lists); every candidate gated "
                   "through its Wikidata record: correct country (P17), not "
                   "dissolved (no P576/P582), typed as television/broadcast; "
                   "ordered by Wikidata sitelink count (international Wikipedia "
                   "presence). Presence is NOT viewership: the curated top_tv "
                   "line remains the Atlas's statement of leading stations."),
        "license": ("Station names/links: Wikipedia (CC BY-SA 4.0, attributed "
                    "per country). Structured facts: Wikidata (CC0)."),
    }

    OUT_PATH.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n",
                        encoding="utf-8")
    print(f"\nWrote {OUT_PATH.name}: {stats['covered']} countries, "
          f"{stats['stations']} stations, {stats['carried']} carried from previous.")
    uncovered = sorted(set(countries) - {k for k in result if not k.startswith('_')})
    if uncovered:
        print(f"No stations found for {len(uncovered)}: {', '.join(uncovered)}")
    if recall_misses:
        print(f"\nRecall check vs curated top_tv ({len(recall_misses)} misses):")
        for m in recall_misses[:40]:
            print(f"  ! {m}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
