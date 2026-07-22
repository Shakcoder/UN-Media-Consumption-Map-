#!/usr/bin/env node
/**
 * run_consulting_review.mjs — captures raw engine output for the 20
 * consulting-review prompts so the answers can be read and graded by hand.
 *
 * Writes eval/consulting_review_outputs.json (pretty-printed array of
 * {prompt, answer, evidence_titles}).
 *
 * Usage: node scripts/run_consulting_review.mjs
 * Needs: Node 18+, no packages. Paths are script-relative.
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

const PROMPTS = [
  "Where should we distribute a vaccination campaign in Nigeria?",
  "How do we reach policymakers in Brussels about climate policy?",
  "How do we counter vaccine misinformation in Brazil?",
  "Reaching rural farmers in Mali with agricultural content",
  "Distribution strategy for youth climate content in Kenya",
  "Where should we distribute cyclone early-warning content in Fiji?",
  "Full media strategy for a girls'-education campaign in Afghanistan",
  "Strategy memo for a water-sanitation campaign in Bolivia",
  "How should we roll out refugee-awareness content across East Africa?",
  "Distribution strategy for food security messaging in the Sahel",
  "How do we launch climate content in Germany?",
  "Media plan for humanitarian messaging in Myanmar",
  "How should DGC distribute peacekeeping content in the DRC?",
  "Strategy for launching gender-equality content in Saudi Arabia",
  "Rollout plan for anti-trafficking content in Thailand",
  "How do we promote content about the UN in the United States?",
  "Crisis communication plan for an outbreak in Sudan",
  "How do we engage young people in Japan with UN content?",
  "Best way to distribute content in the Holy See",
  "Where should we distribute climate content in Tuvalu?",
];

const engine = await import(join(ROOT, "ask-engine.js"));
await engine.initEngine();

const out = [];
for (const prompt of PROMPTS) {
  engine.resetConversation();           // each prompt stands alone
  const entry = { prompt };
  try {
    const r = engine.answerQuestion(prompt);
    entry.answer = r.answer || "";
    entry.evidence_titles = (r.evidence || []).map(e => e.title);
    if (r.clarify) {
      entry.clarify_question = r.clarify.question;
      entry.clarify_options = r.clarify.options;
    }
  } catch (e) {
    entry.answer = "";
    entry.evidence_titles = [];
    entry.error = e.message;
    entry.stack = String(e.stack || "").split("\n").slice(0, 4).join("\n");
  }
  out.push(entry);
}

await mkdir(join(ROOT, "eval"), { recursive: true });
const OUT_PATH = join(ROOT, "eval", "consulting_review_outputs.json");
await writeFile(OUT_PATH, JSON.stringify(out, null, 2));

const empty = out.filter(e => !e.answer || !e.answer.trim());
console.log(`Consulting review: ${out.length} prompts run, ${out.length - empty.length} with non-empty answers.`);
console.log(`Results: ${OUT_PATH}`);
if (empty.length) {
  console.log("\nEMPTY ANSWERS:");
  for (const e of empty) console.log(`  - ${e.prompt}${e.error ? "\n      " + e.error : ""}`);
  process.exit(1);
}
