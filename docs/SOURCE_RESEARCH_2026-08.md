# Open Data Source Research — August 2026

*A live-verified survey of open data sources the Atlas could integrate next, focused on **attention and trend data** (what people are actually reading, watching, and searching for, per country, per day) with a secondary section on structured indicators. Every claim below was verified against the live web on **2026-08-06** — real requests were made to every keyless API, and docs/license pages were pulled fresh. Do not trust this document indefinitely: APIs closed, moved, or changed terms repeatedly during 2023–2026, and several "famously keyless" APIs quietly grew key walls this year alone (FAOSTAT, UCDP, ReliefWeb).*

**Status of shortlist #1:** integrated 2026-08-07 — Wikimedia top-per-country now runs daily in `trend-engine.yml` (see `scripts/fetch_trends_wiki_countries.py` and DATA_SOURCES.md §1).

**Status of shortlist #2:** integrated 2026-08-10 — Google Trends "Trending Now" RSS now runs daily as the trend engine's first step (`scripts/fetch_trends_google.py`; DATA_SOURCES.md §1). First full run: 121/195 countries returned data. Correction to §2.2 below: unsupported geos do **not** "fail soft" — Google answers **HTTP 400** with an HTML page, which the fetcher treats as "not covered" (and re-probes weekly) rather than as an error.

---

## 1. The state of platform APIs in 2026 — the blunt version

| Platform | Status (verified 2026-08-06) | Working alternative |
|---|---|---|
| **X/Twitter** | Dead for us. Free tier discontinued Feb 2026; pay-per-use ($0.005/post read). Academic program killed 2023. | Bluesky + Mastodon (open-social substitutes). State X's exclusion openly in the methodology. |
| **TikTok** | Dead for us. Research API = accredited academic institutions only (US/EEA/UK/CH/BR). Creative Center has no official API. | None. |
| **Meta (FB/IG/WhatsApp/Threads)** | Dead for us. CrowdTangle shut Aug 2024; Meta Content Library is a supervised clean-room (no export, no pipeline). | None for the pipeline. |
| **Reddit** | Practically no. Free OAuth tier exists but datacenter IPs (= GitHub Actions) get HTTP 403 on public endpoints, per-country filter covers only ~36 countries, and deletion-sync terms conflict with a public git history. | Skip. |
| **Spotify** | Dead for us. Per-country charts login-walled; new apps lost editorial-playlist API access Nov 2024; API shrank further Feb 2026. | Apple Marketing Tools RSS (music/podcast charts). |
| **Google Trends** | Half-open. Official API still application-gated alpha (announced Jul 2025; worth applying — form is free). Old JSON endpoints 404. pytrends archived Apr 2025. | The official-ish **"Trending Now" RSS** — candidate #2 below. |
| **Telegram / Discord / WhatsApp / LinkedIn** | No trending or public-content APIs. | None. |

**Cross-cutting 2026 pattern:** for a public-repo project, the disqualifier is almost never the request quota — it is the **redistribution clause**. Commercial news APIs now explicitly exclude "archives, datasets, republication" from free tiers; that is exactly what committing daily JSON to a public repo is.

---

## 2. Primary candidates — attention & trend data

### 2.1 Wikimedia per-country reading lists (AQS `top-per-country`) — ✅ INTEGRATED 2026-08-07

