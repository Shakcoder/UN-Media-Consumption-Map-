/**
 * UN Media Atlas — "Ask the Analyst" backend (Cloudflare Worker)
 * ==============================================================
 *
 * ZERO-COST DESIGN. This Worker answers plain-English questions about the
 * Atlas using Cloudflare's FREE Workers AI allowance (open models such as
 * Llama running on Cloudflare's servers — no API key, no credit card, no
 * monthly bill). It works in two steps:
 *
 *   1. RETRIEVE (deterministic code, no AI): find the countries, regions,
 *      and topics mentioned in the question and pull the exact matching
 *      records from the Atlas's published data files. Each record becomes
 *      a numbered piece of evidence (E1, E2, ...).
 *   2. WRITE (free AI model): the model receives ONLY the question and the
 *      evidence pack, and writes the answer with [E#] citation tags. It is
 *      instructed to refuse rather than guess beyond the evidence.
 *
 * Because retrieval is deterministic and the model only summarizes what it
 * was handed, answers stay grounded in the verified data.
 *
 * OPTIONAL UPGRADE: if an ANTHROPIC_API_KEY secret is ever added (paid),
 * the Worker automatically switches to Claude with full multi-step tool
 * use — nothing else needs to change. Without the key it uses the free
 * Workers AI path. See worker/DEPLOY_GUIDE.md for the 15-minute setup.
 */

// ---------------------------------------------------------------------------
// Configuration
// ---------------------------------------------------------------------------
const SITE_ORIGIN = "https://shakcoder.github.io";           // allowed browser origin (CORS)
const DATA_BASE = "https://shakcoder.github.io/UN-Media-Consumption-Map-/data";
const DATA_CACHE_SECONDS = 1800;
const MAX_QUESTION_CHARS = 600;

// Free path (Workers AI). The 70B model gives the best writing; if the daily
// free allowance runs low the Worker automatically retries on the small model.
const CF_MODEL_PRIMARY = "@cf/meta/llama-3.3-70b-instruct-fp8-fast";
const CF_MODEL_FALLBACK = "@cf/meta/llama-3.1-8b-instruct";

// Paid path (only used if the secret exists).
const ANTHROPIC_MODEL = "claude-sonnet-5";
const MAX_TOOL_ROUNDS = 6;

// ---------------------------------------------------------------------------
// Shared writing rules (both engines)
// ---------------------------------------------------------------------------
const ANALYST_RULES = `You are the analyst for the UN Global Media Consumption Atlas — an evidence-first assistant for UN communications officers. You advise on where and how to communicate: media landscapes, platform use and trust, press/internet freedom, connectivity, and live topic trends.

Absolute rules:
1. Use ONLY the evidence provided. EVERY factual number or claim must carry its evidence tag, e.g. "online news use is 91% weekly [E1]". Never invent numbers, sources, or tags.
2. If the evidence does not cover part of the question, say so plainly ("The Atlas has no data on X") — never fill gaps from general knowledge.
3. Weigh non-digital channels seriously: where the data shows TV/radio out-reaching online or internet penetration is low, say so and recommend accordingly. Never assume digital-first.
4. Flag risks when the data shows them: internet penetration under ~40%, press-freedom score under 40/100, political freedom "Not Free".
5. Structure: a bolded one-line recommendation or headline finding first; then the key numbers with tags; then risks/caveats; then one line on what the data does not cover, if relevant. Use **bold** and simple bullet/table formatting. Be concise and plain-spoken.
6. Answer in the language of the question.
7. You advise on channels, formats, timing, audiences. You do not write political messaging or take political positions.`;

// ---------------------------------------------------------------------------
// Atlas data access (cached per Worker instance)
// ---------------------------------------------------------------------------
let _cache = { at: 0, countries: null, trends: null };

