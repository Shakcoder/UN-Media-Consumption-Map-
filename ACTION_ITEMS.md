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

### 1. The Google Analytics walkthrough — in the next few days
The team will walk you through the UN's GA360 data. Before you go, read
[docs/GA360_WALKTHROUGH.md](docs/GA360_WALKTHROUGH.md) — it is a one-page
sheet of exactly what to ask and the three things to walk out with (a sample
CSV, the administrator's name, and a yes/no on viewer access). The entire
integration design depends on what comes back from that meeting.

### 2. Send the access + privacy email — this week, because the latency outlasts the build
Two asks, both slow, both needing only a name from your supervisor:

**Copy-paste draft** (adjust names):

> Subject: Two quick asks for the Audience Intelligence Atlas
>
> Hi [supervisor],
>
> 1. **Analytics access**: the team is walking me through our Google
>    Analytics 360 data shortly, so the Atlas can show how UN content
>    performs alongside its media-landscape data. Could you point me to (or
>    loop in) whoever administers our Google Analytics and Salesforce
>    accounts? View-only access is all it needs; nothing is installed on
>    their side.
> 2. **Privacy/security sign-off**: before the Atlas is used as a real DGC
>    product, I want to confirm what review it needs on the UN side — data
>    protection, hosting, or a simple OK. Who would be the right person to
>    ask? The technical security review is already underway on my side; I'm
>    starting the organizational one early because it tends to be the slower
>    track.
>
> Neither has any cost. Thanks!

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
