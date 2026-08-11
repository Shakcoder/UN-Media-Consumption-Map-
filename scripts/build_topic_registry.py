#!/usr/bin/env python3
"""
build_topic_registry.py — one-time builder for the topic registry.

Takes a curated list of UN-relevant topics (as English Wikipedia titles),
resolves each to its Wikidata QID (following redirects), and fetches the
article title in every tracked language edition. Output: data/topics.json.

Run once (or whenever topics are added). The daily trend connectors read
the registry; they never call Wikidata themselves.

No API keys required. Uses only the Python standard library (+ certifi on
macOS if available, to work around local SSL certificate issues).
"""

from __future__ import annotations

import json
import ssl
import time
import urllib.parse
import urllib.request
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
OUTPUT_PATH = REPO_ROOT / "data" / "topics.json"

USER_AGENT = "UN-Media-Atlas/1.0 (Global Content Intelligence Platform; research)"

# Language editions tracked for pageviews. Chosen for UN relevance and
# mappability to countries (see compute_topic_intelligence.py for weights).
LANGS = [
    "en", "fr", "es", "ar", "pt", "ru", "zh", "hi", "bn", "id",
    "sw", "ha", "am", "ur", "fa", "tr", "vi", "th", "ja", "de",
    "uk", "ko",
]

