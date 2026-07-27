# Acceptance tests — the Golden-100, plus two invariant suites

*The design doc (docs/PLATFORM_DESIGN.md §11) defines 100 realistic UN-comms-officer questions as the platform's acceptance test: "the system answers these, with citations, or it isn't done." This folder is the standing record of that test, and of the two automated suites added since — one for strategy briefs, one for Market Finder.*

## How to run it

```
node scripts/run_eval.mjs
```

Requires Node 18+ and nothing else. It runs all 100 questions through the **real browser engine** (`ask-engine.js`, loaded with the repo's own data files) and writes every answer to `eval/golden100_results.json`. Takes a few seconds.

### Run all three suites after ANY change to `ask-engine.js`

`run_eval.mjs` has three modes. They test different things and none of them covers the others, so run all three — from the repository root — before shipping any engine change:

```
node scripts/run_eval.mjs            # golden-100: 100 questions, must end "0 CRASHED"
node scripts/run_eval.mjs strategy   # 18 strategy briefs, must be 18/18
node scripts/run_eval.mjs market     # 73 Market Finder invariants, must be 73/73
```

The strategy and market modes exit non-zero on any failure, so they can act as a gate. **Nothing runs them automatically** — no GitHub workflow does — so this list is the only thing standing between an engine edit and a silent regression.

The golden-100 mode is different: it exits 0 whatever happens, because its answers are graded by a human against the bar below, not by the script. Read the line it prints — `0 CRASHED` is the only part of it that is pass/fail on its own.

## The bar

An answer passes when it either:
- **answers substantively with citations** from data the Atlas holds, or
- **declines honestly and specifically** — naming exactly what data is missing and offering the nearest useful thing — for questions no free data source can answer (campaign history, format performance, age/gender crosstabs, multi-year trends), or
- **asks a scoping question** when the question genuinely can't be grounded ("targeting youth" with no geography; "country Y" placeholders).

A confident wrong answer is the only true failure. A generic refusal where data exists, or a misleading clarify implying an unanswerable question is answerable, scores PARTIAL.

## Score history (graded by an independent multi-agent panel with adversarial verification)

| Date | GOOD | PARTIAL | BAD | Notes |
|---|---|---|---|---|
| 2026-07-20 (baseline) | 17 | 82 | 1 | The BAD: "climate adaptation" answered with the broader falling "Climate change" topic while the exact-match topic was rising +31% |
| 2026-07-20 (after fix round 1) | 74 | 26 | 0 | Known-gap honesty system, exact-topic matching, regional trends, region-vs-region comparisons, press-risk rankings, capital cities, country groups |
| 2026-07-20 (after fix round 2, **final**) | **82** | 18 | 0 | Theme-filtered attention, countries-first topic answers, platform comparison rows, source-mismatch notes, 6 new gap categories |

Raw outcome counts after round 2 fixes: **98 answered, 2 clarify (both rubric-sanctioned), 0 refusals, 0 crashes.**

The loop stopped at 82 deliberately: of the 18 remaining PARTIALs, five were graded GOOD by the category grader and flipped only by the extra-strict leniency auditor (one was called "exemplary" in the same breath) — at that point further iteration polishes grader disagreement, not real defects. The other 13 are documented refinements (e.g. audience-adjusted headlines, SDG-subset filter, topic+region trend routing) — none misinforms; all fail toward extra caution. They are listed with suggested fixes in `golden100_scorecard_round3.json`.

## What the analyst deliberately does NOT answer (and says so)

These question classes have no free data source and get specific honest declines by design: campaign history & engagement benchmarks · format-level performance (video vs text vs podcast) · age/gender/segment crosstabs · platform growth time-series · seasonal & multi-year timing patterns · real-time platform blocking · misinformation flow measurement · sentiment/framing/legal risk · subnational splits · topic-linkage measurement.

## The strategy-brief suite (added 2026-07-21, at DGC request)

The analyst also produces a full **consulting-style brief** when asked a strategy/campaign/distribution question about a country or region. (The original who/what/where/when/how memo format was replaced on 2026-07-21 — briefs now answer the *decision*, not the question.)

`node scripts/run_eval.mjs strategy` runs 18 DGC-style prompts and structurally checks every brief for:

- **all eight mandatory parts, in order** — a `Decision being addressed` line, then `### Executive summary`, `### Key insights`, `### Strategic assessment`, `### Opportunities` (ranked), `### Risks`, `### Confidence and limits`, `### Evidence used`;
- the **closing `Advisory` disclaimer** (there is only one disclaimer, at the end — the top of a brief carries the decision line instead);
- a **stated confidence level** (`Confidence: High|Medium|Low`);
- **ranked recommendations that justify themselves** — every opportunity carries at least one `- Why:` line;
- **evidence tiering** — both `[measured]` and `[inferred]` tags appear, so no claim is unlabelled;
- **no null leakage** (`null` / `undefined` / `NaN%` reaching the reader).

Single-country briefs carry a ninth section, `### Tradeoffs`, between Opportunities and Risks; regional briefs omit it because the tradeoff maths needs one country's figures. That is why it is not in the mandatory list.

Current status: **18/18 sound**; briefs were additionally adversarially reviewed (overclaiming, missing caveats, contradictions, data-poor degradation) before shipping.

Format guidance inside briefs is **feasibility inference** (connectivity, literacy, radio habit) and is labeled as such — the Atlas measures no format performance. Timing guidance is current momentum only (~120-day window).

## The Market Finder invariant suite (added 2026-07-24)

Market Finder (`finder.html`) answers the question *before* the brief: given a campaign, **which countries** should get it? `node scripts/run_eval.mjs market` runs 73 checks over `findMarkets()` and over the natural-language answers that route to it. Unlike the golden-100, these are not graded by a human — each one either holds or the suite fails.

What the 73 checks cover:

- **The honesty contract.** Every excluded country carries a named reason; ranked and excluded lists never overlap; a country missing *language* data is scored 0 and stays in the ranking, because only a missing **survey** may exclude a country — and then it is named.
- **The digital cap.** Effective reach for online news and social media never exceeds the country's internet penetration, and the "capped" flag is set exactly when the cap binds. This is the single most expensive mistake the tool prevents: survey reach *of the connected population* presented as national reach.
- **The Not-Free warning.** Every ranked market that Freedom House rates Not Free carries the partner-vetting flag. A companion check confirms such markets actually appear in the world ranking, so the test can never pass vacuously. **This is a project invariant — if this check ever fails, do not "fix" it by loosening the check.**
- **Scoring mechanics.** Determinism (identical inputs, identical output), scores within 0–100, ranking sorted, disclosed weights summing to ~100 over the *active* criteria only, and reachable-people equal to effective reach × population.
- **Hard filters.** An explicit channel request filters rather than merely re-weights: every ranked country is genuinely led by that channel.
- **Composed answers.** Five natural-language prompts must return the screening header, the disclosed weights, the results table, the "Not rankable (N countries)" line, per-country evidence, and the Advisory disclaimer — and a prompt scoped to a region where no country has a survey (the Caribbean) must decline gracefully and name the data gap rather than return an empty table.

Current status: **73/73 hold**.

## Files

Everything ending in `_results.json` is **regenerated by each run** — never hand-edit one. The scorecards are the opposite: a permanent record of a grading round, kept for comparison.

- `golden100_results.json` — every question's latest raw answer (regenerated by each run)
- `golden100_scorecard.json` — baseline grading (17/82/1)
- `golden100_scorecard_round2.json` — after fix round 1 (74/26/0)
- `golden100_scorecard_round3.json` — after fix round 2 (final)
- `strategy_results.json` — the 18 briefs plus their per-brief structural checks (regenerated by `run_eval.mjs strategy`)
- `market_results.json` — all 73 invariant results with pass/fail and the composed answers (regenerated by `run_eval.mjs market`)
- `strategy_review_outputs.json` (18 prompts), `consulting_review_outputs.json` (20 prompts) — raw briefs captured by `scripts/run_strategy_review.mjs` and `scripts/run_consulting_review.mjs` for the by-hand adversarial reviews, kept as the record of what was reviewed

## Maintenance notes

- The grading rounds were performed by independent AI grader panels (one per question category) with adversarial re-verification of every non-GOOD grade and a leniency audit of GOOD grades. To re-grade in future, any careful reviewer can sample `golden100_results.json` against the bar above — the raw answers are all there. Grade against the structure the engine *actually* produces (run one prompt and look), not against a remembered format: it has changed once already.
- If a future data source closes one of the "deliberate declines" above (e.g. a barometer adds gender crosstabs), update both the engine's `GAPS` table (ask-engine.js) and this README.
- When a suite's expected result changes (a new invariant, a new strategy prompt), update the numbers in this file in the same commit. A README claiming 73/73 while the suite actually runs 80 checks tells the next maintainer nothing about whether the run they just did was healthy.
