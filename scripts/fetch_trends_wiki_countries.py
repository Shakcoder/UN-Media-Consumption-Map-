#!/usr/bin/env python3
"""
fetch_trends_wiki_countries.py — daily per-country Wikipedia reading lists.

For every Atlas country, fetches the ~100 most-read Wikimedia pages FROM that
country (Wikimedia AQS `pageviews/top-per-country`, free, no key, CC0) and
writes a filtered, display-ready summary to data/trends/country_reading.json.

WHAT THIS MEASURES (and what it does not): the list is what that country's
Wikipedia READERS opened yesterday — a measured, directly per-country demand
signal (unlike topic_intelligence.json, whose country attribution is a
language-weight approximation). It says nothing about people who are not on
Wikipedia. View counts are Wikimedia's `views_ceil` — privacy-rounded UP to
the next hundred — so they are ceilings, not exact counts.

COVERAGE IS HONESTLY PARTIAL. Wikimedia withholds this dataset for countries
on its Country and Territory Protection List (e.g. RUS, CHN, IRN, SAU) and
for low-volume countries below its reporting threshold (e.g. MLT, FJI).
Those countries get an explicit {"withheld": true} entry — the site says so
instead of showing nothing, and nothing is ever estimated in their place.

FILTERING: the raw top-100 includes main pages, Special:/search pages and
bot/VPN noise (observed: it.wikisource "Speciale:Ricerca" in Brazil's top 5).
We keep only *.wikipedia projects and drop known main-page titles and
non-article namespaces via the curated lists below. Heuristic by nature —
an occasional non-article title may survive; the method note says so.

Cadence: daily (trend-engine.yml). Each run fetches yesterday (falls back to
the day before — the API publishes with ~1 day lag). A country whose fetch
fails keeps its previous entry, so the file never loses data on a bad day.
"""

from __future__ import annotations

import json
import os
import sys
import time
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import requests

# Reuse the project's ISO3→ISO2 map so scripts can never drift on country
# identity (same convention as fetch_statcounter.py).
sys.path.insert(0, str(Path(__file__).parent))
from refresh_data import ISO3_TO_ISO2  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
STATIC_PATH = ROOT / "data" / "static_countries.json"
OUTPUT_PATH = ROOT / "data" / "trends" / "country_reading.json"

API = "https://wikimedia.org/api/rest_v1/metrics/pageviews/top-per-country"
USER_AGENT = "UN-Media-Atlas/1.0 (Global Content Intelligence Platform; research)"
REQ_TIMEOUT = (5, 20)   # (connect, read) seconds
PACE_SECONDS = 1.0      # polite pacing — AQS burst-limits anonymous clients
RETRY_PACE_SECONDS = 3.0  # slower second pass over countries that errored
TOP_N = 15              # articles kept per country after filtering
MIX_TOP = 5             # reading-language entries kept per country

# Known main-page titles (underscore form, as the API returns them). Most
# main pages carry a project namespace prefix and are caught by
# NAMESPACE_PREFIXES below; these are the ones that do not.
MAIN_PAGES = {
    "Main_Page", "Pagina_principale", "Hoofdpagina", "Strona_główna",
    "Заглавная_страница", "メインページ", "الصفحة_الرئيسية", "صفحهٔ_اصلی",
    "עמוד_ראשי", "मुखपृष्ठ", "প্রধান_পাতা", "Halaman_Utama", "Trang_Chính",
    "หน้าหลัก", "Anasayfa", "Головна_сторінка", "Hlavní_strana", "Forside",
    "Kezdőlap", "Pagina_principală", "Начална_страница", "Главна_страна",
    "Glavna_stranica", "Hlavná_stránka", "Pagrindinis_puslapis", "Ana_Səhifə",
    "Басты_бет", "Bosh_sahifa", "صفحۂ_اول", "முதற்_பக்கம்", "మొదటి_పేజీ",
    "പ്രധാന_താൾ", "Mwanzo", "ዋናው_ገጽ", "ဗဟိုစာမျက်နှာ", "ទំព័រដើម",
    "मुख्य_पृष्ठ", "ප්‍රධාන_පිටුව", "მთავარი_გვერდი", "Գլխավոր_էջ", "Esileht",
    "Sākumlapa", "Glavna_stran", "Laman_Utama", "Unang_Pahina",
    "Faqja_kryesore", "Главна_страница", "Почетна_страна",
}

