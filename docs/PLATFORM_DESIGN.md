# UN Global Content Intelligence Platform — System Design

**Version 1.0 — July 2026**
**Status:** Design proposal. Builds on the existing Global Media Consumption Atlas (195 countries, verified 2025–26 data from World Bank, RSF, Freedom House, Reuters Institute DNR, Afrobarometer).

---

## 0. Executive Summary

The Atlas today answers *"where do people consume media?"* This design evolves it into a system that answers *"what should the UN say, where, to whom, in what format — and what's the evidence?"*

The end state is an **AI communications analyst**: a natural-language interface where a UN communications officer asks *"Where should we publish climate content targeting youth in East Africa?"* and receives a strategy memo with platform recommendations, format guidance, timing, risks, alternatives — every claim cited to a named source with a confidence score.

Three principles govern every decision below:

1. **Evidence-first, or refuse.** The agent may only state what the evidence store can support. When data is missing (and for many countries it will be), it says so explicitly. A wrong recommendation with a fake citation is worse than no answer — for the UN, credibility is the product.
2. **Free and licensed data only.** Every source is registered with its license and reliability tier. Paid sources (Brandwatch, SimilarWeb, Semrush, Statista, etc.) are designed *around*, with free proxies documented.
3. **Batch intelligence, not real-time theater.** UN campaigns are planned over weeks, not minutes. Daily-updated signals (Wikipedia, GDELT, Google Trends) deliver 95% of the value at 1% of the complexity of streaming infrastructure.

---

## 1. Challenged Assumptions (read this first)

The brief's ambitions are right; five assumptions need correction before building.

### 1.1 "Free data" and "platform-level engagement metrics" are in direct tension
The questions *which content formats perform best?* and *platform demographics per country* are precisely what the paid vendors (SimilarWeb, Sensor Tower, GWI, Brandwatch) sell. Free sources give:
- **Platform usage & trust per country** — surveys (DNR, Afrobarometer, Eurobarometer) — we already have this, it's high quality.
- **Topic demand** — Wikipedia pageviews, Google Trends — free, daily, near-global.
- **Media supply & tone** — GDELT — free, 100+ languages, 15-min updates.
- **Format performance** — only survey-level ("61% of French respondents watch news video weekly"), not post-level analytics.

**Design consequence:** the platform reasons at the **country × platform × topic × format** level, not the individual-post level. That is the honest resolution free data supports — and it's the resolution UN campaign planning actually needs.

### 1.2 Digital-first bias will produce bad UN recommendations
Our own Afrobarometer extraction shows radio is the #1 weekly news source in 30+ African countries (Kenya 85%, Uganda 79%, Liberia 79%), and WhatsApp/Telegram "dark social" dominates messaging in the Global South but is unmeasurable except by survey. A system trained only on scrapeable digital signals will recommend TikTok for audiences that are on radio.
**Design consequence:** radio, TV, print, and dark social are first-class platforms in the schema, populated from survey data, and the recommendation engine must always score them alongside digital platforms.

### 1.3 Real-time streaming is unnecessary complexity
Kafka/Flink-style architectures solve problems the UN comms workflow doesn't have. Daily batch (with GDELT's 15-minute feed available for crisis mode) is the right cadence.
**Design consequence:** scheduled connectors (daily/weekly/annual per source), not streaming. Massive cost and maintainability win.

### 1.4 Demographics will be coarse — say so, don't fake it
Free platform demographics = survey crosstabs (age bands, gender, urban/rural) plus DataReportal's annual aggregates. Not "18–24 women interested in fitness in Jakarta."
**Design consequence:** audience segments are modeled as coarse, survey-backed segments with explicit provenance. Confidence scores drop automatically when a query requests finer granularity than sources support.

### 1.5 An 8-week intern timeline builds the *foundation*, not the platform
This document designs the full system (as briefed). Section 15 separates it into: **Phase A** (buildable now, on the current GitHub-Actions stack, ~zero budget), **Phase B** (a successor/consultant with a small VM and LLM API budget), **Phase C** (a funded UN team). Phase A is scoped so the current work is never thrown away — the existing JSON database becomes the seed of the canonical store.

---

