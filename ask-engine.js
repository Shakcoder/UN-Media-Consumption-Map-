/**
 * ask-engine.js — the Atlas analyst, running entirely in the browser.
 *
 * No servers, no accounts, no cost. Two stages:
 *   1. UNDERSTAND + RETRIEVE (deterministic): find the countries, regions,
 *      and topics named in the question; pull the matching records from the
 *      Atlas's own published data files; wrap each as numbered evidence.
 *   2. COMPOSE: build a structured, cited answer with real recommendation
 *      logic (channel mix, risk flags, comparisons, trends).
 *
 * ask.html can optionally hand the composed evidence to a small AI model
 * running locally in the visitor's browser (WebLLM) for smoother prose —
 * but the engine below is the source of truth for every number.
 */

const DATA_BASE = "data";

// ---------------------------------------------------------------------------
// Data loading
// ---------------------------------------------------------------------------
let COUNTRIES = null, TRENDS = null, REGISTRY = [];

export async function initEngine() {
  if (COUNTRIES) return true;
  const [cRes, tRes, gRes] = await Promise.all([
    fetch(`${DATA_BASE}/countries.json`, { cache: "no-cache" }),
    fetch(`${DATA_BASE}/trends/topic_intelligence.json`, { cache: "no-cache" }),
    fetch(`${DATA_BASE}/topics.json`, { cache: "no-cache" }),
  ]);
  COUNTRIES = await cRes.json();
  delete COUNTRIES._meta;
  TRENDS = tRes.ok ? await tRes.json() : null;
  // full registry: all 167 tracked topics, including ones currently below
  // the trend-measurement floor (they match questions but report honestly)
  if (gRes.ok) {
    const reg = await gRes.json();
    REGISTRY = (reg.topics || []).map(t => [t.label_en, t.qid]);
  } else if (TRENDS) {
    REGISTRY = Object.entries(TRENDS.topics).map(([qid, t]) => [t.label_en, qid]);
  }
  return true;
}

// ---------------------------------------------------------------------------
// Entity detection (same logic validated in the Worker tests)
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

const REGION_MAP = {
  "east africa": { subregion: "Eastern Africa" }, "eastern africa": { subregion: "Eastern Africa" },
  "west africa": { subregion: "Western Africa" }, "western africa": { subregion: "Western Africa" },
  "north africa": { subregion: "Northern Africa" }, "southern africa": { subregion: "Southern Africa" },
  "central africa": { subregion: "Middle Africa" }, "africa": { region: "Africa" },
  "western europe": { subregion: "Western Europe" }, "eastern europe": { subregion: "Eastern Europe" },
  "northern europe": { subregion: "Northern Europe" }, "southern europe": { subregion: "Southern Europe" },
  "europe": { region: "Europe" },
  "south asia": { subregion: "Southern Asia" }, "southern asia": { subregion: "Southern Asia" },
  "southeast asia": { subregion: "South-Eastern Asia" }, "south-east asia": { subregion: "South-Eastern Asia" },
  "east asia": { subregion: "Eastern Asia" }, "central asia": { subregion: "Central Asia" },
  "middle east": { subregion: "Western Asia" }, "western asia": { subregion: "Western Asia" },
  "asia": { region: "Asia" },
  "latin america": { subregions: ["South America", "Central America", "Caribbean"] },
  "south america": { subregion: "South America" }, "central america": { subregion: "Central America" },
  "caribbean": { subregion: "Caribbean" }, "north america": { subregion: "Northern America" },
  "oceania": { region: "Oceania" }, "pacific": { region: "Oceania" },
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
};

