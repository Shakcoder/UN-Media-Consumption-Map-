# How the automation works — in plain English

*Updated 2026-07-27. The Atlas refreshes itself on three schedules. You don't have to do anything to keep it running — and when something DOES need a human (a failed run, a new annual report), the automation opens a GitHub Issue to tell you.*

---

## The one-paragraph version

**Daily**, GitHub runs the trend engine: it reads Wikipedia attention data and GDELT news coverage for 167 UN-relevant topics in 22 languages, computes what's rising where, and publishes the result. **Weekly** (Monday 03:00 UTC), a second workflow pulls 15 World Bank indicators plus per-country language data and rebuilds `data/countries.json`, then refreshes the Statcounter platform shares in `data/platform_web_shares.json`. **Monthly** (the 3rd), a watchdog checks whether RSF, Freedom House, Reuters, GSMA, Afrobarometer, UN DESA, or the WPP Media/Dentsu ad forecasts have published a new annual edition — and opens an Issue with step-by-step refresh instructions when they have. GitHub Pages republishes the site automatically after every data commit. If any workflow fails, it opens an Issue so failures are never silent.

---

## The four workflows

| Workflow | Schedule | What it refreshes | Output |
|---|---|---|---|
| [`trend-engine.yml`](../.github/workflows/trend-engine.yml) | Daily 05:30 UTC | Runs as **parallel lanes since 2026-08-10** (each lane gets its own runner, i.e. its own IP and rate budget — one runner could not carry a whole day's fetching). Supply lane: each country's trending Google searches (Trending Now RSS — first, because the feed keeps no history), the global Bluesky pulse, GDELT coverage, each country's most-read Wikipedia pages. Press lane: each country's UN-share of national-press stories (Media Cloud — needs the `MEDIACLOUD_API_KEY` repo secret, set 2026-08-10 from the team account). Demand lanes: Wikipedia pageviews in 3 stalest-first shards. An assemble job merges everything, computes the trend intelligence, makes the single daily commit, and fails loudly if anything is going stale | `data/trends/country_searches.json`, `data/trends/bluesky_trends.json`, `data/trends/press_un_coverage.json`, `data/trends/wiki_pageviews.json`, `data/trends/gdelt_coverage.json`, `data/trends/topic_intelligence.json`, `data/trends/country_reading.json` |
| [`refresh-data.yml`](../.github/workflows/refresh-data.yml) | Weekly, Mon 03:00 UTC + whenever `static_countries.json` or `refresh_data.py` changes | World Bank indicators (population, GDP, internet, literacy, Findex financial accounts, …) + Unicode CLDR language shares; then Statcounter social-platform web shares | `data/countries.json`, `data/platform_web_shares.json` |
| [`refresh-tv-stations.yml`](../.github/workflows/refresh-tv-stations.yml) | Monthly, 12th at 04:30 UTC | Extended per-country TV-station lists: candidates harvested from Wikipedia's station-list pages, each gated through its Wikidata record (in-country, not defunct, typed as a broadcaster) | `data/tv_stations.json` |
| [`source-watchdog.yml`](../.github/workflows/source-watchdog.yml) | Monthly, 3rd at 06:00 UTC | Nothing directly — it **watches** the eight annual sources (RSF, Freedom House ×2, Reuters DNR, GSMA, Afrobarometer, UN WPP, WPP Media + Dentsu ad forecasts) and opens a GitHub Issue (with non-coder instructions) when a new edition is out | Issues labeled `data-refresh` |

All four also have a manual **Run workflow** button: GitHub → Actions tab → pick the workflow → Run workflow.

## What the website reads

These files ARE the site. Every page loads them straight from the repo — nothing else is fetched at runtime. The last column is what to check first when a page looks wrong.

| File | Written by | Cadence | Which pages read it |
|---|---|---|---|
| `data/countries.json` | weekly refresh | Mondays (or minutes after you upload a changed script/static file) | Map, AI Analyst, Market Finder |
| `data/trends/topic_intelligence.json` | daily trend engine | every morning | Topic Explorer, Map, AI Analyst |
| `data/topics.json` | `scripts/build_topic_registry.py` (manual, rare) | only when the topic list changes | AI Analyst, Market Finder (the topic list) |
| `data/platform_web_shares.json` | weekly refresh, via `scripts/fetch_statcounter.py` | Mondays | Map — the "social web-traffic share" block on a country's Media tab |
| `data/ad_market.json` | **you**, by hand | once a year, each December/January | AI Analyst — ad-market context inside strategy briefs |
| `data/tv_stations.json` | monthly TV-station refresh | 12th of each month | Map — the "More TV stations" block on a country's Media tab; AI Analyst — extended station lists in country answers |
| `data/trends/country_reading.json` | daily trend engine, via `scripts/fetch_trends_wiki_countries.py` | every morning | Map — the "Most-read Wikipedia pages" block on a country's Media tab; AI Analyst — reading-list evidence in country answers |
| `data/trends/country_searches.json` | daily trend engine, via `scripts/fetch_trends_google.py` | every morning | Map — the "Trending searches" block on a country's Media tab; AI Analyst — the "What X is searching for" line and evidence in country answers |
| `data/trends/bluesky_trends.json` | daily trend engine, via `scripts/fetch_trends_bluesky.py` | every morning | Topic Explorer — the "Open social web right now" section on the overview pane (global only, never on country pages) |
| `data/trends/press_un_coverage.json` | daily trend engine, via `scripts/fetch_press_un_coverage.py` (needs the `MEDIACLOUD_API_KEY` repo secret; country→collection mapping lives in `data/sources/mediacloud_collections.json`) | every morning (rolling 7-day window) | Map — the "UN in the national press" block on a country's Media tab; AI Analyst — the national-press line and evidence in country answers |
| `data/boundaries/countries.geojson` | `scripts/build_boundaries.py` (manual, rare) | only if the boundary snapshot pin is deliberately moved | Map — the country outlines themselves |

The "AI Analyst" and "Market Finder" pages need **no backend at all** — `ask-engine.js` runs in the visitor's browser and reads the published JSON files above.

**Five of these degrade quietly on purpose.** If `platform_web_shares.json`, `ad_market.json`, `tv_stations.json`, `trends/country_reading.json` or `trends/country_searches.json` is missing or fails to load, the page simply leaves out that block instead of showing an error — the rest of the profile or brief is unaffected. That is why a Statcounter outage is not an emergency, and also why a *silently missing* file can go unnoticed: if the social-share, "Most-read Wikipedia pages" or "Trending searches" block has vanished from the Media tab, its file is the thing to check. (The reading-lists and trending-searches files also have freshness guards in the trend-engine workflow itself: if either one's newest data goes more than 4 days old, the daily run fails and opens an Issue — for the searches file that matters doubly, because its feed keeps no history and every silent missed day is unrecoverable.)

`data/static_countries.json` is **not** in the table because the site never loads it directly. It is the hand-curated input — country blurbs, leading outlets, top social platforms — that the weekly refresh merges into `countries.json`. Editing it triggers a refresh run within minutes.

`data/ad_market.json` is the one *published* file with no automation behind it at all. WPP Media and Dentsu each publish a free year-end advertising forecast in December; the watchdog opens an Issue when a new edition appears, and the file's own `_meta.how_to_update` field walks through the four steps. Nothing else needs changing when you update it — the analyst reads the file directly.

## Resilience — what happens when things go wrong

- **A daily trend run fails?** The next day's run catches up; partial progress is committed so nothing is lost. The site keeps serving yesterday's trends meanwhile.
- **Wikimedia rate-limits the fetcher?** It adapts its pace, checkpoints every 250 series, and completes what it can — working through the **stalest series first**, so whatever a timeout cuts off is exactly what runs first next time. Sundays attempt a full refresh of every series.
- **Refreshed data comes back wrong?** `validate_atlas.py` now runs as a gate *before* the weekly refresh commits. If it finds an error (a source label that isn't on the fabrication whitelist, a percentage outside 0–100, a value with no citation), the workflow stops, nothing is published, and an Issue is opened. The site keeps serving the last good data.
- **The World Bank API is down on Monday?** The refresh keeps each country's last good value (with its original source label) rather than writing gaps.
- **Statcounter doesn't answer?** Deliberately non-fatal. The step logs a yellow `::warning::` and the run carries on; the previous `data/platform_web_shares.json` stays in place, so the Map keeps showing last month's shares. The fetcher also refuses to write a file with far fewer countries than the published one, so a half-successful fetch can't quietly replace a good 195-country file with three.
- **Two workflows commit at the same moment?** Each one commits first, then rebases on the other's commit, then pushes — no lost updates.
- **A workflow fails outright?** It opens a GitHub Issue automatically (and GitHub also emails the repo owner). One failure is normal noise; the Issue exists so *repeated* failures get noticed.
- **A file got corrupted mid-write?** Writes are atomic (temp file + rename), and readers rebuild from scratch rather than crashing if they ever meet a bad file.

## The annual sources (the only human job left)

RSF, Freedom House (×2), Reuters DNR, GSMA, Afrobarometer, UN WPP, and the WPP Media + Dentsu ad forecasts publish once a year — a human integrates each new edition (the watchdog's Issue explains exactly how, step by step). After integrating, bump that source's year in `scripts/check_source_editions.py` (the `INTEGRATED` map at the top) so the watchdog stops reminding you.

**RSF is now a one-command refresh.** It used to mean hand-typing ~350 numbers into `scripts/refresh_data.py`. Instead run:

```bash
python3 scripts/fetch_rsf.py
```

That downloads RSF's own published table into `data/sources/rsf/rsf_index.json`; the weekly refresh picks it up automatically. Add `--year 2027` when a newer edition is out. If the download fails, the existing file is left untouched and the command exits non-zero — it will never half-update the index.

**Known pending as of 2026-07-27:** DataReportal smartphone estimates are 2024-vintage. Freedom House FOTN 2025 and Reuters DNR 2026 are current. RSF 2026 is integrated. The ad-market figures are the December 2025 editions, so the next hand-update falls due around January 2027.

---

## Troubleshooting

### "Trend engine failed" Issue, red step = *Fail if most trend series are stale* (assemble job)

**What it means.** A fetch lane is not keeping up. The error names the file: `topic_intelligence` coverage means the Wikipedia pageview shards, `country_reading` means the per-country reading-list fetch, `country_searches` means the Google Trends fetch (that one matters doubly — its feed keeps no history, so silently missed days are gone forever). The site stays honest either way — it scores only what it can measure and says so — but coverage shrinks.

**Why the alarm exists.** Through July 2026 this happened silently for three weeks: the fetch timed out daily, the step was marked "continue on error", the run reported success, and two-thirds of series stayed frozen at 2026-07-05 while the site said it was updating daily. The velocity maths also read "the last 7 array positions" as "the last 7 days", so those frozen series reported three-week-old numbers as this week's. Both are fixed — windows are now anchored to calendar dates, and a majority-stale run fails loudly. In August 2026 the deeper cause was found: Wikimedia and GDELT rate-limit **per IP address**, and a single runner's IP has a smaller daily budget than the work needs. That is why the workflow now runs parallel lanes on separate runners (2026-08-10) — more IPs, more budget — with every fetcher processing stalest-first so truncated days self-heal.

**What to do.** Usually nothing: the fetchers work stalest-first, so consecutive runs claw back coverage on their own. Check `data/trends/topic_intelligence.json` → `coverage` after a few days; `series_stale_excluded` should be falling. If it is still climbing after a week, the pageview fetch needs more parallel budget — raise the shard count (add `4` to the `shard:` list in `trend-engine.yml` AND change the two `3`s in the shard step's command to `4`, plus a fourth filename under the merge step), or raise `DORMANT_MEAN` in `scripts/fetch_trends_wikipedia.py` (fewer low-traffic series fetched on weekdays).

### "Weekly data refresh failed" Issue, red step = *Validate refreshed data*

Something upstream returned data the validator rejects. Open the run's log — `validate_atlas.py` prints each problem with the country and field. **Nothing was published**, so the site is unaffected. Common cause: a new survey integration whose source label has not been added to the whitelist in `scripts/validate_atlas.py` (that whitelist is deliberate — it is what stops invented numbers from reaching the site).

### A yellow warning in the weekly run: *Statcounter fetch failed*

Not a failure — the run goes green and the data is published as normal. Statcounter's free CSV endpoint simply didn't answer, so `data/platform_web_shares.json` was left exactly as it was and the Map keeps showing the previous 3-month window. Statcounter publishes monthly, and the refresh runs weekly, so a skipped week costs nothing.

**When to act:** only if the warning appears several weeks in a row. Then run `python3 scripts/fetch_statcounter.py` yourself and read the error — if Statcounter has changed or withdrawn the CSV endpoint, the honest fix is to remove the block from the Media tab rather than to keep publishing a frozen file. Check the `_meta.window` field inside `data/platform_web_shares.json` to see how old the data actually is.

### The map or a page looks empty

Open the browser console (right-click → Inspect → Console). If you see `using inline fallback data`, `data/countries.json` did not load — the page now shows an on-screen banner saying so. Check that the last `refresh-data` run succeeded and that GitHub Pages finished publishing.

## Things the automation does NOT do (by design)

- It never edits `data/static_countries.json` (the hand-curated country blurbs and outlet lists — review them opportunistically, e.g. once a year alongside the DNR refresh).
- It never invents data: missing values stay "no data" on the site and the analyst says so.
- It never spends money. Everything runs on GitHub's free tier against free public APIs.

## Changing schedules

Edit the `cron:` line in the relevant workflow file. https://crontab.guru explains cron syntax in plain English. Times are UTC.
