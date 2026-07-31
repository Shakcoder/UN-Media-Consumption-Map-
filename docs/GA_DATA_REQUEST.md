# Google Analytics data request — the ask, the wish-list, and the caveats

*Written 2026-07-30, ahead of the analytics walkthrough. Part 1 is a short
email that can be sent as-is. Parts 2–5 are the detail behind it: everything
worth requesting, how it would be obtained, and the known problems with the
data — including the language field, which does not measure what its name
suggests. Companion to [GA360_WALKTHROUGH.md](GA360_WALKTHROUGH.md), which is
the in-meeting checklist, and to
[GA_SUMMARY_EXPORTS.md](GA_SUMMARY_EXPORTS.md), the practical export steps
under the approved scope.*

---

## Part 0 — APPROVED, WITH A SCOPE (2026-07-30/31)

The Part 1 email was sent on 2026-07-30. The thread is the governing record;
this is what it decided.

**Approved by Fang Chen** (Chief, Partnerships Unit, News and Media Division,
DGC) on 2026-07-30: *"your plan works fine with our goal!"*

**With an explicit scope on the data, from the same message:** *"As for the
google data, why don't we start with summaries, instead of the full access of
data to see how it works?"*

**So the operative rule for this project is: summaries only, for now.**

| Allowed under the approved scope | Out of scope until the Chief widens it |
|---|---|
| Google Analytics' own **aggregate reports** (counts by country, device, channel, page, month) | Raw or event-level exports |
| Exploration / Free-form tables built from those dimensions | BigQuery event export |
| CSV downloads of the above | Anything user-level: client IDs, individual sessions, IP-derived precision beyond country/region |
| Aggregates computed locally from those reports | A live API/connector pulling arbitrary data |

**Why this is recorded here rather than left in an inbox.** Two people
answered the question at different levels of authority, and the answers
differ in scope. Gretchen Corcuera relayed (2026-07-30) that Ali had said it
was "totally ok to connect our Google Analytics account to Claude", on the
grounds that it is "open data" and that connecting is read-only. She then
asked Fang to *"greenlight as you see fit"* — that is, she referred the
decision upward rather than making it. Fang greenlit the plan and named a
narrower starting scope. **The Chief's written instruction is the one this
project follows.** If the broader reading is ever cited later, it should be
re-confirmed with Fang in writing before anything changes.

Two notes worth keeping straight, neither of which changes what we do:
- "Open data" is doing a lot of work in the relayed summary. UN Google
  Analytics data is *internal operational data* the UN happens to own, not
  openly-licensed public data in the sense the Atlas's other sources are
  (CC BY, CC0, public domain). This is exactly why the summaries-first scope
  is the sensible starting point, and why nothing derived from it should be
  published on the public site without a specific OK.
- "Read-only" is true and beside the point. The concern was never that the
  analytics account might be modified; it is what leaves UN systems during
  processing. Summaries answer that concern directly.

**Practical effect on the architecture:** raw exports stay on Shakti's
machine and out of version control; aggregation happens locally; only the
computed country-level summary is used in the Atlas or shared. This is the
same pattern the project already applies to licensed survey microdata
(Afrobarometer, WVS, Eurobarometer and the rest are processed locally by
`scripts/compute_*.py` and only their aggregates are published), so the
approved scope fits the existing design rather than fighting it.

Committed next step, per Shakti's reply on 2026-07-31: experiment with what
the summary reports can support, and report back to the team early the
following week (w/c 2026-08-03).

---

## Part 1 — The email (paste-ready)

> **Subject:** Analytics data for the Audience Intelligence Atlas — what we'd like and why
>
> Hi [name],
>
> Thank you for walking me through the Analytics property. Here is what the
> Atlas project would like to draw on, and why it matters.
>
> **The gap it fills.** The Atlas currently holds verified media-landscape data
> for all 195 UN member states: how many people are online, which channels
> they use for news, which languages they speak, press-freedom conditions, and
> so on. All of it describes a country's *general population*. What it has no
> visibility into is our own audience: who actually reads and watches UN
> content, where, on what device, and how that compares to the population we
> could theoretically reach. Analytics is exactly that missing half. With it,
> the tool can stop saying "here is what Kenya's media landscape looks like"
> and start saying "here is who we currently reach in Kenya, here is the
> audience we don't, and here is the gap" — which is the question a
> communications officer actually needs answered.
>
> **What we'd like.** Ideally, view-only access to the property so I can pull
> reports as the work needs them, rather than coming back to you repeatedly.
> If that isn't possible, scheduled exports of the reports listed in the
> attached document would work nearly as well. The single most valuable
> breakdown is **audience by country over time** — country is the key that
> joins your data to everything already in the Atlas. Beyond that, the
> attached list covers device, traffic source, language edition, content
> performance, and engagement, roughly in priority order.
>
> **Time period.** As far back as the property retains, ideally 24–36 months.
> A single year cannot distinguish a seasonal pattern from a trend, and
> seasonality is one of the things the tool currently tells users it cannot
> answer.
>
> **On handling.** Nothing user-level would be needed, and no raw export would
> ever be committed to the project's public repository — only country-level
> aggregates, at the same granularity as everything else the Atlas publishes.
> Before anything derived from this data goes on a public page, I'd want your
> explicit sign-off on what is and isn't publishable. I'm also happy to keep
> it entirely internal if that's the preference.
>
> Happy to talk any of this through.
>
> Thanks,
> Shakti

