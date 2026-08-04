# Things only you can do

*A running list of everything waiting on a human — kept current as work lands.
Nothing here is blocked on code; each item needs an account, an approval, or a
judgement call. Last updated: 2026-07-29.*

**Context as of 2026-07-29:** the team green-lit using the UN's own Google
Analytics 360 data in the Atlas, and the goal is a product DGC can genuinely
use by **September** (in-person until Aug 20, remote to Sept 30). The two new
items below exist because of that.

---

## Do first (highest value first)

### 1. Pull the Google Analytics summary reports ✅ approved, scoped
**Status: approved by Fang Chen on 2026-07-30** — *"your plan works fine with
our goal!"* — **with a scope**: *"why don't we start with summaries, instead
of the full access of data to see how it works?"* You told the team you would
experiment and report back **early w/c 2026-08-03**.

Summaries only, for now. Aggregate reports from the Analytics interface:
yes. Raw/event-level exports, BigQuery, anything user-level: no, not until
the Chief widens the scope in writing. Full record of the decision, including
why it is narrower than the informal "totally ok to connect" relayed in the
same thread, is in
[docs/GA_DATA_REQUEST.md](docs/GA_DATA_REQUEST.md) Part 0.

**What to do:** follow
[docs/GA_SUMMARY_EXPORTS.md](docs/GA_SUMMARY_EXPORTS.md) — step-by-step
export instructions for six summary reports, written for someone who has
never opened the Explore tool. Report 1 (users by country by month) is the
one that matters most; country is the key that joins Analytics to all 195
Atlas records. Report 4 is the interesting one: it captures which *language
edition* of a page people actually opened, which is the real language signal,
unlike the "Language" dimension that only reports device settings.

**Save the CSVs OUTSIDE this folder** (e.g. `~/Documents/UN Analytics
Exports/`) — this repository is public. `.gitignore` now refuses
`ga_*.csv` and similar as a second line of defence, but keeping them out of
the folder is the real protection. Then say where the folder is and the
aggregation gets built against the real column shapes.

**Update 2026-08-04 — first summary published.** An aggregate pull covering
the six report shapes (API-assisted equivalents of the Explore exports; same
aggregation level, nothing raw retained) is now live as
`data/ga_summary.json`, feeding the Map's "UN News analytics" section, the
per-country readership blocks, the Topic Explorer strip, and the analyst's
trending-topics report and dissemination strategy. For the report-back Fang
asked for, the four questions now have answers: **(1)** all six report shapes
were available on the English and All-languages properties, no permission
gaps; **(2)** demographics were deliberately *not* pulled — treat as a scope
question for Fang; **(3)** history reaches back beyond June 2026 (the pull
used Jun 9 – Aug 3; full depth not yet probed); **(4)** no sampling was
reported on any request. One flag worth raising with her: the pull was made
through the Analytics *API* at aggregate-report level — same summaries, less
error-prone than hand-exporting CSVs — confirm she is comfortable calling
that "summaries" too, and show her the published file so the scope stays
visibly honoured.

Other reference documents:
- **[docs/GA360_WALKTHROUGH.md](docs/GA360_WALKTHROUGH.md)** — the in-meeting
  checklist, if a walkthrough with the administrators still happens.
- **[docs/GA_DATA_REQUEST.md](docs/GA_DATA_REQUEST.md)** — the full wish-list
  and the twelve known problems with analytics data.

### 2. Ask who owns privacy/security sign-off — still unanswered
The analytics question got answered; this one did not, and it is the slower
of the two. Before the Atlas is used as a real DGC product, someone on the UN
side has to say what review it needs — data protection, hosting, or a simple
OK. Worth asking Fang directly, since she has now engaged with the project:

> Hi Fang,
>
> One follow-up, and there is no urgency to it. Before the database is used
> as a real product within DGC, I would like to confirm what review it needs
> on the UN side: data protection, hosting, or simply your OK. Who would be
> the right person to ask? I am starting the technical side myself; I am
> raising the organisational side early because it tends to take longer.
>
> Thanks!

*(The audience-survey approval that used to be bundled into this email is
deferred by choice, 2026-07-29 — see "Deferred" below.)*

### 3. Decide on the AI upgrade (see the section below)
Free, but it needs an account in your name that can be transferred to the UN,
and one judgement call about risk.

