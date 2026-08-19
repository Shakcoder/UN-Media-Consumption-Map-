#!/usr/bin/env node
/**
 * probe_ask.mjs — phrasing probe for the AI Analyst.
 * ===================================================
 * Runs a list of questions through the REAL engine (ask-engine.js) and
 * reports, for each one, how the engine understood it: which route it took,
 * which entities it recognised, and whether it dead-ended (generic refusal)
 * or asked to clarify. Used to test that different phrasings of the same
 * question land on the same, relevant answer.
 *
 * Usage:  node scripts/probe_ask.mjs questions.json      (JSON array of strings)
 *         node scripts/probe_ask.mjs "one question"      (single question)
 *
 * Output: JSON array to stdout, one entry per question:
 *   { q, route, refusal, clarify, gap, entities, answerHead }
 *   - route:    which composing route answered ("country", "rank", ... or null)
 *   - refusal:  true if the generic "I couldn't match that" fallback fired
 *   - clarify:  the clarifying question asked, or null
 *   - entities: what was recognised (countries, regions, topics, measures...)
 *
 * Each question runs with conversation state reset, so probes are independent
 * (add "FOLLOWUP:" prefix to a question to keep the previous state instead).
 */

import { readFile } from "node:fs/promises";
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

const engine = await import(join(ROOT, "ask-engine.js"));
await engine.initEngine();

const arg = process.argv[2];
if (!arg) {
  console.error("Usage: node scripts/probe_ask.mjs <questions.json | \"question\">");
  process.exit(1);
}
let questions;
try {
  questions = JSON.parse(await readFile(arg, "utf8"));
} catch {
  questions = [arg];
}

const out = [];
for (const raw of questions) {
  const isFollowup = typeof raw === "string" && raw.startsWith("FOLLOWUP:");
  const q = isFollowup ? raw.slice("FOLLOWUP:".length).trim() : raw;
  if (!isFollowup) engine.resetConversation();
  let entry = { q };
  try {
    const r = engine.answerQuestion(q);
    const routeStep = (r.reasoning || []).find(s => /\*\*Chose the \w+ route\*\*/.test(s));
    entry.route = routeStep ? routeStep.match(/Chose the (\w+) route/)[1] : null;
    entry.refusal = !!(r.answer && r.answer.startsWith("I couldn't match"));
    entry.clarify = r.clarify ? r.clarify.question : null;
    entry.gap = entry.route === "gap";
    const e = r.entities || {};
    entry.entities = {
      countries: e.countries || [],
      regions: e.regions || [],
      topics: (e.topics || []).map(t => t.label),
      attributes: e.attributes || [],
      platforms: e.platforms || [],
      intents: e.intents || [],
    };
    entry.answerHead = (r.answer || "").slice(0, 400);
  } catch (err) {
    entry.error = err.message;
  }
  out.push(entry);
}
console.log(JSON.stringify(out, null, 2));
