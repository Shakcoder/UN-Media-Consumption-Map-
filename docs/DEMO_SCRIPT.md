# Supervisor demo script — Audience Intelligence Atlas

*A 7-minute walkthrough. Every question below is copy-paste ready and was re-run, step by step, against the live deployed site on 2026-07-28 — including every quoted number. Read the **Say** lines in your own words — they're the point you're making, not a script to recite.*

**Before you start:** open the site in a private/incognito window (avoids cached versions), have this page open on your phone or a second screen, and know that the analyst runs entirely in the browser — there's nothing to log into and nothing that can fail to connect.

> **Maintainer note:** the analyst's wording changes whenever `ask-engine.js` changes, and the numbers change every Monday when the data refreshes. The **structure** below (which sections appear, in what order) is locked by the eval suite, so it stays true — but before presenting, run the prompts once yourself and glance at the quoted numbers. If one has moved, say the new number; nothing else in the script depends on it.

---

## Opening (30 seconds)

**Say:** "This is the Atlas. It answers one question for communications staff: *where and how do we reach people in any country* — and it shows its evidence for every number. It covers all 195 countries, it updates itself daily, and it costs nothing to run."

**Do:** Land on the map. Let it sit for a moment — the map is the credibility opener. Click any country (try **Kenya**) so a profile slides in. Point at the tabs: Overview, Economy, Media, Society, Sources.

**Say:** "Every figure has a named source with a link. Nothing here is estimated by us."

**Do:** Click the **Sources** tab so they see the citation list.

---

## 1. The headline capability — a full strategy brief (2 minutes)

**Do:** Click **AI Analyst** in the top navigation. Type exactly:

```
Distribution strategy for vaccination content in Nigeria
```

**Say while it renders:** "This is what the team asked for last month — not just data, but a recommendation."