---

## Part 2 — Why this data, specifically

The Atlas's own strategy briefs end with a section listing what they cannot
know. That list is currently:

> *past campaign performance, format-level effectiveness (video vs text vs
> audio), age/gender breakdowns, cost per channel, and day-of-week or seasonal
> timing.*

Analytics plausibly closes four of those five. Only cost stays out of reach —
Google Analytics holds no media prices.

More importantly, it adds an axis the project does not have at all. Every
number in the Atlas today is population-level: *85% of Kenyans reach radio
weekly; 35% are online; 66% speak Swahili*. Nothing anywhere in the system
knows a single thing about UN's actual readership. Adding it makes three new
things possible:

1. **Reach-gap analysis.** Reached vs. reachable, per country. Impossible
   without our own numbers, and the most decision-useful output the tool
   could produce.
2. **Measured rather than inferred format guidance.** Today a brief reasons
   "video is *feasible* here because connectivity is 35%." With engagement
   data it can say what actually gets watched and finished.
3. **Real seasonality.** The Atlas's trend window is ~120 days of public
   attention signals. Multi-year analytics history replaces guesswork about
   timing with observation.

---

## Part 3 — The wish-list

Grouped by priority. Everything here is a standard Google Analytics dimension
or metric unless marked otherwise — none of it requires custom engineering on
the analytics side.

### Tier 1 — Essential (the integration is built on these)

| What | Why it matters to the Atlas |
|---|---|
| **Country** (× date) | The join key. Every one of the Atlas's 195 records is keyed by country; this is what connects the two datasets. Without it nothing else can be used. |
| **Users / active users** | The base audience-size number per market. |
| **Sessions** | Visit volume; users × frequency. |
| **Views (pageviews)** | Content consumption volume. |
| **Date** (daily granularity) | Enables seasonality, day-of-week, and event-response analysis. Monthly rollups lose too much. |
| **Device category** (mobile / desktop / tablet) | Joins directly to the Atlas's smartphone-adoption and mobile-connectivity figures; mobile share is the single strongest signal of how content should be formatted. |

### Tier 2 — High value (each unlocks a specific capability)

| What | Why it matters |
|---|---|
| **Session default channel group** (Organic Search, Direct, Organic Social, Referral, Email, Paid) | Shows which channels actually deliver UN audiences per country — validates or contradicts the Atlas's platform recommendations against real behaviour. |
| **Session source / medium** | The granular version of the above: which specific platforms and referrers drive traffic. Directly comparable to the Atlas's leading-platform data. |
| **Landing page / page path** | Which content performs where. If content is organised by topic, this becomes topic-level demand per country. |
| **Content group** *(if configured)* | The clean version of the above — topic/section labels rather than raw URLs. Worth asking whether these exist. |
| **Language edition of the page** (via page path or hostname, e.g. `/ar/`, `/fr/`, `news.un.org/en`) | **This, not the "Language" dimension, is the real language signal.** See Part 5. Lets the Atlas compare which language editions get used against which languages a country actually speaks. |
| **Average engagement time per session** | Distinguishes a real read from a bounce; the quality half of every volume number. |
| **Engagement rate / engaged sessions** | Same, at session level. |
| **Site search terms** *(if site search tracking is on)* | Extremely valuable and often overlooked: a direct measure of what audiences came looking for and could not find, per country. Maps onto the Atlas's existing topic-demand data. Worth asking about explicitly. |
| **Video events** (`video_start`, `video_progress`, `video_complete`) | The one realistic route to measured format performance — completion rates by country turn an inference into an observation. |
| **Scroll depth** (`scroll` / 90% events) | Read-completion proxy for text content; the text-side equivalent of video completion. |
| **File downloads / outbound clicks** | Signals of deeper intent than a pageview. |
| **New vs returning users** | Distinguishes reach-building from audience-retention — different strategic problems with different recommendations. |

### Tier 3 — Valuable where available

