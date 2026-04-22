# UN Media Consumption Map — Project Plan

**Owner:** Shakti (UN intern) · **Handover target:** ~August 2026 · **Today:** 2026-04-22

---

## 1. What we're building, in plain English

A single public website with a clickable world map. Click a country (or a whole continent) and a side panel opens showing:

- **Who lives there** (population, age breakdown, urban/rural split, languages, literacy, internet penetration).
- **What media they use** (TV, radio, print, social media, streaming, podcasts — share of adults using each).
- **How much time** they spend on each medium per day.
- **What they consume** (news, entertainment, sports, education, religious content, etc.) and on which platforms.
- **Topics of interest** (politics, climate, health, business, culture…).
- **Trust levels** in different media types.
- **Device mix** (mobile vs. desktop vs. TV set vs. radio set).
- **Press-freedom / information-environment** indicators (RSF index, Freedom House).
- **Source list** with a clickable citation for every number on the page.
- **"Last updated" stamp** on every data point.

Under the hood, the data is stored in simple spreadsheet-like files. A scheduled robot job refreshes those files from official sources on a regular cadence. A separate pipeline ingests responses from a public Google Form survey and merges them in as a distinct "community-sourced" layer (kept visually separate from official stats so credibility is never muddied).

## 2. The tech stack I recommend (and why)

