# Topic Explorer audit — 2026-08-11

**Trigger.** The magnitude-7.4 Chocó (Colombia) earthquake of 2026-08-10 was not
visible in the Topic Explorer the next morning. This audit traced that case
end-to-end, then verified the whole surface: all 167 registry topics, the
global movers, per-country trending across five regions against live outside
sources, and the pipeline code. Method: 12 parallel audit lanes, every finding
adversarially verified (by an independent verifier agent or by direct
numerical reproduction) before acceptance. 36 findings were verified as real;
7 were refuted and discarded.

## The Colombia earthquake case — resolved

The Atlas was never blind; it was late, and it was looked at in the wrong
place. Four verified causes:

1. **Publication race (fixed).** The daily run fired at 05:30 UTC, but
   Wikimedia publishes each day's per-article pageviews late morning UTC the
   NEXT day. Every run therefore stored series whose newest day was empty,
   and sudden events took an extra cycle to appear. The 2026-08-11 rerun at
   15:00 UTC captured the quake-day spike (es "Terremoto": 6,533 views,
   16× baseline; event article: 18,122 on day one) and Earthquake flipped to
   **rising +32% globally / +76% in Spanish**, leading Colombia's rising
   list. *Fix: the cron moved to 16:05 UTC (trend-engine.yml).*
2. **Topic Explorer is global-only (by design; now clearer).** Per-country
   trending lives in the map's country panel. Colombia's measured most-read
   list carried the quake (past-quake articles, the Richter scale, the
   epicenter town San José del Palmar) from the first post-quake run.
3. **Google Trends cadence (fixed).** The trending-searches feed lists only
   searches accelerating *at fetch time* and keeps no history; one snapshot
   a day at 00:30 Bogotá time missed the entire daytime search wave —
   Colombia's published "trending searches" on quake day were lottery
   numbers. *Fixes: snapshots now union-merge into the per-day archive
   instead of overwriting, and a new lightweight workflow (trends-pulse.yml)
   polls the feed three extra times daily.*
4. **Concept pages vs event pages (documented limitation).** The registry
   tracks concept articles ("Earthquake"); event attention concentrates on
   event articles we do not track. The measured per-country reading lists
   are the Atlas's safety net for this — they caught the quake correctly.

## Verified findings and what was done

### High severity — fixed 2026-08-11

| Finding | Fix |
|---|---|
| **29 series permanently dead**: a failed first fetch stored an all-None series, which the dormant classifier then skipped forever (`stored_mean` returned 0.0 for "never fetched"). One casualty: en "Vocational education" (~187 views/day upstream) — a topic that vanished from the UI blamed on "low traffic" when the pipeline had simply never fetched it. | `stored_mean` now returns None for all-None series so they re-queue daily at the front of the stalest-first list; all dead series backfilled locally. |
| **Bot flood published as reading**: on 2026-08-10 the en "Roblox" article took 4.78M "user" views (683× baseline) with automated views in lockstep (4.75M) — a flood that half-evaded Wikimedia's classifier and ranked #1–2 in the published most-read lists of India, the Philippines, Indonesia, Colombia and others. Morocco's list was topped by fr "Cookie (informatique)" whose Moroccan views equalled ~100% of the article's worldwide user traffic. | New flood gate in fetch_trends_wiki_countries.py: large entries are checked against their own global per-article series and dropped on automated-lockstep, or on whipsaw + single-country concentration ≥80%. Fail-open on API errors. |
| **Ecuador's quake-day reading lost as "withheld"**: the day loop broke on the first HTTP-200 even when nothing survived filtering, never trying the fallback day; the fetch window would have slid past Aug 10 permanently. | Fallback day now also tried after an empty day-1; Ecuador re-fetched same day (two quake articles now publish). |
| **Same-day reruns erased the search archives**: both snapshot fetchers replaced `history[today]` instead of merging — 807 queries were destroyed by reruns on audit day alone, on an archive the docstrings correctly call unrebuildable. | Union-merge in both fetchers (also what makes the intraday pulse workflow safe). |
| **France's #1 topic ("5G", 30% attention share, 7×"distinctive") is non-organic traffic**: fr "5G" out-reads en 5:1 absolute, is 99.4% mobile-web (healthy control: ~40/60 desktop/mobile), flat-high for 120 days, no French 5G news event exists — and the fr language weights spill it into 13 more countries. | *2026-08-17: auto-gated.* The access-method anomaly gate (recommendation 1 below) now quarantines the series — stored but excluded from attention shares; France's panel no longer headlines 5G. See the GATE_* block in fetch_trends_wikipedia.py for the calibration. |

### Medium severity — fixed

- **Survivorship bias in global velocity**: the weighting basis admitted
  series on the 7-day mean only, so editions spiking *into* the basis counted
  while editions collapsing *out* vanished — verified to flip Tropical
  cyclone to "rising" (+0.32 vs +0.25 symmetric). *Basis is now symmetric
  (either window ≥ floor, weighted by the larger mean).*
- **Single-edition bursts headlined as global movers**: "Wind power +1121%"
  was 85% one Japanese-edition burst (organic-shaped, already ended
  upstream). *Topics now export `top_edition` share; the movers list labels
  rows ≥70% single-edition ("driven by Japanese Wikipedia").*
- **Rising fan-out without weight guard**: 23 language spikes became 219
  identical "rising" entries across 88 of 96 countries, at weights down to
  0.002. *Country rising entries now require attribution weight ≥ 0.05.*
