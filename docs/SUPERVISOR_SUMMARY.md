# Audience Intelligence Atlas — Plain-Language Summary

*One page, no technical background needed. Updated 27 July 2026.*

## What we have today

An interactive world atlas covering **all 195 countries**, showing how people in each country consume media: which platforms they use (including radio and TV, not just social media), which news sources they trust, how free the press is, how connected the population is — and now also **which languages actually reach each population** and **what each country is paying attention to this week**.

Every number is traceable to a reputable source — the World Bank, Reporters Without Borders, Freedom House, the Reuters Institute at Oxford, and six public-opinion survey programmes (Afrobarometer, the World Values Survey, Eurobarometer, Arab Barometer, Asian Barometer, Latinobarómetro), plus UN DESA and Unicode's language data. Each figure carries a named, clickable citation. Two inputs are estimates rather than measurements — advertising-market forecasts from WPP Media and Dentsu, and DataReportal's smartphone-adoption figures — and both are recorded as estimates in the source registry.

**Where we have measured survey data, and where we don't.** 126 of the 195 countries have a real news-consumption survey behind their figures. The other 69 have none, and the site says so by name rather than filling the gap with an estimate — a set of estimates was removed in July for exactly that reason, and the pipeline now blocks any figure whose source is not on an approved list.

## The AI analyst is live — and it costs nothing

The **"AI Analyst"** page (renamed from "Ask the Analyst", July 2026) now answers any plain-English question directly in the visitor's browser:

> *"Where should we publish climate content targeting youth in East Africa?"*
> *"Which country trusts the news most?"* · *"Top 5 African countries by radio"* · *"Compare France and Germany"*

It understands typos and casual phrasing, asks a clarifying question when the request is vague, suggests follow-up questions after each answer, and shows a numbered **source list** under every response linking to the original data. When the data can't support an answer, it says so instead of guessing — credibility is the entire point.

**Strategy briefs (July 2026, at DGC request).** Ask for a distribution strategy — *"How should we distribute vaccination content in Pakistan?"* — and the analyst produces a consulting-style brief in a fixed structure: it names **the decision being addressed**, then gives an **executive summary** (three moves and a confidence level), **key insights**, a **strategic assessment** comparing every channel on the reach it can actually deliver, **ranked opportunities** that each justify themselves, **tradeoffs**, **risks**, **confidence and limits** — including a plain list of what it cannot tell you at any confidence level — and the **evidence used**. Every claim is tagged *measured* or *inferred* so nothing reads as fact that isn't, and every brief closes with an advisory reminder: it is evidence-based decision support, not a final plan.

**Market Finder (July 2026).** A fourth page answers the question *before* the brief: describe a campaign — goal, audience, language, region, channel — and it screens every country with verified media data and ranks the best-fit markets. The weights are printed above the results, and every country it could not rank is listed by name with the reason, so a country with no data is never mistaken for a country that scored badly. Markets with restricted press environments stay in the ranking but carry a warning to vet partner outlets individually.

Because it runs in the browser rather than on a server, there is **no subscription, no account, and nothing that can be switched off by a lapsed contract**. (An optional free upgrade adds AI-polished prose via Cloudflare's no-cost tier — documented, not required.)

## How it stays current — automatically

| How often | What happens |
|---|---|
| **Daily** | Live attention trends refresh for 183 UN-relevant topics across 22 languages (Wikipedia reading patterns + the GDELT global news monitor) |
| **Weekly** | All World Bank country indicators refresh, now including financial-account ownership (digital-inclusion signal), per-country language shares, and measured social-platform web-traffic shares |
| **Monthly** | A watchdog checks whether any of the eight annual sources — RSF, Freedom House (×2), Reuters, GSMA, Afrobarometer, UN DESA, or the advertising-market forecasts — has published a new edition, and files a reminder with step-by-step instructions when it has |
| **Every refresh** | Refreshed data must pass an automatic quality check before it can reach the site. If a source returns something implausible, uncited, or from a source not on the approved list, nothing is published and an alert is filed |
| **Always** | If any automated run fails, the system files an alert by itself; the site keeps serving the last good data meanwhile |

## What it costs

**US$0.** The data (free public sources), the hosting (GitHub Pages), the automation (GitHub Actions), and the AI analyst (in-browser) are all free. There are no servers to maintain and nothing to renew.

## What it will NOT do

- It will not collect any personal data — all information is country-level and from public, licensed sources. (The analyst keeps a log of the questions asked so recurring gaps can be reviewed, but that log never leaves the visitor's own browser; nothing is uploaded anywhere.)
- It will not guess. Where data is missing, it says so explicitly.
- It will not require technical staff to keep running. The automation is self-sustaining and monitors itself; full handover documentation is part of the delivery.

## Milestones

| Status | Milestone |
|---|---|
| ✅ done | Daily topic-trend tracking · per-country trending intelligence · the AI analyst · Topic Explorer · Market Finder · accessibility & quality audit (162 findings reviewed) |
| ✅ done | **Testing against 100 realistic UN staff questions.** Closed 20 July 2026: 82 of 100 fully satisfactory and **zero wrong answers**. The 18 shortfalls are all cases where the analyst was more cautious than it needed to be — none misinforms. Two further automated test suites now guard the strategy briefs and the Market Finder |
| ✅ done | **Measured survey data replacing estimates.** Five survey programmes integrated from source microdata in July, and the earlier compiled estimates removed rather than kept |
| Remaining | Final handover documentation · live demonstration |