The ~100 most-read Wikimedia pages *from each country*, daily, with privacy-rounded view ceilings and per-edition mix. **CC0, keyless, CORS-open, history since 2021-01-01.** Verified live (US/IN/BR returned complete data for the prior day). Coverage honestly partial: Wikimedia's Country and Territory Protection List excludes RUS, CHN, IRN, PRK, CUB, BLR, SAU, AFG among others, and a volume threshold truncates small countries — the Atlas shows an explicit "withheld" state, never an estimate. Raw lists carry main-page/Special:-page/bot noise that must be filtered (observed: it.wikisource search pages in Brazil's top 5; single-page Cornish Wikipedia spikes in Argentina).
Sample: `https://wikimedia.org/api/rest_v1/metrics/pageviews/top-per-country/IN/all-access/2026/08/05`
Same family, not yet integrated: `top-by-country` (monthly ranking of countries by views per language edition) and the differential-privacy bulk CSVs (`analytics.wikimedia.org/published/datasets/country_project_page/`, daily since 2023-02, cover some withheld countries).
**Integration reality check (2026-08-07):** article-level coverage after honest filtering is **~45–60 countries**, not the ~140–160 the API's raw reach suggests — the per-page privacy threshold truncates most smaller markets' lists to main/search pages, and those become explicit "withheld (below-threshold)" states. The DP bulk CSVs above are the route to broader coverage if ever wanted.

### 2.2 Google Trends "Trending Now" RSS — ✅ INTEGRATED 2026-08-10

~10 currently-trending search queries per country with traffic buckets ("100+", "1000+") and linked headlines. The only live, free search-demand signal. Verified for 57/73 tested geos (realistic ceiling ~110–125 countries; unsupported geos fail soft). **No history — a snapshot; every unpolled day is lost forever**, so the archive should start as early as possible. No auth; RSS/XML; no CORS (Action only). License: Google's "Export, embed, and cite Trends data" guidance permits reuse with attribution ("Data source: Google Trends"); commit only derived facts (query, bucket, date), never the embedded third-party headlines/images.
Sample: `https://trends.google.com/trending/rss?geo=KE`
Watch item: the official Trends API (consistently-scaled interest, 5-year window) is application-gated alpha — apply, but do not build on a waitlist.

### 2.3 Media Cloud

Searchable archive of 1.8B news stories with human-curated **National collections for 100+ countries** — "how much is Kenya's own press covering X this week" with a defensible denominator. Free key (open signup, verified); **4,000 requests/week, some endpoints 2/minute** — a paced daily 195-country sweep fits. JSON; no CORS → Action + key in Actions secrets. **License standout:** ToS explicitly permits reproducing/distributing "Platform Outputs" (counts, time series) — precisely what the Atlas commits. Never commit story text. Archive solid from the ~2022 rebuild; verify per-collection depth before promising history.
Sample (needs key): `https://search.mediacloud.org/api/search/count-over-time?q=%22climate%22&start=2026-07-01&end=2026-08-05&cs=34412118&platform=onlinenews-mediacloud` (34412118 = India National)

### 2.4 YouTube Data API v3 — per-country charts

`videos.list?chart=mostPopular&regionCode=XX` for ~100–110 countries; 1 quota unit per call (a full daily sweep ≈ 4.5% of the free 10,000-unit quota; free Google Cloud project, no billing card). **Two hard rules:** (a) since 2025-07-10 the chart reflects YouTube's *Music/Movies/Gaming charts*, not the retired general "Trending" — label accordingly; (b) Developer Policies III.E.4.d cap storage of API data at **30 calendar days** and forbid building long-term series of YouTube metrics — the Action needs a pruning step from day one, and week-over-week is the deepest honest comparison. Visible YouTube attribution required.
Sample: `https://www.googleapis.com/youtube/v3/videos?part=snippet&chart=mostPopular&regionCode=JP&maxResults=25&key=API_KEY`

### 2.5 Cloudflare Radar

Per-country **top-100 and trending domains** (daily, `rankingType=TRENDING_RISE`), traffic-change timelines (15-min resolution), internet quality, and a curated Outage Center with cause labels (including government-directed shutdowns) and citation links. Free account + API token (Radar-read); 1,200 req/5 min global cap; JSON/CSV. History ~3–4.5 years by endpoint. **License: CC BY-NC 4.0 (non-commercial) — needs the Chief's read given the DGC pivot before it touches anything monetized.**
Sample (needs token): `https://api.cloudflare.com/client/v4/radar/ranking/top?rankingType=TRENDING_RISE&location=NG&limit=10`

