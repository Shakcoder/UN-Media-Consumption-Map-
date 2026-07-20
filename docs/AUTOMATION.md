# How the automation works — in plain English

*Updated 2026-07-20. The Atlas refreshes itself on three schedules. You don't have to do anything to keep it running — and when something DOES need a human (a failed run, a new annual report), the automation opens a GitHub Issue to tell you.*

---

## The one-paragraph version

**Daily**, GitHub runs the trend engine: it reads Wikipedia attention data and GDELT news coverage for 167 UN-relevant topics in 22 languages, computes what's rising where, and publishes the result. **Weekly** (Monday 03:00 UTC), a second workflow pulls 15 World Bank indicators plus per-country language data and rebuilds `data/countries.json`. **Monthly** (the 3rd), a watchdog checks whether RSF, Freedom House, Reuters, GSMA, Afrobarometer, or UN DESA have published a new annual edition — and opens an Issue with step-by-step refresh instructions when they have. GitHub Pages republishes the site automatically after every data commit. If any workflow fails, it opens an Issue so failures are never silent.

---

## The three workflows

| Workflow | Schedule | What it refreshes | Output |
|---|---|---|---|
| [`trend-engine.yml`](../.github/workflows/trend-engine.yml) | Daily 05:30 UTC | Wikipedia pageviews (demand) + GDELT coverage (supply) → per-topic and per-country trend intelligence | `data/trends/wiki_pageviews.json`, `data/trends/gdelt_coverage.json`, `data/trends/topic_intelligence.json` |
| [`refresh-data.yml`](../.github/workflows/refresh-data.yml) | Weekly, Mon 03:00 UTC + whenever `static_countries.json` or `refresh_data.py` changes | World Bank indicators (population, GDP, internet, literacy, Findex financial accounts, …) + Unicode CLDR language shares | `data/countries.json` |
| [`source-watchdog.yml`](../.github/workflows/source-watchdog.yml) | Monthly, 3rd at 06:00 UTC | Nothing directly — it **watches** the annual sources and opens a GitHub Issue (with non-coder instructions) when a new edition is out | Issues labeled `data-refresh` |

All three also have a manual **Run workflow** button: GitHub → Actions tab → pick the workflow → Run workflow.

## What the website reads

| File | Written by | Cadence |
|---|---|---|
| `data/countries.json` | weekly refresh | Mondays (or minutes after you upload a changed script/static file) |
| `data/trends/topic_intelligence.json` | daily trend engine | every morning |
| `data/topics.json` | `scripts/build_topic_registry.py` (manual, rare) | only when the topic list changes |
| `data/static_countries.json` | **you** (hand-curated country blurbs, outlets) | whenever you edit it |

The "Ask the Analyst" page needs **no backend at all** — `ask-engine.js` runs in the visitor's browser and reads the same published JSON files above.

## Resilience — what happens when things go wrong

- **A daily trend run fails?** The next day's run catches up; partial progress is committed so nothing is lost. The site keeps serving yesterday's trends meanwhile.
- **Wikimedia rate-limits the fetcher?** It adapts its pace, checkpoints every 250 series, and completes what it can. Sundays do a full refresh of every series.
- **The World Bank API is down on Monday?** The refresh keeps each country's last good value (with its original source label) rather than writing gaps.
- **Two workflows commit at the same moment?** Each one commits first, then rebases on the other's commit, then pushes — no lost updates.
- **A workflow fails outright?** It opens a GitHub Issue automatically (and GitHub also emails the repo owner). One failure is normal noise; the Issue exists so *repeated* failures get noticed.
- **A file got corrupted mid-write?** Writes are atomic (temp file + rename), and readers rebuild from scratch rather than crashing if they ever meet a bad file.

## The annual sources (the only human job left)

RSF, Freedom House (×2), Reuters DNR, GSMA, Afrobarometer, and UN WPP publish once a year — a human integrates each new edition (the watchdog's Issue explains exactly how, step by step). After integrating, bump that source's year in `scripts/check_source_editions.py` (the `INTEGRATED` map at the top) so the watchdog stops reminding you.

**Known pending as of 2026-07-20:** RSF 2026 is already published (Atlas carries 2025) — expect the watchdog's Issue on its first run; DataReportal smartphone estimates are 2024-vintage.

## Things the automation does NOT do (by design)

- It never edits `data/static_countries.json` (the hand-curated country blurbs and outlet lists — review them opportunistically, e.g. once a year alongside the DNR refresh).
- It never invents data: missing values stay "no data" on the site and the analyst says so.
- It never spends money. Everything runs on GitHub's free tier against free public APIs.

## Changing schedules

Edit the `cron:` line in the relevant workflow file. https://crontab.guru explains cron syntax in plain English. Times are UTC.