| What | Why it matters | Caveat |
|---|---|---|
| **Region / city** | Would give the Atlas its first subnational data — currently a documented gap. Urban/rural skew is directly comparable to the World Bank urbanisation figures already held. | IP-derived; city-level accuracy is modest. |
| **Age bracket, gender** | Closes the age/gender crosstab gap the briefs currently decline outright. | **Only exists if Google Signals is enabled**, covers only a subset of signed-in users, is inferred rather than declared, and is withheld entirely below reporting thresholds — so it will be blank for exactly the smaller countries where Atlas data is already thinnest. |
| **Interest / affinity categories** | Topic-affinity signal comparable to the Atlas's topic intelligence. | Same Google Signals caveats; inferred by Google, not observed. |
| **Operating system, browser, screen resolution** | Device-capability picture: what content will actually render well in a market. | Low priority. |
| **Hour of day** | Publishing-time guidance. | Reported in the property's timezone, not the reader's — needs care. |
| **Cohort / retention reports** | Whether audiences come back — the strongest available proxy for content resonance. | |
| **Custom dimensions** *(GA360 feature)* | Whatever the UN has defined — content type, author, campaign tags, agency. Worth asking what exists; these are often the most useful fields in a mature property. | |
| **Property / site list** | Which properties exist at all (un.org, news.un.org, UN Web TV, SDG sites, agency sites) and whether a roll-up property combines them. | |

### Also worth asking about

- **Multiple properties**: does each UN site have its own, and is there a
  roll-up? Pooling differently-tagged properties naively would produce wrong
  numbers.
- **Apps**: are there UN mobile apps reporting into the same property as
  separate data streams?
- **BigQuery export**: whether it's switched on. It's the GA360 feature that
  makes long-range and unsampled analysis straightforward.
- **Data retention setting**: what it's configured to (this bounds how far
  back anything can go — see Part 5).
- **Annotations / campaign calendar**: knowing which spikes were campaigns
  versus news events is the difference between insight and noise.

---

## Part 4 — How the data would be obtained and used

### Obtaining it, in order of preference

1. **View-only (Viewer) access** to the property for a UN address. Read-only,
   the cheapest thing for an administrator to grant, and it removes the need
   to keep asking. Reports get pulled as the analysis requires.
2. **Scheduled report exports** — Analytics can email a CSV on a recurring
   schedule. Fits the project's existing architecture (which already runs on
   scheduled automated data refreshes) and requires no credentials.
3. **The Analytics Data API with a service account** — fully automated. Needs
   an administrator to create a credential, which would be stored as an
   encrypted secret, never in the repository.
4. **BigQuery export** — the most powerful option and the only one that gives
   unsampled, event-level history. Also the most complex and the most likely
   to carry personal data, so it is a deliberate later step, not a first one.

### Using it

Analytics figures would be aggregated to **country-level** and joined to each
country's existing Atlas record on its ISO code. From there:

- a new *current performance* view per country (audience size, device split,
  channel mix, top content);
- the **reach-gap** comparison — current audience against the population the
  Atlas already knows is reachable, by channel and by language;
- **format guidance upgraded** from inference to measurement wherever video
  or scroll data supports it;
- **seasonality** replacing the current ~120-day attention window;
- and a **new evidence tag** so this data is never confused with the survey
  data (see Part 5, point 2).

### What would and would not be published

The project's repository is public. So:

- **Never published, never committed**: any raw export, any user-level or
  event-level row, anything with identifiers.
- **Candidate for publication, only with sign-off**: country-level aggregates
  — the same granularity as every other figure the Atlas shows.
- The raw files would live outside version control, exactly as the project
  already handles licensed survey microdata (Afrobarometer, WVS and others are
  processed locally; only computed aggregates are published).

---

## Part 5 — Known problems with this data

These are not reasons to avoid the data. They are the things that must be
designed around, and several of them are the kind of error that looks like a
finding until someone checks.

### 1. The "Language" dimension does not measure language preference

This is the most important caveat, and the easiest to get wrong.

Google Analytics's **Language** field reports the *browser or device locale* —
the language setting on the device. It does **not** report the language of the
content read, and it does **not** report the reader's preferred or best
language. A Kenyan reading an English UN page on a phone shipped with English
as its default locale registers as "English", regardless of whether Swahili
would have served them better. Since most phones sold in East Africa ship with
an English locale and many users never change it, the field systematically
over-reports English.

Meanwhile the Atlas holds Unicode CLDR data showing **66% of Kenya speaks
Swahili and 19% English**. If the analytics language field were read as
"our audience prefers English", it would directly contradict better evidence
and push exactly the wrong recommendation.

**How it gets handled:** the browser-locale field is treated as a
device-configuration signal, not a language signal. The real measure of
language demand is **which language edition of the site people actually use**
— derived from the page path or hostname (`/ar/`, `/es/`, `news.un.org/fr`).
That is observed behaviour on content whose language is known, and it is the
field worth requesting.

### 2. It measures who already arrived — not who could be reached