| Piece | Tool | Why this one |
|---|---|---|
| Website hosting | **GitHub Pages** (free) | Free, reliable, simple for UN staff to inherit. No server to maintain. |
| Code storage | **GitHub repository** | Standard. Works hand-in-glove with GitHub Copilot, which you said the UN uses. |
| Map library | **Leaflet + Natural Earth country shapes** | The most widely-used free map library in the world. Huge community, easy to learn. |
| Styling | Plain HTML + CSS (UN color palette: #009EDB blue, #FFFFFF, #333333) | No framework overhead — any future maintainer can read it. |
| Data files | CSV + JSON | Human-readable. Can be opened in Excel. |
| Auto-updates | **GitHub Actions** (scheduled workflow) | Free robot job built into GitHub. Runs on a cron schedule. |
| Survey | **Google Forms → Google Sheets → exported CSV** | You already know Forms. Sheets gives a clean API. |
| Analytics (privacy-safe) | **Plausible** or **Umami** (or skip) | GDPR-safe, no cookies, aggregate stats only. |
| Domain | free `*.github.io` initially, optional custom domain later | UN can bring their own domain at handover. |

**What we are NOT using, and why:**
- No database server (adds maintenance burden after handover).
- No paid services (UN procurement friction).
- No React/Next.js/Vue (harder for a non-coder to maintain).
- No npm/build step if we can avoid it (keeps it copy-paste simple).

## 3. The phases

Each phase ends with a **live clickable prototype you can show people**, even if incomplete.

### Phase 0 — Foundations & decisions (Week 1)
**Goal:** Nail down scope and get the plumbing ready before writing anything real.
- Confirm tech choices above.
- Create the GitHub account/repo and GitHub Pages site.
- Decide on: ~10 starter countries to cover deeply first (suggest: US, UK, Brazil, Nigeria, Kenya, India, China, Indonesia, Germany, Mexico — covers all regions).
- Draft the exhaustive **data schema** (every column we want, with source attached) — see appendix.
- Decide on **citation standard** (every cell in the dataset links to one source URL + retrieved-on date).
- Decide on **ethics approach for the survey** (consent language, anonymity, data retention) — critical before we collect anything.

**Prototype at end of phase:** a placeholder page at a real public URL that says "Coming soon" with the UN color scheme. Proves hosting works.

### Phase 1 — Minimal clickable map (Weeks 2–3)
**Goal:** A working world map where clicking any country shows a side panel with *real data* for the 10 starter countries, and "data pending" for the rest.
- Build the map.
- Load country boundaries.
- Build the side panel component.
- Hand-enter the starter data from verified sources (Reuters Institute Digital News Report, ITU, DataReportal, UNESCO, World Bank, Pew).
- Wire every data point to its citation.

**Prototype:** live URL. You click a country, panel opens, data shows, citations work.

### Phase 2 — Full coverage + polish (Weeks 4–6)
**Goal:** All ~195 countries covered with at least the core indicators; continent-level roll-ups; responsive on mobile; accessibility (screen-reader and keyboard friendly — UN accessibility guidelines are strict).
- Fill in remaining country data (we'll do this in batches, with a spreadsheet-style workflow you can edit directly).
- Add continent aggregation view.
- Add search bar, filters (e.g., "show countries where social media is the #1 medium").
- Add a methodology / sources page.
- Add About / UN branding page.
- Accessibility audit (WCAG 2.1 AA).

**Prototype:** a production-grade site you could realistically share publicly.

### Phase 3 — Survey pipeline (Weeks 7–8)
**Goal:** Public survey live, responses flowing into the site as a clearly-labeled secondary layer.
- Design the Google Form (demographic + consumption questions; consent language; under 5 minutes to complete).
- Pilot it with ~20 people in your network; revise.
- Build the pipeline from Google Sheets → the website's "community data" layer (separated visually from official stats).
- Add a "Take the survey" CTA on the site.
- **Flag:** automated mass-dissemination across countries is out-of-scope by default (explanation below). We'll instead build a shareable link + embed-on-other-sites kit and a handover doc for the UN's communications team to drive distribution through legitimate channels.

**Prototype:** survey live, first responses visible in a "Community insights" section.

### Phase 4 — Automation (Weeks 9–11)
**Goal:** The site updates itself without you.
- Scheduled GitHub Actions job that:
  - Pulls refreshed data from any source with a public API or downloadable file (World Bank, ITU, Our World in Data, etc.).
  - Re-runs survey ingestion.
  - Regenerates the site.
  - Emails you if something fails.
- Dashboard page showing "last refreshed" per source.
- Realistic cadence: **most official data updates annually or quarterly**, not daily — we'll refresh *checks* daily but actual data will only change when the source publishes new numbers. I'll explain this more below.

**Prototype:** a self-updating site. You stop touching it; it keeps working.

### Phase 5 — QA, docs, handover (Weeks 12–16)
**Goal:** A UN staffer who has never seen this project can take it over in an afternoon.
- Full test pass on all browsers + mobile.
- Write a **handover manual** in plain English: "How to add a country", "How to fix a broken source", "How to change the survey", "Who to call if X breaks".
- Record 3–5 short screen-recording walkthroughs.
- Security review (no exposed API keys, no PII leaks from survey).
- Written Copilot "prompt cheat-sheet" for common maintenance tasks.
- Formal handover meeting.

**Prototype:** the finished product + documentation package.

---

## 4. Things I want to push back on honestly

You asked for these — I'd be doing you a disservice not to flag where they're harder than they sound:

1. **"Daily automatic updates"** — most authoritative media-consumption data (Reuters Institute, Pew, ITU) publishes **once a year**. Some (World Bank indicators) publish annually or quarterly. The automation will *check* frequently, but the actual numbers won't change daily. I recommend being transparent about this on the site (show each data point's last-refresh date) — credibility beats apparent freshness.

2. **"Automated survey dissemination to as many people in different countries as possible"** — this is the riskiest item on your list. Automated mass outreach runs into: GDPR (Europe), CAN-SPAM (US), PIPEDA (Canada), and similar laws elsewhere; ethical review requirements for research on human subjects; risk of being flagged as spam (which would hurt UN credibility irreversibly). **I strongly recommend** we instead build excellent shareable assets (a clean URL, social cards, embeddable widgets, a press kit) and let the UN's actual communications channels do the distribution. I can help you draft a distribution plan for them. If you still want automated outreach after hearing that, we should bring in a research-ethics reviewer before building anything.

3. **"Comprehensive database"** — the data you want (age × medium × topic × country) does not exist in a single clean source anywhere in the world. We will be **combining** several sources per country, and some cells will be genuinely unknown. Being honest about gaps ("no reliable data") is more credible than filling them with estimates. I'll design the schema to make gaps visible rather than hidden.

4. **"Evolving, continuously updates itself"** — achievable for ~60% of the data (anything with a public API). The rest (PDF reports from Reuters Institute, etc.) requires a human to re-enter once a year when the new report drops. I'll make that a 10-minute job with a clear checklist.

## 5. Data sources I plan to use (all vetted, free)

**Tier 1 — Institutional:**
- ITU (International Telecommunication Union) — internet/mobile penetration
- UNESCO Institute for Statistics — literacy, media education
- World Bank Open Data — demographics, GDP, infrastructure
- UN Data Portal — cross-cutting indicators
- UNDP Human Development Reports
- WHO — health information sources (for health-topic consumption)

**Tier 2 — Reputable research organizations:**
- Reuters Institute Digital News Report (Oxford) — *the* gold standard for news consumption, 47+ countries
- Pew Research Center — especially strong for US + comparative studies
- DataReportal / "Digital XXXX" annual country reports — Kepios-authored, widely cited
- GSMA Intelligence — mobile ecosystem
- Afrobarometer, Latinobarómetro, Asianbarometer, Eurobarometer, Arab Barometer — regional public-opinion surveys
- Reporters Without Borders (RSF) — Press Freedom Index
- Freedom House — Freedom of the Press

**Tier 3 — Aggregators (used with care, always tracing back to primary):**
- Our World in Data
- Statista (limited free access)

Every datapoint on the site will link back to its Tier-1/2 primary source with a retrieval date.

## 6. What I need from you before we start

1. **Go/no-go on the tech stack** in section 2. Anything you want changed?
2. **The 10 starter countries** — the list I suggested or your own?
3. **A GitHub account.** Free. I'll walk you through creating one. It's where everything lives.
4. **Your stance on the survey automation pushback** in section 4 — are you comfortable with my recommendation, or do you want to push for the fuller automated-outreach version?
5. **Anything from the UN side** — do they have a preferred domain name, brand guidelines document, or existing data platform we should integrate with?

Once you give me the green light on these five, I'll kick off Phase 0 and show you a live "Coming Soon" page with the UN color scheme within a day.

---

## Appendix A — Draft data schema

For each country, we'll track (with a source + retrieval-date stamp on each):

**Demographics**
- Population (total, by broad age band 0–14/15–24/25–54/55–64/65+)
- Urban / rural split
- Top languages spoken
- Literacy rate
- GDP per capita (for context)

**Infrastructure**
- Internet penetration (% of population)
- Mobile subscriptions per 100 people
- Smartphone adoption rate
- Fixed broadband penetration
- Electricity access (matters for TV/radio reach)

**Media usage — reach (% of adults using at least weekly)**
- Television
- Radio
- Printed newspapers/magazines
- Online news sites
- Social media (with a breakdown by major platform where available)
- Streaming video (Netflix-class, YouTube, regional equivalents)
- Podcasts
- Messaging apps (WhatsApp, Telegram, etc.) as news source

**Media usage — time spent (avg minutes/day where reliably measured)**

**Content preferences — share of media time spent on:**
- News & current affairs
- Entertainment (film/TV/music)
- Sports
- Education / learning
- Religious content
- Business / finance
- Lifestyle

**Topic interests (Reuters Institute categories):**
- Politics, International news, Local news, Climate/environment, Health, Business/economy, Science/tech, Arts/culture, Sports, Lifestyle

**Trust & information environment:**
- Overall trust in news (Reuters Institute score)
- Trust by medium (TV vs. social vs. print)
- RSF Press Freedom score + rank
- Freedom House "Freedom of the Press" score

**Device mix (% of media consumption happening on):**
- Mobile phone
- Desktop/laptop
- TV set
- Radio set
- Print

**Meta (per row):**
- Last updated date
- Primary source URL
- Secondary source URL
- Confidence level (high / medium / low / estimated)

## Appendix B — Project risks, ranked

1. **Data gaps** — some countries have almost no reliable media-consumption data. Mitigation: show "no data" transparently; list known gaps in the methodology page.
2. **Survey ethical review** — UN may require formal research-ethics approval before launching a public survey under its brand. Mitigation: assume yes and draft consent/data-handling docs early; ask UN supervisor.
3. **Source-site breakage** — if the World Bank changes a URL, our auto-update breaks. Mitigation: monitoring + email alert + every source has a manual fallback.
4. **Handover bus-factor** — if the receiving UN team has no one available, the site will rot. Mitigation: written docs + video walkthroughs + the tech stack is standard enough that any web dev can pick it up.
5. **Scope creep** — the temptation to add features is enormous. Mitigation: this plan is the contract; anything else goes to a "Phase 6+" backlog.
