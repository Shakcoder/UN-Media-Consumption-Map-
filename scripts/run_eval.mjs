#!/usr/bin/env node
/**
 * run_eval.mjs — the Atlas acceptance test.
 * ==========================================
 * Runs all 100 golden questions (docs/PLATFORM_DESIGN.md §11) through the
 * REAL browser engine (ask-engine.js) and writes every answer to
 * eval/golden100_results.json for grading.
 *
 * Usage:  node scripts/run_eval.mjs            (the 100 golden questions)
 *         node scripts/run_eval.mjs strategy   (the 18 strategy-brief prompts,
 *                                               with structural checks: all six
 *                                               memo sections + disclaimers
 *                                               present, no null leakage)
 *         node scripts/run_eval.mjs market     (Market Finder invariants: the
 *                                               findMarkets() honesty contract —
 *                                               named exclusions, disclosed
 *                                               weights, digital reach capped —
 *                                               plus composed-answer checks)
 * Needs:  Node 18+ (no packages). Run from anywhere; paths are script-relative.
 *
 * The bar (design doc §11): the system answers with citations, or it
 * honestly says what it doesn't know — a confident wrong answer is the
 * only true failure. Categories with no underlying data source (campaign
 * history, format performance) are EXPECTED to decline gracefully.
 */

import { readFile, mkdir, writeFile } from "node:fs/promises";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";

const ROOT = join(dirname(fileURLToPath(import.meta.url)), "..");

// ask-engine.js loads its data with fetch("data/...") — serve those from disk
globalThis.fetch = async (path) => {
  try {
    const buf = await readFile(join(ROOT, String(path)));
    return { ok: true, status: 200, json: async () => JSON.parse(buf.toString()) };
  } catch {
    return { ok: false, status: 404, json: async () => { throw new Error("404 " + path); } };
  }
};

