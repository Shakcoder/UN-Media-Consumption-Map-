# How the automation works — in plain English

The Global Media Consumption Atlas refreshes itself on a schedule. You don't have to do anything to make it run. This document explains what's happening under the hood, so that a maintainer handing over the project can understand and, if needed, adjust it.

---

## The one-paragraph version

Every Monday at 3 AM UTC, GitHub runs a small Python script that talks to the World Bank's free data API and pulls the latest numbers for each country in our atlas — population, GDP per capita, internet penetration, literacy, urbanisation, and so on. The script writes those numbers into a file called `data/countries.json`. The website reads that file every time a visitor loads the page. Then GitHub automatically rebuilds the public site. You receive a notification if anything fails.

---

## The ingredients

Three files in the repository make this work:

| File | What it does |
|---|---|
| [`data/static_countries.json`](../data/static_countries.json) | The **human-written** part — country overviews, industries, focus areas, media outlets. Edited by hand. |
| [`scripts/refresh_data.py`](../scripts/refresh_data.py) | The **automation brain** — fetches numbers, merges them with the static metadata, writes the output. |
| [`.github/workflows/refresh-data.yml`](../.github/workflows/refresh-data.yml) | The **scheduler** — tells GitHub when and how to run the script. |

And one file it produces:

| File | What it is |
|---|---|
| `data/countries.json` | The **merged, live output**. The website reads this at runtime. Do not edit it by hand — it will be overwritten next Monday. |

---

## What runs, and when

The workflow triggers on **three events**:

1. **Every Monday at 03:00 UTC** — the scheduled refresh.
2. **Any push that touches `static_countries.json`** — so if you add or edit a country's metadata, the numbers auto-populate within a few minutes.
3. **A manual button press** — on GitHub go to the "Actions" tab → "Refresh country data" → "Run workflow". Useful if you want to test a change immediately.

To change the schedule, edit the `cron` line in [`refresh-data.yml`](../.github/workflows/refresh-data.yml). The online tool https://crontab.guru explains cron syntax in plain English.

---

## What gets auto-refreshed vs. what stays manual

### Auto-refreshed (via World Bank API — no key needed)
- Population
- GDP per capita (USD)
- Internet users (% of population)
- Urban population (%)
- Adult literacy (%)
- Population by age band (0–14, 15–64, 65+)
- Mobile subscriptions per 100
- Fixed broadband per 100
- Land area (km²)

### Manual, refreshed once a year
- **Reporters Without Borders (RSF) Press Freedom Index** — RSF publishes new rankings each May. Update the `RSF_RANK_2024` table in [`refresh_data.py`](../scripts/refresh_data.py) (rename to `RSF_RANK_2025` etc.) after the new release.
- **Smartphone adoption %** — DataReportal publishes this annually. Update the `SMARTPHONE_PCT_2024` table similarly.
- **All qualitative fields** — overviews, dominant industries, focus areas, outlet names, topics of interest, languages. Live in `static_countries.json`. Edit whenever the country's reality changes (new government, new dominant platform, etc.).

---

## How to add a new country (30 seconds)

1. Open [`data/static_countries.json`](../data/static_countries.json).
2. Add a new block, copying an existing country as a template. For example, for France:

```json
"FRA": {
  "name": "France",
  "capital": "Paris",
  "region": "Europe",
  "subregion": "Western Europe",
  "flag": "🇫🇷",
  "overview": "…",
  "currency": "Euro (EUR)",
  "languages": ["French"],
  "government": "Semi-presidential republic",
  "dominant_industries": […],
  "focus_areas": […],
  "media": {
    "top_tv": "…",
    "top_radio": "…",
    "top_online_news": "…",
    "top_social": "…"
  },
  "topics_of_interest": […]
}
```

3. Commit the change. The workflow runs automatically within a couple of minutes and populates the country's numbers. Refresh the live site — the new country is there.

The only two fields that need a hand-written source are the ISO-3 alpha code as the key (`"FRA"`) and all the "qualitative" text fields. Everything numeric comes from the World Bank.

If you pick an ISO-3 code the script hasn't seen before, also add it to the `ISO3_TO_ISO2` map inside `refresh_data.py` (e.g. `"FRA": "FR"`).

---

## What happens when something goes wrong

- **The World Bank API is unreachable one morning.** The script catches the error, preserves whatever values it fetched last week, and continues. The site never shows blanks.
- **A new country was added but its data couldn't be fetched.** The country appears on the map with a "preliminary" confidence flag and a note until the next successful refresh.
- **The workflow itself fails.** GitHub emails the repository owner (you) automatically. Click through to the Actions tab to see the exact error log.

To see a history of refresh runs: on GitHub, click **Actions** in the top bar.

---

## Cost

Zero. All of this runs on GitHub's free tier:
- GitHub Pages hosting: free for public repos
- GitHub Actions minutes: free (our workflow uses ~1 minute per run)
- World Bank API: free, no registration

---

## What this automation **doesn't** do (and what to watch for)

1. It doesn't scrape sites that block bots. If a source requires logging in or presents CAPTCHAs, we don't touch it.
2. It doesn't translate country overviews. Those remain hand-curated in English; the UN language service signs off on content translations.
3. It doesn't validate the data. If the World Bank publishes a bad number, we publish a bad number. Occasional manual sanity-checking is still the right instinct — the [Sources tab](../index.html) on every country profile links back to the primary source, so verification is one click away.
4. It doesn't touch survey responses. That pipeline is separate and handled manually when you send CSV exports.

---

## If you need to hand this off

The entire automation fits in two files totalling about 250 lines of code. A developer, a UN IT staffer with Copilot, or even a motivated non-coder walking through the inline comments can maintain it. Nothing proprietary, nothing paid, nothing exotic.