# Non-article namespace prefixes (the segment before the first ":"), canonical
# English plus the localized forms of the large editions. A title whose prefix
# is listed here is a site page (search, portal, project page…), not an
# encyclopedia article.
NAMESPACE_PREFIXES = {
    # Special / search
    "Special", "Spezial", "Especial", "Spécial", "Speciale", "Speciaal",
    "Specjalna", "Служебная", "Спеціальна", "Специални", "Специјална",
    "特別", "特殊", "특수", "خاص", "ویژه", "מיוחד", "विशेष", "বিশেষ", "พิเศษ",
    "Đặc_biệt", "Özel", "Istimewa", "Espesyal", "Speciális", "Speciální",
    "Špeciálne", "Toiminnot", "Spesial", "Speciel", "Ειδικό", "Ειδικές",
    # Project (Wikipedia:) namespaces
    "Wikipedia", "Wikipédia", "Wikipedie", "Википедия", "Вікіпедія",
    "ويكيبيديا", "ویکی‌پدیا", "ויקיפדיה", "विकिपीडिया", "উইকিপিডিয়া",
    "วิกิพีเดีย", "ვიკიპედია", "Վիքիպեդիա", "위키백과", "Viquipèdia",
    "Vikipedi", "Vikipedija", "Wikipedija", "Wikipedia_talk", "Vikipeedia",
    # Other non-article namespaces
    "Portal", "Portail", "Portale", "Портал", "بوابة", "Πύλη", "Portaal",
    "User", "Utilisateur", "Usuario", "Usuário", "Benutzer", "Участник",
    "利用者", "사용자", "Bruger", "Gebruiker",
    "File", "Datei", "Fichier", "Archivo", "Ficheiro", "Файл", "ملف",
    "Berkas", "Tập_tin", "ไฟล์", "Dosya", "Plik", "Soubor", "Tiedosto",
    "Fil", "Bestand", "Fitxer", "Arquivo", "Datoteka", "Датотека", "Фајл",
    "ファイル", "파일", "文件", "Anexo",
    "Category", "Catégorie", "Kategorie", "Categoría", "Categoria",
    "Категория", "Категорія", "تصنيف",
    "Template", "Modèle", "Plantilla", "Vorlage", "Шаблон",
    "Help", "Aide", "Ayuda", "Hilfe", "Справка",
    "Talk", "Discussion", "Discussão", "Diskussion", "Обсуждение",
    "Draft", "Wikidata", "Commons", "Meta",
}


# Legacy endpoints and site plumbing that carry no namespace prefix and so
# slip past the checks below. "wiki.phtml" is a pre-2003 MediaWiki URL that
# only scanners still request — it showed up as a "most-read article" in
# three editions of Kenya's raw list on 2026-08-11.
NON_ARTICLE_TITLES = {"wiki.phtml", "index.php", "index.html"}

# EDITORIAL EXCLUSION (decided by the project owner, 2026-08-17): articles
# about adult-entertainment sites and explicit-content markers are not
# published in the Atlas's reading lists, even when genuinely among a
# country's most-read pages (they reliably are, in small privacy-thresholded
# markets). This is an editorial call for a UN-branded product, not a data
# judgement — the method note discloses it. The list is deliberately NARROW:
# site/brand articles and rating-marker pages only. Encyclopedic sexuality,
# health and rights topics (sex education, HIV/AIDS, LGBT rights) are NOT
# excluded and never will be under this rule. Underscore form, as the API
# returns titles; brand names are near-identical across language editions.
ADULT_CONTENT_TITLES = {
    "XNXX", "XVideos", "Pornhub", "XHamster", "xHamster", "YouPorn",
    "RedTube", "Brazzers", "Chaturbate", "Stripchat", "OnlyFans",
    "XXX", ".xxx", "Xnxx", "PornHub",
    "Pornography", "Pornographie", "Pornografía", "Pornografia",
    "Порнография", "Порнографія",
    # ja: ポルノ (pornography). NEVER add ポルノグラフィティ — that is a
    # rock band whose article is legitimate popular reading in Japan.
    "ポルノ",
    "إباحية", "پورنوگرافی",
}


