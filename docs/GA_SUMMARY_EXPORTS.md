# Pulling the summary reports — step by step

*The approved scope is **summaries, not full data** (Fang Chen, 2026-07-30 —
recorded in [GA_DATA_REQUEST.md](GA_DATA_REQUEST.md) Part 0). Everything in
this file stays inside that scope: these are Google Analytics' own aggregate
reports, exported as CSV. Nothing here touches raw events, BigQuery, or
anything user-level.*

*Written for someone who has never used the Explore tool. If a step doesn't
match what's on screen, the interface has moved — the important part is the
combination of dimensions and metrics, not the exact menu path.*

---

## The tool to use: Explore → Free form

Google Analytics' standard reports are fine to read but awkward to export in
the shape we need. **Explore** builds a plain table of exactly the rows and
columns you choose, and exports it as CSV in two clicks.

To get there: **Explore** in the left sidebar → **Free form** (the first
template) → a blank table appears with a settings column on the left.

The pattern is always the same:

1. **Set the date range** at the top of the settings panel. Use the longest
   the property allows — 24 months if it's there. If a long range errors or
   takes forever, fall back to 12 months.
2. **Dimensions** — click the `+` next to *DIMENSIONS*, search for the ones
   listed below, tick them, click **Apply**. Then drag each into the **Rows**
   box.
3. **Metrics** — same with the `+` next to *METRICS*, then drag into the
   **Values** box.
4. **Row limit** — near the bottom of the settings panel. Raise it to the
   maximum (usually 500 or 1000); the default of 10 silently truncates.
5. **Export** — the download icon at the top right of the table →
   **Export CSV** (not PDF, not Google Sheets).
6. **Save the file** with the name given below, all in one folder.

---

## Report 1 — Users by country by month  ⭐ start here

This is the one that matters most. Country is the key that joins Analytics to
all 195 country records in the Atlas; without it nothing else can be used.

| | |
|---|---|
| **Rows** | Country, **Year**, **Month** *(three separate dimensions)* |
| **Values** | Total users, Sessions, Views, Average engagement time per session |
| **Save as** | `ga_country_month.csv` |

If only one report ever gets pulled, make it this one.

**Why Year AND Month, both:** the plain "Month" dimension alone exports as
`01`–`12` with no year attached, so a 24-month range folds January 2025 and
January 2026 into one row. Seasonality survives that; year-over-year growth
does not. There is a combined "Year month" dimension in GA4, but it doesn't
reliably show up in the picker — rather than hunt for it, just add "Year" and
"Month" as two ordinary dimensions alongside Country. Same result. (The
2026-08-03 export used plain Month only — fine for a first look, worth
redoing with Year added.)

---

## Report 2 — Country by device

Joins to the Atlas's smartphone-adoption and mobile-connectivity figures.
Mobile share is the strongest available signal for how content should be
formatted in a given market.

| | |
|---|---|
| **Rows** | Country, Device category |
| **Values** | Total users, Sessions, Average engagement time per session |
| **Save as** | `ga_country_device.csv` |

---

## Report 3 — Country by how people arrived

Shows which channels actually deliver UN audiences per country — the real
test of the Atlas's platform recommendations.

| | |
|---|---|
| **Rows** | Country, Session default channel group |
| **Values** | Total users, Sessions, Engaged sessions |
| **Save as** | `ga_country_channel.csv` |

If **Session source / medium** is easy to add as a third dimension, it is
worth having; if it makes the table unwieldy, skip it.

---

## Report 4 — Country by language edition ⭐ the interesting one

**Not the "Language" dimension.** That reports the visitor's *device* setting
and systematically over-reports English (see GA_DATA_REQUEST.md Part 5.1).
What we want is which *language version of the page* people actually opened,
which lives in the page path — `/ar/`, `/fr/`, `/es/` or similar.

**⚠ Two settings here are load-bearing — the 2026-08-03 export taught us
this the hard way.** Without them, the CSV filled its entire 100,000-row
budget on the alphabetically-first country ("(not set)") and its endless
`?utm=` URL variants, and contained no real countries at all:

1. Use **"Landing page"** — the plain one, *not* "Landing page + query
   string". Query strings multiply every URL into hundreds of rows.
2. Before exporting, **click the "Total users" column header so the table
   sorts descending** (biggest first). The export keeps the on-screen order;
   sorted this way, the 100k rows carry nearly all the traffic instead of
   nearly none of it.

| | |
|---|---|
| **Rows** | Country, Landing page *(no query string)* |
| **Values** | Total users, Views |
| **Sort** | Total users, descending — click the column header |
| **Save as** | `ga_country_pagepath.csv` |

The paths get aggregated into language editions locally — no need to tidy
this by hand. If UN News turns out to use separate hostnames per language
rather than path prefixes, add **Hostname** as a dimension instead and say so
in the notes.