# Curated topic list: (English Wikipedia title, category).
# Titles must exist on English Wikipedia (redirects are resolved automatically).
TOPICS: list[tuple[str, str]] = [
    # --- Climate & environment ---
    ("Climate change", "climate"),
    ("Climate change adaptation", "climate"),
    ("Climate change mitigation", "climate"),
    ("Renewable energy", "climate"),
    ("Solar power", "climate"),
    ("Wind power", "climate"),
    ("Drought", "climate"),
    ("Flood", "climate"),
    ("Wildfire", "climate"),
    ("Heat wave", "climate"),
    ("Sea level rise", "climate"),
    ("Deforestation", "climate"),
    ("Biodiversity", "climate"),
    ("Biodiversity loss", "climate"),
    ("Plastic pollution", "climate"),
    ("Air pollution", "climate"),
    ("Water scarcity", "climate"),
    ("Desertification", "climate"),
    ("Electric vehicle", "climate"),
    ("Recycling", "climate"),
    ("Extreme weather", "climate"),
    ("Paris Agreement", "climate"),
    # --- Health ---
    ("Vaccine", "health"),
    ("Vaccination", "health"),
    ("Malaria", "health"),
    ("HIV/AIDS", "health"),
    ("Tuberculosis", "health"),
    ("Cholera", "health"),
    ("Ebola", "health"),
    ("Measles", "health"),
    ("Polio", "health"),
    ("Mental health", "health"),
    ("Maternal health", "health"),
    ("Family planning", "health"),
    ("Contraception", "health"),
    ("Breastfeeding", "health"),
    ("Malnutrition", "health"),
    ("Obesity", "health"),
    ("Diabetes", "health"),
    ("Cancer", "health"),
    ("Pandemic", "health"),
    ("Antimicrobial resistance", "health"),
    ("Mpox", "health"),
    ("Dengue fever", "health"),
    ("COVID-19", "health"),
    ("Suicide prevention", "health"),
    # --- Humanitarian & migration ---
    ("Refugee", "humanitarian"),
    ("Internally displaced person", "humanitarian"),
    ("Humanitarian aid", "humanitarian"),
    ("Famine", "humanitarian"),
    ("Food security", "humanitarian"),
    ("Hunger", "humanitarian"),
    ("Human migration", "humanitarian"),
    ("Immigration", "humanitarian"),
    ("Asylum seeker", "humanitarian"),
    ("Human trafficking", "humanitarian"),
    ("Child labour", "humanitarian"),
    ("Land mine", "humanitarian"),
    ("Natural disaster", "humanitarian"),
    ("Earthquake", "humanitarian"),
    ("Tsunami", "humanitarian"),
    ("Tropical cyclone", "humanitarian"),
    # --- Peace & security ---
    ("War", "peace"),
    ("Ceasefire", "peace"),
    ("Peacekeeping", "peace"),
    ("Terrorism", "peace"),
    ("Genocide", "peace"),
    ("War crime", "peace"),
    ("Nuclear weapon", "peace"),
    ("Disarmament", "peace"),
    ("Civil war", "peace"),
    ("International sanctions", "peace"),
    # --- Rights & governance ---
    ("Human rights", "rights"),
    ("Gender equality", "rights"),
    ("Women's rights", "rights"),
    ("Violence against women", "rights"),
    ("Female genital mutilation", "rights"),
    ("Child marriage", "rights"),
    ("Democracy", "rights"),
    ("Election", "rights"),
    ("Corruption", "rights"),
    ("Freedom of the press", "rights"),
    ("Freedom of speech", "rights"),
    ("Censorship", "rights"),
    ("Misinformation", "rights"),
    ("Disinformation", "rights"),
    ("Fake news", "rights"),
    ("Rule of law", "rights"),
    ("Capital punishment", "rights"),
    ("Torture", "rights"),
    ("Slavery", "rights"),
    ("Racism", "rights"),
    ("Discrimination", "rights"),
    ("Indigenous peoples", "rights"),
    ("Disability", "rights"),
    ("Same-sex marriage", "rights"),
    ("Domestic violence", "rights"),
    ("Child abuse", "rights"),
    # --- Development & economy ---
    ("Poverty", "development"),
    ("Extreme poverty", "development"),
    ("Unemployment", "development"),
    ("Inflation", "development"),
    ("Microfinance", "development"),
    ("Remittance", "development"),
    ("Development aid", "development"),
    ("Debt relief", "development"),
    ("Universal basic income", "development"),
    ("Financial inclusion", "development"),
    ("Informal economy", "development"),
    ("Minimum wage", "development"),
    ("Cost of living", "development"),
    ("Homelessness", "development"),
    ("Sustainable Development Goals", "development"),
    ("Fair trade", "development"),
    ("Gender pay gap", "development"),
    ("Youth unemployment", "development"),
    ("Population growth", "development"),
    ("Population ageing", "development"),
    # --- Education & children ---
    ("Education", "education"),
    ("Literacy", "education"),
    ("Female education", "education"),
    ("School meal", "education"),
    ("Children's rights", "education"),
    ("Early childhood education", "education"),
    ("Higher education", "education"),
    ("Vocational education", "education"),
    ("Distance education", "education"),
    # --- Technology & digital ---
    ("Artificial intelligence", "technology"),
    ("Regulation of artificial intelligence", "technology"),
    ("AI safety", "technology"),
    ("ChatGPT", "technology"),
    ("Machine learning", "technology"),
    ("Social media", "technology"),
    ("Digital divide", "technology"),
    ("Computer security", "technology"),
    ("Information privacy", "technology"),
    ("Surveillance", "technology"),
    ("Facial recognition system", "technology"),
    ("Cryptocurrency", "technology"),
    ("Blockchain", "technology"),
    ("Internet access", "technology"),
    ("Internet censorship", "technology"),
    ("5G", "technology"),
    ("Deepfake", "technology"),
    ("Cyberbullying", "technology"),
    # --- Energy, food, water, urban ---
    ("Nuclear power", "infrastructure"),
    ("Fossil fuel", "infrastructure"),
    ("Agriculture", "infrastructure"),
    ("Sustainable agriculture", "infrastructure"),
    ("Genetically modified organism", "infrastructure"),
    ("Overfishing", "infrastructure"),
    ("Drinking water", "infrastructure"),
    ("Sanitation", "infrastructure"),
    ("Urbanization", "infrastructure"),
    ("Public transport", "infrastructure"),
    ("Road traffic safety", "infrastructure"),
    # --- UN & institutions ---
    ("United Nations", "institutions"),
    ("UNICEF", "institutions"),
    ("World Health Organization", "institutions"),
    ("United Nations High Commissioner for Refugees", "institutions"),
    ("World Food Programme", "institutions"),
    ("UNESCO", "institutions"),
    ("International Monetary Fund", "institutions"),
    ("World Bank", "institutions"),
    ("International Criminal Court", "institutions"),
    ("Universal Declaration of Human Rights", "institutions"),
    ("United Nations Climate Change conference", "institutions"),
    # --- Added 2026-08-11 (audit-recommended gaps, approved by Shakti) ---
    ("Influenza", "health"),
    ("Tobacco smoking", "health"),
    ("Ocean acidification", "climate"),
    ("Freedom of religion", "rights"),
    ("LGBTQ rights", "rights"),
    ("Social protection", "development"),
    ("Peacebuilding", "peace"),
    ("Statelessness", "humanitarian"),
    ("Wartime sexual violence", "peace"),
    ("Energy poverty", "infrastructure"),
    ("Electronic waste", "climate"),
    ("Submarine communications cable", "technology"),
    ("International Court of Justice", "institutions"),
    ("United Nations Security Council", "institutions"),
    ("United Nations General Assembly", "institutions"),
    ("UNRWA", "institutions"),
]


