# Handover guide — start here

*Written August 2026 for whoever maintains the Audience Intelligence Atlas next.
No coding background assumed. Reading time: ten minutes. Everything else in
`docs/` goes deeper; this page tells you what exists, what runs by itself, and
what actually needs a human.*

---

## What this is

The Atlas answers one question for UN communications officers: **where and how
should we communicate, in any of 195 countries?** It is a static website — four
pages, no server, no database, no login, total running cost **$0**:

| Page | What it does |
|---|---|
| **Map** (`index.html`) | Country profiles: media landscape, connectivity, press freedom, demographics — every figure cited |
| **Topic Explorer** (`topics.html`) | What the world is looking up, tracked daily across 22 languages |
| **Market Finder** (`finder.html`) | "We have a campaign — which countries should get it?" |
| **AI Analyst** (`ask.html`) | Free-text questions, evidence-backed answers. Deterministic — it computes answers from the Atlas's own data in the visitor's browser and cannot invent figures |

**Sharing what the Atlas produces.** Analyst answers and Market Finder screenings
both live in the URL: asking a question writes it into the address bar, and opening
such a link re-runs it on the recipient's machine (nothing is uploaded — the link
just says which question to compute). Both pages have a "Copy link" button, both
print as clean cited one-pagers, and Market Finder exports a CSV that carries the
excluded countries and their reasons alongside the ranking — so a spreadsheet can
never be mistaken for a ranking of every country.

Hosting is GitHub Pages (publishes automatically on every commit). Automation
is GitHub Actions. Data lives in `data/` as JSON files a human can open.

## The one principle that outranks everything

**Never let an uncited or invented number onto the site.** In June 2026,
16 countries briefly carried fabricated survey figures with real-sounding
citations; the whole safety apparatus below exists so that can never happen
again. When in doubt, showing "no data" is always correct. Estimates are not.

## What runs by itself

Four workflows (GitHub → **Actions** tab), all with a manual "Run workflow"
button. Full detail: [docs/AUTOMATION.md](docs/AUTOMATION.md).

| Workflow | When | What it does |
|---|---|---|
| Trend engine | daily 05:30 UTC | Refreshes topic attention (Wikipedia) + news coverage (GDELT) |
| Refresh country data | Mondays 03:00 UTC | Pulls 15 World Bank indicators + language data, rebuilds `countries.json` — **will not publish if validation fails** |
| Source watchdog | 3rd of each month | Checks whether annual sources published a new edition; opens an Issue with instructions when one has |
| Code gates | every push + daily 12:00 UTC | Runs the validator and all three eval suites; a red X means don't trust the live site until fixed |

**When something breaks, a GitHub Issue opens automatically** (and GitHub
emails the repository owner). One failed day is normal noise. The
[troubleshooting section of AUTOMATION.md](docs/AUTOMATION.md#troubleshooting)
walks through the known failure modes in plain English.

## The four gates (run these after ANY change)

```bash
python3 scripts/validate_atlas.py
node scripts/run_eval.mjs
node scripts/run_eval.mjs strategy
node scripts/run_eval.mjs market
```

Expected: `0 error(s)`, `0 CRASHED`, `18/18`, `73/73`. The Code gates workflow
runs the same four automatically on every push — so even if you forget, a
broken change shows a red X on the commit instead of silently breaking the
site. What the suites check: [eval/README.md](eval/README.md).

## The annual calendar (the only recurring human job)

The watchdog opens a reminder Issue for each of these, with step-by-step
instructions. Rough publication months:

| When | Source | Effort |
|---|---|---|
| February | Freedom House — Freedom in the World | follow the Issue's steps |
| April–May | RSF World Press Freedom Index | **one command**: `python3 scripts/fetch_rsf.py` |
| June | Reuters Institute Digital News Report | hand-update the DNR table in `scripts/refresh_data.py` |
| October | Freedom House — Freedom on the Net | follow the Issue's steps |
| December | WPP Media + Dentsu ad forecasts | hand-update `data/ad_market.json` |
| When published | Afrobarometer Round 10, new barometer waves | see the matching `scripts/compute_*.py` docstring |

Also once a year: skim `data/static_countries.json` for stale political facts
(capitals, forms of government) — nothing refreshes that file automatically.
Two entries were already flagged for a human decision: **Chad and Syria** are
still listed as "Transitional government".

## Things that need the account holder

- **Survey microdata is not in this repository** (licences forbid it). The
  `scripts/compute_*.py` files reproduce every survey figure, but their input
  files live in the maintainer's own downloads after free registration with
  each programme (Afrobarometer, Arab Barometer, World Values Survey,
  Eurobarometer/GESIS, Latinobarómetro, Asian Barometer). Each script's header
  says exactly which file it needs and where to register.
- **Never-finished integrations** blocked on UN-side access, not on code:
  GA4/Salesforce analytics and the audience survey (Google Form) — see
  [docs/SURVEY_SETUP.md](docs/SURVEY_SETUP.md), which requires supervisor
  sign-off on [docs/SURVEY_ETHICS.md](docs/SURVEY_ETHICS.md) first.

## What was deliberately NOT built

- **The Cloudflare worker** (`worker/`) is experimental and switched off. The
  site does not need it. Do not deploy it without reading
  [worker/DEPLOY_GUIDE.md](worker/DEPLOY_GUIDE.md) — it has no test coverage.
- **No estimates for the 69 uncovered countries.** No free nationally
  representative survey exists for them. They show as "profile only" and are
  excluded from rankings *by name, with the reason stated* — that honesty is a
  feature, not a gap to fill.
- **Paid data sources.** The $0 constraint is deliberate and load-bearing.

## Reading order for the rest

1. [docs/AUDIT_2026-07.md](docs/AUDIT_2026-07.md) — the July 2026 production
   audit: what was found, fixed, and knowingly left; the honest limitations
   list is the closest thing to a "known issues" page.
2. [docs/AUTOMATION.md](docs/AUTOMATION.md) — every pipeline, in plain English,
   plus troubleshooting.
3. [docs/DATA_SOURCES.md](docs/DATA_SOURCES.md) — every source: licence,
   cadence, and how conflicts between sources are resolved.
4. [docs/DEMO_SCRIPT.md](docs/DEMO_SCRIPT.md) — a rehearsed 10-minute demo.
5. [docs/PLATFORM_DESIGN.md](docs/PLATFORM_DESIGN.md) — the original design
   (historical context; the audit report reflects current reality).

## If you only remember three things

1. **The site publishes itself; your job is to read the Issues** the
   automation opens and follow their instructions.
2. **Run the four gates** (or just check the commit's ✓/✗) after any change.
3. **"No data" is always an acceptable answer.** An invented number never is.