def is_article(title: str, project: str) -> bool:
    """True when a top-per-country entry looks like an encyclopedia article."""
    if not project.endswith(".wikipedia"):
        return False
    t = title.strip()
    if not t or t in MAIN_PAGES or t in NON_ARTICLE_TITLES:
        return False
    if ":" in t and t.split(":", 1)[0] in NAMESPACE_PREFIXES:
        return False
    if t.endswith("_talk") or t.startswith("-"):
        return False
    return True


def fetch_day(session: requests.Session, iso2: str, day: date) -> tuple[str, list]:
    """
    One country, one day. Returns (status, articles):
      status "ok"        — articles is the raw list
      status "no-data"   — clean 404 (withheld by Wikimedia, or not published yet)
      status "error"     — network/API trouble; caller keeps previous data
    """
    url = f"{API}/{iso2}/all-access/{day.year}/{day.month:02d}/{day.day:02d}"
    for attempt in range(3):
        try:
            resp = session.get(url, timeout=REQ_TIMEOUT)
            if resp.status_code == 404:
                return "no-data", []
            if resp.status_code == 429:
                time.sleep(5 * (attempt + 1))
                continue
            resp.raise_for_status()
            items = resp.json().get("items", [])
            return ("ok", items[0].get("articles", [])) if items else ("no-data", [])
        except Exception:
            time.sleep(1 + attempt)
    return "error", []


# Articles at or above this many country views get checked against their own
# GLOBAL per-article series before publication (two API calls per unique
# title per run, cached). Big bot floods are big — the 2026-08-10 flood put
# "Roblox" at 4.78M "user" views worldwide (683x its baseline, with automated
# views in lockstep at 4.75M) and ranked it #1-2 in the raw lists of India,
# the Philippines, Indonesia and Colombia. Smaller entries are left to the
# structural filters; checking everything would multiply API load for noise
# that cannot dominate a list.
FLOOD_CHECK_MIN_VIEWS = 25_000

# Pages with a DOCUMENTED history of automated traffic that defeats every
# shape-based test because the bot traffic has become their own baseline.
# Curated, evidence required per entry; titles in space form.
#   fr "Cookie (informatique)": flagged in the 2026-08-11 audit — fr edition
#   out-reading en 5:1 on a consent-banner tech page, 99.4% mobile-web
#   access split (healthy pages run ~40/60), one country holding ~100% of
#   its worldwide readership on single days (Morocco 65,100 of 65,225), and
#   the code below had already met it as Germany's raw #1 at 165k. By
#   2026-08-13 its series had flattened at ~58k/day with automated share
#   under 2% — i.e. the artifact now LOOKS organic on any single day, which
#   is exactly why it needs a curated entry instead of a heuristic.
KNOWN_ARTIFACT_PAGES = {("fr.wikipedia", "Cookie (informatique)")}

# Cross-country sweep: an article appearing in this many countries' lists on
# the same day gets ONE global check applied to every occurrence at once.
SWEEP_MIN_COUNTRIES = 3
SWEEP_MIN_VIEWS = 1_000


