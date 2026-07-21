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
  const SECTIONS = ["Who — the audience", "Where — platforms", "What — content formats", "When — timing", "How — execution", "Advisory only", "human review"];
  const out = [];
  let fails = 0;
  for (const prompt of STRATEGY_PROMPTS) {
    engine.resetConversation();
    let entry = { prompt };
    try {
      const r = engine.answerQuestion(prompt);
      const a = r.answer || "";
      const isRegion = /Advisory brief for/.test(a);
      entry.answer = a;
      entry.checks = {
        sections_missing: isRegion ? [] : SECTIONS.filter(s => !a.includes(s)),
        region_form: isRegion,
        null_leak: /\bnull\b|undefined|NaN%/.test(a),
        has_disclaimer: /Advisory (only|brief)/.test(a),
        evidence_count: (r.evidence || []).length,
      };
      if (entry.checks.sections_missing.length || entry.checks.null_leak || !entry.checks.has_disclaimer) fails++;
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