# CURATED TITLE OVERRIDES (2026-08-11 audit) — cases where the Wikidata
# sitelink points at a near-zero synonym page while the language's real
# article for the concept lives on a sibling Wikidata item, plus redirect
# targets that would be wrong to follow. Each entry was verified against
# live per-article traffic before being added; None means "do not track
# this language for this topic" (the redirect target is a broader concept
# and tracking it would measure something else).
#   qid -> {lang: title | None}
TITLE_OVERRIDES: dict[str, dict[str, str | None]] = {
    "Q169950": {           # Wildfire — sitelinks live on Q107434304 'forest fire'
        "fr": "Feu de forêt",        # 283 views/day vs no fr sitelink at all
        "es": "Incendio forestal",   # 72/day vs no es sitelink
        "de": "Waldbrand",           # 125/day vs tracked 'Lauffeuer' at ~0
    },
    "Q1483757": {          # Solar power
        "es": "Energía solar",       # 66/day vs tracked synonym at 1.9/day
    },
    "Q13629441": {         # Electric vehicle
        "ja": "電気自動車",           # 77/day vs tracked '電動輸送機器' at ~0
    },
    "Q9166713": {          # Higher education (tertiary-education item)
        "ru": "Высшее образование",  # 129/day, invisible via the sitelink
    },
    "Q320863": {           # World Bank — main-language articles sit on the
        "es": "Banco Mundial",       # sibling item; sitelinked pages are the
        "fr": "Banque mondiale",     # marginal 'World Bank Group' stubs
        "ru": "Всемирный банк",
    },
    "Q651936": {           # Debt relief — ja redirect target 免除 is the
        "ja": None,                  # generic legal 'exemption', wrong concept
    },
    "Q159595": {           # Distance education — fa redirect lands on
        "fa": None,                  # 'online university', a different thing
    },
    "Q575619": {           # Cost of living — tr article deleted upstream
        "tr": None,
    },
    "Q7212330": {          # Tobacco smoking — es/ar readers use the general
        "es": "Tabaquismo",          # smoking articles (41/day vs sitelinked
        "ar": "تدخين",               # 'Fumar tabaco' 6/day; ar 22 vs 2)
    },
}


def _ssl_context() -> ssl.SSLContext:
    try:
        import certifi  # noqa: PLC0415
        return ssl.create_default_context(cafile=certifi.where())
    except ImportError:
        return ssl.create_default_context()


CTX = _ssl_context()


def fetch_json(url: str, retries: int = 4) -> dict:
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
            with urllib.request.urlopen(req, timeout=30, context=CTX) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            if attempt == retries - 1:
                raise
            # 429 means the IP's budget is spent — waiting seconds does
            # nothing; back off properly (this builder runs rarely, patience
            # is free).
            time.sleep(45 if exc.code == 429 else 2 ** attempt)
        except Exception:
            if attempt == retries - 1:
                raise
            time.sleep(2 ** attempt)
    raise RuntimeError("unreachable")


def resolve_qids(titles: list[str]) -> dict[str, dict]:
    """English titles -> {title: {"qid":..., "resolved_title":...}} via the
    Wikipedia API (follows redirects, exposes the wikibase_item pageprop)."""
    out: dict[str, dict] = {}
    for i in range(0, len(titles), 50):
        batch = titles[i:i + 50]
        url = (
            "https://en.wikipedia.org/w/api.php?action=query&format=json"
            "&redirects=1&prop=pageprops&ppprop=wikibase_item&titles="
            + urllib.parse.quote("|".join(batch))
        )
        data = fetch_json(url)
        query = data.get("query", {})
        # map normalized/redirected titles back to what we asked for
        alias: dict[str, str] = {}
        for n in query.get("normalized", []):
            alias[n["to"]] = n["from"]
        for r in query.get("redirects", []):
            src = alias.get(r["from"], r["from"])
            alias[r["to"]] = src
        for page in query.get("pages", {}).values():
            final_title = page.get("title", "")
            original = alias.get(final_title, final_title)
            qid = page.get("pageprops", {}).get("wikibase_item")
            if qid:
                out[original] = {"qid": qid, "resolved_title": final_title}
            else:
                print(f"  ! no QID for: {original} (page: {final_title})")
        time.sleep(0.2)
    return out


def fetch_sitelinks(qids: list[str]) -> dict[str, dict[str, str]]:
    """QIDs -> {qid: {lang: article_title}} for the tracked language editions."""
    wanted = {f"{lang}wiki" for lang in LANGS}
    out: dict[str, dict[str, str]] = {}
    for i in range(0, len(qids), 50):
        batch = qids[i:i + 50]
        url = (
            "https://www.wikidata.org/w/api.php?action=wbgetentities&format=json"
            "&props=sitelinks&ids=" + "|".join(batch)
        )
        data = fetch_json(url)
        for qid, ent in data.get("entities", {}).items():
            links = {}
            for site, obj in ent.get("sitelinks", {}).items():
                if site in wanted:
                    links[site[:-4]] = obj["title"]
            out[qid] = links
        time.sleep(0.2)
    return out