### 2.6 OONI — censorship evidence

Per-country, per-day counts of measurements confirming news/social sites are blocked (Citizen Lab NEWS category works). Keyless; JSON; history to ~2017; ~4k-request rate bucket observed; **no CORS → Action**. License **CC BY-NC-SA 4.0** (committed JSON must carry the license; NC flag as above). Live-verified: Iran returned 300–600 confirmed-blocked NEWS measurements/day. Natural companion to the RSF layer — measured, citable evidence next to rankings.
Sample: `https://api.ooni.io/api/v1/aggregation?probe_cc=IR&test_name=web_connectivity&category_code=NEWS&since=2026-07-25&until=2026-08-06&axis_x=measurement_start_day`

### 2.7 IODA — outage detection

"Is this country's internet up" in near-real-time (BGP + active probing + Google traffic signals). Keyless, JSON, **CORS-open — and that is the legal escape hatch**: data is stamped "All Rights Reserved" (Georgia Tech), so fetch live in the browser and display with attribution, commit nothing (the GDELT/Wikipedia pattern). Email ioda-info@cc.gatech.edu before ever committing snapshots. Usable history ~2021+.
Sample: `https://api.ioda.inetintel.cc.gatech.edu/v2/outages/summary?entityType=country&from=1785369600&until=1785974400`

### 2.8 Bluesky trends — ✅ INTEGRATED 2026-08-10

Network-wide trending topics with post counts and categories. Keyless, JSON, **CORS-open** (works from the browser today), verified live. **Global list only — no country/language parameter.** Store aggregates only (topics + counts, no posts/handles) and deletion obligations never apply. Risk: the endpoint namespace is officially "unspecced" (unstable) — fail loudly on shape changes.
Sample: `https://public.api.bsky.app/xrpc/app.bsky.unspecced.getTrends?limit=25`

### 2.9 Mastodon trends

Trending hashtags (each with a built-in **7-day history array** — the only source here that ships its own history), trending news links with language tags, per instance. Keyless, JSON, CORS-open, 300 req/5 min. **Per-instance, not per-country** — usable only as a documented sample of flagship language instances, always labeled "instance sample". Store aggregates, not posts.
Sample: `https://mastodon.social/api/v1/trends/tags?limit=20`

### 2.10 Netflix Top 10

Weekly top-10 films/TV per country, **94 countries**, ranks only (hours-viewed exists only in the global file — a per-country "hours watched" claim would be fabrication). Full history to 2021-07-04 ships in every download (~495k rows); published Tuesdays. Old domain 301s to `netflix.com/tudum/top10/data/…`. **No formal license** (customary use — needs sign-off); bot protection requires browser-like headers and may still block datacenter IPs some days (treat as a non-fatal step, like Statcounter).
Sample: `https://www.netflix.com/tudum/top10/data/all-weeks-countries.tsv`

### 2.11 Apple Marketing Tools RSS

Top podcasts / most-played music / top free & paid **apps** (back from the dead — verified live) per storefront; 67/74 tested storefronts returned charts (realistic coverage 150+). Keyless, clean JSON, no CORS → Action; no history (poll-and-archive). **No feed-specific license** — Apple's generic site terms are restrictive boilerplate; the feeds are branded "Marketing Tools" and universally syndicated, but this needs a conscious sign-off. Ranks only, no counts.
Sample: `https://rss.marketingtools.apple.com/api/v2/us/podcasts/top/10/podcasts.json`

### 2.12 The Guardian Open Platform (outlet lens)

Free key (1 call/s, 500/day, non-commercial), decades-deep archive, CORS-open, public `test` playground key works. Honest framing: measures *one outlet's* coverage — usable only as a clearly-labeled "through the Guardian's lens" comparator for the English-lens work, never as a country-attention metric. Commit counts only.
Sample (works now): `https://content.guardianapis.com/search?q=%22united%20nations%22&api-key=test`