const QUESTIONS = [
  // Platform selection (1–10)
  [1, "platform-selection", "Where should we publish climate change content targeting youth?"],
  [2, "platform-selection", "Best platform for reaching rural women in Nigeria?"],
  [3, "platform-selection", "Which platforms should UNHCR use in Jordan?"],
  [4, "platform-selection", "Is TikTok viable for public-health messaging in Indonesia?"],
  [5, "platform-selection", "Where do people over 45 get news in Brazil?"],
  [6, "platform-selection", "Which platforms are blocked or throttled in Iran?"],
  [7, "platform-selection", "Best platform mix for a vaccination campaign in Pakistan?"],
  [8, "platform-selection", "Should we invest in podcasts for France?"],
  [9, "platform-selection", "Where does radio still beat digital in West Africa?"],
  [10, "platform-selection", "Which platform is growing fastest among Kenyan youth?"],
  // Topic discovery (11–20)
  [11, "topic-discovery", "What topics are currently resonating in Indonesia?"],
  [12, "topic-discovery", "Which countries show rising interest in AI governance?"],
  [13, "topic-discovery", "What's trending in East Africa this month?"],
  [14, "topic-discovery", "Is interest in climate adaptation growing or declining in South Asia?"],
  [15, "topic-discovery", "What health topics concern people in Egypt right now?"],
  [16, "topic-discovery", "Which SDG topics get the least media coverage in LatAm?"],
  [17, "topic-discovery", "What was the most-read topic in Ukraine last quarter?"],
  [18, "topic-discovery", "Where is misinformation about vaccines trending?"],
  [19, "topic-discovery", "What environmental topics peak seasonally in India?"],
  [20, "topic-discovery", "Which topics link food security and migration in the Sahel?"],
  // Audience (21–30)
  [21, "audience", "What do we know about Gen Z media habits in Mexico?"],
  [22, "audience", "How do urban and rural audiences differ in Tanzania?"],
  [23, "audience", "Which segment is hardest to reach in Japan?"],
  [24, "audience", "What's the gender gap in internet access across the Sahel?"],
  [25, "audience", "Where are older adults most active on social media?"],
  [26, "audience", "Who trusts public broadcasters most in Europe?"],
  [27, "audience", "What languages should a Morocco campaign use?"],
  [28, "audience", "How news-avoidant are audiences in the UK vs. Germany?"],
  [29, "audience", "Which countries have the most creator-influenced news audiences?"],
  [30, "audience", "What audience overlap exists between Facebook and WhatsApp in Kenya?"],
  // Format & creative (31–40)
  [31, "format-creative", "What format performs best for women's health content in East Africa?"],
  [32, "format-creative", "Short-form or long-form video for Vietnam?"],
  [33, "format-creative", "Are infographics effective where literacy is low?"],
  [34, "format-creative", "Which countries prefer audio content?"],
  [35, "format-creative", "What's the podcast opportunity in Brazil?"],
  [36, "format-creative", "Should climate content be creator-led in the Philippines?"],
  [37, "format-creative", "What format suits humanitarian appeals in Lebanon?"],
  [38, "format-creative", "Where is live video most watched?"],
  [39, "format-creative", "Text vs. video for policy audiences in Brussels?"],
  [40, "format-creative", "What formats work on low-bandwidth connections in Chad?"],
  // Country strategy (41–50)
  [41, "country-strategy", "Best way to distribute humanitarian aid messaging in Peru?"],
  [42, "country-strategy", "Full media strategy for a girls'-education campaign in Afghanistan — what's possible?"],
  [43, "country-strategy", "How should UN comms adapt for Vietnam vs. Thailand?"],
  [44, "country-strategy", "What trusted outlets should we partner with in Ghana?"],
  [45, "country-strategy", "How do we reach displaced populations in Sudan?"],
  [46, "country-strategy", "Communication plan for El Niño warnings in the Pacific islands?"],
  [47, "country-strategy", "How to counter aid skepticism in donor countries?"],
  [48, "country-strategy", "Reaching minority-language speakers in Guatemala?"],
  [49, "country-strategy", "What's the media landscape risk in Myanmar?"],
  [50, "country-strategy", "How should messaging differ between francophone and anglophone Cameroon?"],
  // Comparison (51–60)
  [51, "comparison", "Compare news trust in Nordic vs. Mediterranean countries."],
  [52, "comparison", "TikTok news use: Indonesia vs. Malaysia vs. Philippines."],
  [53, "comparison", "Which G20 country has the lowest news trust?"],
  [54, "comparison", "Radio reach: Kenya vs. Nigeria vs. South Africa."],
  [55, "comparison", "Press freedom trend: Georgia vs. Armenia over 5 years."],
  [56, "comparison", "Compare youth platform preferences France vs. Germany."],
  [57, "comparison", "Where is WhatsApp news use highest globally?"],
  [58, "comparison", "Internet freedom vs. usage: Gulf states compared."],
  [59, "comparison", "News avoidance: highest and lowest countries?"],
  [60, "comparison", "Compare climate interest across BRICS."],
  // Timing (61–70)
  [61, "timing", "When should we launch a malaria campaign in Nigeria?"],
  [62, "timing", "What seasonal peaks exist for education topics in India?"],
  [63, "timing", "Best month for climate content in Europe?"],
  [64, "timing", "When does interest in humanitarian topics spike?"],
  [65, "timing", "How long does a topic stay trending in the US vs. Japan?"],
  [66, "timing", "When do Ramadan-related media habits shift in MENA?"],
  [67, "timing", "What day-of-week patterns exist for news consumption?"],
  [68, "timing", "Timing for World Refugee Day amplification?"],
  [69, "timing", "When did interest in Sudan last peak, and why?"],
  [70, "timing", "Is now a good moment for AI-safety content in Korea?"],
  // Risk & integrity (71–80)
  [71, "risk-integrity", "What are the risks of a UN campaign on X in country Y?"],
  [72, "risk-integrity", "Where could health messaging trigger backlash?"],
  [73, "risk-integrity", "Which countries have state-controlled media environments we should account for?"],
  [74, "risk-integrity", "Is our climate framing vulnerable to politicization in the US?"],
  [75, "risk-integrity", "What platforms carry the most misinformation in Brazil?"],
  [76, "risk-integrity", "Where are journalists most at risk covering our topics?"],
  [77, "risk-integrity", "What happens if TikTok is banned in a target country mid-campaign?"],
  [78, "risk-integrity", "How resilient is our strategy to internet shutdowns in Ethiopia?"],
  [79, "risk-integrity", "Which topics are legally sensitive in Gulf states?"],
  [80, "risk-integrity", "What neutrality risks exist in election years?"],
  // Evidence lookup (81–90)
  [81, "evidence-lookup", "What's the source for Kenya's radio number?"],
  [82, "evidence-lookup", "How confident are we in Indonesia's TikTok data?"],
  [83, "evidence-lookup", "When was Peru's platform data last updated?"],
  [84, "evidence-lookup", "What does Afrobarometer say about Uganda's internet use?"],
  [85, "evidence-lookup", "Show all evidence behind the Nigeria recommendation."],
  [86, "evidence-lookup", "Which countries lack format data entirely?"],
  [87, "evidence-lookup", "What's the methodology behind the trust scores?"],
  [88, "evidence-lookup", "How does DNR sample India — is it nationally representative?"],
  [89, "evidence-lookup", "What changed in Turkey's numbers since last year?"],
  [90, "evidence-lookup", "Which sources disagree about Egypt, and why?"],
  // Campaign learning (91–100)
  [91, "campaign-learning", "What did similar campaigns achieve in this region?"],
  [92, "campaign-learning", "What platform mix did our last climate campaign use, and did it work?"],
  [93, "campaign-learning", "What can we learn from campaign X's underperformance in Colombia?"],
  [94, "campaign-learning", "Which past campaigns reached rural audiences successfully?"],
  [95, "campaign-learning", "Benchmarks for engagement on UN content in MENA?"],
  [96, "campaign-learning", "What content formats did our best campaigns share?"],
  [97, "campaign-learning", "How did timing affect our COP campaign reach?"],
  [98, "campaign-learning", "Which partnerships drove the most trust lift?"],
  [99, "campaign-learning", "What should we A/B test next in Southeast Asia?"],
  [100, "campaign-learning", "Draft a one-page strategy memo for a water-sanitation campaign in Bolivia with full citations."],
];

