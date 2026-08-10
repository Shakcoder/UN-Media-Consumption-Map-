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

Five workflows (GitHub → **Actions** tab), all with a manual "Run workflow"
button. Full detail: [docs/AUTOMATION.md](docs/AUTOMATION.md).

| Workflow | When | What it does |
|---|---|---|
| Trend engine | daily 05:30 UTC | Refreshes topic attention (Wikipedia) + news coverage (GDELT) |
| Refresh country data | Mondays 03:00 UTC | Pulls 15 World Bank indicators + language data, rebuilds `countries.json` — **will not publish if validation fails** |
| TV-station refresh | 12th of each month | Rebuilds the extended TV-station lists (Wikipedia lists gated through Wikidata) — **refuses to publish a thin result** |
| Source watchdog | 3rd of each month | Checks whether annual sources published a new edition; opens an Issue with instructions when one has |
| Code gates | every push + daily 12:00 UTC | Runs the validator and all three eval suites; a red X means don't trust the live site until fixed |

**None of this needs a paid service, an AI subscription, or a password.** The
workflows are ordinary Python and JavaScript scripts running on GitHub's free
machines, fetching public data. Nothing here costs money and nothing expires on
a billing date. (Checked August 2026: no workflow or script references any AI
service.)

**There is exactly one stored credential — know about it.** Since 2026-08-10 the
Media Cloud fetcher (national-press coverage) uses a free API key, stored as the
repository secret `MEDIACLOUD_API_KEY` (GitHub → Settings → Secrets and variables
→ Actions). Two things a successor must know:

- It was deliberately registered on the **UN media-partnerships team account**,
  not a personal one, so the key itself outlives any individual's departure.
