#!/usr/bin/env node
/**
 * run_strategy_review.mjs — one-off: run 18 strategy-style prompts through
 * the real browser engine (ask-engine.js) and dump the raw outputs to
 * eval/strategy_review_outputs.json for review.
 *
 * Usage:  node scripts/run_strategy_review.mjs   (Node 18+, no packages)
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

const { initEngine, answerQuestion, resetConversation } = await import(
  new URL("../ask-engine.js", import.meta.url).href
);

const PROMPTS = [
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

await initEngine();

const results = [];
for (const prompt of PROMPTS) {
  resetConversation();
  let entry;
  try {
    const r = answerQuestion(prompt);
    entry = {
      prompt,
      answer: r.answer,
      evidence_titles: (r.evidence || []).map((e) => e.title),
      followups: r.followups || [],
    };
  } catch (err) {
    entry = { prompt, answer: null, error: String(err && err.stack || err), evidence_titles: [], followups: [] };
  }
  results.push(entry);
  const ok = typeof entry.answer === "string" && entry.answer.trim().length > 0;
  console.log(`${ok ? "OK  " : "FAIL"} ${prompt}`);
}

await mkdir(join(ROOT, "eval"), { recursive: true });
const outPath = join(ROOT, "eval", "strategy_review_outputs.json");
await writeFile(outPath, JSON.stringify(results, null, 2) + "\n");
console.log("Wrote " + outPath);