const STRATEGY_PROMPTS = [
  "Distribution strategy for climate change content in Kenya",
  "Full media strategy for a girls'-education campaign in Afghanistan — what's possible?",
  "Draft a strategy memo for a water-sanitation campaign in Bolivia",
  "Best opportunities for distributing vaccination content in Pakistan?",
  "How should we roll out refugee-awareness content across East Africa?",
  "Strategy for distributing misinformation-literacy content in Brazil",
  "Content distribution plan for reaching young people in Indonesia",
  "How do we launch climate content in Germany?",
  "Distribution strategy for food security messaging in the Sahel",
  "Strategy brief for AI-governance content in South Korea",
  "Opportunities for distributing health content in Egypt",
  "Media plan for humanitarian messaging in Myanmar",
  "How should DGC distribute peacekeeping content in the DRC?",
  "Strategy for launching gender-equality content in Saudi Arabia",
  "Content strategy for small island states — distribute cyclone-preparedness content in Fiji",
  "Rollout plan for anti-trafficking content in Thailand",
  "Distribution opportunities for education content in rural India",
  "Strategy for promoting content about the UN in the United States",
];

const engine = await import(join(ROOT, "ask-engine.js"));
await engine.initEngine();

if (process.argv[2] === "strategy") {
  // The mandatory consulting structure (DGC spec, 2026-07-21). Every strategic
  // answer must carry all of these — the consistency is the point.
  const SECTIONS = [
    "Decision being addressed",   // step 1: what decision is being made
    "### Executive summary",      // the 30-second version
    "### Key insights",
    "### Strategic assessment",
    "### Opportunities",          // ranked + justified
    "### Risks",
    "### Confidence and limits",
    "### Evidence used",
    "Advisory",                   // advisory disclaimer
  ];
  const out = [];
  let fails = 0;
  for (const prompt of STRATEGY_PROMPTS) {
    engine.resetConversation();
    let entry = { prompt };
    try {
      const r = engine.answerQuestion(prompt);
      const a = r.answer || "";
      const isRegion = /Strategic brief — .*across /.test(a);
      entry.answer = a;
      entry.checks = {
        sections_missing: SECTIONS.filter(s => !a.includes(s)),
        region_form: isRegion,
        null_leak: /\bnull\b|undefined|NaN%/.test(a),
        has_disclaimer: /Advisory/i.test(a),
        // consulting-grade requirements: a stated confidence level, ranked
        // recommendations that each answer "why", and evidence tiering
        has_confidence: /Confidence: (High|Medium|Low)/.test(a),
        has_ranked_why: /- Why:/.test(a),
        has_evidence_tags: /\[measured\]/.test(a) && /\[inferred\]/.test(a),
        evidence_count: (r.evidence || []).length,
      };
      const c = entry.checks;
      if (c.sections_missing.length || c.null_leak || !c.has_disclaimer
          || !c.has_confidence || !c.has_ranked_why || !c.has_evidence_tags) fails++;
    } catch (e) {
      entry.error = e.message; fails++;
    }
    out.push(entry);
  }
  await mkdir(join(ROOT, "eval"), { recursive: true });
  await writeFile(join(ROOT, "eval", "strategy_results.json"), JSON.stringify(out, null, 1));
  console.log(`Strategy suite: ${STRATEGY_PROMPTS.length - fails}/${STRATEGY_PROMPTS.length} structurally sound (sections + disclaimers + no null leakage)`);
  console.log("Results: eval/strategy_results.json");
  process.exit(fails ? 1 : 0);
}

