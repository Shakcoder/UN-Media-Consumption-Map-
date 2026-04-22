# Data schema — what we track and where it comes from

Every indicator below is collected for every country, and every cell carries a citation (primary source URL + retrieval date + confidence flag).

Columns marked **[API]** can be pulled automatically. Columns marked **[Manual]** require a once-a-year human update when the source publishes its next report.

---

## 1. Demographics
| Indicator | Primary source | Refresh |
|---|---|---|
| Total population | World Bank Open Data | **[API]** annual |
| Population by age band (0–14, 15–24, 25–54, 55–64, 65+) | UN World Population Prospects | **[API]** annual |
| Urban / rural split (%) | World Bank | **[API]** annual |
| Top languages spoken | CIA World Factbook / Ethnologue | **[Manual]** rarely changes |
| Literacy rate (% adults) | UNESCO Institute for Statistics | **[API]** annual |
| GDP per capita (USD, PPP) | World Bank | **[API]** annual |

## 2. Infrastructure & connectivity
| Indicator | Primary source | Refresh |
|---|---|---|
| Internet users (% of population) | ITU World Telecommunication Indicators | **[API]** annual |
| Mobile subscriptions per 100 people | ITU | **[API]** annual |
| Smartphone adoption (%) | GSMA Intelligence / DataReportal | **[Manual]** annual |
| Fixed broadband per 100 people | ITU | **[API]** annual |
| Electricity access (%) | World Bank / IEA | **[API]** annual |

## 3. Media reach — share of adults using at least weekly (%)
| Medium | Primary source |
|---|---|
| Television | DataReportal Digital Report / Reuters Institute Digital News Report |
| Radio | DataReportal / UNESCO |
| Printed press | Reuters Institute DNR |
| Online news sites | Reuters Institute DNR |
| Social media (overall) | DataReportal |
| Social media by platform (Facebook, YouTube, Instagram, TikTok, X, WhatsApp as news, etc.) | DataReportal |
| Streaming video | DataReportal |
| Podcasts | Reuters Institute DNR (for covered countries) |
| Messaging apps as news source | Reuters Institute DNR |

Refresh: **[Manual]** annually when the Reuters DNR and DataReportal country reports drop.

## 4. Time spent (avg minutes per day) — where reliably measured
| Medium | Source |
|---|---|
| Internet / total digital | DataReportal |
| Social media | DataReportal |
| TV (broadcast + streaming) | DataReportal |
| Press | Reuters Institute DNR / national audience boards |

Refresh: **[Manual]** annual.

## 5. Content preferences — % of media time spent on
Categories: **News & current affairs · Entertainment · Sports · Education · Religious · Business/finance · Lifestyle**

Source: Reuters Institute DNR + regional public-opinion barometers (Afro-, Latino-, Asian-, Euro-, Arab Barometer). Refresh **[Manual]** annual.

## 6. Topic interests (Reuters Institute standard categories)
Politics · International news · Local news · Climate/environment · Health · Business/economy · Science/tech · Arts/culture · Sports · Lifestyle

Source: Reuters Institute DNR. Refresh **[Manual]** annual.

## 7. Trust & information environment
| Indicator | Source | Refresh |
|---|---|---|
| Overall trust in news | Reuters Institute DNR | **[Manual]** annual |
| Trust by medium (TV / social / print / online) | Reuters Institute DNR | **[Manual]** annual |
| Press Freedom Index score + rank | Reporters Without Borders | **[API/scrape]** annual |
| Freedom of the Press score | Freedom House | **[Manual]** annual |
| Internet Freedom score | Freedom House "Freedom on the Net" | **[Manual]** annual |

## 8. Device mix — % of media consumption happening on
Mobile phone · Desktop/laptop · TV set · Radio set · Print

Source: DataReportal + Reuters Institute DNR. Refresh **[Manual]** annual.

## 9. Community-sourced layer (survey)
Kept as a **separate, clearly-labeled dataset** — never blended with official stats. See [`SURVEY_ETHICS.md`](SURVEY_ETHICS.md).

Columns: respondent age band, country, gender (optional), education (optional), main daily medium, platforms used, hours/day on each, topic interests, trust level by medium, consent flag, submission timestamp.

---

## Per-row metadata (required on every cell)
| Field | Purpose |
|---|---|
| `source_url` | Direct link to the primary source page |
| `source_organisation` | e.g. "World Bank" |
| `retrieved_on` | ISO date of last automated refresh |
| `reference_year` | Year the data describes |
| `confidence` | `high` / `medium` / `low` / `estimated` |
| `notes` | Free-text caveat where needed |

---

## Why this structure
- Splitting by indicator group lets us refresh each group independently — if the World Bank API changes, only the demographics sheet breaks, not the whole site.
- `[API]` vs `[Manual]` columns make the maintenance burden obvious: the manual stuff is a once-a-year ~2-hour task tied to the Reuters Institute DNR release (traditionally June).
- Separating survey data from official data is the single most important credibility decision in the project.