### GDELT — free upgrades already owned (no new source needed)

- `mode=TimelineTone` / `ToneChart` per `sourcecountry:` — the only free, live, multi-language news-sentiment signal anywhere (65 languages). Label "tone of coverage", never "public opinion".
- `TimelineVolInfo` — top articles behind each volume spike (ready-made for "View sources").
- Web NGrams 3.0 raw files — GDELT's recommended path for heavier Action-side trend work.
- **Warnings (verified 2026-08-06):** the GEO 2.0 API is dead (404); the throttle wall now enforces 1 request/5 s and blocks deep-history DOC queries (the existing 6.5 s pacing is compliant — keep it); a multi-day platform outage occurred June 2025. License remains ideal: unrestricted use/redistribution with citation + link.

---

## 3. Secondary candidates — structured indicators

All verified with real requests 2026-08-06. These map to the topic categories: humanitarian (HAPI/ReliefWeb/UNHCR), peace (UCDP), climate (GDACS/OWID), health/development/education (SDG/WHO/OWID), technology (ITU series already in via World Bank).

| Source | What | Access | License | Notes |
|---|---|---|---|---|
| **UN SDG Indicators API** (UNSD) | all 713 official SDG series, quarterly releases | keyless, JSON, CORS | UN open terms | `https://unstats.un.org/sdgapi/v1/sdg/Series/Data?seriesCode=IT_USE_ii99&pageSize=2` |
| **ReliefWeb API v2** (OCHA) | humanitarian reports since 1996; report-volume-per-country doubles as an attention signal | **pre-approved appname required since 2025-11-01** (request form; then a plain query param, not a secret); 1,000 calls/day | CC BY for derived counts | `https://api.reliefweb.int/v2/reports?appname=<approved>&limit=1&profile=list` |
| **HDX HAPI** (OCHA) | needs, IDPs, refugees, funding, food security; crisis countries, admin0–2 | self-generated app identifier (base64 of appname:email — safe in public code), JSON/CSV, CORS | mostly CC BY — check per-dataset field; **conflict-events are ACLED-derived: do not republish** | `https://hapi.humdata.org/api/v2/metadata/location?output_format=json&limit=2&app_identifier=<base64>` |
| **UNHCR Refugee Data Finder** | refugees/asylum/IDPs by origin AND asylum country, 1951+ | keyless, JSON, CORS | CC BY | `https://api.unhcr.org/population/v1/population/?limit=2&year=2024` |
| **UCDP** (Uppsala) | research-grade conflict events 1989+ | **API now token-walled (emailed token)** but bulk CSVs stay keyless (monthly candidate + annual GED) | **CC BY 4.0** — the clean public-repo alternative to ACLED | bulk: `https://ucdp.uu.se/downloads/ged/ged261-csv.zip` |
| **GDACS** (EC JRC + OCHA) | near-real-time multi-hazard disaster alerts with severity | keyless; GeoJSON API CORS-open | RSS declares public domain | `https://www.gdacs.org/gdacsapi/api/events/geteventlist/MAP` |
| **Our World in Data** | thousands of tidy country-year series as CSV + metadata | keyless, CORS | CC BY (cite the upstream from `.metadata.json` — OWID aggregates WB/WHO/UN) | `https://ourworldindata.org/grapher/share-of-individuals-using-the-internet.csv?useColumnShortNames=true` |

One-liners: **WHO GHO** works but its OData API is officially slated for replacement (and CC BY-NC-SA) — wrap thinly. **IMF's** new SDMX API answers keyless (SDMX parsing is the tax). **FAOSTAT** key-walled its query API in 2025/26 (bulk CSVs still open). **ITU DataHub**: no public API, NC license — take ITU indicators through World Bank (already integrated, CC BY) and credit ITU. **Eurostat**: excellent, EU-only. **V-Dem**: annual downloads, CC BY-SA. **EM-DAT**: license forbids derived redistributions — skip. **ACLED**: EULA prohibits providing access to the data — **never** commit it. **IOM DTM**: comes free inside HAPI. **ISOC Pulse**: promising (shutdown costs, resilience index) but docs bot-walled; evaluate after creating an account.