def flood_check(session: requests.Session, project: str, title: str,
                day: date, cache: dict) -> bool:
    """
    True when an article's own global traffic says its big number is
    automation, not people. Two measured signals (2026-08-11 audit):

    - LOCKSTEP: automated-classified views on the list day are at least half
      of user-classified views. Organic events (elections, deaths, disasters)
      spike user traffic with automated remaining proportionally tiny; view
      floods leak into both classifications at similar volume (Roblox
      2026-08-10: user 4.78M, automated 4.75M).
    - CONCENTRATION + WHIPSAW: this one country accounts for >=80% of the
      article's worldwide user views that day AND the global series swings
      >=5x within the last week. All of the world's readers of a page being
      in one country, on a violently swinging series, is a VPN/bot exit, not
      a readership (Morocco's fr "Cookie (informatique)": 65,100 of 65,225
      worldwide, series whipsawing 974k->62k across four days).

    Fails OPEN (returns False) on any API trouble: a Wikimedia hiccup must
    never delete measured data. `cache` maps (project, title) -> the fetched
    series so a flood is checked once per run, not once per country.
    """
    key = (project, title)
    if key not in cache:
        base = ("https://wikimedia.org/api/rest_v1/metrics/pageviews/"
                f"per-article/{project}.org/all-access")
        start = (day - timedelta(days=7)).strftime("%Y%m%d00")
        end = day.strftime("%Y%m%d00")
        series = {}
        for agent in ("user", "automated"):
            series[agent] = None
            for attempt in range(2):     # one retry — fail-open must be rare
                try:
                    resp = session.get(
                        f"{base}/{agent}/{requests.utils.quote(title, safe='')}"
                        f"/daily/{start}/{end}", timeout=REQ_TIMEOUT)
                    if resp.status_code == 200:
                        series[agent] = {
                            str(i.get("timestamp", ""))[:8]: i.get("views", 0)
                            for i in resp.json().get("items", [])}
                        break
                    if resp.status_code == 404:
                        break            # no data for this agent split
                    time.sleep(2 * (attempt + 1))
                except Exception:
                    time.sleep(1 + attempt)
            time.sleep(0.3)
        cache[key] = series
    series = cache[key]
    if not series.get("user"):
        return False
    dkey = day.strftime("%Y%m%d")
    user_today = series["user"].get(dkey)
    if not user_today:
        return False
    auto_today = (series.get("automated") or {}).get(dkey, 0)
    if auto_today >= 0.5 * user_today:
        return True          # lockstep
    prior = [v for k, v in series["user"].items() if k != dkey and v]
    if prior and (max(prior + [user_today]) >= 5 * max(1, min(prior))):
        # whipsaw present — concentration is judged by the caller, which
        # knows the country's views_ceil
        return None          # sentinel: "whipsaw, check concentration"
    return False


def summarize(session: requests.Session, raw: list, iso2: str, day: date,
              retrieved: str, flood_cache: dict) -> tuple[dict | None, bool]:
    """
    Filter the raw top-per-country list into the published record.
    Returns (record, had_articles): record is None when nothing article-like
    survives — small countries' lists are truncated by the privacy threshold
    to a couple of main pages (observed: Angola = 2 entries, both main pages),
    and an empty entry must not publish. had_articles reports whether any
    encyclopedia article existed BEFORE the Atlas's own quality gates, so the
    withheld note can say truthfully who removed what.
    """
    kept = [a for a in raw
            if is_article(str(a.get("article") or ""), str(a.get("project") or ""))
            and isinstance(a.get("views_ceil"), int) and a["views_ceil"] > 0
            and (str(a.get("project")),
                 str(a.get("article")).replace("_", " ")) not in KNOWN_ARTIFACT_PAGES
            and str(a.get("article")).replace("_", " ") not in ADULT_CONTENT_TITLES]
    had_articles = bool(kept)

    # AUTOMATED-TRAFFIC GATE (2026-08-11): large entries must survive a check
    # against their own global per-article series — see flood_check above.
    gated = []
    for a in kept:
        if a["views_ceil"] >= FLOOD_CHECK_MIN_VIEWS:
            verdict = flood_check(session, str(a["project"]),
                                  str(a["article"]), day, flood_cache)
            if verdict is True:
                continue                         # lockstep flood — drop
            if verdict is None:
                # whipsaw series: drop only when this country also holds
                # >=80% of the article's worldwide user views that day
                series = flood_cache.get((str(a["project"]), str(a["article"]))) or {}
                world = (series.get("user") or {}).get(day.strftime("%Y%m%d"))
                if world and a["views_ceil"] >= 0.8 * world:
                    continue
        gated.append(a)
    kept = gated

    # Editions represented by a SINGLE page in the country's list are excluded
    # everywhere — observed to be bot/VPN spikes, not people (a French
    # "Cookie (informatique)" at 165k views was Germany's raw #1; a Cornish
    # page sat at "3%" of Argentina's reading). A real cross-language
    # readership shows up as several pages, not one spike.
    counts: dict[str, int] = {}
    for a in kept:
        counts[a["project"]] = counts.get(a["project"], 0) + 1
    kept = [a for a in kept if counts[a["project"]] >= 2]
    if not kept:
        return None, had_articles
    articles = [{
        "title": str(a["article"]).replace("_", " "),
        "project": a["project"],
        "rank": a.get("rank"),
        "views_ceil": a["views_ceil"],
    } for a in kept[:TOP_N]]

    # Reading-language mix: share of (privacy-rounded) views per Wikipedia
    # edition across the filtered list.
    by_project: dict[str, int] = {}
    for a in kept:
        by_project[a["project"]] = by_project.get(a["project"], 0) + a["views_ceil"]
    total = sum(by_project.values())
    mix = {}
    if total:
        top = sorted(by_project.items(), key=lambda kv: -kv[1])[:MIX_TOP]
        mix = {p: round(100 * v / total) for p, v in top if round(100 * v / total) >= 1}

    return {
        "date": day.isoformat(),
        "articles": articles,
        "language_mix": mix,
        "source": (
            "Wikimedia Pageviews API (top-per-country) | most-read pages "
            f"{day.isoformat()} | {API}/{iso2}/all-access/"
            f"{day.year}/{day.month:02d}/{day.day:02d} | retrieved {retrieved}"
        ),
    }, had_articles