## 2. System Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│  PRESENTATION                                                    │
│  Ask bar (chat) · World map · Dashboards · Topic/Keyword         │
│  explorers · Compare mode · Recommendation builder · Admin       │
├─────────────────────────────────────────────────────────────────┤
│  AGENT LAYER                                                     │
│  Planner agent (tool-calling LLM) → tools:                       │
│   resolve_entities · query_metrics · graph_neighbors ·           │
│   search_evidence · trend_stats · compare · recommend ·          │
│   cite_check(verifier)                                           │
│  Guardrails: citation-mandatory · refusal on low coverage ·      │
│  injection isolation · read-only data access                     │
├─────────────────────────────────────────────────────────────────┤
│  INTELLIGENCE SERVICES                                           │
│  Topic Intelligence · Keyword Engine · Platform Intelligence ·   │
│  Recommendation Engine · Trend Stats (velocity/seasonality/      │
│  forecast) · Confidence Scorer                                   │
├─────────────────────────────────────────────────────────────────┤
│  SEMANTIC LAYER                                                  │
│  Entity resolution (ISO-3166, Wikidata QIDs, BCP-47 langs) ·     │
│  Metric registry (one definition of "engagement") · Source       │
│  registry (license, tier, cadence) · Topic taxonomy              │
├─────────────────────────────────────────────────────────────────┤
│  STORAGE                                                         │
│  Postgres (canonical, + TimescaleDB for time series, +           │
│  pgvector for embeddings) · Graph projection (edge tables →      │
│  Neo4j at scale) · Object store (raw source files) · Document    │
│  store (ingested reports/PDFs, chunked + embedded)               │
├─────────────────────────────────────────────────────────────────┤
│  INGESTION                                                       │
│  Scheduled connectors (daily/weekly/annual). Each: fetch →       │
│  validate (schema contract) → land raw → normalize → load        │
│  canonical → update graph → log freshness.                       │
│  Phase A: GitHub Actions (current). Phase B+: Prefect/Airflow.   │
└─────────────────────────────────────────────────────────────────┘
```

### Data flow
1. Connectors pull each source on its natural cadence (Wikipedia pageviews daily; GDELT daily; Google Trends weekly; DNR/RSF/Freedom House/barometers annually — the pipelines we already built become connectors).
2. Everything lands raw first (auditable), then is normalized to canonical entities via the semantic layer (country → ISO3, topic → Wikidata QID, language → BCP-47).
3. Intelligence services precompute nightly aggregates: topic interest scores, velocities, platform rankings, keyword maps. Precomputation keeps query-time fast and cheap.
4. The document store ingests source PDFs/reports (DNR country pages, Freedom House narratives, UNESCO reports), chunked and embedded for retrieval.

### How the AI reasons (answer lifecycle)
1. **Parse & resolve** — extract entities (countries, topics, segments, platforms) from the question; resolve to canonical IDs.
2. **Plan** — the agent decomposes the question into tool calls ("youth climate East Africa" → resolve region → get platform usage for youth segments → get climate interest trend → get format evidence → check risk flags).
3. **Retrieve** — structured metrics (semantic-layer functions), graph context (neighbors of the entities), and unstructured evidence (hybrid search over documents). Every retrieved item carries an evidence ID.
4. **Synthesize** — the LLM drafts the answer with inline evidence tags `[E1] [E2]`.
5. **Verify** — a checker pass confirms every tagged claim is supported by its cited evidence (NLI-style entailment); unsupported claims are cut or flagged. Coverage gaps produce explicit "what we don't know" sections.
6. **Score** — confidence = f(source coverage, cross-source agreement, recency, reliability tier). Shown to the user, logged for audit.

### Scaling path
- **Phase A:** static JSON + SQLite, GitHub Actions, agent as a thin script/notebook calling the Claude API. Handles 195 countries × ~50 metrics easily.
- **Phase B:** one small VM (or UN Azure), Postgres+pgvector, FastAPI, scheduled connectors, chat web UI. Handles daily signals for 195 countries × thousands of topics.
- **Phase C:** managed Postgres, Neo4j, OpenSearch, SSO (Azure AD/UN federation), horizontal API scaling, multi-region read replicas. The schema doesn't change between phases — only the engines under it.

---

## 3. Canonical Data Model

Core entities (relational; sketched as table → key columns):

| Entity | Key columns | Notes |
|---|---|---|
| `country` | iso3 (PK), iso2, name, m49_region, subregion, capital, population, income_group | Exists today (195 rows) |
| `language` | bcp47 (PK), name, script | |
| `country_language` | iso3, bcp47, pct_speakers, official (bool) | n:m |
| `platform` | platform_id, name, type (social/video/messaging/search/radio/tv/print/podcast), owner, discovery_mechanism (feed/graph/search/broadcast) | Radio/TV are platforms |
| `platform_country_stat` | iso3, platform_id, metric (weekly_news_use_pct/all_use_pct/trust_pct), value, source_id, year | From DNR/Afrobarometer — exists as NEWS_CONSUMPTION today |
| `media_outlet` | outlet_id, name, iso3_home, type, wikidata_qid | From DNR brand lists + static_countries media fields |
| `outlet_country_stat` | outlet_id, iso3, metric (weekly_reach/trust/neither/distrust), value, source_id, year | DNR brand-trust tables |
| `topic` | topic_qid (PK, Wikidata-aligned), canonical_label, sdg_mapping | Language-agnostic concepts |
| `keyword` | keyword_id, surface_form, bcp47, topic_qid | Per-language surface forms |
| `topic_metric_daily` | iso3, topic_qid, date, signal (wiki_pv/trends/gdelt_vol/gdelt_tone), value | TimescaleDB hypertable |
| `topic_relation` | topic_a, topic_b, weight, method (clickstream/embedding/gkg_cooccur), as_of | |
| `content_format` | format_id (short_video/long_video/audio/podcast/article/infographic/live/thread/broadcast) | |
| `format_evidence` | iso3, platform_id, format_id, finding, value, source_id, year | Survey-level, not post-level |
| `audience_segment` | segment_id, age_band, gender, urban_rural, definition_source | Coarse, survey-backed |
| `segment_platform_stat` | segment_id, iso3, platform_id, metric, value, source_id | Where crosstabs exist |
| `survey_fact` | fact_id, iso3, metric, value, source_id, wave, year, method_note | Generalizes today's snapshot dicts (RSF, FH, DNR...) |
| `source` | source_id, name, publisher, url, license, cost (free/registered/paid), cadence, reliability_tier (A/B/C), last_fetched | The source registry |
| `evidence` | evidence_id, source_id, locator (table+row / doc+chunk), retrieved_at, quote | Everything citable |
| `un_campaign` | campaign_id, agency, objective, topic_qid, start/end | Filled by users |
| `campaign_outcome` | campaign_id, iso3, platform_id, metric, value | Closes the learning loop |
| `org` | org_id, name, type (UN/NGO/gov/academic), wikidata_qid | |
| `creator` | creator_id, public_name, iso3, platforms, wikidata_qid | **Public figures only** (e.g., DNR-named news creators). See §13 privacy rules |
| `recommendation_log` | rec_id, query, answer, evidence_ids, confidence, model, ts | Full audit trail |
| `user_feedback` | rec_id, rating, correction, ts | Feeds evaluation |

Key relationships: country↔platform (stats), country↔topic (daily interest), topic↔keyword (per language), topic↔topic (relatedness), outlet↔country (reach/trust), campaign↔topic/country/platform (planning + outcomes), everything↔source (provenance).

**Migration note:** today's `static_countries.json` + `countries.json` map 1:1 onto `country`, `platform_country_stat`, `survey_fact`, and `media_outlet`. Nothing built so far is discarded.

---

## 4. Knowledge Graph

### Should it be a graph? Yes — as a *layer*, not a replacement.
- **Why yes:** the platform's hardest questions are multi-hop: *"trusted outlets covering health topics in French-speaking West African countries where radio reach > 60%"* touches outlet→trust→country→language→platform→topic. In SQL that's a 6-way join someone must hand-write; in a graph it's a path query, and — critically — **the path itself is the explanation** shown to the user.
- **Why not a rip-and-replace:** time-series metrics (millions of daily topic rows) belong in a columnar/relational store. Graph databases are poor at aggregation-heavy analytics.
- **Decision:** canonical data in Postgres; a **property-graph projection** built nightly from the edge tables. Phase A/B: edges in Postgres queried recursively or via NetworkX in-process (the graph is small — ~10⁵ nodes). Phase C: Neo4j or Amazon Neptune when edge count and query concurrency justify it.

### Graph schema
**Nodes:** Country, Region, Language, Platform, MediaOutlet, Topic (QID), Keyword, ContentFormat, AudienceSegment, Source, Campaign, Org, Creator.

**Edges (all carry `source_id`, `as_of`, `confidence`):**
- `(Platform)-[:USED_IN {weekly_pct, segment}]->(Country)`
- `(MediaOutlet)-[:TRUSTED_IN {trust_pct}]->(Country)`
- `(Country)-[:INTERESTED_IN {score, velocity}]->(Topic)` (materialized weekly from time series)
- `(Topic)-[:RELATED_TO {weight, method}]->(Topic)`
- `(Keyword)-[:LABEL_OF {lang}]->(Topic)`
- `(Country)-[:SPEAKS {pct, official}]->(Language)`
- `(MediaOutlet)-[:PUBLISHES_ON]->(Platform)`
- `(Campaign)-[:TARGETED]->(Topic|Country|Segment)`, `(Campaign)-[:PERFORMED {metric,value}]->(Country)`
- `(Segment)-[:PREFERS {evidence}]->(Platform|Format)`

**Wikidata alignment** (topics, outlets, creators, orgs keyed to QIDs) buys free multilingual labels, aliases in 300+ languages, and type hierarchies — the cheapest multilingual capability available anywhere.

**GraphRAG:** at query time, the agent extracts entities, pulls their 1–2-hop neighborhood (filtered by edge type relevance), serializes it as structured context, and merges it with vector-retrieved document chunks. Graph context answers "what's connected"; documents answer "what did the source actually say."

---

## 5. Data Source Registry

Tiers: **A** = official statistics / peer-reviewed survey · **B** = platform/passive data with known measurement bias · **C** = estimates, scraped, or method-opaque. ✅ = integrate · 🟡 = free but gated/gray — needs institutional registration or ToS review · ❌ = paid, excluded (free proxy noted).

### Already integrated (keep — these are the foundation)
| Source | Contents | Coverage | License/Cost | Tier |
|---|---|---|---|---|
| World Bank Open Data API | 14 socioeconomic/connectivity indicators | ~200 countries | CC-BY, free | A ✅ |
| RSF Press Freedom Index 2025 | Rank + 0–100 score | 180 countries | Free (attribution) | A ✅ |
| Freedom House FITW 2026 | Political freedom 0–100 | 195 | Free | A ✅ |
| Freedom House FOTN 2025 | Internet freedom 0–100 | 70 | Free | A ✅ |
| Reuters Institute DNR 2026 | Trust, platform use, formats, brands, creators | 48 markets | Free PDF | A ✅ |
| Afrobarometer R9 microdata | Weighted media use by demographic | 39 African countries | Free | A ✅ |

### Surveys & indices (free, high value)
| Source | Contents | Coverage | Access | Tier |
|---|---|---|---|---|
| Arab Barometer W8 | Media use, trust, attitudes | 8 MENA | Free, registration form | A 🟡 |
| Asian Barometer W6 | Same | 13+ Asia | Free, application | A 🟡 |
| Latinobarómetro | Same | 17 LatAm | Free, registration | A 🟡 |
| Eurobarometer (Media & News Survey) via GESIS | Media habits, trust, EU 27 | EU-27 | Free, GESIS account | A 🟡 |
| World Values Survey W7 | Values, media trust | ~90 countries | Free, registration | A 🟡 |
| V-Dem | Media freedom, disinformation indices | 200 countries, 1789– | CC-BY | A ✅ |
| UNDP HDR / UNESCO UIS / ITU DataHub | HDI, literacy, ICT prices & skills | Global | Free | A ✅ |
| DHS Program | Health + media exposure microdata | ~90 developing countries | Free, registration | A 🟡 |
| Pew Research | Topline reports, some microdata | Varies | Free | A ✅ |
| Edelman Trust Barometer | Trust in media/institutions | 28 countries | Free PDF | B ✅ |
| Gallup World Poll | Wellbeing, media | 140+ | **Microdata paid** ❌ — use free toplines only | B |
| Ipsos Global Advisor | Topic attitude reports | ~30 | Free PDFs | B ✅ |

### Demand & attention signals (the new engine of the platform)
| Source | Contents | Coverage | Access | Tier |
|---|---|---|---|---|
| **Wikipedia Pageviews API** | Daily views per article per language edition | Global, 300+ langs, 2015– | Fully free, no key | B ✅ **highest priority new source** |
| **Wikipedia Clickstream** | Article→article navigation pairs | Monthly, major langs | Free | B ✅ (powers topic relations) |
| **Wikidata** | Entity labels/aliases/types, 100M+ items | All languages | CC0 | A ✅ (taxonomy backbone) |
| **GDELT 2.0 (Events + GKG)** | Global news events, themes, tone, 100+ langs, 15-min cadence | Global | Free (API + BigQuery free tier) | B ✅ **second priority** |
| **Google Trends** | Relative search interest, related/rising queries, per country | Global | Free UI; unofficial API (pytrends) is ToS-gray; official API in limited alpha | B 🟡 (use conservatively, cache aggressively) |
| Media Cloud | News coverage volume/attention by outlet collection | Global | Free, academic API key | B ✅ |
| Common Crawl | Web crawl corpus | Global | Free | C ✅ (Phase C research uses) |
| OpenAlex | Academic publication trends per topic/country | Global | CC0 | A ✅ (long-term interest signal) |
| ReliefWeb API (OCHA) | Humanitarian reports/updates | Crisis countries | Free | A ✅ |
| WHO GHO / UNICEF / UNHCR APIs | Health & humanitarian indicators | Global | Free | A ✅ |

### Platform data (the honest picture)
| Source | Contents | Access | Tier |
|---|---|---|---|
| YouTube Data API | Search/video/channel stats, trending per country | Free quota (10k units/day) | B ✅ |
| Reddit API | Subreddit posts/engagement | Free tier (rate-limited); research access program | B 🟡 |
| **Meta Content Library** | Public FB/IG content & engagement (CrowdTangle's replacement) | Free for qualified researchers via ICPSR application — **UN affiliation likely qualifies; apply in Phase B** | B 🟡 |
| TikTok Research API | Public video/comment data | Free, application, US/EU-focused eligibility | B 🟡 |
| Telegram (public channels) | Public channel posts via MTProto API | Free; ToS-compliant for public data; ethics review required | C 🟡 |
| Meta Ad Library API | Social/political ads (who runs what, where) | Free | B ✅ (see what govs/NGOs push) |
| Google Ads Transparency Center | Advertiser transparency | Free (no bulk API) | B ✅ manual |
| X (Twitter) API | Posts/engagement | **Paid** ($100+/mo basic; research tier gutted) | ❌ — proxy: GDELT, news quoting, academic archives |
| WhatsApp | — | **Closed. No data exists.** | ❌ — proxy: survey questions (DNR, Afrobarometer measure WhatsApp news use) |
| LinkedIn | — | No usable public API | ❌ — proxy: DataReportal ad-audience aggregates |
| Google Ads Keyword Planner | Search volumes (bucketed) | Free with Ads account; ToS for non-advertising use is gray | 🟡 manual reference only |
| Bing/Microsoft search data | — | Bing Search APIs retired (2025) | ❌ |

### Connectivity & device context
| Source | Contents | Access | Tier |
|---|---|---|---|
| ITU DataHub | Internet use, broadband, prices, gender gap | Free | A ✅ |
| Ookla Open Data | Fixed/mobile speeds per tile | Free (AWS Open Data, CC-BY-NC) | B ✅ |
| M-Lab | Speed tests | Free | B ✅ |
| Cloudflare Radar | Traffic, outages, popular domains per country | Free API | B ✅ |
| GSMA Mobile Connectivity Index | Mobile internet enablers | Free (index); GSMA Intelligence data paid ❌ | B ✅ |
| DataReportal | Annual digital snapshot per country (platform users, device stats) | Free reports, attribution; estimates | C ✅ (cite as estimates) |

### Excluded (paid) — and their free substitutes
| Paid source | What it would add | Free substitute |
|---|---|---|
| SimilarWeb | Website traffic ranks | Cloudflare Radar domain rankings, Chrome UX Report |
| Semrush/Ahrefs | Keyword volumes/SEO | Google Trends relative interest + Wikipedia pageviews |
| Brandwatch/Meltwater/Talkwalker | Social listening | GDELT + Media Cloud + Meta Content Library + YouTube API |
| Sensor Tower/data.ai | App downloads | (no good free proxy; note gap) |
| Statista | Aggregated charts | Go to Statista's underlying primary sources directly |
| Gallup World Poll microdata | Global wellbeing | Free toplines + WVS + barometers |

---

## 6. Topic Intelligence

**Demand vs. supply — the core distinction.** Wikipedia pageviews and Google Trends measure what people *seek* (demand). GDELT measures what media *publish* (supply). Divergence is itself a signal: high demand + low local supply = an information gap the UN can fill. The system stores both and never conflates them.

**Country attribution caveat:** Wikipedia pageviews are per language edition, not per country. Mapping (e.g., Swahili wiki → KE/TZ/UG weighted by speaker share from `country_language`) is documented, imperfect, and always labeled. Google Trends is properly per-country. Signals are triangulated, never merged blindly.

For every (country, topic, day), store component signals and compute:

| Question | Method |
|---|---|
| **What do people care about?** | Composite interest score = weighted z-scores of wiki pageviews (language-mapped), Trends, YouTube search where available. Components stored separately for explainability. |
| **Emerging topics** | Velocity = (7-day share − 90-day share) / 90-day share. Emerging = velocity > +50% AND z > 2 vs. seasonal baseline AND above an absolute volume floor (kills noise). |
| **Declining** | Mann-Kendall trend test on 26-week window, sustained negative slope. |
| **Seasonal** | STL decomposition; seasonal strength > 0.6 → tag with peak weeks (Ramadan, COP, exam seasons, monsoon). Recommendation engine uses peaks for timing. |
| **Long-term interests** | 3-year annual aggregates; stable-high topics = evergreen content candidates. |
| **Sentiment** | GDELT tone (media framing) + multilingual sentiment on headlines, aggregated to country-topic-week. **Never** individual-level. Labeled "media tone," not "public opinion." |
| **Velocity/momentum** | First and second derivative of rolling share; powers "rising now" feeds. |
| **Topic relationships** | Blend of Wikipedia clickstream edges (behavioral), GKG co-occurrence (editorial), embedding similarity (semantic). Method tagged on every edge. |
| **Cross-country comparison** | Within-country normalization first (share of that country's attention), then compare shares — never raw volumes (panel sizes differ by 1000×). |

Nightly job materializes: top-20 topics per country, global movers, per-topic country league tables, alerts (topic crossed emergence threshold in ≥3 countries of a region).

---

## 7. Keyword Intelligence

The keyword engine resolves a phrase to a **concept**, then works per-language.

**Pipeline for "Climate Change":**
1. Resolve → Wikidata Q7942; pull labels/aliases in all languages (free multilingual expansion: *changement climatique*, *mabadiliko ya tabianchi*, *jieunywa...*).
2. Per target country: interest time series (Trends + wiki pageviews in relevant language editions), rising related queries (Trends), navigational neighbors (clickstream), semantic neighbors (embeddings).
3. Join platform intelligence (§8) and format evidence for the countries where interest is highest.
4. Assemble the response contract:

```json
{
  "concept": {"qid": "Q7942", "label": "climate change"},
  "top_countries": [{"iso3": "KEN", "interest_z": 2.1, "velocity": "+38%/90d"}],
  "keywords_by_language": {"sw": ["mabadiliko ya tabianchi", "..."], "fr": ["..."]},
  "related_topics": [{"qid": "Q898653", "label": "drought", "weight": 0.7, "method": "clickstream"}],
  "recommended_platforms": [{"platform": "radio", "why": "KEN weekly radio 85% [E3]"}],
  "recommended_formats": [{"format": "audio + short_video", "evidence": ["E4","E5"]}],
  "demographics": {"note": "youth skew on TikTok KE (DNR 2026) [E6]", "granularity": "coarse"},
  "evidence": [{"id": "E3", "source": "Afrobarometer R9", "quote": "...", "year": 2023}],
  "confidence": {"score": 0.72, "label": "Medium-High", "gaps": ["no format data for TZA"]},
  "strategy_memo": "…LLM-written, every sentence citing E-ids…"
}
```

Confidence = coverage × cross-source agreement × recency decay × source tier weight. The formula is published in the UI — no black-box scores.

---

## 8. Platform Intelligence

Per country, the platform profile combines what we can honestly know:

| Attribute | Source | Honesty note |
|---|---|---|
| Preferred platforms (news + general) | DNR 2026, Afrobarometer R9, barometers | Strong — already integrated |
| Trust by outlet/platform | DNR brand-trust tables, Eurobarometer | 48 + EU markets |
| Preferred formats | DNR (video/podcast/creator uptake), platform norms | Survey-level |
| Content length norms | Platform-published guidance + published meta-analyses | **Prior, not measurement** — labeled as such |
| Posting frequency/timing | Best-practice priors + seasonality from §6 | Same |
| Preferred language(s) | `country_language` + official/media languages | Strong |
| Platform demographics | Survey crosstabs, DataReportal aggregates | Coarse (see §1.4) |
| Audience overlap | Survey multi-platform usage | Where microdata exists (Afrobarometer ✔) |
| Discovery mechanism | Classification: algorithmic feed (TikTok) / social graph (FB, WhatsApp) / search (YouTube, Google) / broadcast (radio/TV) | Determines strategy type |
| Algorithm characteristics | Platform transparency reports, DSA disclosures (EU) | Directional only — proprietary |
| Platform growth | DataReportal YoY, DNR wave-over-wave deltas | Estimates + survey deltas |
| Access risk | FOTN blocks/throttling, Cloudflare Radar outages | Already have FOTN |

**Dark social rule:** WhatsApp/Telegram get full profiles from survey data with `measurement: "survey-only"` flags, and the recommendation engine treats them as *distribution-via-community* channels (you don't post to WhatsApp; you seed shareable assets through trusted intermediaries).

---

## 9. Recommendation Engine

**Input — structured objective** (parsed from natural language by the agent):
```json
{"topic": "Q7942", "audience": {"age": "15-24"}, "geography": ["East Africa"],
 "goal": "awareness", "assets": ["video","audio"], "languages": null, "constraints": []}