A single-country brief always comes back in the same nine parts, in this order: a *Decision being addressed* line, then **Executive summary · Key insights · Strategic assessment · Opportunities — ranked · Tradeoffs · Risks · Confidence and limits · Evidence used**, closing with an *Advisory* disclaimer. (Ask for a whole region and you get the same brief without Tradeoffs — that section needs one country's figures.) The consistency is deliberate: a supervisor reading two briefs never has to hunt for the caveats.

**Then walk them through the four things that matter:**

**① It names the decision, then leads with the answer.** Point at the italic line under the title — *"Decision being addressed: driving behaviour change"* — then at the three numbered lines under **Executive summary**.
> *"It doesn't hand you a data dump and make you find the recommendation. It tells you the decision it thinks you're making, gives you three moves, and puts a confidence level on them in the first ten lines."*

**② The finding that justifies the whole project.** Point at the first bullet under **Key insights**, and at the channel table in **Strategic assessment**:
> *"Look at this. Online news measures 94% in Nigeria — so the obvious call is a digital campaign. But the Atlas catches that internet penetration is only 41%. That 94% is 94% **of the people who are already online**, so the table shows online news and social media capped at 41% — 'capped at internet access', in its own words — and radio, at 65%, becomes the lead channel for national reach."*
>
> *"That's a campaign that would have missed most of Nigeria, caught by the data."*

**③ Every claim is labelled measured or inferred.** Point at the `[measured]` and `[inferred]` tags running down the brief.
> *"Every line tells you whether it rests on a survey figure or on the system's own reasoning. The reach numbers are measured. 'Behaviour change needs repeated exposure through trusted voices' is inferred, and says so. And under **Confidence and limits** it lists what it can't tell you at any confidence level — past campaign performance, whether video beats text, age and gender breakdowns, cost per channel. No free source measures those, so it won't pretend."*

**④ Language.** Point at the second **Executive summary** line and its matching entry under **Opportunities — ranked**.
> *"'Produce in English first — 53% of the population, and official.' Language shares come from Unicode's territory-language data, so the recommendation is sourced, not assumed."*

**Do:** Point at the numbered **Sources** list under the answer — it is always visible, no click needed.

**Say:** "Every brief carries its receipts, on screen, every time."

---

## 2. Prove it isn't guessing (45 seconds)

*This is the most important 45 seconds of the demo. Credibility comes from what a tool refuses to do.*

**Do:** Type exactly:

```
What did our last campaign achieve?
```

It answers: **"The Atlas holds no campaign archive."** — then explains what it *can* describe instead and asks for a country.

**Say:** "It has no campaign archive, and it says so plainly instead of inventing a plausible answer. There are ten question types it's built to decline this way — past campaign results, format performance, age and gender breakdowns, seasonal timing, and six more. Each one names what's missing and offers the closest real evidence instead."

---

## 3. Choosing *where* to run it — Market Finder (1 minute)

**Do:** Click **Market Finder** in the top navigation. Set **Campaign goal** to *Drive behaviour change*, **Channel** to *Radio*, **Region** to *Africa*. Press **Find markets**.

**Say:** "The brief answers 'how do we run this in Nigeria'. This answers the question before it: *which countries should get this campaign at all?*"

**Point at three things, in this order:**

- **The method line above the table** — the weights are printed before the results. "Nothing is hidden in a black box; you can see exactly what it optimised for."
- **The 'Excluded' panel below the table** — expand it. "Twelve African countries aren't in this ranking because no media survey covers them at all. It names every one of them, with the reason, rather than quietly ranking them last. A country with no data is not a country that scored badly."
- **The Notes column** — Uganda ranks around #9 on radio reach and carries **⚠ Not Free — vet partner outlets individually**.
> *"When a high-reach market has a restricted press environment, it doesn't drop the country and it doesn't stay quiet — it ranks it and warns you to vet partners individually. That's a judgement call we want a human making, with the flag in front of them."*

*(The same screening is available in plain English from the analyst — "Which countries should we prioritize for a radio vaccination campaign?" returns the ranked table plus a **"Not rankable (111 countries)"** line that breaks the excluded countries down by reason. Use whichever fits the room; don't demo both.)*

---

## 4. Speed round — the range (1.5 minutes)

*Back in the **AI Analyst**. Type these back to back. Don't over-explain; the pace is the point.*

```
Compare news trust in France and Germany
```
> *"Side-by-side comparison, any countries, any measure — and it flags where low trust changes the strategy."*

```
Top 5 African countries by radio reliance
```
> *"Rankings across all 195 countries — and note the line underneath: it says how many countries it had to leave out for lack of data."*

```
whats trending in nigerai
```
> *"Note the typos — I typed that wrong on purpose. It handles real typing, and this is live attention data, refreshed every morning."*

```
Which countries have state-controlled media environments?
```
> *"It understands what you mean, not just keywords — that's a press-freedom ranking, worst first."*

---

## 5. Close — why it survives (45 seconds)

**Say:** "Three things worth knowing about how this runs:

**It maintains itself.** Trends refresh daily, country indicators weekly, and once a month a watchdog checks whether the big annual reports — Reporters Without Borders, Freedom House, Reuters — have published new editions. When they do, it files a reminder with step-by-step instructions. Nothing silently goes stale. And since July, refreshed data has to pass an automatic validation check before it can reach the site — if an upstream source returns something wrong, nothing is published and the site keeps serving the last good data.

**It costs zero.** Free public data, free hosting, free automation, and the analyst runs in the visitor's browser. There's no subscription that can lapse and no server to maintain.

**It's been tested.** We ran it against 100 realistic questions written by the team — the acceptance test in the design document. It passes 82, and critically, zero of the failures give a wrong answer. The remaining gaps are all cases where it's more cautious than it needs to be. Two further suites guard it — 18 strategy briefs checked for structure, and 73 checks on the market screener, including one that fails if a restricted-press market ever loses its partner-vetting warning. And since late July these checks run **automatically on every single change** — a commit that breaks any of them gets a red ✗ on GitHub and files an alert, so a broken analyst can't reach this site quietly."

---

## Likely questions — and honest answers

**"How accurate is this?"**
> Every figure comes from a named institutional source — World Bank, Reuters Institute, Freedom House, Afrobarometer, the World Values Survey, Eurobarometer, UN DESA. The Atlas doesn't generate numbers, it aggregates and cites them. Where a survey has known limits, like the Reuters panel being urban and online in some countries, the answer says so.

**"Why do some countries have no media data at all?"**
> Because no free survey measures them. 126 of the 195 countries have a real news-consumption survey behind them; the other 69 have none, and we show that rather than filling the gap with an estimate. A set of estimates *was* removed from this project in July for exactly that reason, and the pipeline now blocks any number whose source isn't on an approved list.

**"Didn't the Topic Explorer show more topics before?"** *(or: "why did a number go down?")*
> Yes — and that's a fix, not a loss. In July we found the daily attention feed had been quietly serving stale data for some topics while displaying them as current. The page now measures freshness by date, scores only topics with genuinely current data, and says on screen how many it set aside that day. Some headline numbers went down because the old ones were wrong; every number that remains is one we can stand behind. That's the trade this whole project makes, everywhere: smaller and true beats bigger and unverifiable.

**"Can it replace agency research?"**
> No, and it says so in every brief. It's the first 80% — the landscape evidence you'd otherwise spend two weeks assembling — so that human expertise goes into judgment, not data-gathering.

**"What happens when Shakti leaves?"**
> The automation is self-maintaining and self-monitoring. The documentation is written for non-coders. The one recurring human job is integrating the annual reports when the watchdog flags them, which is a documented, step-by-step task — and the biggest of them, the press-freedom index, is now a single command.

**"Can it do [X] that it just refused?"**
> Usually the honest answer is that no free source measures it. Where a paid source exists, that's a budget conversation. Where a free source exists that we haven't integrated, there's a documented list of vetted candidates in `docs/DATA_SOURCES.md` §4.

**"Can we add more countries / topics?"**
> All 195 UN countries are already covered. Topics are a tracked list of 167 — adding more is a small, documented change.

---

## If something goes wrong live

- **Page looks stale or odd:** hard-refresh (⌘⇧R). It's almost always browser cache.
- **A number doesn't match this script:** say the number on screen. The data refreshes weekly; the script is a guide, not the source of truth.
- **An answer looks thin:** say so out loud and move on — *"that's one of the gaps we've documented"* is a stronger look than pretending. The tool's honesty is the pitch.
- **No internet:** the screenshots in your slides still make every point above. The map, a strategy brief, and a Market Finder ranking with its Excluded panel open are the three images worth having on hand.