- **After transferring the repository, confirm the secret is still there** (same
  Settings page). If it is missing, log in to
  [search.mediacloud.org](https://search.mediacloud.org/), copy the key from the
  account page, and paste it back — one minute's work. Everything else keeps
  running regardless; only the "UN in the national press" figures would stop
  refreshing, and the engine raises a loud failure after 7 stale days.

Every other source (Wikimedia, GDELT, Google Trends, Bluesky, World Bank,
Statcounter, CLDR) is keyless and needs no account at all.

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
node scripts/run_eval.mjs selfknowledge
```

Expected: `0 error(s)`, `0 CRASHED`, `18/18`, `73/73`, `28/28 routed (0 dead ends)`. The Code gates workflow
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
- **Still blocked on UN-side access:** Salesforce, and the audience survey
  (Google Form) — see [docs/SURVEY_SETUP.md](docs/SURVEY_SETUP.md), which
  requires supervisor sign-off on
  [docs/SURVEY_ETHICS.md](docs/SURVEY_ETHICS.md) first.

## Handing over: what to do before the current maintainer leaves

*Written 2026-08-05, while the Atlas was still maintained by its original
author (a UN intern, contract ending September 2026). Everything below is a
one-time job, none of it costs money, and all of it takes under an hour.*

### The reassuring part

Once handed over, the Atlas keeps running on its own. **There is nothing to
cancel, renew, or pay for.** Hosting is free, the automation is free, and no
part of the live site calls a paid service.

Two points that surprise people:

- **The "AI Analyst" page is not powered by AI.** Despite the name, it is a
  set of rules running inside the visitor's own browser, reading the published
  data files. There is no AI service behind it and no subscription attached to
  it. It will keep working exactly as it does today. (The optional AI
  text-polishing layer in `worker/` was deliberately left switched **off**.)
- **The daily and weekly data refreshes need no human at all.** Country
  indicators, topic trends, per-country reading lists, trending searches, the
  Bluesky pulse, national-press coverage, TV-station lists and the safety
  checks all continue without anyone touching them.

What *stops* without a person: the annual report updates, and reading the
Issues the automation opens. Those are listed above.

**The one thing that would stop everything** is not technical: it is the
GitHub account. Today `Shakcoder` is the repository's **only** collaborator and
administrator (verified 2026-08-10). Nobody else can currently re-enable a
sleeping workflow, re-add the Media Cloud key, or recover the site. That is
what item 1 below fixes, and it is the single highest-value hour of the whole
handover.

### Three things to do before the handover

**1. Transfer the repository to a UN-owned account. (The most important one.)**

The project currently lives under a personal GitHub account (`Shakcoder`). If
that account is closed or abandoned, **the website and all of its automation
disappear with it.** Move it to an account or organisation the UN controls:

> GitHub → the repository → **Settings** → scroll to the bottom (**Danger
> Zone**) → **Transfer ownership** → type the new owner's account name.

*After the transfer, check two things:* that the `MEDIACLOUD_API_KEY` secret is
still listed under Settings → Secrets and variables → Actions (re-add it from
the Media Cloud account page if not), and that the five workflows still show as
enabled under the Actions tab.

**One honest consequence:** the public web address changes. A GitHub Pages
site is named after its owner, so `shakcoder.github.io/...` becomes
`newowner.github.io/...`, and GitHub does **not** forward the old address.
Any link already shared in an email or slide deck would stop working.

Two ways to handle that, both fine:

- *Transfer anyway* (recommended) and re-share the new link. Safest long-term:
  the UN genuinely owns the project.
- *If a link has already been circulated widely*, add the successor as an
  **admin** instead (Settings → Collaborators), which keeps the address
  working. This is weaker — the personal account still ultimately owns it — so
  treat it as a temporary step, not the destination.

**2. Make sure a real person receives the failure alerts.**

When a workflow fails, GitHub emails **the repository owner**. After the
transfer that should be a UN address or a team, not a departing intern's
personal inbox. Check under Settings → Notifications for the new owner, and
tell the successor plainly: *if you get an email saying a workflow failed, open
the Issue it created and follow the steps written inside it.*

**3. Know about the 60-day sleep rule.**

GitHub switches off scheduled jobs in a public project after **60 days with no
repository activity**. The daily trend engine does commit every morning — but
those commits are made by the automation itself (the `atlas-bot` identity using
GitHub's built-in token), and **GitHub does not reliably count a bot's own
commits as "activity"** for this rule. Treat the safe assumption as the true
one: *the jobs may fall asleep even while they appear to be working.*

Two cheap defences, either is enough:

1. **A human touches the repository at least once every couple of months** —
   any real commit, comment, or edit through the website resets the clock. In
   practice, anyone maintaining the data does this without trying.
2. **Know how to wake it up.** GitHub emails the repository owner before
   disabling, and re-enabling takes one click:
   > GitHub → **Actions** tab → pick the workflow → **Enable workflow**.

The symptom to recognise: the site's "Data last checked" date stops advancing
while nothing appears to have failed. That is this rule, not a broken script.

### What happens if nobody does any of this

Being honest about the failure mode: the site keeps publishing and the
automatic data keeps refreshing, possibly for years. What decays is everything
needing a human — the annual reports go stale (each figure still names its
year, so nothing becomes a *lie*, just older), the UN News numbers freeze at
their last pull, and failure Issues pile up unread. The real cliff-edge is the
account: if the personal GitHub account goes, so does the site. **That is the
one item worth doing this week rather than in September.**

## What was deliberately NOT built

- **A Google Analytics layer (added 2026-08-04, removed 2026-08-06).** The Atlas briefly carried aggregate UN News readership summaries from Google Analytics (integrated 2026-08-04, removed 2026-08-06). They were removed because DGC has a dedicated, automatically-updating GA dashboard — a second, manually-refreshed copy in the Atlas was redundant and would inevitably drift out of step with it. The approvals and method remain documented in docs/GA_SUMMARY_EXPORTS.md and docs/GA_DATA_REQUEST.md, and the code and data remain in git history if ever wanted again.

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