---

## The AI analyst upgrade — what it needs from you

**What already shipped, needing nothing from you:** the analyst now shows its
reasoning, answers questions about its own methodology and data, and no longer
dead-ends on conversational phrasing.

**What needs you, if you want free-text answers on questions the engine cannot
route deterministically:**

1. **A free Cloudflare account** (~5 minutes, no card required). Workers AI's
   free tier runs a Llama model server-side. Create it with a UN-transferable
   address — *not* a personal one — because the account is the thing handed
   over. The deploy steps are in [worker/DEPLOY_GUIDE.md](worker/DEPLOY_GUIDE.md).
2. **A judgement call, and it is a real one.** A language model rewriting
   answers is the one thing that can reintroduce invented figures — the exact
   failure this project spent July eliminating. The guardrail already written
   is that the model may only rephrase the evidence pack, and any figure it
   emits that is not in that pack is rejected and the deterministic answer is
   shown instead. That reduces the risk; it does not erase it.
3. **Tell your supervisor before it goes live.** A UN-branded page whose text
   is machine-written should not be a surprise to the people it represents.

**My recommendation:** leave it off until someone can own it. The deterministic
improvements cover most of what "feels limited", and the Worker has no test
coverage — it is the one part of the Atlas that could publish something wrong.

---

## Once a year (the automation will remind you)

The source watchdog opens a GitHub Issue with step-by-step instructions when
each annual source publishes. Nothing to remember; just act on the Issues.

| Roughly when | Source | What it takes |
|---|---|---|
| February | Freedom House — Freedom in the World | follow the Issue |
| April–May | RSF Press Freedom Index | one command: `python3 scripts/fetch_rsf.py` |
| June | Reuters Institute Digital News Report | hand-update the DNR table |
| October | Freedom House — Freedom on the Net | follow the Issue |
| December | WPP Media + Dentsu ad forecasts | hand-update `data/ad_market.json` |

**Outstanding now:** WPP published a **Midyear 2026** forecast on 16 June 2026
while the Atlas carries the December 2025 edition, so `data/ad_market.json` is
one edition behind. The watchdog will file this; integrating it means reading
WPP's and Dentsu's published regional tables. Nothing here was estimated, and
nothing should be.

Also worth an annual skim: the hand-written parts of
`data/static_countries.json` (capitals, governments, currencies) drift with
political events and nothing checks them.

---

## Deferred by choice

- **The audience survey** (Google Form + supervisor sign-off on
  [docs/SURVEY_ETHICS.md](docs/SURVEY_ETHICS.md)) — explicitly parked
  2026-07-29 to keep the focus on analytics integration. When it comes back:
  the withdrawal-request email address in SURVEY_ETHICS.md is still
  `[to be added]`, and the sign-off checklist at the bottom of that file is
  the launch gate.

---

## Standing to-dos with no deadline

- **Survey microdata registrations.** Each `scripts/compute_*.py` reproduces
  its figures from a file you download after a free registration
  (Afrobarometer, Arab Barometer, World Values Survey, Eurobarometer/GESIS,
  Latinobarómetro, Asian Barometer). The files are not in the repository
  because their licences forbid it. If you register for **Asian Barometer
  Wave 6** country files beyond Cambodia, a couple more countries could gain
  real survey data.
- **Watch [Issue #2](https://github.com/Shakcoder/UN-Media-Consumption-Map-/issues/2)**
  (trend engine catching up). Close it when a run goes green; if it is still
  failing in a week, see AUTOMATION.md → Troubleshooting.

---

## Done — no longer needs you

- ~~Em-dash cleanup~~ — resolved 2026-07-29: the database is at zero em-dashes,
  enforced at the generators. The analyst's sentence punctuation was left
  untouched by explicit decision (rewriting ~500 sentences risked fragment
  bugs for no functional gain).

- ~~RSF 2026~~ — integrated; now a one-command refresh.
- ~~Gabon / Burundi country facts~~ — corrected July 2026.
- ~~Chad / Syria country facts~~ — corrected 2026-07-30 (Chad: Presidential
  republic; Syria: Transitional presidential republic — per the CIA World
  Factbook).
- ~~Crimea shown inside Russia~~ — corrected to UN position (GA res 68/262).
