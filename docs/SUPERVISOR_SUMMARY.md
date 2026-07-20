# Global Content Intelligence Platform — Plain-Language Summary

*One page, no technical background needed. Updated 20 July 2026.*

## What we have today

An interactive world atlas covering **all 195 countries**, showing how people in each country consume media: which platforms they use (including radio and TV, not just social media), which news sources they trust, how free the press is, how connected the population is — and now also **which languages actually reach each population** and **what each country is paying attention to this week**.

Every number is traceable to a reputable source — the World Bank, Reporters Without Borders, Freedom House, the Reuters Institute at Oxford, the Afrobarometer research network, UN DESA, and Unicode's language data. Each figure carries a named, clickable citation.

## The AI analyst is live — and it costs nothing

The **"Ask the Analyst"** page now answers any plain-English question directly in the visitor's browser:

> *"Where should we publish climate content targeting youth in East Africa?"*
> *"Which country trusts the news most?"* · *"Top 5 African countries by radio"* · *"Compare France and Germany"*

It understands typos and casual phrasing, asks a clarifying question when the request is vague, suggests follow-up questions after each answer, and shows a **"View sources"** list under every response linking to the original data. When the data can't support an answer, it says so instead of guessing — credibility is the entire point.

Because it runs in the browser rather than on a server, there is **no subscription, no account, and nothing that can be switched off by a lapsed contract**. (An optional free upgrade adds AI-polished prose via Cloudflare's no-cost tier — documented, not required.)

## How it stays current — automatically

| How often | What happens |
|---|---|
| **Daily** | Live attention trends refresh for 167 UN-relevant topics across 22 languages (Wikipedia reading patterns + the GDELT global news monitor) |
| **Weekly** | All World Bank country indicators refresh, now including financial-account ownership (digital-inclusion signal) and per-country language shares |
| **Monthly** | A watchdog checks whether RSF, Freedom House, Reuters, GSMA, Afrobarometer, or UN DESA have published a new annual edition — and files a reminder with step-by-step instructions when they have |
| **Always** | If any automated run fails, the system files an alert by itself; the site keeps serving the last good data meanwhile |

## What it costs

**US$0.** The data (free public sources), the hosting (GitHub Pages), the automation (GitHub Actions), and the AI analyst (in-browser) are all free. There are no servers to maintain and nothing to renew.

## What it will NOT do

- It will not collect any personal data — all information is country-level and from public, licensed sources.
- It will not guess. Where data is missing, it says so explicitly.
- It will not require technical staff to keep running. The automation is self-sustaining and monitors itself; full handover documentation is part of the delivery.

## Remaining milestones

| Weeks | Milestone |
|---|---|
| ✅ done | Daily topic-trend tracking · per-country trending intelligence · the AI analyst · Topic Explorer · accessibility & quality audit (162 findings reviewed) |
| 10–11 | Testing against 100 realistic UN staff questions + final documentation |
| 12 | Live demonstration |
