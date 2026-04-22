# Global Media Consumption Map

An interactive, source-cited public website showing how the world consumes media — demographics, preferred mediums, content preferences, topic interests, trust levels — country by country and continent by continent.

Built for handover to the United Nations. Grounded in data from ITU, UNESCO, the World Bank, the Reuters Institute, Pew Research, and other vetted institutions.

## Status
**Phase 0 — Foundations.** Live "coming soon" page; data schema and source list drafted; survey ethics language prepared.

## Documents
- [`PLAN.md`](PLAN.md) — full phased build plan
- [`docs/GITHUB_SETUP.md`](docs/GITHUB_SETUP.md) — step-by-step guide to putting the site online
- [`docs/DATA_SCHEMA.md`](docs/DATA_SCHEMA.md) — what data we track per country and from where
- [`docs/SURVEY_ETHICS.md`](docs/SURVEY_ETHICS.md) — consent and data-handling language for the survey

## Repository layout
```
/              index.html — the public website
/assets/       images, icons
/data/         CSV/JSON datasets, one per indicator group
/scripts/      automated data-refresh scripts (GitHub Actions)
/docs/         human-readable documentation
```

## Principles
1. **Every number has a citation.** No exceptions.
2. **Gaps are shown honestly.** "No reliable data" beats a bad estimate.
3. **Boring tech.** Plain HTML/CSS/JS so anyone using GitHub Copilot can maintain it.
4. **Open and free.** No paid services, no closed formats.
