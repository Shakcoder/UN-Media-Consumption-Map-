# Supervisor demo script — Global Media Consumption Atlas

*A 6-minute walkthrough. Every question below is copy-paste ready and has been tested against the live site. Read the **Say** lines in your own words — they're the point you're making, not a script to recite.*

**Before you start:** open the site in a private/incognito window (avoids cached versions), have this page open on your phone or a second screen, and know that the analyst runs entirely in the browser — there's nothing to log into and nothing that can fail to connect.

---

## Opening (30 seconds)

**Say:** "This is the Atlas. It answers one question for communications staff: *where and how do we reach people in any country* — and it shows its evidence for every number. It covers all 195 countries, it updates itself daily, and it costs nothing to run."

**Do:** Land on the map. Let it sit for a moment — the map is the credibility opener. Click any country (try **Kenya**) so a profile slides in. Point at the tabs: Overview, Economy, Media, Society, Sources.

**Say:** "Every figure has a named source with a link. Nothing here is estimated by us."

**Do:** Click the **Sources** tab so they see the citation list.

---

## 1. The headline capability — a full strategy brief (2 minutes)

**Do:** Click **Ask the Analyst** in the top navigation. Type exactly:

```
Distribution strategy for vaccination content in Nigeria
```

**Say while it renders:** "This is what the team asked for last month — not just data, but a recommendation."

**Then walk them through the four things that matter:**

**① The honesty line at the top.** Point at the italic disclaimer.
> *"It opens by telling you what it can't do. That's deliberate — this is decision support, not a decision."*

**② The finding that justifies the whole project.** Point at the Where section, specifically the ⚠ line:
> *"Look at this. Online news measures 94% in Nigeria — so the obvious call is a digital campaign. But the Atlas catches that internet penetration is only 41%. That 94% is 94% **of the people who are already online**. So it recommends radio, at 65%, as the lead channel for national reach."*
>
> *"That's a campaign that would have missed most of Nigeria, caught by the data."*

**③ Formats, honestly labeled.** Point at the What section header.
> *"It says 'feasibility, not measured performance.' No source in the world reliably measures whether video beats text per country, so it won't pretend. What it does instead is tell you what's *possible* given connectivity and literacy."*

**④ Language.** Point at the How section.
> *"English-only content would miss roughly 47% of Nigerians. It tells you to produce in English and Nigerian Pidgin."*

**Do:** Click **"View sources"** at the bottom of the answer.

**Say:** "Every brief carries its receipts."

---

## 2. Prove it isn't guessing (45 seconds)

*This is the most important 45 seconds of the demo. Credibility comes from what a tool refuses to do.*

**Do:** Type exactly:

```
What did our last campaign achieve?
```

**Say:** "It has no campaign archive, and it says so plainly instead of inventing a plausible answer. There are about ten question types it's built to decline this way — past campaign results, format performance, age and gender breakdowns, seasonal timing. Each one names what's missing and offers the closest real evidence instead."

---

## 3. Speed round — the range (1.5 minutes)

*Type these back to back. Don't over-explain; the pace is the point.*

```
Compare news trust in France and Germany
```
> *"Side-by-side comparison, any countries, any measure."*

```
Top 5 African countries by radio reliance
```
> *"Rankings across all 195 countries."*

```
whats trending in nigerai
```
> *"Note the typos — I typed that wrong on purpose. It handles real typing, and this is live attention data, refreshed every morning."*

```
Which countries have state-controlled media environments?
```
> *"It understands what you mean, not just keywords — that's a press-freedom ranking, worst first."*

---

## 4. Close — why it survives (45 seconds)

**Say:** "Three things worth knowing about how this runs:

**It maintains itself.** Trends refresh daily, country indicators weekly, and once a month a watchdog checks whether the big annual reports — Reporters Without Borders, Freedom House, Reuters — have published new editions. When they do, it files a reminder with step-by-step instructions. Nothing silently goes stale.

**It costs zero.** Free public data, free hosting, free automation, and the analyst runs in the visitor's browser. There's no subscription that can lapse and no server to maintain.

**It's been tested.** We ran it against 100 realistic questions written by the team — the acceptance test in the design document. It passes 82, and critically, zero of the failures give a wrong answer. The remaining gaps are all cases where it's more cautious than it needs to be."

---

## Likely questions — and honest answers

**"How accurate is this?"**
> Every figure comes from a named institutional source — World Bank, Reuters Institute, Freedom House, Afrobarometer, UN DESA. The Atlas doesn't generate numbers, it aggregates and cites them. Where a survey has known limits, like the Reuters panel being urban and online in some countries, the answer says so.

**"Can it replace agency research?"**
> No, and it says so in every brief. It's the first 80% — the landscape evidence you'd otherwise spend two weeks assembling — so that human expertise goes into judgment, not data-gathering.

**"What happens when Shakti leaves?"**
> The automation is self-maintaining and self-monitoring. The documentation is written for non-coders. The one recurring human job is integrating the annual reports when the watchdog flags them, which is a documented, step-by-step task.

**"Can it do [X] that it just refused?"**
> Usually the honest answer is that no free source measures it. Where a paid source exists, that's a budget conversation. Where a free source exists that we haven't integrated, there's a documented list of vetted candidates in `docs/DATA_SOURCES.md`.

**"Can we add more countries / topics?"**
> All 195 UN countries are already covered. Topics are a tracked list of 167 — adding more is a small, documented change.

---

## If something goes wrong live

- **Page looks stale or odd:** hard-refresh (⌘⇧R). It's almost always browser cache.
- **An answer looks thin:** say so out loud and move on — *"that's one of the gaps we've documented"* is a stronger look than pretending. The tool's honesty is the pitch.
- **No internet:** the screenshots in your slides still make every point above. The map and a strategy brief are the two images worth having on hand.