---

## 4. Not viable (verified, with reasons)

- **Google News RSS** — alive and tempting but formally off-limits: the feed's own terms restrict to "personal, non-commercial" feed readers, and `news.google.com/robots.txt` disallows the RSS paths. A UN-branded public repo should not build on it.
- **Commercial news APIs** — all fail for this project: NewsAPI.org free tier is dev-only (production $449/mo); Mediastack now 100 calls/*month*; TheNewsAPI 3 articles/request; Event Registry's real free tier (2,000 tokens/mo, 30-day window) cannot cover 195 countries; Currents/APITube/Webz.io licenses explicitly exclude archives/datasets/republication.
- **Common Crawl News** — healthy (July 2026 WARCs verified) but no query API; a compute pipeline, not a static-site fit.
- **Hacker News** — open APIs, zero country granularity, wrong audience. Skip.
- **Baidu Index / Yandex Wordstat** — login/approval-walled, single-region. **Naver DataLab** — open but Korea-only.
- **M-Lab statistics API** — quietly stale: no aggregate files after 2024 (fresh data only via BigQuery + billing account).
- **NetBlocks** — no API, reports/tweets only. **Censored Planet** — raw tarballs, no aggregated API.
- **Sentiment, plainly:** there is no free, live, multi-country sentiment API. Hedonometer froze May 2023 when the Twitter API died. GDELT tone is the only signal; anything else would be invented.

---

## 5. License tiers (decision framework)

1. **Clean, committable:** Wikimedia (CC0), Media Cloud counts, Google Trends facts-with-attribution, GDELT (citation+link), UN SDG/UNHCR/ReliefWeb-counts/HAPI (CC BY family), UCDP (CC BY), OWID (CC BY), GDACS (public domain).
2. **Non-commercial (fine for the Atlas today; needs the Chief's read for anything DGC-monetized):** Cloudflare Radar (CC BY-NC), OONI (CC BY-NC-SA), WHO (CC BY-NC-SA), ITU's own portal (routed around via World Bank).
3. **No formal license (customary use — explicit sign-off before shipping):** Netflix Top 10, Apple Marketing Tools RSS.
4. **Special rules:** YouTube (30-day retention, no long-term metric series, visible attribution); IODA (display-only via live browser fetch, commit nothing without written permission).

**Snapshot sources have no memory** (Trends RSS, YouTube, Apple, Bluesky, Mastodon): history exists only from the day polling starts. If wanted, start the Action early even if the front-end comes later.

---

## 6. Ranked shortlist

1. **Wikimedia top-per-country** — ✅ integrated 2026-08-07.
2. **Google Trends RSS** — ✅ integrated 2026-08-10 (121 countries on the first run; the no-history archive is now accruing daily).
3. **Media Cloud** — news volume vs named national source lists; free key; counts explicitly redistributable.
4. **YouTube charts** — new consumption vertical, ~110 countries; needs the 30-day pruning design + correct labeling.
5. **Cloudflare Radar** — trending domains + shutdown evidence; gated on the NC-license check.

Then: OONI (press-freedom evidence — NC license, needs the Chief), Bluesky — ✅ integrated 2026-08-10 (Topic Explorer, global-only, aggregates-only, shape-guarded), Mastodon/Netflix/Apple as labeled extras (Mastodon deliberately parked: per-instance sampling, thin value for its caveat load).

**Actions only the account holder can take:** apply for the Google Trends API alpha; request a ReliefWeb appname; ask the Chief about tier-2 (NC) and tier-3 (no-license) sources.