def _rebuild_language_mix(rec: dict) -> None:
    """Recompute language_mix from the articles that remain in a record."""
    by_project: dict[str, int] = {}
    for a in rec.get("articles", []):
        by_project[a["project"]] = by_project.get(a["project"], 0) + a["views_ceil"]
    total = sum(by_project.values())
    mix = {}
    if total:
        top = sorted(by_project.items(), key=lambda kv: -kv[1])[:MIX_TOP]
        mix = {p: round(100 * v / total) for p, v in top if round(100 * v / total) >= 1}
    rec["language_mix"] = mix


def sweep_cross_country_floods(session: requests.Session, out: dict,
                               retrieved: str, cache: dict,
                               stale_cutoff: str = "") -> list[str]:
    """
    Post-pass over EVERY published entry — fresh and carried alike.

    WHY (2026-08-13): the in-summarize gate only inspects entries above
    FLOOD_CHECK_MIN_VIEWS, so the 2026-08-10 Roblox flood was scrubbed from
    India (930k) but survived in Kenya (11.5k) — backwards for a platform
    whose point is the small markets. And carried-forward entries were never
    re-screened at all, so a flood frozen into a small country's last good
    day outlived the flood itself. A flood is cross-country by nature, so
    the same-day presence of one article in several countries' lists is the
    cheap tell: each flagged (article, day) costs ONE global check applied
    to every occurrence at once — fewer API calls than lowering the
    per-entry threshold, and it reaches carried entries.

    The verdict is LOCKSTEP ONLY (automated >= 0.5x user on the entry's own
    day), plus the curated KNOWN_ARTIFACT_PAGES list. Deliberately NOT used:
    whipsaw/concentration shapes. Calibrated against every multi-country
    article live on 2026-08-13: the Aug-12 solar eclipse's de/fr/es articles
    legitimately hit 91-97% listed-country concentration WITH event-day
    whipsaw — a shape rule would have deleted the day's biggest genuine
    reading event, while every real article (eclipse, films, quake pages,
    Deaths in 2026) showed automated shares of 0.3-14% against Roblox's
    99%. Lockstep separates cleanly; shapes do not.

    Fails OPEN per group on API trouble. Returns human-readable action lines.
    """
    groups: dict[tuple, list] = {}   # (project, title, date) -> [(iso3, views)]
    for iso3, rec in out.items():
        if rec.get("withheld"):
            continue
        d = rec.get("date")
        for a in rec.get("articles", []):
            if a.get("views_ceil", 0) >= SWEEP_MIN_VIEWS:
                groups.setdefault((a["project"], a["title"], d), []).append(
                    (iso3, a["views_ceil"]))

    actions: list[str] = []
    for (project, title, d), hits in sorted(groups.items()):
        curated = (project, title) in KNOWN_ARTIFACT_PAGES
        # Entries older than the run's own fetch window are carryovers no
        # gate has re-examined — screen their articles individually, however
        # few countries still hold them. Without this, a flood's footprint
        # decays below the group threshold as countries heal and the last
        # holdouts keep it forever (observed 2026-08-13: Tanzania refreshed
        # itself clean mid-run, the Roblox group fell to 2 countries, and
        # Kenya + Sri Lanka kept publishing the flood).
        stale_entry = bool(stale_cutoff) and bool(d) and d < stale_cutoff
        if len(hits) < SWEEP_MIN_COUNTRIES and not curated and not stale_entry:
            continue
        if curated:
            verdict, why = True, "curated artifact page"
        else:
            try:
                day = datetime.strptime(d, "%Y-%m-%d").date()
            except (TypeError, ValueError):
                continue
            key = (project, title, d)
            if key not in cache:
                base = ("https://wikimedia.org/api/rest_v1/metrics/pageviews/"
                        f"per-article/{project}.org/all-access")
                t_url = requests.utils.quote(title.replace(" ", "_"), safe="")
                win = (f"{(day - timedelta(days=7)).strftime('%Y%m%d')}00/"
                       f"{day.strftime('%Y%m%d')}00")
                series = {}
                for agent in ("user", "automated"):
                    series[agent] = None
                    for attempt in range(2):
                        try:
                            resp = session.get(f"{base}/{agent}/{t_url}/daily/{win}",
                                               timeout=REQ_TIMEOUT)
                            if resp.status_code == 200:
                                series[agent] = {
                                    str(i.get("timestamp", ""))[:8]: i.get("views", 0)
                                    for i in resp.json().get("items", [])}
                                break
                            if resp.status_code == 404:
                                break
                            time.sleep(2 * (attempt + 1))
                        except Exception:
                            time.sleep(1 + attempt)
                    time.sleep(0.3)
                cache[key] = series
            series = cache[key]
            dkey = day.strftime("%Y%m%d")
            user_today = (series.get("user") or {}).get(dkey)
            if not user_today:
                continue                      # fail-open
            auto_today = (series.get("automated") or {}).get(dkey, 0)
            verdict = auto_today >= 0.5 * user_today
            why = (f"lockstep: automated {auto_today:,} vs user {user_today:,}"
                   if verdict else "")
        if not verdict:
            continue
        for iso3, _v in hits:
            rec = out[iso3]
            rec["articles"] = [a for a in rec["articles"]
                               if not (a["project"] == project and a["title"] == title)]
            if rec["articles"]:
                _rebuild_language_mix(rec)
            else:
                out[iso3] = {
                    "withheld": True,
                    "reason": "filtered",
                    "note": ("Wikimedia publishes only a heavily truncated list "
                             "for this country, and the few encyclopedia "
                             "articles in it were excluded by the Atlas's own "
                             "quality gates (single-edition spikes and "
                             "automated-traffic patterns), so no reliable "
                             "reading list can be shown."),
                    "checked": retrieved,
                }
        actions.append(f"swept '{title}' ({project}, {d}) from "
                       f"{len(hits)} countries — {why}")
    return actions