- **Registry titles gone stale**: 21 tracked titles had become redirects
  (pageviews accrue to the target, so the series undercounted — es "Climate
  change", zh "COVID-19", de "Computer security"…), 1 was deleted, and
  several sitelinks pointed at near-zero synonym pages while the language's
  real article lived on a sibling Wikidata item (Wildfire had NO fr/es entry
  in peak fire season; fr "Feu de forêt" alone runs ~283 views/day). *The
  registry builder now resolves redirects in every language, applies curated
  overrides (verified against live traffic), and guards against two topics
  claiming one article; the registry was regenerated and affected series
  wiped + backfilled from the corrected titles.*
- **Coverage arithmetic couldn't account for tracked topics** (164 scored +
  0 stale ≠ 167): below-floor topics vanished with no bucket and no UI
  trace. *New `topics_below_floor` count and `topics_unscored` list; the
  Topic Explorer now shows unscored topics dimmed, with the reason.*
- **Chart drew 66%-coverage days as full totals** (floor was 50%): the #2
  global mover's entire final nine days were partial sums presented as
  whole. *Plot floor raised to 70%; missing days break the line instead.*
- **Withheld notes blamed Wikimedia for the Atlas's own filters** (Panama,
  DRC, Côte d'Ivoire): the published note claimed "none of them are
  encyclopedia articles" when our single-edition gate had removed real
  articles. *Three truthful note variants now distinguish who removed what.*
- **A 200-with-non-XML response marked covered countries "unsupported"**,
  destroying their search history for a week. *Only HTTP 400 now means
  unsupported; history is preserved inside unsupported records.*
- **Freshness police watched only the newest date per file**: individually
  frozen countries stayed invisible (4 live on audit day). *The assemble
  gate now counts per-country staleness and alarms on the distribution.*
- **GDELT "news articles, 7 days" is incomparable across topics** —
  "Surveillance" counts 11,724 mostly off-sense articles while "Regulation
  of AI" counted 4 during AI-Act enforcement week. *Not fixed today: needs
  a query-quality overhaul in fetch_trends_gdelt.py (recommended below).*
- **Turkey's panel is one suspect spike**: tr "Artificial intelligence"
  carries 71.7% of Turkey's attention share; its "user" surge moves in
  lockstep with an equal automated surge (likely misclassified automation).
  The weight guard + concentration cue reduce the blast radius; the
  access-method gate (below) is the real fix. *2026-08-17: shipped — the
  series trips the gate (4.3% desktop vs the tr edition's 25.3% norm) and
  is quarantined from Turkey's profile.*

### Structural limitations now documented (not bugs)

- **Language-weight country panels are shared, not national**: countries
  whose profile derives from the same language(s) get near-identical panels
  (18 clone groups covering ~48 countries on audit day: Australia = Kenya =
  South Africa; five Gulf states identical; six Latin American countries
  identical). The measured layers (reading lists, searches) are the
  per-country truth; the heuristic panel is context. The country panel
  already carries the approximation note; treat "distinctive interests" for
  clone-group countries with caution.
- **Momentum is level-blind**: "Heat wave" read "falling" during the 2026
  European heat dome because attention was declining *from a very high
  level*. Velocity measures change, not importance.
- **7-day velocity damps one-day catastrophes** by ~1/7 on day one; the
  reading lists and (now) intraday searches carry the fast signal.
- **Some published lists contain uncomfortable but genuine reading**
  (e.g. porn-site articles in small privacy-thresholded markets). They are
  measured reality; whether to editorially suppress them is a decision for
  DGC, not the pipeline.

### Refuted claims (checked, not real — recorded so they aren't re-found)

- "The Sunday dormant refresh is silently failing" — dormant series are
  current through Aug 8–10; the real hole was the 29 never-fetched series.
- "The ja Wind-power burst is bot traffic" — 9-day organic-shaped ramp with
  weekend peak and clean collapse; automated split stayed proportionally low.
- "Cuba's trending-searches feed works but is marked unsupported" — the
  7-day re-probe design already covers it.
- "Cross-country presence proves Roblox reading was organic" — the reverse:
  the global per-article series proves the flood; presence in many countries'
  lists was flood leakage. (The flood gate drops it everywhere.)

## Registry gaps recommended for curation (needs DGC sign-off)

Influenza; tobacco/smoking; ocean–climate (ocean acidification or marine
heatwave); Freedom of religion; broader LGBT rights (only Same-sex marriage
is tracked); Social protection; Peacebuilding; Statelessness;
Conflict-related sexual violence; energy access/poverty; e-waste; submarine
cables; International Court of Justice; UN Security Council; UN General
Assembly; UNRWA. Each needs title curation across 22 languages via the
(now redirect-safe) registry builder.

## Remaining recommended work

1. **Access-method anomaly gate** for pageview series (the France-5G class):
   flag non-en series exceeding a sane multiple of the en series with a
   degenerate desktop/mobile split; quarantine from attention shares.
   *Shipped 2026-08-17.* Screens: ≥1.5× the topic's en series, or ≥50% of
   the edition's tracked attention; verdict: desktop share under ⅓ of the
   SAME edition's aggregate desktop norm (a fixed cutoff false-positives
   mobile-first editions — healthy hi series run 4–9% desktop). Calibrated
   live: fr 5G (0.02×) and tr Yapay zekâ (0.17×) trip; es Terremoto
   (quake week, 0.80×), ja 風力発電 (0.97 desktop-heavy tail, 3.08×) and
   every mobile-first control (≥0.48×) pass. Quarantine, never delete;
   fail-open on API errors; design + rejected alternatives (incl. why
   automated-lockstep does NOT transfer to per-series gating) documented
   at the GATE_* block in fetch_trends_wikipedia.py.
2. **GDELT query-quality overhaul** (sense-disambiguation for terms like
   "surveillance"; per-topic query review).
3. **Event-article linkage**: surface each country's measured reading list
   inside the Topic Explorer, or map event articles to topics via Wikidata
   "instance of" chains, so concept-page dilution stops hiding events.
4. Registry gap curation (list above).
