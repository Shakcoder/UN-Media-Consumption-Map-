# Data Source Registry & Methodology

*The authoritative record of every source in the Global Media Consumption Atlas: what it provides, its license, how often it updates, and how conflicts between sources are resolved. Derived from the UN "Audience Intelligence Database: Feasibility and Data Availability Assessment" (June 2026) — every free source in that report is either integrated, covered by an equivalent, pending a registration only the account holder can complete, or documented as a linked reference tool.*

Last updated: 2026-07-14

## 1. Integrated sources (data flows into the Atlas)

| Source | Fields | Coverage | Update cadence | License | Status |
|---|---|---|---|---|---|
| World Bank Open Data API | population, GDP/capita, internet %, urban %, literacy, age structure, mobile subs, broadband, area, electricity, life expectancy, education spending | ~195 countries | **Automated weekly** (Atlas workflow) | CC BY 4.0 | ✅ live |
| — ITU (via World Bank) | the ICT indicators above (internet, mobile, broadband) are *originally compiled by ITU* | | | WB redistribution = CC BY 4.0 (ITU's own portal is CC BY-NC-SA — we deliberately use the WB version for clean public licensing) | ✅ attributed |
| — UNESCO Institute for Statistics (via World Bank) | literacy, education spending originally compiled by UIS | | | CC BY 4.0 via WB | ✅ attributed |
| UN DESA World Population Prospects 2024 | median age (2025 estimates) | 195/195 | Biennial revision | CC BY 3.0 IGO | ✅ live |
| GSMA Mobile Connectivity Index | composite mobile-internet enabling score (0–100) | 172/195 | Annual (2024 edition) | Free dataset, attribution | ✅ live |
| RSF World Press Freedom Index 2025 | rank (1–180) + score (0–100) | 174/195 | Annual | Free, attribution | ✅ live |
| Freedom House — Freedom in the World 2026 | political freedom 0–100, official status, political rights /40, civil liberties /60, electoral-democracy designation | 193/195 | Annual | Official data files provided directly by Freedom House (July 2026); free with attribution | ✅ live, verified 192/192 vs our prior compilation |
| Freedom House — Freedom on the Net 2025 | internet freedom 0–100 | 70/195 | Annual | Free, attribution | ✅ live |
| Reuters Institute Digital News Report 2026 | trust in news, TV/online/social weekly reach | 46 markets | Annual (June) | Free report, attribution | ✅ live; **non-representative samples flagged** (see §3) |
| Afrobarometer Round 9 microdata | TV/radio/online/social weekly news use, computed from 53,444 weighted interviews | 35–39 African countries | Per wave (~2–3 years; R10 releasing 2025–26) | Free | ✅ live (radio is exclusive to this source) |
| Wikimedia Pageviews API | topic demand signal (167 topics × 22 languages, daily) | Global | **Automated daily** | CC0 | ✅ live |
| GDELT 2.0 | topic news-coverage volume + source-country mix | Global, 100+ languages | **Automated daily** | Open | ✅ live |
| DataReportal 2024 | smartphone adoption estimates | 50 countries | Annual | Free, attribution (estimates) | ✅ live, tier-C estimates |
| CIA World Factbook | cross-reference for curated profile fields (languages, government, media outlines) | Global | Continuous | Public domain | ✅ attributed |

## 2. Pending sources (free, but require a personal registration the account holder must complete)

| Source | Would add | Blocker |
|---|---|---|
| Arab Barometer Wave IX | measured news consumption for ~8 MENA countries (replacing compiled estimates) | Registration form (name/email/institution) |
| Asian Barometer Wave 6 | same for ~13 Asian countries | Application form |
| Eurobarometer (via GESIS) | EU-27 media trust detail | Free GESIS account |
| Latinobarómetro | ~17 Latin American countries | Download form |
| World Values Survey Wave 7 | media-trust trends, ~90 countries | Registration |

Until these are completed, the affected countries carry clearly-labeled compiled estimates (`src` field names the basis). **This is the single largest remaining data-quality upgrade available.**

## 3. Known caveats & how conflicts are resolved

1. **DNR representativeness.** Reuters DNR 2026 samples in **India, Kenya, Nigeria, South Africa, Morocco** are online, younger, urban, mainly English-speaking (per the report's own methodology). These countries carry a visible `survey_note` caveat on the site and in analyst answers.
2. **Smartphone %: DataReportal estimates vs GSMA.** Where both exist we display DataReportal's headline estimate for continuity but ship the GSMA Mobile Connectivity Index alongside as the measured, methodologically-consistent signal. If they diverge sharply for a country, trust MCI's direction.
3. **Internet %: ITU vs World Bank.** Identical numbers (WB republishes ITU); no conflict possible. We use WB for the license (CC BY 4.0 vs ITU's NC).
4. **Freedom status: our thresholds vs official.** Resolved July 2026 — 11 countries were mislabeled by score-threshold derivation; official Freedom House statuses (derived from PR/CL ratings) now override everywhere.
5. **Trend country-attribution.** Wikipedia pageviews are per *language edition*; mapping to countries uses documented speaker-population weights — an approximation, labeled as such everywhere it appears. GDELT attributes by *outlet* country (supply), never mixed with demand.
6. **Radio.** Only Afrobarometer measures radio as a single reach figure (39 countries). DNR reports radio per-brand only. No synthetic radio numbers are generated for other countries.
7. **Missing values** are shown as "no data" — never imputed, never averaged from neighbors.
8. **True data years.** World Bank values carry the year of the actual observation (the fetcher scans a 12-year window for each country's latest real value rather than using gap-filled series).

## 4. Reference tools (linked, not ingested)

These are cited in the Atlas's Sources page as analyst tools rather than data feeds: **UNESCO World Trends in Freedom of Expression** (sister-agency report; qualitative), **Pew Research Center** (topline reports), **Edison Research** (US podcast/audio), **OECD Data** (overlaps WB for our fields), **Meta Ad Library** and **Google Ads Transparency Center** (real-time ad-activity lookups, no bulk export), **Google Trends** (covered by the Wikipedia+GDELT trend engine, which offers bulk access and clean licensing).

## 5. Excluded (paid) sources

Per the June 2026 feasibility report and the zero-budget mandate: GWI, Statista, Semrush/Ahrefs/Moz, SimilarWeb, Crunchbase, LinkedIn Sales Navigator, Nielsen/Comscore/Kantar/eMarketer. Free equivalents documented in the feasibility report §5 are what the Atlas uses.