```

**Pipeline:**
1. **Retrieve** all relevant evidence (interest, platforms, formats, trust, risks) for candidate countries.
2. **Generate candidates** via transparent rules — e.g., *youth + video assets → rank platforms by (youth usage × penetration × not-blocked)*; *radio mandatory in any country where radio weekly > 60%*.
3. **Score** each (country, platform, format): `reach × audience_fit × trust × (1 − risk_penalty)`. Risk penalty from FOTN blocks, press-freedom retaliation risk (RSF < 40), connectivity floor (internet < 30% → digital penalized), misinformation-prone flags.
4. **Synthesize memo** (LLM): target countries, platform mix, format guidance, message adaptation notes (language, trusted-messenger strategy), timing (seasonal peaks from §6), risks, and **at least one alternative strategy** (typically the non-digital one).
5. **Verify + score confidence**, log to `recommendation_log`.

**Output sections (always):** Recommendation · Evidence table · Confidence + gaps · Risks · Alternatives · "What would change this answer" (sensitivity note).

The `campaign_outcome` table closes the loop: officers record what actually happened; future recommendations cite real UN campaign performance — the platform's moat after 2–3 years.

---

## 10. Agentic AI Design

**Decision matrix (why each technique is used or rejected):**

| Technique | Verdict | Why |
|---|---|---|
| Pure vector RAG | ❌ alone | Can't aggregate ("average trust across East Africa") — retrieval ≠ computation |
| Text-to-SQL (raw) | ❌ alone | Brittle, injection-prone, un-auditable for non-technical users |
| **Semantic-layer functions** | ✅ core | Vetted, typed functions (`get_platform_usage(iso3, segment)`) — every number traceable; raw read-only SQL as capped fallback |
| **Hybrid search (BM25 + vector)** | ✅ core | Document evidence retrieval; exact-term + semantic |
| **Knowledge-Graph RAG** | ✅ core | Multi-hop context + paths-as-explanations (§4) |
| **Single planner agent + tools** | ✅ core | One ReAct-style tool-calling LLM (Claude). Simple, debuggable, auditable |
| Multi-agent | 🟡 later | Only for long-form report generation (researcher → writer → critic). Premature otherwise; adds cost and failure modes |
| Reasoning models | ✅ selective | Extended thinking for comparative/planning queries; standard mode for lookups (cost control) |
| Memory | ✅ scoped | Session memory + curated org memory (approved campaign learnings, glossaries). **No individual user profiling** |
| Fine-tuning | ❌ for now | Retrieval + prompting sufficient; revisit for domain embeddings in Phase C |

**Tools:** `resolve_entities` · `query_metrics` (semantic layer) · `graph_neighbors` · `search_evidence` · `trend_stats` · `compare_countries` · `compose_recommendation` · `cite_check`.

**Guardrails:**
- **Citation-mandatory generation** — claims without evidence IDs are stripped by the verifier pass (NLI entailment check against the cited chunk).
- **Refusal on thin data** — coverage below threshold → the agent says what's missing and offers the nearest answerable question instead of guessing.
- **Injection isolation** — scraped/ingested text is data, never instructions; delimited and sanitized before entering context.
- **Read-only** — the agent cannot write to canonical stores; recommendations log to an append-only table.
- **Sensitive-query policy** — election-related, conflict-related, or individual-person queries route through stricter templates aligned with UN neutrality rules (§13).

**Evaluation harness:** the 100 questions below become the **golden set** — each with required evidence and a scoring rubric. CI runs the set on every prompt/model/data change; metrics: citation precision/recall, refusal correctness, answer consistency, latency, cost. Regression = blocked release.

---

## 11. 100 Example Queries (golden evaluation set)

**Platform selection (1–10):** 1. Where should we publish climate change content targeting youth? 2. Best platform for reaching rural women in Nigeria? 3. Which platforms should UNHCR use in Jordan? 4. Is TikTok viable for public-health messaging in Indonesia? 5. Where do people over 45 get news in Brazil? 6. Which platforms are blocked or throttled in Iran? 7. Best platform mix for a vaccination campaign in Pakistan? 8. Should we invest in podcasts for France? 9. Where does radio still beat digital in West Africa? 10. Which platform is growing fastest among Kenyan youth?

**Topic discovery (11–20):** 11. What topics are currently resonating in Indonesia? 12. Which countries show rising interest in AI governance? 13. What's trending in East Africa this month? 14. Is interest in climate adaptation growing or declining in South Asia? 15. What health topics concern people in Egypt right now? 16. Which SDG topics get the least media coverage in LatAm? 17. What was the most-read topic in Ukraine last quarter? 18. Where is misinformation about vaccines trending? 19. What environmental topics peak seasonally in India? 20. Which topics link food security and migration in the Sahel?

**Audience (21–30):** 21. What do we know about Gen Z media habits in Mexico? 22. How do urban and rural audiences differ in Tanzania? 23. Which segment is hardest to reach in Japan? 24. What's the gender gap in internet access across the Sahel? 25. Where are older adults most active on social media? 26. Who trusts public broadcasters most in Europe? 27. What languages should a Morocco campaign use? 28. How news-avoidant are audiences in the UK vs. Germany? 29. Which countries have the most creator-influenced news audiences? 30. What audience overlap exists between Facebook and WhatsApp in Kenya?

**Format & creative (31–40):** 31. What format performs best for women's health content in East Africa? 32. Short-form or long-form video for Vietnam? 33. Are infographics effective where literacy is low? 34. Which countries prefer audio content? 35. What's the podcast opportunity in Brazil? 36. Should climate content be creator-led in the Philippines? 37. What format suits humanitarian appeals in Lebanon? 38. Where is live video most watched? 39. Text vs. video for policy audiences in Brussels? 40. What formats work on low-bandwidth connections in Chad?

**Country strategy (41–50):** 41. Best way to distribute humanitarian aid messaging in Peru? 42. Full media strategy for a girls'-education campaign in Afghanistan — what's possible? 43. How should UN comms adapt for Vietnam vs. Thailand? 44. What trusted outlets should we partner with in Ghana? 45. How do we reach displaced populations in Sudan? 46. Communication plan for El Niño warnings in the Pacific islands? 47. How to counter aid skepticism in donor countries? 48. Reaching minority-language speakers in Guatemala? 49. What's the media landscape risk in Myanmar? 50. How should messaging differ between francophone and anglophone Cameroon?

**Comparison (51–60):** 51. Compare news trust in Nordic vs. Mediterranean countries. 52. TikTok news use: Indonesia vs. Malaysia vs. Philippines. 53. Which G20 country has the lowest news trust? 54. Radio reach: Kenya vs. Nigeria vs. South Africa. 55. Press freedom trend: Georgia vs. Armenia over 5 years. 56. Compare youth platform preferences France vs. Germany. 57. Where is WhatsApp news use highest globally? 58. Internet freedom vs. usage: Gulf states compared. 59. News avoidance: highest and lowest countries? 60. Compare climate interest across BRICS.

**Timing (61–70):** 61. When should we launch a malaria campaign in Nigeria? 62. What seasonal peaks exist for education topics in India? 63. Best month for climate content in Europe? 64. When does interest in humanitarian topics spike? 65. How long does a topic stay trending in the US vs. Japan? 66. When do Ramadan-related media habits shift in MENA? 67. What day-of-week patterns exist for news consumption? 68. Timing for World Refugee Day amplification? 69. When did interest in Sudan last peak, and why? 70. Is now a good moment for AI-safety content in Korea?

**Risk & integrity (71–80):** 71. What are the risks of a UN campaign on X in country Y? 72. Where could health messaging trigger backlash? 73. Which countries have state-controlled media environments we should account for? 74. Is our climate framing vulnerable to politicization in the US? 75. What platforms carry the most misinformation in Brazil? 76. Where are journalists most at risk covering our topics? 77. What happens if TikTok is banned in a target country mid-campaign? 78. How resilient is our strategy to internet shutdowns in Ethiopia? 79. Which topics are legally sensitive in Gulf states? 80. What neutrality risks exist in election years?

**Evidence lookup (81–90):** 81. What's the source for Kenya's radio number? 82. How confident are we in Indonesia's TikTok data? 83. When was Peru's platform data last updated? 84. What does Afrobarometer say about Uganda's internet use? 85. Show all evidence behind the Nigeria recommendation. 86. Which countries lack format data entirely? 87. What's the methodology behind the trust scores? 88. How does DNR sample India — is it nationally representative? 89. What changed in Turkey's numbers since last year? 90. Which sources disagree about Egypt, and why?

**Campaign learning (91–100):** 91. What did similar campaigns achieve in this region? 92. What platform mix did our last climate campaign use, and did it work? 93. What can we learn from campaign X's underperformance in Colombia? 94. Which past campaigns reached rural audiences successfully? 95. Benchmarks for engagement on UN content in MENA? 96. What content formats did our best campaigns share? 97. How did timing affect our COP campaign reach? 98. Which partnerships drove the most trust lift? 99. What should we A/B test next in Southeast Asia? 100. Draft a one-page strategy memo for a water-sanitation campaign in Bolivia with full citations.

---

## 12. User Experience

- **Ask bar** — global, top of every page. Answers render as a memo: recommendation up top, evidence chips inline (click → source, quote, retrieval date), confidence badge, "what we don't know" box, and a **"show the data"** expander revealing the exact metric calls behind every number. Trust is built by never hiding the plumbing.
- **World map (home)** — the existing map evolves: color by any metric (trust, platform use, topic interest, freedom scores); click country → profile.
- **Country profile** — platform stack (incl. radio/TV), trusted outlets, trending topics, format evidence, risk flags, data freshness meter.
- **Topic explorer** — search any topic → global heat map, trend lines per country, related-topic graph (the KG rendered), velocity leaderboard.
- **Keyword explorer** — §7's engine as UI: concept card, per-language keywords, rising queries, platform/format guidance.
- **Compare mode** — 2–4 countries side by side on any metric set.
- **Recommendation builder** — a guided form (topic, audience, geography, goal, assets) → full memo; save/share/export to PDF.
- **Conversation view** — multi-turn follow-ups retaining context ("now exclude countries with FOTN < 40").
- **Admin dashboard** — connector health, source freshness, eval-suite pass rates, recommendation audit log.
- **Standards** — WCAG 2.1 AA; UI in the six UN official languages (agent answers in the user's query language via the multilingual model).

---

## 13. Governance, Privacy, Neutrality

- **UN Personal Data Protection Principles (2018) compliance:** the platform stores **zero individual-level data**. All signals are aggregate (country/segment). Survey microdata is processed to aggregates and the raw files handled per each program's license.
- **Creators/influencers:** public figures only, sourced from published research (e.g., DNR-named creators); no scraping of personal accounts; right-to-removal process.
- **Neutrality:** sentiment is labeled "media tone," never "public opinion." Election- and conflict-adjacent outputs carry mandatory human-review flags. The platform recommends channels and formats — never political framing.
- **License registry:** every source's license and attribution requirement is machine-checked before any public display (e.g., Ookla CC-BY-NC → internal use only).
- **Audit:** every recommendation logged with full evidence chain, model version, and prompt version. A DPIA (data protection impact assessment) precedes Phase B deployment.

---

## 14. Five-Year Capabilities

Ordered by (value ÷ difficulty), with prerequisites:

1. **Trend forecasting** — per-topic, per-country interest forecasts (statistical baselines → time-series foundation models). Needs 2+ years of accumulated daily signals — *which is why the connectors should start running now*.
2. **Early-warning system** — infodemic/attention alerts for health & humanitarian ops (WHO infodemic-management aligned): topic velocity anomalies trigger regional office notifications.
3. **Campaign simulation** — "what-if" reach modeling across platform mixes using accumulated `campaign_outcome` data; later, synthetic-audience simulation (with clear ethics review).
4. **Content generation + localization** — draft posts/scripts per platform-format-language, grounded in the evidence base; human-in-the-loop always; UN terminology glossaries enforced.
5. **Narrative & misinformation observatory** — GDELT + Meta Content Library + fact-check feeds (ClaimReview) tracking narrative spread around UN topics; governed by an oversight board given the sensitivity.
6. **Influencer/partner mapping** — rights-respecting graph of public communicators per topic-country, for partnership (not surveillance).
7. **Network analysis** — outlet syndication and information-flow mapping from GDELT/Media Cloud.
8. **Policy intelligence** — link comms data to policy calendars (COP, UNGA, HLPF) for automatic moment-planning.
9. **Workflow integration** — push recommendations into the tools officers already use (Drupal, Hootsuite-class schedulers, Teams).
10. **Federation** — expose the knowledge graph via API to sister UN data platforms (ITU, UNDP, OCHA) — the Atlas becomes UN comms infrastructure.

---

## 15. Delivery Plan — 12 Weeks, Team of Two (One Human + One AI)

Constraint update: the platform must be delivered in 2–3 months by the current intern working with Claude, with no engineering team and near-zero budget. The plan below ships the *essence* of the brief — an AI analyst answering natural-language questions with cited evidence — on infrastructure that requires no servers to maintain.

**Architecture for this reality:** everything runs on what already works today. GitHub Actions = the data engine (scheduled connectors + nightly intelligence calculations). GitHub Pages = the data store *and* the website (all intelligence published as JSON files). A single Cloudflare Worker (free tier) = the AI backend, holding the API key and letting Claude call tools that read the published JSON. No databases to administer, no servers to patch.

| Weeks | Deliverable |
|---|---|
| **1–2** | **Trend engine.** Two new connectors on GitHub Actions: Wikipedia pageviews + GDELT news themes (both free, no API keys), tracking ~150 UN-relevant topics (mapped to Wikidata QIDs) across all countries/language editions, daily. Restructure existing JSON into the canonical entity shapes (§3) so nothing is thrown away. Also: a one-page non-technical summary for supervisors. |
| **3–4** | **Intelligence calculations.** Nightly jobs compute: trending/rising/declining/seasonal topics per country (§6 math), top countries per topic, platform + format rankings per country (from the survey data already integrated). Published as JSON on the site. |
| **5–7** | **The AI analyst.** Cloudflare Worker (free tier) with the Anthropic API key as a secret; Claude with tool access to the published intelligence JSON; citation-mandatory answers with confidence labels and explicit "what we don't know" gaps; chat page on the site. |
| **8–9** | **The product around it.** Country profiles gain "Trending now" panels; new Topic Explorer page (trend lines, country league tables); Recommendation Builder form feeding the same agent. |
| **10–11** | **Evaluation + docs.** Test against 30+ of the 100 golden questions (§11); fix gaps; plain-English user guide; supervisor demo script; full handover documentation. |
| **12** | **Buffer + demo.** Live demonstration to supervisors; collect feedback; log v2 requests. |

**The only real cost:** an Anthropic API key (~US$5–25/month at demo/pilot usage). Everything else — data, hosting, compute — is free.

**Explicitly cut from the 12-week scope** (documented in §2–§14 as the funded-team path): dedicated graph/relational database servers, multi-agent report generation, Meta Content Library & TikTok Research API integrations (institutional applications exceed the timeline), forecasting, six-UN-language UI, SSO. The schema-first design means none of these require rework later — they slot in under the same data model.

**Definition of done (for a non-technical stakeholder):** a communications officer opens the site, asks "Where should we publish climate content for youth in East Africa?", and receives a recommendation citing Afrobarometer, DNR 2026, and live trend data — with sources clickable and confidence stated. The system declines to answer where data doesn't support an answer.

---

## 16. Handover Notes

- The existing repo remains the single source of truth; this document lives at `docs/PLATFORM_DESIGN.md`.
- Current data assets (195-country JSON, verified 2025–26 survey tables, the extraction scripts) map directly onto §3's schema — they are the seed data.
- The 100 queries (§11) double as the acceptance test for any future contractor: "the system answers these, with citations, or it isn't done."
- First engineering task for a successor: implement the `topic_metric_daily` table + the Wikipedia pageviews connector. Every week it runs is a week of trend history the forecasting features (§14) will need.
