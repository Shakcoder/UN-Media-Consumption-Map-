# Data Source Registry & Methodology

*The authoritative record of every source in the Audience Intelligence Atlas: what it provides, its license, how often it updates, and how conflicts between sources are resolved. Derived from the UN "Audience Intelligence Database: Feasibility and Data Availability Assessment" (June 2026) — every free source in that report is either integrated, covered by an equivalent, pending a registration only the account holder can complete, or documented as a linked reference tool.*

Last updated: 2026-08-07

> **If you are checking where a number came from, §1 is the list.** Every source label you can see on the site (a country's Sources tab, the footnotes under an analyst answer) must appear in §1 below. If you ever find a label on the site that is *not* in this table, that is a defect worth reporting — it is exactly the condition `scripts/validate_atlas.py` exists to prevent.

## 1. Integrated sources (data flows into the Atlas)

| Source | Fields | Coverage | Update cadence | License | Status |
|---|---|---|---|---|---|
| World Bank Open Data API | population, GDP/capita, internet %, urban %, literacy, age structure, mobile subs, broadband, area, electricity, life expectancy, education spending | ~195 countries | **Automated weekly** (Atlas workflow) | CC BY 4.0 | ✅ live |
| — ITU (via World Bank) | the ICT indicators above (internet, mobile, broadband) are *originally compiled by ITU* | | | WB redistribution = CC BY 4.0 (ITU's own portal is CC BY-NC-SA — we deliberately use the WB version for clean public licensing) | ✅ attributed |
| — UNESCO Institute for Statistics (via World Bank) | literacy, education spending originally compiled by UIS | | | CC BY 4.0 via WB | ✅ attributed |
| UN DESA World Population Prospects 2024 | median age (2025 estimates) | 195/195 | Biennial revision | CC BY 3.0 IGO | ✅ live |
| GSMA Mobile Connectivity Index | composite mobile-internet enabling score (0–100) | 172/195 | Annual (2024 edition) | Free dataset, attribution | ✅ live |
| RSF World Press Freedom Index 2026 | rank (1–180), score (0–100), and RSF's five context sub-scores (political, economic, legal, social, safety) | 175/195 | Annual — one command, `python3 scripts/fetch_rsf.py`, which downloads RSF's own published CSV (no hand-typed numbers) | Free, attribution | ✅ live |
| Freedom House — Freedom in the World 2026 | political freedom 0–100, official status, political rights /40, civil liberties /60, electoral-democracy designation | 193/195 | Annual | Official data files provided directly by Freedom House (July 2026); free with attribution | ✅ live, verified 192/192 vs our prior compilation |
| Freedom House — Freedom on the Net 2025 | internet freedom 0–100 | 70/195 | Annual | Free, attribution | ✅ live |
| Reuters Institute Digital News Report 2026 | trust in news, TV/online/social weekly reach | 46 markets | Annual (June) | Free report, attribution | ✅ live; **non-representative samples flagged** (see §3) |
| Afrobarometer Round 9 microdata | TV/radio/online/social weekly news use, computed from 53,444 weighted interviews | 35 countries for news use, 39 for radio | Per wave (~2–3 years; R10 releasing 2025–26) | Free | ✅ live |
| World Values Survey Wave 7 microdata | TV/radio/online/social news use + trust, computed by `scripts/compute_wvs_news.py` | 28 | Per wave (Wave 7 fieldwork 2017–2022) | Free after registration; **the raw file may not be redistributed**, so only computed aggregates are published, with WVSA's required citation (Haerpfer et al. 2022, doi:10.14281/18241.24) | ✅ live — **different construct**: use = daily *or* weekly (DNR asks "past week"); trust = confidence in the press as an institution, not DNR's trust-in-news. Every country entry carries that note |
| Eurobarometer 102.2 (GESIS ZA8905) microdata | TV/radio/online-news/social weekly reach, computed by `scripts/compute_eurobarometer.py` | 12 | Per Eurobarometer wave | Free after a GESIS account; raw file stays local (doi:10.4232/1.14726) | ✅ live — **different construct**: measures *general* media use, not news use (except the online-news item), so TV/radio/social are an upper bound on news reach. Trust is deliberately left empty: EB measures trust per medium, and picking or averaging one would be construct invention |
| Arab Barometer Waves VII & VIII microdata | primary news source per channel, computed by `scripts/compute_arabbarometer_w7.py` and `scripts/compute_arabbarometer_w8.py` | 4 (Algeria from W VII; Iraq, Kuwait, Palestine from W VIII) | Per wave (~2 years) | Free after a short form; raw file stays local | ✅ live — **different construct**: a *single-choice* "primary source" question, so percentages are structurally lower than weekly-use figures and sum to ~100 across channels. Never compare head-to-head with DNR. No trust question exists in either wave |
| Asian Barometer Wave 6 microdata | most-important news channel, computed by `scripts/compute_asianbarometer.py` | 1 (Cambodia) | Per wave; Wave 6 country files are released one country at a time | Free after registration; raw file stays local | ✅ live — same single-choice caveat as Arab Barometer. Wave 6's answer option merges internet and social media, so social media is left empty rather than double-counted |
| Latinobarómetro 2024 microdata | measured social/messaging platform use (S14M battery), computed by `scripts/compute_latinobarometro.py` | 17 | Per wave (2024 wave in use) | Free after registration; raw file stays local | ✅ live in the separate `platform_use` field — **platform use is not news consumption**, so it never fills news-consumption figures (see §2) |
| Statcounter GlobalStats | social-platform share of *web referrals*, 3-month average (`data/platform_web_shares.json`) | 195 | Monthly data; re-fetched weekly with the country refresh by `scripts/fetch_statcounter.py` | Free public CSV endpoint, used with attribution — check Statcounter's own terms before redistributing it in bulk | ✅ live — shown *alongside*, never instead of, the curated leading-platform field. App-first platforms (WhatsApp, TikTok, Telegram) barely refer web traffic, so the top platform here is **not** necessarily the country's leading platform |
| WPP Media "This Year, Next Year" + Dentsu Global Ad Spend Forecasts | global/regional/market advertising spend and growth (`data/ad_market.json`) | global + APAC + 7 markets (US, China, India, Brazil, UK, Japan, Australia) | Annual **hand-update** each December/January — the watchdog opens an Issue and `data/ad_market.json` → `_meta.how_to_update` lists every step | Free published year-end summaries, used with attribution (headline figures only) | ✅ live — **industry estimates, not surveys**. The two firms measure different market baskets, so their totals differ on purpose; the Atlas keeps both as a cross-check and treats every figure as directional |
| Wikimedia Pageviews API | topic demand signal (167 topics × 22 languages, daily) | Global | **Automated daily** | CC0 | ✅ live |
| Wikimedia Pageviews API — top-per-country | each country's most-read Wikipedia pages + reading-language mix (`data/trends/country_reading.json`, `scripts/fetch_trends_wiki_countries.py`) | **~45–60/195 with article-level data** (varies daily; first run: 45) — all major media markets. The rest carry an explicit **withheld** flag and are never estimated: Wikimedia's Country and Territory Protection List (e.g. RUS, CHN, IRN, SAU) plus its per-page privacy threshold, which truncates most smaller markets' lists to main/search pages only | **Automated daily** (trend engine) | CC0 | ✅ added 2026-08-07 — *directly* per-country demand (no language weighting, unlike the topic engine's attribution). Filtered to encyclopedia articles (main pages / Special: pages / single-page-edition bot artifacts removed — heuristic, documented in the file's method_note); view counts are Wikimedia's privacy-rounded ceilings. Measures Wikipedia readers, not the general population |
| GDELT 2.0 | topic news-coverage volume + source-country mix | Global, 100+ languages | **Automated daily** | Open | ✅ live |
| DataReportal 2024 | smartphone adoption estimates | 50 countries | Annual | Free, attribution (estimates) | ✅ live, tier-C estimates |
| CIA World Factbook | cross-reference for curated profile fields (languages, government, media outlines) | Global | Continuous | Public domain | ✅ attributed |
| World Bank Global Findex (via the same WB API) | financial-account ownership incl. mobile money (% adults 15+) — digital/financial-inclusion signal | 158/195 | **Automated weekly** (same workflow) | CC BY 4.0 | ✅ added 2026-07-20 |
| Unicode CLDR territory-language data | per-country language shares (% of population) + official status — "which languages should content use" | all 195 | **Automated weekly** (same workflow; CLDR itself updates ~2×/year) | Unicode License V3 | ✅ added 2026-07-20 |
| Wikipedia station lists + Wikidata records | extended per-country TV-station lists (`data/tv_stations.json`) — a breadth layer UNDER the curated top_tv line, requested by DGC 2026-07 | ~150+/195 (varies with Wikipedia's own coverage) | **Automated monthly** (`scripts/fetch_tv_stations.py`; workflow `refresh-tv-stations.yml`) | Names/links: Wikipedia CC BY-SA 4.0, attributed per country. Structured facts (country, active status, typing): Wikidata CC0 | ✅ added 2026-07-31 — **presence-ranked, not viewership**: candidates are harvested from Wikipedia's station-list pages, then each must pass its Wikidata record (in-country per P17, no dissolution date, typed as a broadcaster) before it is published; ordering is sitelink count (international Wikipedia presence). Wikipedia tags several of the source pages unreferenced/incomplete, which is exactly why nothing is published without passing the Wikidata gate, and why the hand-curated `top_tv` line (CIA-Factbook-cross-checked) remains the Atlas's statement of *leading* stations |

*Removed source, for the record: The Atlas briefly carried aggregate UN News readership summaries from Google Analytics (integrated 2026-08-04, removed 2026-08-06). They were removed because DGC has a dedicated, automatically-updating GA dashboard — a second, manually-refreshed copy in the Atlas was redundant and would inevitably drift out of step with it. The approvals and method remain documented in docs/GA_SUMMARY_EXPORTS.md and docs/GA_DATA_REQUEST.md, and the code and data remain in git history if ever wanted again.*

## 2. Pending sources (free, but not yet obtainable or not yet downloaded)

The five barometer/WVS registrations that used to sit here were all completed in July 2026 and their microdata is integrated — see §1. What is genuinely still outstanding:

| Source | Would add | Blocker |
|---|---|---|
| Arab Barometer Wave IX | newer news-consumption figures for the MENA countries | **Not published yet** — Wave IX fieldwork ran through May 2026 and nothing has been released. Nothing to do but wait |
| The rest of Asian Barometer Wave 6 | measured news consumption for more Asian countries (only Cambodia is in so far — Wave 6 releases one country file at a time, and Mongolia and Vietnam are already covered by WVS) | Each new country file has to be downloaded from asianbarometer.org after registration, then run through `scripts/compute_asianbarometer.py` |
| Latinobarómetro **2023** wave | news-*channel* figures for Latin America. The 2024 wave the Atlas uses dropped the "how do you get informed?" battery, so it can only fill measured platform use | Download form (the same registration already used for 2024) |
| Wikipedia **radio-station / newspaper** lists via the same Wikidata gate | extended radio and print outlet lists per country, exactly like the TV layer added 2026-07-31 (`scripts/fetch_tv_stations.py` generalizes: same harvest, same gate, different Wikidata class) | Deliberately staged: ship the TV layer first, extend once it has survived a few monthly refresh cycles |
| ~~Wikipedia social-media-platform lists~~ | — | **Considered 2026-07-31 and rejected**: Wikipedia has no per-country social-platform lists comparable to its TV-station lists, and the Atlas already holds *better* platform evidence on three constructs — curated leading platforms per country, Statcounter's measured web-referral shares (195 countries, refreshed weekly), and Latinobarómetro's measured platform use (17 countries, weighted survey). An unreferenced enumeration would dilute measured data, so per the "feed into, don't replace" instruction the existing platform layers stand |

**The honest headline: 69 of 195 countries still have no measured news-consumption survey of any kind.** They are not estimated and not quietly ranked low — the site names them as excluded wherever that matters (Market Finder lists every one of them; the analyst says so in rankings). Closing that gap, country by country, is the single largest remaining data-quality upgrade available. `python3 scripts/validate_atlas.py` prints the current list of the 69 every time it runs.

**What "pending" must never mean.** A country without a survey stays empty. There is no fallback tier of "compiled estimates": a set of them was found to be invented and was deleted on 2026-07-22, and `scripts/validate_atlas.py` now rejects any source label that is not on its whitelist so the same thing cannot recur. Never add a whitelist pattern for a source that has no real downloaded file behind it.

## 3. Known caveats & how conflicts are resolved

1. **DNR representativeness.** Reuters DNR 2026 samples in **India, Kenya, Nigeria, South Africa, Morocco** are online, younger, urban, mainly English-speaking (per the report's own methodology). These countries carry a visible `survey_note` caveat on the site and in analyst answers.
2. **Smartphone %: DataReportal estimates vs GSMA.** Where both exist we display DataReportal's headline estimate for continuity but ship the GSMA Mobile Connectivity Index alongside as the measured, methodologically-consistent signal. If they diverge sharply for a country, trust MCI's direction.
3. **Internet %: ITU vs World Bank.** Identical numbers (WB republishes ITU); no conflict possible. We use WB for the license (CC BY 4.0 vs ITU's NC).
4. **Freedom status: our thresholds vs official.** Resolved July 2026 — 11 countries were mislabeled by score-threshold derivation; official Freedom House statuses (derived from PR/CL ratings) now override everywhere.
5. **Trend country-attribution.** Wikipedia pageviews are per *language edition*; mapping to countries uses documented speaker-population weights — an approximation, labeled as such everywhere it appears. GDELT attributes by *outlet* country (supply), never mixed with demand.
6. **Radio.** 84 countries have a radio figure, from five different surveys (Afrobarometer 39, WVS 28, Eurobarometer 12, Arab Barometer 4, Asian Barometer 1) — each on that survey's own construct, per rule 9. Reuters DNR is *not* among them: it reports radio per-brand only, so its 46 markets have a radio figure only where another survey supplies one. The remaining 111 countries have no radio number and none is generated for them.
7. **Missing values** are shown as "no data" — never imputed, never averaged from neighbors.
8. **True data years.** World Bank values carry the year of the actual observation (the fetcher scans a 12-year window for each country's latest real value rather than using gap-filled series).
9. **One survey per country — never two.** Six surveys now measure news consumption and their questions are *not* interchangeable, so a country's figures all come from a single one of them. Reuters DNR and Afrobarometer are used wherever they cover a country; each later integration was added only for countries no earlier survey reached. (That is why Cambodia is the sole Asian Barometer entry: Mongolia and Vietnam already had WVS, and mixing two constructs in one country would make its own figures incomparable with each other.) Every country's `src` label names the survey that actually produced its numbers, and the construct caveat from §1 travels with it — which is why the analyst tells you to treat cross-country gaps under ~5 points as noise.
10. **Platform *use* vs platform *web referrals* vs the leading-platform field.** Three different things, deliberately kept apart. Latinobarómetro's `platform_use` is measured self-reported usage (17 countries). Statcounter is measured web-referral share (195 countries) and under-counts app-first platforms. The curated "top social platforms" list in `data/static_countries.json` is a human judgement about actual usage. None of the three overwrites another, and none of them says anything about *news* use.

## 3b. Freshness automation (added 2026-07-20)

Three GitHub Actions keep everything current without human attention. `docs/AUTOMATION.md` explains all of this in non-technical detail, including what to do when a run fails.

| Workflow | Cadence | What it refreshes |
|---|---|---|
| `trend-engine.yml` | **Daily** 05:30 UTC | Wikipedia pageviews + GDELT coverage → topic intelligence; per-country most-read Wikipedia pages → `data/trends/country_reading.json` (with its own 4-day freshness guard) |
| `refresh-data.yml` | **Weekly** Mon 03:00 UTC (and on every data/script upload) | All World Bank indicators (incl. Findex), CLDR languages → `countries.json`; Statcounter platform web shares → `platform_web_shares.json`. `validate_atlas.py` runs as a gate **before** anything is committed, so data that fails the fabrication/range/citation checks is never published |
| `source-watchdog.yml` | **Monthly** 3rd, 06:00 UTC | Probes RSF / Freedom House ×2 / DNR / GSMA / Afrobarometer / UN WPP / the WPP Media + Dentsu ad forecasts; **opens a GitHub Issue with step-by-step instructions** when a new annual edition is detected. Nothing annual can silently go stale again. |

## 4. Vetted future sources (verified free & working, July 2026 research sweep)

> **A fuller August 2026 sweep supersedes parts of this table** — see [docs/SOURCE_RESEARCH_2026-08.md](SOURCE_RESEARCH_2026-08.md) (19 candidates live-verified 2026-08-06, ranked shortlist, license flags, and a blunt closed-platform list). Notable corrections from that sweep: the GDELT **GEO 2.0 API is dead** (404s), Media Cloud signup is an open form (not email), and Wikimedia top-per-country moved from this list into §1.

Each was fetch-verified during the 2026-07-20 audit. Ordered by value; integration effort noted.

| Source | Adds | Access | Effort |
|---|---|---|---|
| Digital Society Project v8 | per-country disinformation / state-media-manipulation indices (179 countries, thru 2025) | direct zip, no registration | low |
| ReliefWeb API v2 | UN-owned per-country crisis salience (needs pre-approved `appname` parameter since Nov 2025) | keyless REST | low |
| OONI Aggregation API | measured blocking of news sites/apps per country | keyless REST | low |
| IODA API | internet-shutdown detection (5-min granularity) | keyless REST | low |
| UN SDG Indicators API | gender-disaggregated mobile ownership (5.b.1), journalist-safety (16.10.1) | keyless REST | medium |
| Our World in Data Grapher API | any context indicator as CSV + ready-made citations | keyless CSV | low |
| Eurostat `isoc_*` | measured EU social/online usage (44 geos) | keyless REST | low |
| V-Dem v16 | media-censorship indices (202 countries) | GitHub download | medium |
| UNDP HDR indices | human-development context | direct CSV (URL changes yearly) | low |
| GDELT TV API | US-centric broadcast attention | keyless REST | low |
| Wikimedia Clickstream | where topic attention comes from (search vs. browse) | monthly dumps | medium |
| Cloudflare Radar API | traffic/outage corroboration | free token (existing CF account) | medium |
| Media Cloud API | curated national outlet lists (4k req/wk free) | free key via email | medium |
| Google Trends alpha API | search attention (apply — UN use case is strong) | application-gated | medium |
| OECD SDMX | measured ICT usage for rich non-EU countries | keyless SDMX | medium |

**Documented exclusions:** DataReportal bulk reuse (license), ITU DataHub API (conflicting access reports — WB already carries the headline ITU indicators; revisit if gender-split data becomes a requirement), Google News RSS (ToS gray zone — validation only).

## 4b. Reference tools (linked, not ingested)

These are cited in the Atlas's Sources page as analyst tools rather than data feeds: **UNESCO World Trends in Freedom of Expression** (sister-agency report; qualitative), **Pew Research Center** (topline reports), **Edison Research** (US podcast/audio), **OECD Data** (overlaps WB for our fields), **Meta Ad Library** and **Google Ads Transparency Center** (real-time ad-activity lookups, no bulk export), **Google Trends** (covered by the Wikipedia+GDELT trend engine, which offers bulk access and clean licensing).

## 5. Excluded (paid) sources

Per the June 2026 feasibility report and the zero-budget mandate: GWI, Statista, Semrush/Ahrefs/Moz, SimilarWeb, Crunchbase, LinkedIn Sales Navigator, Nielsen/Comscore/Kantar/eMarketer. Free equivalents documented in the feasibility report §5 are what the Atlas uses.