async function loadData() {
  const now = Date.now();
  if (_cache.countries && now - _cache.at < DATA_CACHE_SECONDS * 1000) return _cache;
  const [cRes, tRes] = await Promise.all([
    fetch(`${DATA_BASE}/countries.json`, { cf: { cacheTtl: DATA_CACHE_SECONDS } }),
    fetch(`${DATA_BASE}/trends/topic_intelligence.json`, { cf: { cacheTtl: DATA_CACHE_SECONDS } }),
  ]);
  if (!cRes.ok) throw new Error("countries.json fetch failed: " + cRes.status);
  const countries = await cRes.json();
  const trends = tRes.ok ? await tRes.json() : null;
  delete countries._meta;
  _cache = { at: now, countries, trends };
  return _cache;
}

function makeEvidenceStore() {
  const items = [];
  return {
    add(title, detail) {
      const id = "E" + (items.length + 1);
      items.push({ id, title, detail });
      return id;
    },
    list: () => items,
  };
}

// ---------------------------------------------------------------------------
// STEP 1 — deterministic entity detection (no AI involved)
// ---------------------------------------------------------------------------
const COUNTRY_ALIASES = {
  "usa": "USA", "united states": "USA", "america": "USA", "us": "USA",
  "uk": "GBR", "britain": "GBR", "united kingdom": "GBR", "england": "GBR",
  "drc": "COD", "dr congo": "COD", "democratic republic of the congo": "COD",
  "congo-kinshasa": "COD", "congo brazzaville": "COG", "republic of the congo": "COG",
  "ivory coast": "CIV", "cote d'ivoire": "CIV", "côte d'ivoire": "CIV",
  "south korea": "KOR", "north korea": "PRK", "russia": "RUS", "syria": "SYR",
  "iran": "IRN", "vietnam": "VNM", "laos": "LAO", "bolivia": "BOL",
  "venezuela": "VEN", "tanzania": "TZA", "moldova": "MDA", "brunei": "BRN",
  "turkey": "TUR", "türkiye": "TUR", "czechia": "CZE", "czech republic": "CZE",
  "uae": "ARE", "emirates": "ARE", "saudi": "SAU", "saudi arabia": "SAU",
  "burma": "MMR", "myanmar": "MMR", "cape verde": "CPV", "east timor": "TLS",
  "gambia": "GMB", "bahamas": "BHS", "kyrgyzstan": "KGZ", "slovakia": "SVK",
  "somalia": "SOM", "micronesia": "FSM", "eswatini": "SWZ", "swaziland": "SWZ",
  "palestine": "PSE", "vatican": "VAT", "holy see": "VAT",
};

// Region phrases -> filter over the country list (region or subregion values).
const REGION_MAP = {
  "east africa": { subregion: "Eastern Africa" },
  "eastern africa": { subregion: "Eastern Africa" },
  "west africa": { subregion: "Western Africa" },
  "western africa": { subregion: "Western Africa" },
  "north africa": { subregion: "Northern Africa" },
  "southern africa": { subregion: "Southern Africa" },
  "central africa": { subregion: "Middle Africa" },
  "africa": { region: "Africa" },
  "europe": { region: "Europe" },
  "western europe": { subregion: "Western Europe" },
  "eastern europe": { subregion: "Eastern Europe" },
  "northern europe": { subregion: "Northern Europe" },
  "southern europe": { subregion: "Southern Europe" },
  "asia": { region: "Asia" },
  "south asia": { subregion: "Southern Asia" },
  "southern asia": { subregion: "Southern Asia" },
  "southeast asia": { subregion: "South-Eastern Asia" },
  "south-east asia": { subregion: "South-Eastern Asia" },
  "east asia": { subregion: "Eastern Asia" },
  "central asia": { subregion: "Central Asia" },
  "middle east": { subregion: "Western Asia" },
  "western asia": { subregion: "Western Asia" },
  "latin america": { subregions: ["South America", "Central America", "Caribbean"] },
  "south america": { subregion: "South America" },
  "central america": { subregion: "Central America" },
  "caribbean": { subregion: "Caribbean" },
  "north america": { subregion: "Northern America" },
  "oceania": { region: "Oceania" },
  "pacific": { region: "Oceania" },
};