**Worth pulling the device "Language" dimension too**, in its own small
report (`ga_language_dimension.csv`, rows: Country + Language, values: Total
users) — not to use as a language signal, but to demonstrate the gap between
device locale and actual language-edition use. That comparison is a genuinely
interesting finding for the team and costs one extra export.

---

## Report 5 — What content performs where

| | |
|---|---|
| **Rows** | Country, Page title (or Content group, if the property has them) |
| **Values** | Views, Total users, Average engagement time per session |
| **Sort** | Views, descending — click the column header (same reason as Report 4) |
| **Save as** | `ga_country_content.csv` |

Row limit matters here — raise it as high as the tool allows, and the
descending sort is what makes the capped export carry the traffic that
matters rather than an alphabetical sliver.

---

## Report 6 — New vs returning

Distinguishes building reach from holding an audience. Different strategic
problems, different recommendations.

| | |
|---|---|
| **Rows** | Country, New / returning |
| **Values** | Total users, Sessions, Average engagement time per session |
| **Save as** | `ga_country_newreturning.csv` |

---

## Two things to note while exporting

**Sampling.** If the table header shows anything other than 100% of data (a
small icon or a "based on N% of sessions" note), write that down — it changes
how much weight a number can carry. Shortening the date range usually removes
sampling.

**"(other)" rows.** When a table hits its cardinality limit, Analytics dumps
the long tail into a single `(other)` row. If that row is large, the smaller
countries — exactly the ones the Atlas has least data on — are hiding inside
it. Raising the row limit and narrowing the date range both help.

---

## Where to put the files

Save all of them in **one folder anywhere on the Mac except inside the
project folder** — for example `~/Documents/UN Analytics Exports/`.

**Not inside `~/Desktop/UN Project/`.** That folder is a public GitHub
repository, and a stray `git add -A` would publish whatever is sitting in it.
The project's `.gitignore` will also be set to refuse these filenames as a
second line of defence, but the simplest protection is keeping them outside
the folder entirely.

Then say where the folder is, and the aggregation gets built from the real
column shapes rather than guessed ones. The Atlas ingests only the computed
country-level summary; the CSVs themselves stay put.

---

## If the exports turn out to be limited

Entirely possible — properties differ, and permissions may not cover every
report. That is useful information, not a failure. Worth noting for the
report back to the team:

- which reports were available and which were not;
- whether demographics (age/gender) appear at all, or are suppressed;
- how far back the date range actually goes;
- whether any table showed sampling.

Those four answers determine what the Atlas can honestly build on, and they
are the substance of "seeing how it works" — which is exactly what Fang
asked for.

---

## Addendum 2026-08-04 — first published summary: `data/ga_summary.json`

The first real pull is done and published. What happened, for the record:

- **Method:** aggregate reports were pulled through the GA Data API
  (API-assisted equivalents of the six Explore reports above — identical
  aggregation level: country/device/channel/page totals, nothing raw,
  nothing event- or user-level, no BigQuery). No sampling was reported on
  any request.
- **Windows:** 28 days 2026-07-07 → 2026-08-03 (vs the prior 28 days), plus
  14-day trend windows for the top-pages momentum comparison.
- **Properties:** UN News — English (247887035) and UN News — All languages
  (247862254), starting English-first per the current project scope.
- **What was published:** `data/ga_summary.json` — a summaries-only file
  (top-30 country aggregates, device/channel/source shares, top-40 page
  titles per window, browser-locale counts, documented caveats).
  `scripts/validate_atlas.py` now gates it: `_meta` provenance and the
  summaries-only scope line are mandatory, raw/event-level field names are
  hard errors, and top-pages lists are capped at a top-N.
- **What reads it:** the Map ("UN News analytics" modal + per-country
  "UN News readership"), the Topic Explorer ("What UN News readers opened"),
  the Market Finder (proven-audience note, deliberately unscored), and the
  AI Analyst ("Top 5 trending topics report", "Where should we focus
  dissemination?"). Every surface carries the arrivals-not-reach caveat.
- **Known data-quality flags** (recorded in `_meta.caveats`): China's
  English-edition row is bot/VPN-like (8.4% engagement, views < users);
  54% of sessions are unattributed ("Unassigned" channel); Netherlands and
  Singapore look datacenter-inflated; one story excluded as anomalous
  (7.1 views/user).
- **To refresh:** re-run the same aggregate pull for a new window and
  regenerate `data/ga_summary.json` in the same shape (the `_meta.window`
  dates and `retrieved_on` must move with it), then run
  `python3 scripts/validate_atlas.py` before committing. If the file is
  absent the site degrades gracefully — every GA block simply disappears.