Analytics can only see people who found UN content. It is a self-selected
sample of the addressable audience, and it is silent about everyone missed.

The dangerous misreading: *"our audience is urban, English-speaking and on
mobile, so target urban English-speaking mobile users."* That reasoning
optimises toward the audience already captured and away from the audience
being missed — the exact opposite of what a reach strategy should do.

**How it gets handled:** analytics data always shown *against* the
population-level baseline, never alone. And a distinct evidence tag. The
briefs currently label every claim `[measured]`, `[inferred]` or `[unknown]`;
analytics figures are measured, but of a *different population* than the
surveys. Without their own tag, "85% of Kenyans hear radio weekly" and "85% of
our readers came via mobile" would read as the same kind of fact. This project
already applies exactly this discipline to survey sources that measure
different constructs (Reuters DNR, Arab Barometer and WVS are never compared
head-to-head for this reason) — the pattern extends, but it must be built in
deliberately.

### 3. It is digital-only

No radio, no TV, no print. In more than 30 African countries radio is the
leading news channel, and the Atlas's strongest recommendations often point
there. Analytics will make the *digital* half of every brief sharper while the
highest-reach channel stays unmeasured — which creates a quiet pull toward
digital-first recommendations simply because that is where the data is. This
has to be actively resisted in how the briefs are written.

### 4. Geography is IP-derived and imperfect

VPNs, corporate networks, roaming and diaspora traffic all misattribute.
Traffic labelled "United States" for a UN property is also likely to include a
large institutional share — press, missions, NGOs, universities — rather than
general public. Country totals are directional, not precise, and heavily
institutional markets should not be read as public reach.

### 5. Demographic data may barely exist

Age and gender only appear if Google Signals is enabled, cover only a subset
of signed-in Google users, are **inferred** by Google rather than declared,
and are suppressed entirely below reporting thresholds. The practical effect:
they will be blank or unusable for small and low-traffic countries — precisely
the countries where the Atlas's survey coverage is already thinnest. Where
they exist they are useful; they cannot be relied on for global coverage.

### 6. Retention limits how far back anything goes

Event-level data in Analytics 4 is kept for a configured window — commonly 14
months on standard properties, up to 50 on 360. Aggregate reports reach
further back than detailed explorations do. Since seasonality needs at least
two annual cycles to be distinguishable from a trend, this is worth
establishing early: **what is the retention setting, and is BigQuery export
on?** If retention is short and no export exists, multi-year seasonality may
simply not be recoverable.

### 7. Consent banners distort European figures specifically

If UN sites run GDPR consent banners, traffic from users who decline is either
missing or modelled rather than observed. European numbers are therefore not
directly comparable to numbers from regions without consent gating — a
particular hazard for any region-vs-region comparison, which the Atlas's
analyst produces routinely.

### 8. Sampling and "(other)" bucketing

Large reports may be sampled rather than exact (much less so on 360, and not
at all via BigQuery). Separately, high-cardinality dimensions get collapsed
into an "(other)" bucket once limits are hit — which silently swallows the
long tail. Since the long tail here is *small countries*, the countries most
in need of data are the ones most likely to vanish into it. Any export should
be checked for a sampling indicator and for the presence of "(other)" rows.

### 9. Cross-property comparability

Different UN sites may have different tagging, event definitions, content
groupings and consent configurations. Pooling them without checking would
produce a number that looks authoritative and means nothing. Each property
needs to be understood before any combination.

### 10. Bots, scrapers and AI crawlers

Known bots are filtered automatically; many are not. Traffic spikes in the
current era frequently reflect scrapers rather than readers. Sudden
unexplained growth should be treated as suspect until checked.

### 11. Definition drift over time

Channel groupings and metric definitions have been redefined more than once
(and the platform itself migrated from Universal Analytics). Multi-year
comparisons can silently compare two different definitions of the same word.
Anything spanning that migration needs its break points known.

### 12. Traffic is not impact

Views measure arrival, not comprehension, persuasion or behaviour change.
The Atlas should present analytics as evidence of *reach*, never as evidence
of *effectiveness* — a distinction the tool's existing disclaimers already
make carefully, and which must not erode when richer numbers arrive.

---

## Summary

Worth requesting, in one line each:

- **Ask for**: view-only access; failing that, scheduled CSV exports.
- **Priority breakdown**: audience by **country × date**, plus device,
  channel, language edition, content, and engagement.
- **Time span**: as long as retention allows — 24–36 months if possible.
- **Establish early**: retention setting, whether BigQuery export is on,
  whether Google Signals is on, what custom dimensions exist, and which
  properties there are.
- **Design around**: the language field measuring device locale rather than
  language preference; the data describing arrivals rather than the reachable
  audience; and its digital-only blind spot.
- **Never**: commit a raw export to the public repository, or publish
  anything derived from this data without the data owner's sign-off.