const TOPIC_SYNONYMS = {
  "ai": "Artificial intelligence", "artificial intelligence": "Artificial intelligence",
  "climate": "Climate change", "global warming": "Climate change",
  "covid": "COVID-19", "coronavirus": "COVID-19",
  "refugees": "Refugee", "migration": "Human migration", "migrants": "Human migration",
  "vaccines": "Vaccine", "vaccination": "Vaccination",
  "misinformation": "Misinformation", "disinformation": "Disinformation",
  "fake news": "Fake news", "gender": "Gender equality",
  "women's rights": "Women's rights", "press freedom": "Freedom of the press",
  "food": "Food security", "hunger": "Hunger", "famine": "Famine",
  "war": "War", "health": "Mental health",
};

function detectEntities(question, countries, trends) {
  const q = " " + question.toLowerCase().replace(/[?!.,;:()"]/g, " ").replace(/\s+/g, " ") + " ";
  const found = { countries: [], regions: [], topics: [], wantsTrends: false, wantsCompare: false };

  // country names from the data itself
  const nameToIso = {};
  for (const [iso, c] of Object.entries(countries)) {
    if (c && c.name) nameToIso[c.name.toLowerCase().replace(/,.*$/, "").trim()] = iso;
  }
  Object.assign(nameToIso, COUNTRY_ALIASES);
  // longest names first so "south africa" wins over "africa" handling later
  const names = Object.keys(nameToIso).sort((a, b) => b.length - a.length);
  let scrub = q;
  for (const nm of names) {
    if (nm.length < 3) continue;
    const idx = scrub.indexOf(" " + nm + " ") >= 0 ? scrub.indexOf(" " + nm + " ")
      : (scrub.includes(" " + nm) && nm.length > 4 ? scrub.indexOf(" " + nm) : -1);
    if (idx >= 0) {
      const iso = nameToIso[nm];
      if (!found.countries.includes(iso)) found.countries.push(iso);
      scrub = scrub.replace(new RegExp(" " + nm.replace(/[.*+?^${}()|[\]\\]/g, "\\$&"), "g"), " ");
    }
  }

  // regions (checked on the scrubbed string so "South Africa" doesn't trigger "africa")
  const regionKeys = Object.keys(REGION_MAP).sort((a, b) => b.length - a.length);
  for (const rk of regionKeys) {
    if (scrub.includes(" " + rk + " ")) {
      found.regions.push(rk);
      scrub = scrub.split(" " + rk + " ").join(" ");
    }
  }

  // topics: synonyms first, then the tracked topic labels
  const topicLabels = trends ? Object.entries(trends.topics).map(([qid, t]) => [t.label_en, qid]) : [];
  for (const [syn, label] of Object.entries(TOPIC_SYNONYMS)) {
    if (q.includes(" " + syn + " ")) {
      const hit = topicLabels.find(([l]) => l === label);
      if (hit && !found.topics.some(t => t.qid === hit[1])) found.topics.push({ label: hit[0], qid: hit[1] });
    }
  }
  for (const [label, qid] of topicLabels) {
    const l = label.toLowerCase();
    if (l.length >= 4 && q.includes(l) && !found.topics.some(t => t.qid === qid)) {
      found.topics.push({ label, qid });
    }
  }
  found.topics = found.topics.slice(0, 3);

  found.wantsTrends = /trend|trending|rising|right now|this week|currently|interested in|care about|popular topic/.test(q);
  found.wantsCompare = /compare|versus| vs |difference between|better than/.test(q) || found.countries.length >= 2;

  // expand regions to concrete country lists (largest populations first, cap 8)
  const regionCountries = [];
  for (const rk of found.regions) {
    const spec = REGION_MAP[rk];
    for (const [iso, c] of Object.entries(countries)) {
      if (!c || !c.subregion) continue;
      const match = spec.region ? c.region === spec.region
        : spec.subregion ? c.subregion === spec.subregion
        : spec.subregions.includes(c.subregion);
      if (match) regionCountries.push([iso, c.population || 0]);
    }
  }
  regionCountries.sort((a, b) => b[1] - a[1]);
  found.regionCountries = [...new Set(regionCountries.map(x => x[0]))].slice(0, 8);

  return found;
}

// ---------------------------------------------------------------------------
// Country/topic record formatting (shared by both engines' evidence packs)
// ---------------------------------------------------------------------------
function countryRecord(iso, countries, trends, ev) {
  const c = countries[iso];
  if (!c) return null;
  const nc = c.news_consumption || {}, inf = c.information_freedom || {},
        conn = c.connectivity || {}, dem = c.demographics || {};
  const rec = {
    name: c.name, iso3: iso, region: `${c.region} / ${c.subregion}`,
    population: c.population,
    news_use_weekly_pct: {
      tv: nc.tv_as_news_source_pct, online: nc.online_as_news_source_pct,
      social_media: nc.social_as_news_source_pct, trust_in_news: nc.trust_in_news_pct,
      survey: nc.source,
    },
    connectivity: {
      internet_users_pct: conn.internet_pct == null ? null : Math.round(conn.internet_pct),
      smartphone_pct: conn.smartphone_pct, mobile_per_100: conn.mobile_per_100,
    },
    freedom: {
      press_freedom_score_rsf_0to100: inf.press_freedom_score,
      political_freedom_status_fh: inf.political_freedom_status,
      internet_freedom_score_fh: inf.internet_freedom_score,
      electoral_democracy: inf.electoral_democracy,
    },
    audience: { under_15_pct: dem.age_0_14_pct, urban_pct: dem.urban_pct, literacy_pct: dem.literacy_pct },
    top_outlets: c.media ? { tv: c.media.top_tv, radio: c.media.top_radio, online: c.media.top_online_news, social: c.media.top_social } : null,
    languages: c.languages,
  };
  const tr = trends && trends.countries ? trends.countries[iso] : null;
  if (tr) {
    rec.trending_now = {
      as_of: trends.generated,
      rising: (tr.rising_topics || []).slice(0, 5).map(r => `${r.label_en} +${Math.round(r.velocity * 100)}%`),
      distinctive_interests: (tr.distinctive_topics || []).slice(0, 5).map(d => `${d.label_en} ${d.vs_global_avg}x global average`),
    };
  }
  const id = ev.add(`${c.name} — country profile`,
    `Atlas record. News use & trust: ${nc.source || "n/a"}. Freedom: RSF 2025 + Freedom House 2026 official files. Connectivity/demographics: World Bank (retrieved ${c.retrieved_on || "n/a"}).` +
    (tr ? ` Trends: daily engine as of ${trends.generated} (Wikipedia reading patterns; language-weight country attribution — approximation).` : ""));
  return { id, rec };
}

function topicRecord(qid, trends, ev) {
  const t = trends && trends.topics ? trends.topics[qid] : null;
  if (!t) return null;
  const rec = {
    topic: t.label_en, category: t.category, momentum: t.momentum,
    global_velocity_7d_vs_30d: t.global_velocity,
    demand_by_language: t.demand_by_language,
    news_articles_last_7d: t.news_articles_7d,
    media_coverage_by_country: (t.top_covering_media_countries || []).slice(0, 8),
    as_of: trends.generated,
  };
  const id = ev.add(`Topic: ${t.label_en}`,
    `Daily trend engine as of ${trends.generated}. Demand = Wikipedia reading patterns (what people look up); coverage = GDELT news monitoring (what media publish).`);
  return { id, rec };
}

// ---------------------------------------------------------------------------
// FREE ENGINE — retrieve deterministically, then one Workers AI writing call
// ---------------------------------------------------------------------------
async function askAnalystFree(question, env) {
  const { countries, trends } = await loadData();
  const ev = makeEvidenceStore();
  const ents = detectEntities(question, countries, trends);

  // Assemble the evidence pack
  const pack = [];
  const isoList = [...new Set([...ents.countries, ...ents.regionCountries])].slice(0, 8);
  for (const iso of isoList) {
    const r = countryRecord(iso, countries, trends, ev);
    if (r) pack.push({ evidence_id: r.id, data: r.rec });
  }
  for (const t of ents.topics) {
    const r = topicRecord(t.qid, trends, ev);
    if (r) pack.push({ evidence_id: r.id, data: r.rec });
  }

  // Nothing recognized: refuse deterministically (costs no AI quota).
  if (pack.length === 0) {
    return {
      answer: "I couldn't match your question to the Atlas's data. I can answer questions about **specific countries or regions** (all 195 UN member states) and **167 tracked topics** (climate, health, refugees, AI, misinformation, gender equality…). Try naming a country, a region like *East Africa*, or a topic — for example: *\"Compare news trust in France and Germany\"* or *\"What is trending in Nigeria?\"*",
      evidence: [],
      engine: "retrieval-only",
    };
  }

  const prompt = `${ANALYST_RULES}

EVIDENCE PACK (the only information you may use — cite by evidence_id):
${JSON.stringify(pack, null, 1)}

QUESTION: ${question}

Write the analyst's answer now, following the rules exactly. Tag every figure with its [E#].`;

  const runModel = async (model) => env.AI.run(model, {
    messages: [{ role: "user", content: prompt }],
    max_tokens: 1200,
    temperature: 0.2,
  });

  let out;
  try {
    out = await runModel(CF_MODEL_PRIMARY);
  } catch (e) {
    // daily free allowance exhausted on the big model, or model hiccup —
    // retry once on the small model before giving up
    out = await runModel(CF_MODEL_FALLBACK);
  }
  const text = (out && (out.response || out.result || "")).trim();
  if (!text) throw new Error("Workers AI returned an empty response.");

  const citedIds = new Set([...text.matchAll(/\[E(\d+)\]/g)].map(m => "E" + m[1]));
  const evidence = ev.list().filter(e => citedIds.has(e.id));
  return { answer: text, evidence: evidence.length ? evidence : ev.list(), engine: "workers-ai" };
}

// ---------------------------------------------------------------------------
// PAID ENGINE (optional) — full agentic tool use with Claude.
// Active only when the ANTHROPIC_API_KEY secret exists.
// ---------------------------------------------------------------------------
const TOOLS = [
  { name: "list_countries",
    description: "List countries (ISO3, name, region, subregion). Optional region filter: Africa, Americas, Asia, Europe, Oceania.",
    input_schema: { type: "object", properties: { region: { type: "string" } } } },
  { name: "get_country",
    description: "Full media/connectivity/freedom/trends profile for one country by ISO3.",
    input_schema: { type: "object", properties: { iso3: { type: "string" } }, required: ["iso3"] } },
  { name: "compare_countries",
    description: "Compare up to 8 countries on core indicators.",
    input_schema: { type: "object", properties: { iso3_list: { type: "array", items: { type: "string" } } }, required: ["iso3_list"] } },
  { name: "search_topics",
    description: "Find tracked topics by keyword among 167 UN-relevant topics.",
    input_schema: { type: "object", properties: { query: { type: "string" } }, required: ["query"] } },
  { name: "get_topic",
    description: "Live trend detail for one topic by QID.",
    input_schema: { type: "object", properties: { qid: { type: "string" } }, required: ["qid"] } },
  { name: "trending_in_country",
    description: "Rising/top/distinctive topics for one country by ISO3.",
    input_schema: { type: "object", properties: { iso3: { type: "string" } }, required: ["iso3"] } },
];

async function runTool(name, input, ev) {
  const { countries, trends } = await loadData();

  if (name === "list_countries") {
    const rows = Object.entries(countries)
      .filter(([, c]) => !input.region || c.region === input.region)
      .map(([iso, c]) => `${iso} ${c.name} (${c.subregion})`);
    return { text: rows.join("\n"), cite: null };
  }
  if (name === "get_country") {
    const iso = String(input.iso3 || "").toUpperCase();
    const r = countryRecord(iso, countries, trends, ev);
    if (!r) return { text: `No country with ISO3 code ${iso} in the Atlas.`, cite: null };
    return { text: JSON.stringify(r.rec), cite: [r.id] };
  }
  if (name === "compare_countries") {
    const list = (input.iso3_list || []).slice(0, 8).map(s => String(s).toUpperCase());
    const rows = [];
    for (const iso of list) {
      const c = countries[iso];
      if (!c) { rows.push({ iso3: iso, error: "not found" }); continue; }
      const nc = c.news_consumption || {}, inf = c.information_freedom || {}, conn = c.connectivity || {};
      rows.push({
        iso3: iso, name: c.name, population: c.population,
        trust_pct: nc.trust_in_news_pct, tv_pct: nc.tv_as_news_source_pct,
        online_pct: nc.online_as_news_source_pct, social_pct: nc.social_as_news_source_pct,
        internet_pct: conn.internet_pct == null ? null : Math.round(conn.internet_pct),
        smartphone_pct: conn.smartphone_pct,
        press_freedom_score: inf.press_freedom_score,
        political_freedom: inf.political_freedom_status,
      });
    }
    const id = ev.add(`Comparison: ${list.join(", ")}`,
      "Atlas records. News figures: Reuters Institute DNR 2026 / Afrobarometer R9 / regional barometers. Connectivity: World Bank. Freedom: RSF 2025, Freedom House 2026.");
    return { text: JSON.stringify(rows), cite: [id] };
  }
  if (name === "search_topics") {
    if (!trends) return { text: "Trend data unavailable right now.", cite: null };
    const q = String(input.query || "").toLowerCase();
    const hits = Object.entries(trends.topics)
      .filter(([, t]) => t.label_en.toLowerCase().includes(q))
      .slice(0, 12)
      .map(([qid, t]) => ({ qid, label: t.label_en, category: t.category, momentum: t.momentum }));
    return { text: hits.length ? JSON.stringify(hits) : `No tracked topic matches "${input.query}".`, cite: null };
  }
  if (name === "get_topic") {
    if (!trends) return { text: "Trend data unavailable right now.", cite: null };
    const r = topicRecord(input.qid, trends, ev);
    if (!r) return { text: `No topic ${input.qid}.`, cite: null };
    return { text: JSON.stringify(r.rec), cite: [r.id] };
  }
  if (name === "trending_in_country") {
    if (!trends) return { text: "Trend data unavailable right now.", cite: null };
    const iso = String(input.iso3 || "").toUpperCase();
    const tr = trends.countries[iso];
    const cname = countries[iso] ? countries[iso].name : iso;
    if (!tr) return { text: `No trend profile for ${cname} — below the measurement floor. Survey data in get_country still applies.`, cite: null };
    const out = {
      country: cname, as_of: trends.generated,
      rising_topics: (tr.rising_topics || []).map(r => ({ topic: r.label_en, velocity_pct: Math.round(r.velocity * 100) })),
      top_attention: (tr.top_topics || []).slice(0, 8),
      distinctive_vs_world: tr.distinctive_topics || [],
    };
    const id = ev.add(`${cname} — trending topics`,
      `Daily trend engine as of ${trends.generated}; Wikipedia reading patterns via language-population weights (approximation).`);
    return { text: JSON.stringify(out), cite: [id] };
  }
  return { text: `Unknown tool ${name}.`, cite: null };
}

async function askAnalystClaude(question, apiKey) {
  const ev = makeEvidenceStore();
  const messages = [{ role: "user", content: question }];

  for (let round = 0; round <= MAX_TOOL_ROUNDS; round++) {
    const resp = await fetch("https://api.anthropic.com/v1/messages", {
      method: "POST",
      headers: { "content-type": "application/json", "x-api-key": apiKey, "anthropic-version": "2023-06-01" },
      body: JSON.stringify({
        model: ANTHROPIC_MODEL, max_tokens: 1600, temperature: 0.2,
        system: ANALYST_RULES + "\nYou have tools that read the Atlas database — use them for every lookup.",
        tools: TOOLS, messages,
      }),
    });
    if (!resp.ok) throw new Error(`Claude API ${resp.status}: ${(await resp.text()).slice(0, 300)}`);
    const data = await resp.json();

    if (data.stop_reason !== "tool_use") {
      const text = data.content.filter(b => b.type === "text").map(b => b.text).join("\n");
      const citedIds = new Set([...text.matchAll(/\[E(\d+)\]/g)].map(m => "E" + m[1]));
      return { answer: text, evidence: ev.list().filter(e => citedIds.has(e.id)), engine: "claude" };
    }
    messages.push({ role: "assistant", content: data.content });
    const results = [];
    for (const block of data.content) {
      if (block.type !== "tool_use") continue;
      let result;
      try { result = await runTool(block.name, block.input || {}, ev); }
      catch (e) { result = { text: "Tool error: " + e.message, cite: null }; }
      const cited = result.cite && result.cite.length ? `\n\n[Cite the above as: ${result.cite.join(", ")}]` : "";
      results.push({ type: "tool_result", tool_use_id: block.id, content: result.text + cited });
    }
    messages.push({ role: "user", content: results });
  }
  return { answer: "I hit my lookup limit — please ask a narrower question.", evidence: ev.list(), engine: "claude" };
}

// ---------------------------------------------------------------------------
// HTTP plumbing
// ---------------------------------------------------------------------------
function corsHeaders(origin) {
  const allowed = origin === SITE_ORIGIN || origin === "http://localhost:8899";
  return {
    "Access-Control-Allow-Origin": allowed ? origin : SITE_ORIGIN,
    "Access-Control-Allow-Methods": "POST, OPTIONS",
    "Access-Control-Allow-Headers": "content-type",
    "content-type": "application/json",
  };
}

// Exported for local testing under Node (harmless in Cloudflare).
export { detectEntities, countryRecord, topicRecord, makeEvidenceStore, loadData, runTool };

export default {
  async fetch(request, env) {
    const origin = request.headers.get("Origin") || "";
    const headers = corsHeaders(origin);

    if (request.method === "OPTIONS") return new Response(null, { headers });
    if (request.method !== "POST")
      return new Response(JSON.stringify({ ok: true, usage: 'POST {"question": "..."}' }), { headers });

    let body;
    try { body = await request.json(); } catch {
      return new Response(JSON.stringify({ error: "Invalid JSON body." }), { status: 400, headers });
    }
    const question = String(body.question || "").trim().slice(0, MAX_QUESTION_CHARS);
    if (!question)
      return new Response(JSON.stringify({ error: "Empty question." }), { status: 400, headers });

    try {
      let result;
      if (env.ANTHROPIC_API_KEY) {
        result = await askAnalystClaude(question, env.ANTHROPIC_API_KEY);   // optional paid upgrade
      } else if (env.AI) {
        result = await askAnalystFree(question, env);                        // free path (default)
      } else {
        return new Response(JSON.stringify({
          error: "The Worker is deployed but the free AI binding is missing. In the Cloudflare dashboard: Worker → Settings → Bindings → Add → Workers AI, name it exactly AI. (See worker/DEPLOY_GUIDE.md.)",
        }), { status: 500, headers });
      }
      return new Response(JSON.stringify(result), { headers });
    } catch (e) {
      return new Response(JSON.stringify({ error: "Analyst error: " + e.message }), { status: 502, headers });
    }
  },
};
