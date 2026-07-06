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
]


def _ssl_context() -> ssl.SSLContext:
    try:
        import certifi  # noqa: PLC0415
        return ssl.create_default_context(cafile=certifi.where())
    except ImportError:
        return ssl.create_default_context()


CTX = _ssl_context()


def fetch_json(url: str, retries: int = 3) -> dict:
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
            with urllib.request.urlopen(req, timeout=30, context=CTX) as resp:
                return json.loads(resp.read().decode("utf-8"))
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


def main() -> None:
    titles = [t for t, _ in TOPICS]
    cats = dict(TOPICS)
    print(f"Resolving {len(titles)} topics to Wikidata QIDs…")
    resolved = resolve_qids(titles)
    print(f"  resolved: {len(resolved)}/{len(titles)}")

    qids = [v["qid"] for v in resolved.values()]
    print("Fetching sitelinks for tracked languages…")
    sitelinks = fetch_sitelinks(qids)

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