def main() -> int:
    static = json.loads(STATIC_PATH.read_text(encoding="utf-8"))
    iso3s = sorted(k for k in static if not k.startswith("_"))
    limit = int(sys.argv[1]) if len(sys.argv) > 1 and sys.argv[1].isdigit() else None

    previous: dict = {}
    if OUTPUT_PATH.exists():
        try:
            previous = json.loads(OUTPUT_PATH.read_text(encoding="utf-8")).get("countries", {})
        except (json.JSONDecodeError, OSError) as exc:
            print(f"WARNING: existing {OUTPUT_PATH.name} unreadable ({exc}) — rebuilding", flush=True)

    # STALEST-FIRST (2026-08-10). This step used to process alphabetically and
    # hit its time budget around country ~100 on throttled days — so the same
    # back half of the alphabet (roughly N through Z) starved every single
    # day. Ordering by each country's own last-touch date makes a truncated
    # run self-healing: whatever the timeout cuts off runs first tomorrow.
    # Never-seen countries ("" sorts first) are picked up promptly; withheld
    # countries rotate on their weekly re-check via their `checked` stamp.
    def _last_touch(iso3: str) -> str:
        rec = previous.get(iso3) or {}
        return rec.get("date") or rec.get("checked") or ""
    iso3s.sort(key=lambda i: (_last_touch(i), i))
    if limit:
        iso3s = iso3s[:limit]

    today = date.today()
    retrieved = today.isoformat()
    # The API publishes with ~1 day of lag; ask for yesterday, fall back one
    # more day per country if yesterday is not out yet.
    days = [today - timedelta(days=1), today - timedelta(days=2)]

    session = requests.Session()
    session.headers["User-Agent"] = USER_AGENT
    # (project, title) -> global per-article series, shared across countries so
    # a flood that hits 20 lists costs 2 API calls, not 40. See flood_check.
    flood_cache: dict = {}

    # Seed the working state from the previous file, so EVERY write — the
    # 50-country checkpoints included — is a superset of the last good state.
    # Without this, a checkpoint os.replace()s the published file with only
    # the countries processed so far, and a timeout kill mid-run silently
    # drops every remaining country from the site (caught in review before
    # it ever shipped). Fresh results overwrite their seeded entries.
    out: dict[str, dict] = dict(previous)
    n_fresh = n_withheld = 0
    carried_isos: set[str] = set()

    def write_output() -> None:
        OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
        result = {
            "_meta": {
                "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                "source": "Wikimedia Pageviews API, top-per-country endpoint",
                "source_url": API,
                "license": "CC0 (Wikimedia analytics data)",
                "method_note": (
                    "The ~100 most-read Wikimedia pages from each country per day, "
                    "filtered to *.wikipedia encyclopedia articles (main pages, "
                    "Special:/search pages and other non-article namespaces removed "
                    "via curated lists — heuristic, so an occasional non-article "
                    "title may survive). View counts are Wikimedia's views_ceil, "
                    "privacy-rounded UP to the next hundred: ceilings, not exact "
                    "counts. Reading-language mix is the share of those rounded "
                    "views per Wikipedia edition within the filtered top-100 — an "
                    "approximation from the top of the distribution; editions "
                    "represented by a single page are excluded as likely "
                    "automated-traffic artifacts, and large entries are "
                    "checked against their own global per-article traffic "
                    "(user vs automated split, day-to-day shape) so view "
                    "floods that leak through Wikimedia's bot classifier are "
                    "dropped rather than published as reading; a cross-country "
                    "sweep re-screens every published entry the same way, and "
                    "a small curated list excludes pages with a documented "
                    "history of automated traffic. One editorial exclusion "
                    "applies: articles about adult-entertainment sites and "
                    "explicit-content markers are not published even when "
                    "genuinely among a country's most-read pages (owner "
                    "decision, 2026-08-17); encyclopedic sexuality, health "
                    "and rights topics are unaffected. Measures "
                    "Wikipedia readers only, not the general population. Countries "
                    "Wikimedia withholds (Country and Territory Protection List, "
                    "or below the volume reporting threshold) carry withheld:true "
                    "and are never estimated."
                ),
                "countries_with_data": 0,   # filled below
                "countries_withheld": 0,
            },
            "countries": out,
        }
        result["_meta"]["countries_with_data"] = sum(
            1 for r in out.values() if not r.get("withheld"))
        result["_meta"]["countries_withheld"] = sum(
            1 for r in out.values() if r.get("withheld"))
        tmp = OUTPUT_PATH.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(result, separators=(",", ":"), ensure_ascii=False) + "\n",
                       encoding="utf-8")
        os.replace(tmp, OUTPUT_PATH)

    def process(iso3: str) -> str:
        """Fetch one country into `out`. Returns 'fresh' | 'withheld' | 'error'."""
        nonlocal n_fresh, n_withheld
        iso2 = ISO3_TO_ISO2.get(iso3)
        if not iso2:
            # Config bug (every Atlas country has a mapping) — say so loudly
            # instead of vanishing; the seeded previous entry, if any, stays.
            print(f"WARNING: no ISO2 mapping for {iso3} — country skipped",
                  file=sys.stderr, flush=True)
            return "error"
        status, rec, had_articles = "error", None, False
        for day in days:
            status, raw = fetch_day(session, iso2, day)
            if status == "ok":
                rec, had = summarize(session, raw, iso2, day, retrieved,
                                     flood_cache)
                had_articles = had_articles or had
                if rec is not None:
                    break
                # A 200 whose list yields nothing publishable must NOT stop
                # the fallback day: on 2026-08-11 Ecuador's day-1 answer was
                # empty while day-2 (quake day) held two publishable quake
                # articles — breaking here stamped the country 'withheld'
                # and the sliding window then lost the data for good.
                continue
            if status == "error":
                break   # network trouble — do not burn the fallback day too
        if rec is not None:
            out[iso3] = rec
            n_fresh += 1
            return "fresh"
        if status in ("no-data", "ok"):
            # Either two clean 404s (Wikimedia does not publish this country)
            # or published lists that yield nothing publishable (small
            # countries under the privacy threshold, or everything removed by
            # our own gates). Both are an honest "nothing to show" — but a
            # previously good entry is NOT downgraded on a single odd day
            # (the seeded entry simply stays); withheld applies only where
            # the file has never held data.
            if iso3 in previous and not previous[iso3].get("withheld"):
                carried_isos.add(iso3)
            else:
                # Three truthful variants — never blame Wikimedia for the
                # Atlas's own filters (2026-08-11 audit: the old single note
                # claimed "none of them are encyclopedia articles" for
                # countries where our gates had removed real articles).
                if status != "ok":
                    reason, note = "not-published", (
                        "Wikimedia does not publish per-country reading data "
                        "for this country (privacy protection list or below "
                        "the reporting threshold).")
                elif had_articles:
                    reason, note = "filtered", (
                        "Wikimedia publishes only a heavily truncated list "
                        "for this country, and the few encyclopedia articles "
                        "in it were excluded by the Atlas's own quality "
                        "gates (single-edition spikes and automated-traffic "
                        "patterns), so no reliable reading list can be "
                        "shown.")
                else:
                    reason, note = "below-threshold", (
                        "Wikimedia publishes too little per-country reading "
                        "data here to report: only pages above a privacy "
                        "threshold are listed, and none of them are "
                        "encyclopedia articles.")
                out[iso3] = {
                    "withheld": True,
                    "reason": reason,
                    "note": note,
                    "checked": retrieved,
                }
                n_withheld += 1
            return "withheld"
        # network/API error — the seeded previous entry, if any, stays as-is
        if iso3 in previous:
            carried_isos.add(iso3)
        return "error"

    errored: list[str] = []
    for i, iso3 in enumerate(iso3s):
        if process(iso3) == "error":
            errored.append(iso3)
        if (i + 1) % 25 == 0:
            print(f"  · {i + 1}/{len(iso3s)} countries — {n_fresh} fresh, "
                  f"{n_withheld} withheld, {len(carried_isos)} carried, "
                  f"{len(errored)} errored", flush=True)
        if (i + 1) % 50 == 0:
            write_output()   # checkpoint: safe at any interruption point
        time.sleep(PACE_SECONDS)

    # SECOND PASS — throttle windows come and go; a country that exhausted its
    # retries in the main sweep usually succeeds a few minutes later at a
    # slower pace. Without this, a bad window leaves countries entirely absent
    # from the file (observed: 33 of 195, including France, on the first run).
    if errored:
        print(f"Retrying {len(errored)} errored countries at "
              f"{RETRY_PACE_SECONDS:.0f}s pacing…", flush=True)
        still_missing = []
        for iso3 in errored:
            time.sleep(RETRY_PACE_SECONDS)
            if process(iso3) == "error" and iso3 not in out:
                still_missing.append(iso3)
        if still_missing:
            print(f"WARNING: no data obtained this run for "
                  f"{len(still_missing)} countries: {' '.join(still_missing)} "
                  f"— absent from the file until a later run succeeds.",
                  flush=True)

    # CROSS-COUNTRY FLOOD SWEEP (2026-08-13): re-screens every entry about
    # to be published, including carried-forward ones the fetch loop never
    # touched this run. See sweep_cross_country_floods for the reasoning.
    sweep_actions = sweep_cross_country_floods(session, out, retrieved,
                                               flood_cache,
                                               stale_cutoff=days[-1].isoformat())
    for line in sweep_actions:
        print(f"  {line}", flush=True)

    if n_fresh == 0 and previous:
        # Nothing fetched at all (API down / shape change / hard throttle).
        # Every previously-good entry is preserved (the working state was
        # seeded from the previous file, so any checkpoint that fired wrote a
        # superset of it) — skip the final write to avoid a churn-only commit
        # and fail loudly so the breakage is visible in the workflow logs.
        # Exception: if the sweep scrubbed something, that cleanup must
        # still reach the published file.
        if sweep_actions:
            write_output()
            print(f"NOTE: wrote sweep cleanup ({len(sweep_actions)} actions) "
                  "despite zero fresh fetches.")
        print("ERROR: no country returned fresh data — previous data "
              "preserved; check the AQS endpoint and the response shape.",
              file=sys.stderr)
        return 1

    write_output()
    size_kb = OUTPUT_PATH.stat().st_size / 1e3
    print(f"Wrote {OUTPUT_PATH} ({size_kb:.0f} kB) — {n_fresh} fresh, "
          f"{n_withheld} withheld, {len(carried_isos)} carried forward.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