if (process.argv[2] === "market") {
  // Market Finder acceptance suite (added 2026-07-25, the day after the
  // feature shipped). Two layers:
  //   A. findMarkets() API invariants — the honesty contract the commit
  //      message promises: countries without data are EXCLUDED with a named
  //      reason (never silently ranked low), weights are disclosed and
  //      renormalized over active criteria, digital reach is capped at
  //      internet penetration, an explicit channel ask is a hard filter,
  //      Not-Free markets always carry the partner-vetting flag.
  //   B. Composed answers — natural-language prompts that route to the
  //      finder must disclose method + weights, list the not-rankable
  //      countries, carry the Advisory disclaimer, and leak no nulls.
  const checks = [];
  let fails = 0;
  const check = (name, pass, detail = "") => {
    checks.push({ name, pass: !!pass, ...(detail ? { detail } : {}) });
    if (!pass) { fails++; console.log(`  FAIL ${name}${detail ? " — " + detail : ""}`); }
  };
  const DIGITAL = new Set(["online news", "social media"]);
  const sortedDesc = (rows) => rows.every((r, i) => i === 0 || rows[i - 1].score >= r.score);
  const weightSum = (res) => Object.values(res.weights).reduce((a, b) => a + b, 0);
  const structurallySound = (name, res) => {
    check(`${name}: scores in [0,100]`, res.ranked.every(r => r.score >= 0 && r.score <= 100));
    check(`${name}: ranked sorted by score desc`, sortedDesc(res.ranked));
    check(`${name}: weights sum to ~100`, Math.abs(weightSum(res) - 100) <= 1, `sum=${weightSum(res)}`);
    const rankedIsos = new Set(res.ranked.map(r => r.iso));
    check(`${name}: ranked/excluded disjoint`, !res.excluded.some(x => rankedIsos.has(x.iso)));
    check(`${name}: every exclusion has a named reason`,
      res.excluded.every(x => typeof x.reason === "string" && x.reason.length > 0));
    check(`${name}: reachPeople = effective% of population`,
      res.ranked.every(r => r.population == null || r.reachPeople === Math.round((r.lead.effective / 100) * r.population)));
  };

  // --- A. API invariants -----------------------------------------------------
  const base = engine.findMarkets({});
  const base2 = engine.findMarkets({});
  const radio = engine.findMarkets({ objectiveKey: "behaviour", channel: "radio" });
  const french = engine.findMarkets({ language: "fr" });
  const youth = engine.findMarkets({ objectiveKey: "youth", audience: "youth" });
  const scoped = engine.findMarkets({ isos: ["KEN", "NGA", "GHA", "TCD"] });
  const nodata = engine.findMarkets({ isos: ["TCD", "SSD", "ERI"] }); // none has a news-channel survey

  check("determinism: identical opts give identical results",
    JSON.stringify(base) === JSON.stringify(base2));
  structurallySound("base", base);
  structurallySound("radio-filter", radio);
  structurallySound("language=fr", french);
  structurallySound("youth", youth);
  structurallySound("iso-scoped", scoped);

  // weights renormalize over ACTIVE criteria only — inactive ones must not appear
  check("base: only reach+openness weighted (no language/audience/momentum)",
    Object.keys(base.weights).sort().join(",") === "openness,reach", JSON.stringify(base.weights));
  check("language=fr: language criterion active and weighted", french.weights.language > 0);
  check("youth: audience criterion active and weighted", youth.weights.audience > 0);

  // the single most expensive mistake this tool prevents: survey reach of the
  // connected population presented as national reach
  check("digital cap: effective reach never exceeds internet penetration",
    base.ranked.every(r => !DIGITAL.has(r.lead.name) || r.internet == null || r.lead.effective <= r.internet + 1e-9));
  check("digital cap: capped flag set exactly when the cap binds",
    base.ranked.every(r => DIGITAL.has(r.lead.name)
      ? r.lead.capped === (r.lead.effective < r.lead.measured)
      : (r.lead.capped === false && r.lead.effective === r.lead.measured)));

  // an explicit channel ask is a hard filter, not a preference
  check("radio-filter: every ranked country led by radio",
    radio.ranked.length > 0 && radio.ranked.every(r => r.lead.name === "radio"));
  check("radio-filter: countries without radio data excluded with the named reason",
    radio.excluded.every(x => /no radio survey data|platform-use data only|no media survey data/.test(x.reason)));

  // Not-Free invariant (2026-07-21: never remove the partner-vetting warning)
  const notFree = base.ranked.filter(r => r.fh === "Not Free");
  check("Not-Free markets appear in world ranking (check is non-vacuous)", notFree.length > 0);
  check("every ranked Not-Free market carries the partner-vetting flag",
    notFree.every(r => r.flags.some(fl => /Not Free/.test(fl))));

  // scoping is exact: nothing outside the requested pool, in either list
  const inScope = new Set(["KEN", "NGA", "GHA", "TCD"]);
  check("iso scope respected in ranked+excluded",
    [...scoped.ranked, ...scoped.excluded].every(r => inScope.has(r.iso)));
  check("iso scope: unsurveyed Chad excluded, surveyed Kenya ranked",
    scoped.excluded.some(x => x.iso === "TCD") && scoped.ranked.some(r => r.iso === "KEN"));
  check("all-unsurveyed pool: zero ranked, all three excluded",
    nodata.ranked.length === 0 && nodata.excluded.length === 3);

  // missing language data scores 0 and stays ranked — missing data must never
  // silently exclude, only missing SURVEY data excludes (with its reason)
  check("language=fr: countries without a French figure ranked at language=0, not dropped",
    french.ranked.some(r => r.langPct == null && r.components.language === 0)
    && french.ranked.every(r => typeof r.components.language === "number"));

  // --- B. composed natural-language answers ---------------------------------
  const COMPOSED = [
    { prompt: "Which countries should we prioritize for a radio vaccination campaign?",
      expect: { header: true, table: true, notRankable: true, marker: "· radio-led" } },
    { prompt: "Best markets to launch English-language content for young people?",
      expect: { header: true, table: true, notRankable: true, marker: "English content", marker2: "youth audience" } },
    { prompt: "Which countries in West Africa best fit a climate change campaign?",
      expect: { header: true, table: true, scoped: true } },
    { prompt: "Which Caribbean markets should we prioritize for a campaign?",
      expect: { emptyGraceful: true } },  // no Caribbean country has a news-channel survey
  ];
  const composed = [];
  for (const { prompt, expect } of COMPOSED) {
    engine.resetConversation();
    let entry = { prompt };
    try {
      const r = engine.answerQuestion(prompt);
      const a = r.answer || "";
      entry.answer = a;
      const p = (name, pass, detail) => check(`"${prompt.slice(0, 40)}…": ${name}`, pass, detail);
      p("no null/undefined/NaN leakage", !/\bnull\b|\bundefined\b|\bNaN\b/.test(a));
      if (expect.emptyGraceful) {
        p("declines gracefully, names the data gap",
          /cannot rank markets/.test(a) && /data gap/.test(a));
      } else {
        p("finder header present", /\*\*Market screening — /.test(a));
        p("method + weights disclosed", /How this ranking works:/.test(a) && /reach \d+%/.test(a));
        p("results table present", /\| # \| Country \| Score \|/.test(a));
        p("advisory disclaimer present", /Advisory\./.test(a));
        p("evidence includes the screening method", (r.evidence || []).some(e => /Market screening method/.test(e.title)));
        p("per-country evidence attached", (r.evidence || []).filter(e => /screening inputs/.test(e.title)).length > 0);
        if (expect.notRankable) p("not-rankable countries listed", /\*\*Not rankable \(\d+ countries\)/.test(a));
        if (expect.marker) p(`routed with "${expect.marker}"`, a.includes(expect.marker));
        if (expect.marker2) p(`routed with "${expect.marker2}"`, a.includes(expect.marker2));
        if (expect.scoped) p("region scope applied (not all 195)", !a.includes("all 195 countries"));
      }
      entry.evidence_titles = (r.evidence || []).map(e => e.title);
    } catch (e) {
      entry.error = e.message;
      check(`"${prompt.slice(0, 40)}…": no crash`, false, e.message);
    }
    composed.push(entry);
  }

  await mkdir(join(ROOT, "eval"), { recursive: true });
  await writeFile(join(ROOT, "eval", "market_results.json"), JSON.stringify({
    run_note: "Market Finder invariant suite — findMarkets() API contract + composed answers.",
    counts: { passed: checks.filter(c => c.pass).length, failed: fails, total: checks.length },
    checks, composed,
  }, null, 1));
  console.log(`Market Finder suite: ${checks.length - fails}/${checks.length} invariants hold`);
  console.log("Results: eval/market_results.json");
  process.exit(fails ? 1 : 0);
}

const results = [];
let crashed = 0, clarified = 0, refused = 0, answered = 0;

for (const [num, category, question] of QUESTIONS) {
  engine.resetConversation();          // each golden question stands alone
  let entry = { num, category, question };
  try {
    const r = engine.answerQuestion(question);
    if (r.clarify) {
      clarified++;
      entry.outcome = "clarify";
      entry.clarify_question = r.clarify.question;
      entry.clarify_options = r.clarify.options;
    } else {
      const isRefusal = /couldn't match|likely \*can\* help if we rephrase/i.test(r.answer || "");
      if (isRefusal) { refused++; entry.outcome = "refusal"; }
      else { answered++; entry.outcome = "answer"; }
      entry.answer = r.answer;
      entry.evidence_count = (r.evidence || []).length;
      entry.evidence_titles = (r.evidence || []).map(e => e.title);
      entry.followups = r.followups || [];
    }
  } catch (e) {
    crashed++;
    entry.outcome = "CRASH";
    entry.error = e.message;
    entry.stack = String(e.stack || "").split("\n").slice(0, 4).join("\n");
  }
  results.push(entry);
}

await mkdir(join(ROOT, "eval"), { recursive: true });
await writeFile(
  join(ROOT, "eval", "golden100_results.json"),
  JSON.stringify({ run_note: "Answers from ask-engine.js run under Node with data served from local files.", counts: { answered, clarified, refused, crashed }, results }, null, 1),
);

console.log(`Golden-100 run complete: ${answered} answered, ${clarified} asked to clarify, ${refused} refused, ${crashed} CRASHED`);
console.log(`Results: eval/golden100_results.json`);
if (crashed > 0) {
  console.log("\nCRASHES:");
  for (const r of results.filter(x => x.outcome === "CRASH")) console.log(`  #${r.num}: ${r.question}\n    ${r.error}`);
}
// A generic refusal means a golden question the engine used to answer now
// falls through to "I couldn't match that" — a regression, not a judgement
// call, so it fails the gate alongside crashes. Honest gap answers and
// clarifying questions are fine (they are counted separately above).
process.exit(crashed > 0 || refused > 0 ? 1 : 0);