export function detectEntities(question) {
  const q = " " + question.toLowerCase().replace(/[?!.,;:()"]/g, " ").replace(/\s+/g, " ") + " ";
  const found = { countries: [], regions: [], topics: [], wantsTrends: false, wantsCompare: false };

  const nameToIso = {};
  for (const [iso, c] of Object.entries(COUNTRIES)) {
    if (c && c.name) nameToIso[c.name.toLowerCase().replace(/,.*$/, "").trim()] = iso;
  }
  Object.assign(nameToIso, COUNTRY_ALIASES);
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

  const regionKeys = Object.keys(REGION_MAP).sort((a, b) => b.length - a.length);
  for (const rk of regionKeys) {
    if (scrub.includes(" " + rk + " ")) {
      found.regions.push(rk);
      scrub = scrub.split(" " + rk + " ").join(" ");
    }
  }

  const topicLabels = REGISTRY;
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

  const regionCountries = [];
  for (const rk of found.regions) {
    const spec = REGION_MAP[rk];
    for (const [iso, c] of Object.entries(COUNTRIES)) {
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
// Evidence + fact helpers
// ---------------------------------------------------------------------------
function evidenceStore() {
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

function facts(iso) {
  const c = COUNTRIES[iso];
  if (!c) return null;
  const nc = c.news_consumption || {}, inf = c.information_freedom || {},
        conn = c.connectivity || {}, dem = c.demographics || {};
  const tr = TRENDS && TRENDS.countries ? TRENDS.countries[iso] : null;
  return {
    iso, name: c.name, pop: c.population, subregion: c.subregion,
    trust: nc.trust_in_news_pct, tv: nc.tv_as_news_source_pct,
    online: nc.online_as_news_source_pct, social: nc.social_as_news_source_pct,
    radio: nc.radio_as_news_source_pct, surveyNote: nc.survey_note || null,
    survey: nc.source,
    internet: conn.internet_pct == null ? null : Math.round(conn.internet_pct),
    smartphone: conn.smartphone_pct, mci: conn.mobile_connectivity_index,
    medianAge: dem.median_age,
    rsf: inf.press_freedom_score, fh: inf.political_freedom_status,
    fotn: inf.internet_freedom_score, electoral: inf.electoral_democracy,
    under15: dem.age_0_14_pct, urban: dem.urban_pct, literacy: dem.literacy_pct,
    outlets: c.media || {}, languages: c.languages || [],
    rising: tr ? (tr.rising_topics || []) : [],
    distinctive: tr ? (tr.distinctive_topics || []) : [],
  };
}

function addCountryEvidence(f, ev) {
  const bits = [
    `News use & trust: ${f.survey || "no survey integrated yet"}`,
  ];
  if (f.radio != null) bits.push("radio reach: Afrobarometer Round 9 microdata (2023, weighted)");
  bits.push("press freedom: RSF World Press Freedom Index 2025");
  bits.push("political & internet freedom: Freedom House 2026 official data files (incl. electoral-democracy designation)");
  bits.push("connectivity & demographics: World Bank CC BY 4.0 (ICT indicators originally compiled by ITU; literacy by UNESCO Institute for Statistics)");
  if (f.medianAge != null) bits.push("median age: UN DESA World Population Prospects 2024");
  if (f.mci != null) bits.push("mobile connectivity: GSMA Mobile Connectivity Index 2024");
  if (TRENDS) bits.push(`live trends: Wikimedia Pageviews + GDELT, daily engine as of ${TRENDS.generated} (language-weight country attribution — approximation)`);
  return ev.add(`${f.name} — country profile`, "Atlas record. " + bits.join("; ") + ".");
}

const fmt = (v, suffix = "%") => v == null ? "no data" : `${Math.round(v * 10) / 10}${suffix}`;

function riskLines(f, tag) {
  const risks = [];
  if (f.surveyNote)
    risks.push(`Survey caveat for ${f.name}: ${f.surveyNote} ${tag}`);
  if (f.internet != null && f.internet < 40)
    risks.push(`Internet penetration is only ${f.internet}% ${tag} — digital-only campaigns will miss most of the population.`);
  if (f.rsf != null && f.rsf < 40)
    risks.push(`Press-freedom score ${Math.round(f.rsf)}/100 (RSF 2025) ${tag} — a restrictive media environment; plan messenger and content review carefully.`);
  if (f.fh === "Not Free")
    risks.push(`Freedom House rates the country **Not Free** ${tag} — state influence over media is likely.`);
  if (f.trust != null && f.trust < 30)
    risks.push(`Trust in news is low (${f.trust}%) ${tag} — trusted intermediaries may matter more than outlet reach.`);
  return risks;
}

function bestChannel(f) {
  const ch = [["TV", f.tv], ["radio", f.radio], ["online sources", f.online], ["social media", f.social]]
    .filter(x => x[1] != null).sort((a, b) => b[1] - a[1]);
  return ch.length ? ch[0] : null;
}

// ---------------------------------------------------------------------------
// Composers
// ---------------------------------------------------------------------------
function composeCountryBrief(f, ev, wantsTrends) {
  const tag = `[${addCountryEvidence(f, ev)}]`;
  const lines = [];
  const top = bestChannel(f);

  if (wantsTrends && f.rising.length) {
    lines.push(`**Trending in ${f.name} right now** (as of ${TRENDS.generated}):`);
    for (const r of f.rising.slice(0, 5))
      lines.push(`- **${r.label_en}** +${Math.round(r.velocity * 100)}% vs its 30-day baseline ${tag}`);
    if (f.distinctive.length) {
      lines.push(`\nDistinctive interests vs the world average: ${f.distinctive.slice(0, 4).map(d => `**${d.label_en}** (${d.vs_global_avg}×)`).join(", ")} ${tag}`);
    }
    lines.push("");
  }

  if (top && top[1] != null) lines.push(`**${f.name}: ${top[0]} leads for news reach — ${fmt(top[1])} weekly** ${tag}`);
  else lines.push(`**${f.name} — media profile** ${tag}`);
  lines.push("");
  if (f.radio != null) {
    lines.push(`- Radio as a weekly news source: ${fmt(f.radio)} ${tag} *(Afrobarometer Round 9 microdata — the leading channel in much of Africa)*`);
  }
  if (f.tv == null && f.online == null && f.social == null && f.radio == null) {
    lines.push(`- The Atlas has no news-source survey for ${f.name} (not yet covered by the Reuters Institute DNR or the regional barometers integrated so far) ${tag} — the figures below are connectivity, freedom, and demographics.`);
  } else {
    lines.push(`- News sources (weekly reach): TV ${fmt(f.tv)}, online ${fmt(f.online)}, social media ${fmt(f.social)} ${tag} *(survey: ${f.survey || "n/a"})*`);
  }
  if (f.trust != null) lines.push(`- Trust in news: ${f.trust}% ${tag}`);
  lines.push(`- Connectivity: ${fmt(f.internet)} internet penetration${f.smartphone != null ? `, ${fmt(f.smartphone)} smartphone adoption` : ""}${f.mci != null ? `, GSMA mobile connectivity index ${f.mci}/100` : ""} ${tag}`);
  if (f.rsf != null) lines.push(`- Press freedom: ${Math.round(f.rsf)}/100 (RSF 2025); political status: ${f.fh || "n/a"}${f.electoral != null ? `; electoral democracy: ${f.electoral ? "yes" : "no"}` : ""} ${tag}`);
  if (f.under15 != null || f.urban != null || f.medianAge != null) lines.push(`- Audience structure: ${f.medianAge != null ? `median age ${f.medianAge}, ` : ""}${f.under15 != null ? `${fmt(f.under15)} under 15, ` : ""}${f.urban != null ? `${fmt(f.urban)} urban, ` : ""}${f.literacy != null ? `${fmt(f.literacy)} literacy` : ""} ${tag}`);
  const o = f.outlets;
  if (o.top_tv || o.top_radio) lines.push(`- Leading outlets — TV: ${o.top_tv || "n/a"}; radio: ${o.top_radio || "n/a"}; online: ${o.top_online_news || "n/a"} ${tag}`);

  if (!wantsTrends && f.rising.length) {
    lines.push(`- Rising topics this week: ${f.rising.slice(0, 3).map(r => `${r.label_en} (+${Math.round(r.velocity * 100)}%)`).join(", ")} ${tag}`);
  }

  const risks = riskLines(f, tag);
  if (risks.length) {
    lines.push("");
    lines.push("**Risks & caveats:**");
    for (const r of risks) lines.push("- " + r);
  }
  return lines.join("\n");
}

function composeComparison(fs, ev) {
  const ids = fs.map(f => `[${addCountryEvidence(f, ev)}]`);
  const lines = [];

  // headline: biggest contrast
  const withTrust = fs.filter(f => f.trust != null);
  if (withTrust.length >= 2) {
    const hi = withTrust.reduce((a, b) => a.trust > b.trust ? a : b);
    const lo = withTrust.reduce((a, b) => a.trust < b.trust ? a : b);
    if (hi.iso !== lo.iso)
      lines.push(`**${hi.name} leads on news trust (${hi.trust}% vs ${lo.name}'s ${lo.trust}%).**\n`);
  }

  lines.push(`| | ${fs.map(f => f.name).join(" | ")} |`);
  lines.push(`|---|${fs.map(() => "---").join("|")}|`);
  const row = (label, key, suffix = "%") =>
    `| ${label} | ${fs.map(f => f[key] == null ? "no data" : Math.round(f[key] * 10) / 10 + suffix).join(" | ")} |`;
  lines.push(row("Trust in news", "trust"));
  lines.push(row("TV for news (weekly)", "tv"));
  if (fs.some(f => f.radio != null)) lines.push(row("Radio for news (weekly)", "radio"));
  lines.push(row("Online sources", "online"));
  lines.push(row("Social media", "social"));
  lines.push(row("Internet penetration", "internet"));
  lines.push(row("Press freedom (RSF /100)", "rsf", ""));
  lines.push(`| Political status | ${fs.map(f => f.fh || "n/a").join(" | ")} |`);
  lines.push("");
  lines.push(fs.map((f, i) => `${f.name} ${ids[i]}`).join(" · "));
  lines.push("");

  // channel guidance
  const digital = fs.filter(f => f.online != null && f.tv != null && f.online >= f.tv);
  const broadcast = fs.filter(f => f.online != null && f.tv != null && f.tv > f.online);
  if (digital.length && broadcast.length) {
    lines.push(`**Channel guidance:** online-first works in ${digital.map(f => f.name).join(", ")}; in ${broadcast.map(f => f.name).join(", ")} TV still out-reaches online — plan a split strategy.`);
  }
  const allRisks = fs.flatMap((f, i) => riskLines(f, ids[i]));
  if (allRisks.length) {
    lines.push("");
    lines.push("**Risks & caveats:**");
    for (const r of allRisks) lines.push("- " + r);
  }
  return lines.join("\n");
}

function composeRegionBrief(fs, ev, topic, regionName) {
  const lines = [];
  const ids = {};
  for (const f of fs) ids[f.iso] = `[${addCountryEvidence(f, ev)}]`;

  const digital = fs.filter(f => f.internet != null && f.internet >= 55).sort((a, b) => (b.online || 0) - (a.online || 0));
  const mixed = fs.filter(f => f.internet != null && f.internet >= 35 && f.internet < 55);
  const broadcast = fs.filter(f => f.internet != null && f.internet < 35);

  lines.push(`**${regionName}: split the strategy by connectivity — the gap between countries is decisive.**\n`);
  if (digital.length)
    lines.push(`- **Digital-first:** ${digital.map(f => `${f.name} (online news ${fmt(f.online)}, internet ${f.internet}% ${ids[f.iso]})`).join("; ")}.`);
  if (mixed.length)
    lines.push(`- **Mixed digital + broadcast:** ${mixed.map(f => `${f.name} (internet ${f.internet}%, TV ${fmt(f.tv)} ${ids[f.iso]})`).join("; ")}.`);
  if (broadcast.length)
    lines.push(`- **Broadcast/community-first:** ${broadcast.map(f => `${f.name} (internet only ${f.internet}%, TV ${fmt(f.tv)} ${ids[f.iso]})`).join("; ")}. Digital-only campaigns would structurally miss most people here.`);

  if (topic) {
    const t = TRENDS.topics[topic.qid];
    if (t) {
      const tid = `[${ev.add(`Topic: ${t.label_en}`, `Daily trend engine as of ${TRENDS.generated}. Demand = Wikipedia reading patterns; coverage = GDELT news monitoring.`)}]`;
      lines.push("");
      lines.push(`**${t.label_en} right now:** globally ${t.momentum} (${t.global_velocity > 0 ? "+" : ""}${Math.round(t.global_velocity * 100)}% vs 30-day baseline) ${tid}.`);
      const local = fs.filter(f => f.distinctive.some(d => d.label_en === t.label_en) || f.rising.some(r => r.label_en === t.label_en));
      if (local.length)
        lines.push(`Above-average or rising attention in: ${local.map(f => f.name).join(", ")} ${local.map(f => ids[f.iso]).join("")}.`);
    }
  }

  const allRisks = fs.flatMap(f => riskLines(f, ids[f.iso])).slice(0, 5);
  if (allRisks.length) {
    lines.push("");
    lines.push("**Risks & caveats:**");
    for (const r of allRisks) lines.push("- " + r);
  }
  lines.push("");
  lines.push("*The Atlas has no age-segmented platform data for most countries — youth targeting above is inferred from population structure and platform norms, not measured crosstabs.*");
  return lines.join("\n");
}

function composeTopicBrief(topic, ev) {
  const t = TRENDS && TRENDS.topics ? TRENDS.topics[topic.qid] : null;
  if (!t) {
    return `**${topic.label}** is one of the Atlas's 167 tracked topics, but its measured attention is currently below the reliability floor, so no trend report is available for it right now. Country-level media data may still help — try naming a country or region alongside the topic.`;
  }
  const tid = `[${ev.add(`Topic: ${t.label_en}`, `Daily trend engine as of ${TRENDS.generated}. Demand = Wikipedia reading patterns (what people look up); coverage = GDELT news monitoring (what media publish).`)}]`;
  const lines = [];
  lines.push(`**${t.label_en} — ${t.momentum} globally** (${t.global_velocity > 0 ? "+" : ""}${Math.round(t.global_velocity * 100)}% attention vs its 30-day baseline, as of ${TRENDS.generated}) ${tid}\n`);
  const langs = Object.entries(t.demand_by_language || {}).slice(0, 6);
  if (langs.length)
    lines.push(`- Demand by language (daily lookups): ${langs.map(([l, v]) => `${l.toUpperCase()} ${Math.round(v.weekly_daily_avg_views).toLocaleString()}/day (${v.velocity > 0 ? "+" : ""}${Math.round(v.velocity * 100)}%)`).join("; ")} ${tid}`);
  if (t.news_articles_7d != null)
    lines.push(`- News coverage: ${t.news_articles_7d.toLocaleString()} articles in the last 7 days (GDELT) ${tid}`);
  const cov = (t.top_covering_media_countries || []).slice(0, 6);
  if (cov.length)
    lines.push(`- Media coverage concentrated in: ${cov.map(c => `${c.iso3} (${c.coverage_share_pct}%)`).join(", ")} ${tid}`);
  // countries where this topic is distinctive
  const hot = [];
  if (TRENDS.countries) {
    for (const [iso, tr] of Object.entries(TRENDS.countries)) {
      const d = (tr.distinctive_topics || []).find(x => x.label_en === t.label_en);
      if (d && COUNTRIES[iso]) hot.push([COUNTRIES[iso].name, d.vs_global_avg]);
    }
  }
  hot.sort((a, b) => b[1] - a[1]);
  if (hot.length)
    lines.push(`- Countries with above-average attention: ${hot.slice(0, 6).map(([n, x]) => `${n} (${x}×)`).join(", ")} ${tid}`);
  return lines.join("\n");
}

// ---------------------------------------------------------------------------
// Main entry
// ---------------------------------------------------------------------------
export function answerQuestion(question) {
  const ev = evidenceStore();
  const ents = detectEntities(question);
  const parts = [];

  const isoList = [...new Set([...ents.countries, ...ents.regionCountries])];

  if (ents.regions.length && isoList.length > 2) {
    const fs = isoList.map(facts).filter(Boolean);
    const regionName = ents.regions.map(r => r.replace(/\b\w/g, ch => ch.toUpperCase())).join(", ");
    parts.push(composeRegionBrief(fs, ev, ents.topics[0] || null, regionName));
  } else if (ents.wantsCompare && isoList.length >= 2) {
    parts.push(composeComparison(isoList.map(facts).filter(Boolean), ev));
    for (const t of ents.topics) {
      const tb = composeTopicBrief(t, ev);
      if (tb) parts.push(tb);
    }
  } else if (isoList.length >= 1) {
    for (const iso of isoList.slice(0, 3)) {
      const f = facts(iso);
      if (f) parts.push(composeCountryBrief(f, ev, ents.wantsTrends));
    }
    for (const t of ents.topics) {
      const tb = composeTopicBrief(t, ev);
      if (tb) parts.push(tb);
    }
  } else if (ents.topics.length) {
    for (const t of ents.topics) {
      const tb = composeTopicBrief(t, ev);
      if (tb) parts.push(tb);
    }
  }

  if (!parts.length) {
    return {
      answer: "I couldn't match your question to the Atlas's data. I can answer questions about **specific countries or regions** (all 195 UN member states) and **167 tracked topics** (climate, health, refugees, AI, misinformation, gender equality…). Try naming a country, a region like *East Africa*, or a topic — for example: *\"Compare news trust in France and Germany\"* or *\"What is trending in Nigeria?\"*",
      evidence: [],
      entities: ents,
    };
  }

  return { answer: parts.join("\n\n---\n\n"), evidence: ev.list(), entities: ents };
}