def resolve_redirects(by_lang: dict[str, dict[str, str]]) -> dict[str, dict[str, str]]:
    """
    {lang: {title: qid}} -> {lang: {title: final_title}} following redirects.

    WHY (2026-08-11 audit): pageviews accrue to the page actually served, so
    a sitelink that has become a redirect counts only the trickle of readers
    who hit the old name — es 'Climate change' and zh 'COVID-19' were among
    21 series silently undercounting this way after upstream renames.
    """
    out: dict[str, dict[str, str]] = {}
    for lang, titles in sorted(by_lang.items()):
        out[lang] = {}
        tlist = list(titles)
        for i in range(0, len(tlist), 50):
            batch = tlist[i:i + 50]
            url = (
                f"https://{lang}.wikipedia.org/w/api.php?action=query"
                "&format=json&redirects=1&formatversion=2&titles="
                + urllib.parse.quote("|".join(batch))
            )
            data = fetch_json(url)
            q = data.get("query", {})
            normalized = {n["from"]: n["to"] for n in q.get("normalized", [])}
            redirected = {r["from"]: r["to"] for r in q.get("redirects", [])}
            missing = {p["title"] for p in q.get("pages", []) if p.get("missing")}
            for t in batch:
                t2 = normalized.get(t, t)
                final = redirected.get(t2, t2)
                if final in missing:
                    print(f"  ! {lang}: '{t}' is missing upstream — dropped")
                    continue
                if final != t:
                    print(f"  · {lang}: '{t}' → '{final}' (redirect resolved)")
                out[lang][t] = final
            time.sleep(0.2)
    return out


def main() -> None:
    titles = [t for t, _ in TOPICS]
    cats = dict(TOPICS)
    print(f"Resolving {len(titles)} topics to Wikidata QIDs…")
    resolved = resolve_qids(titles)
    print(f"  resolved: {len(resolved)}/{len(titles)}")

    qids = [v["qid"] for v in resolved.values()]
    print("Fetching sitelinks for tracked languages…")
    sitelinks = fetch_sitelinks(qids)

    # Apply curated overrides, then resolve redirects per language edition.
    for qid, overrides in TITLE_OVERRIDES.items():
        if qid not in sitelinks and any(v for v in overrides.values()):
            sitelinks[qid] = {}
        for lang, title in overrides.items():
            if title is None:
                sitelinks.get(qid, {}).pop(lang, None)
            else:
                sitelinks[qid][lang] = title

    print("Resolving redirects in every tracked language…")
    by_lang: dict[str, dict[str, str]] = {}
    for qid, links in sitelinks.items():
        for lang, title in links.items():
            by_lang.setdefault(lang, {})[title] = qid
    final_titles = resolve_redirects(by_lang)

    # COLLISION GUARD: after redirect resolution two topics can land on the
    # same article in one language (e.g. a specific concept merged into a
    # broader one). Tracking one article under two topics double-counts it,
    # so the topic whose claim arrived via redirect loses the language.
    for qid, links in sitelinks.items():
        for lang in list(links):
            resolved_title = final_titles.get(lang, {}).get(links[lang])
            if resolved_title is None:
                del links[lang]        # missing upstream
            else:
                links[lang] = resolved_title
    for lang in {l for links in sitelinks.values() for l in links}:
        owners: dict[str, list[str]] = {}
        for qid, links in sitelinks.items():
            if lang in links:
                owners.setdefault(links[lang], []).append(qid)
        for title, qs in owners.items():
            if len(qs) > 1:
                # keep the topic whose original sitelink WAS this title;
                # drop the ones that arrived via redirect
                direct = [q for q in qs if by_lang.get(lang, {}).get(title) == q]
                keep = direct[0] if direct else sorted(qs)[0]
                for q in qs:
                    if q != keep:
                        print(f"  ! {lang}: '{title}' claimed by {qs} — "
                              f"kept {keep}, dropped the rest (collision)")
                        del sitelinks[q][lang]

    registry = []
    for title, info in sorted(resolved.items()):
        qid = info["qid"]
        links = sitelinks.get(qid, {})
        registry.append({
            "qid": qid,
            "label_en": title,
            "category": cats[title],
            "titles": links,               # {lang: article title}
            "lang_coverage": len(links),
        })

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(
        json.dumps({"generated_at": time.strftime("%Y-%m-%d"),
                    "languages": LANGS,
                    "topics": registry},
                   indent=1, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    total_pairs = sum(t["lang_coverage"] for t in registry)
    print(f"Wrote {OUTPUT_PATH} — {len(registry)} topics, "
          f"{total_pairs} topic-language pairs.")


if __name__ == "__main__":
    main()
