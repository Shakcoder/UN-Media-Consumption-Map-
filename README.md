# Audience Intelligence Atlas

*(formerly “Global Media Consumption Atlas”)*
### An AI-assisted Content Intelligence Platform for UN communications

An interactive, source-cited public resource showing **where and how the world gets its information** — and **what each country is paying attention to right now** — across all 195 UN-recognised countries.

**Live site:** the Atlas (interactive map) · Topic Explorer (live trends, 167 UN-relevant topics tracked) · Market Finder (which countries fit a campaign) · AI Analyst (free-text questions, evidence-backed answers — runs entirely in your browser)

## What it does

| Page | What it answers |
|---|---|
| **Map** (`index.html`) | "What does Country X's media landscape look like?" — platforms, trust, connectivity, press freedom, demographics, with a citation on every number |
| **Topic Explorer** (`topics.html`) | "What is the world paying attention to this week?" — daily attention trends for 167 topics across 22 languages |
| **Market Finder** (`finder.html`) | "We have a campaign — **which countries** should get it?" — a disclosed, deterministic screen over every country with verified media data; countries without the required survey are listed as excluded, never silently ranked low. Screenings are shareable by link, exportable to CSV (exclusions included), and printable |
| **AI Analyst** (`ask.html`) | Any question in plain English — comparisons, rankings, campaign guidance, live trends. Understands typos and follow-ups, asks clarifying questions, cites all sources per answer. Every answer has a shareable link and prints as a cited one-pager |

## How it stays current, at $0

- **Daily** — the trend engine (GitHub Actions) refreshes Wikipedia-attention and GDELT news-coverage signals, each country's most-read Wikipedia pages, each country's trending Google searches, each country's UN-share of national-press coverage (Media Cloud), and a global Bluesky social pulse.
- **Weekly** — the data refresh pulls 15 World Bank indicators and Unicode CLDR language data for every country.
- **Monthly** — a source watchdog probes the annual flagship sources (RSF, Freedom House, Reuters DNR, GSMA, Afrobarometer, UN WPP) and **opens a GitHub Issue with step-by-step instructions** whenever a new edition is published.
- **Hosting** — GitHub Pages. **Automation** — GitHub Actions. **AI analyst** — in-browser, no server. Total running cost: **$0**.

## Documents
- [`HANDOVER.md`](HANDOVER.md) — **start here if you are taking over maintenance**: what runs by itself, the four gates, the annual calendar
- [`docs/PLATFORM_DESIGN.md`](docs/PLATFORM_DESIGN.md) — full platform design (the pivot plan)
- [`docs/DATA_SOURCES.md`](docs/DATA_SOURCES.md) — every source: license, cadence, conflict-resolution rules
- [`docs/AUTOMATION.md`](docs/AUTOMATION.md) — how the automated pipelines work, for non-coders
- [`docs/SUPERVISOR_SUMMARY.md`](docs/SUPERVISOR_SUMMARY.md) — one-page summary for supervisors
- [`docs/AUDIT_2026-07.md`](docs/AUDIT_2026-07.md) — July 2026 production-readiness audit: what was checked, what was wrong, what changed, and what is still open
- [`worker/DEPLOY_GUIDE.md`](worker/DEPLOY_GUIDE.md) — **experimental, switched off**: an unfinished Cloudflare prose layer. The analyst does not need it and nothing on the site calls it.

## Repository layout
```
/                index.html, topics.html, finder.html, ask.html, ask-engine.js — the site
/data/           countries.json (generated weekly), topics.json, trends/ (generated daily)
/data/sources/   original files from annual sources (Freedom House, …)
/scripts/        data pipeline (Python, run by GitHub Actions) + validate_atlas.py
/eval/           acceptance-test records (see Testing below)
/.github/        the three automated workflows
/docs/           human-readable documentation
/worker/         optional Cloudflare Worker (free AI-written prose)
```

## Principles
1. **Every number has a citation.** No exceptions — every answer ends with a numbered Sources list, and every country profile has a Sources tab.
2. **Gaps are shown honestly.** "No data" beats a bad estimate; the analyst refuses rather than guesses.
3. **Radio and TV are first-class.** In much of the world they out-reach digital — recommendations respect that.
4. **Boring tech, zero cost.** Plain HTML/CSS/JS + GitHub's free tier, maintainable after handover by non-coders.
