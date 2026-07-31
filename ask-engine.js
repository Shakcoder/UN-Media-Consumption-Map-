/**
 * ask-engine.js — the Atlas analyst, running entirely in the browser.
 * ====================================================================
 *
 * No servers, no accounts, no cost, nothing to maintain. The engine:
 *
 *   1. UNDERSTANDS the question — tolerant of typos ("Nigerai"), aliases
 *      ("DRC", "Ivory Coast"), demonyms ("Kenyan audiences"), synonyms
 *      ("press freedom" = "media freedom"), rankings ("top 5 by radio"),
 *      comparisons, vague asks (it asks a clarifying question back), and
 *      follow-ups ("what about radio there?").
 *   2. RETRIEVES the matching records from the Atlas's published data files.
 *      Retrieval is deterministic — every number in an answer is real.
 *   3. COMPOSES a structured answer with recommendation logic, risk flags,
 *      and a per-answer source list (rendered by ask.html as numbered footnotes).
 *
 * The public contract (used by ask.html):
 *   await initEngine()
 *   const r = answerQuestion("...")
 *   // r = { answer, evidence:[{id,title,detail,links:[{label,url}]}],
 *   //       followups:[..], clarify:{question,options:[..]}|null, entities }
 *   resetConversation()   // clears follow-up memory (new session)
 *
 * MAINTENANCE (for non-coders): the lookup tables below (COUNTRY_ALIASES,
 * DEMONYMS, TOPIC_SYNONYMS, ATTRIBUTES) are plain lists — adding a line is
 * safe and is all that's usually needed to teach the analyst a new word.
 */

const DATA_BASE = "data";

// ---------------------------------------------------------------------------
// Data loading
// ---------------------------------------------------------------------------
let COUNTRIES = null, TRENDS = null, REGISTRY = [], META = null, AD_MARKET = null, TV_STATIONS = null;
let NAME_TO_ISO = {};   // every recognizable name/alias/demonym -> ISO3
let GENERATED = new Set();  // machine-generated demonyms: exact-match only, never fuzzy targets

export async function initEngine() {
  if (COUNTRIES) return true;
  const [cRes, tRes, gRes, aRes, tvRes] = await Promise.all([
    fetch(`${DATA_BASE}/countries.json`, { cache: "no-cache" }),
    fetch(`${DATA_BASE}/trends/topic_intelligence.json`, { cache: "no-cache" }),
    fetch(`${DATA_BASE}/topics.json`, { cache: "no-cache" }),
    fetch(`${DATA_BASE}/ad_market.json`, { cache: "no-cache" }).catch(() => null),
    fetch(`${DATA_BASE}/tv_stations.json`, { cache: "no-cache" }).catch(() => null),
  ]);
  if (!cRes.ok) throw new Error("countries.json failed to load (" + cRes.status + ")");
  COUNTRIES = await cRes.json();
  META = COUNTRIES._meta || null;
  delete COUNTRIES._meta;
  TRENDS = tRes.ok ? await tRes.json() : null;
  // Ad-market signals (industry estimates, annual hand-update) — optional:
  // the analyst degrades gracefully when the file is absent.
  AD_MARKET = (aRes && aRes.ok) ? await aRes.json().catch(() => null) : null;
  // Extended TV-station lists (Wikipedia lists gated through Wikidata,
  // monthly refresh) — optional layer under the curated top_tv line.
  TV_STATIONS = (tvRes && tvRes.ok) ? await tvRes.json().catch(() => null) : null;
  // full registry: all tracked topics, including ones currently below the
  // trend-measurement floor (they match questions and report honestly)
  if (gRes.ok) {
    const reg = await gRes.json();
    REGISTRY = (reg.topics || []).map(t => [t.label_en, t.qid]);
  } else if (TRENDS) {
    REGISTRY = Object.entries(TRENDS.topics).map(([qid, t]) => [t.label_en, qid]);
  }
  buildNameIndex();
  return true;
}

// ---------------------------------------------------------------------------
// Name index: official names + aliases + generated & irregular demonyms
// ---------------------------------------------------------------------------
const COUNTRY_ALIASES = {
  "usa": "USA", "united states": "USA", "america": "USA", "us": "USA",
  "uk": "GBR", "britain": "GBR", "united kingdom": "GBR", "england": "GBR",
  "drc": "COD", "dr congo": "COD", "democratic republic of the congo": "COD",
  "congo-kinshasa": "COD", "congo brazzaville": "COG", "republic of the congo": "COG",
  "ivory coast": "CIV", "cote d'ivoire": "CIV", "côte d'ivoire": "CIV", "cote divoire": "CIV",
  "south korea": "KOR", "north korea": "PRK", "korea": "KOR",
  "russia": "RUS", "syria": "SYR", "iran": "IRN", "vietnam": "VNM", "viet nam": "VNM",
  "laos": "LAO", "bolivia": "BOL", "venezuela": "VEN", "tanzania": "TZA",
  "moldova": "MDA", "brunei": "BRN", "turkey": "TUR", "türkiye": "TUR", "turkiye": "TUR",
  "czechia": "CZE", "czech republic": "CZE", "uae": "ARE", "emirates": "ARE",
  "united arab emirates": "ARE", "saudi": "SAU", "saudi arabia": "SAU",
  "burma": "MMR", "myanmar": "MMR", "cape verde": "CPV", "cabo verde": "CPV",
  "east timor": "TLS", "timor leste": "TLS", "timor-leste": "TLS",
  "gambia": "GMB", "the gambia": "GMB", "bahamas": "BHS", "kyrgyzstan": "KGZ",
  "slovakia": "SVK", "somalia": "SOM", "micronesia": "FSM",
  "eswatini": "SWZ", "swaziland": "SWZ", "palestine": "PSE", "vatican": "VAT",
  "holy see": "VAT", "netherlands": "NLD", "holland": "NLD", "macedonia": "MKD",
  "north macedonia": "MKD", "bosnia": "BIH", "bosnia and herzegovina": "BIH",
  "sri lanka": "LKA", "new zealand": "NZL", "png": "PNG", "papua new guinea": "PNG",
  // NOTE: no "car" alias. It resolved the ordinary English noun — "which
  // platform for a car safety campaign?" returned a full strategic brief on
  // the Central African Republic. The country stays reachable by its name
  // and by "centrafrique"; a bare "CAR" is too costly to guess at.
  "central african republic": "CAF", "centrafrique": "CAF", "south sudan": "SSD",
  "south africa": "ZAF", "burkina": "BFA", "burkina faso": "BFA",
  "philippines": "PHL", "the philippines": "PHL", "china": "CHN", "prc": "CHN",
  "hong kong": "CHN", "taiwan": "CHN",
};

// Irregular demonyms the suffix generator below can't derive.
const DEMONYMS = {
  "french": "FRA", "dutch": "NLD", "swiss": "CHE", "greek": "GRC", "danish": "DNK",
  "swedish": "SWE", "finnish": "FIN", "polish": "POL", "spanish": "ESP",
  "portuguese": "PRT", "german": "DEU", "turkish": "TUR", "chinese": "CHN",
  "japanese": "JPN", "korean": "KOR", "thai": "THA", "vietnamese": "VNM",
  "filipino": "PHL", "british": "GBR", "english": "GBR", "irish": "IRL",
  "welsh": "GBR", "scottish": "GBR", "icelandic": "ISL", "norwegian": "NOR",
  "american": "USA", "argentine": "ARG", "argentinian": "ARG", "brazilian": "BRA",
  "mexican": "MEX", "peruvian": "PER", "chilean": "CHL", "cuban": "CUB",
  "haitian": "HTI", "canadian": "CAN", "emirati": "ARE", "saudi arabian": "SAU",
  "israeli": "ISR", "iranian": "IRN", "iraqi": "IRQ", "syrian": "SYR",
  "lebanese": "LBN", "jordanian": "JOR", "yemeni": "YEM", "omani": "OMN",
  "qatari": "QAT", "kuwaiti": "KWT", "bahraini": "BHR", "egyptian": "EGY",
  "moroccan": "MAR", "algerian": "DZA", "tunisian": "TUN", "libyan": "LBY",
  "sudanese": "SDN", "ethiopian": "ETH", "somali": "SOM", "kenyan": "KEN",
  "ugandan": "UGA", "tanzanian": "TZA", "rwandan": "RWA", "burundian": "BDI",
  "congolese": "COD", "nigerian": "NGA", "ghanaian": "GHA", "ivorian": "CIV",
  "senegalese": "SEN", "malian": "MLI", "beninese": "BEN", "togolese": "TGO",
  "cameroonian": "CMR", "gabonese": "GAB", "chadian": "TCD", "nigerien": "NER",
  "burkinabe": "BFA", "guinean": "GIN", "liberian": "LBR", "sierra leonean": "SLE",
  "gambian": "GMB", "mauritanian": "MRT", "malagasy": "MDG", "mozambican": "MOZ",
  "zambian": "ZMB", "zimbabwean": "ZWE", "malawian": "MWI", "botswanan": "BWA",
  "namibian": "NAM", "south african": "ZAF", "angolan": "AGO", "basotho": "LSO",
  "indian": "IND", "pakistani": "PAK", "bangladeshi": "BGD", "nepali": "NPL",
  "nepalese": "NPL", "bhutanese": "BTN", "afghan": "AFG", "uzbek": "UZB",
  "kazakh": "KAZ", "kyrgyz": "KGZ", "tajik": "TJK", "turkmen": "TKM",
  "mongolian": "MNG", "indonesian": "IDN", "malaysian": "MYS", "singaporean": "SGP",
  "cambodian": "KHM", "laotian": "LAO", "burmese": "MMR", "australian": "AUS",
  "fijian": "FJI", "russian": "RUS", "ukrainian": "UKR", "belarusian": "BLR",
  "georgian": "GEO", "armenian": "ARM", "azerbaijani": "AZE", "italian": "ITA",
  "romanian": "ROU", "bulgarian": "BGR", "hungarian": "HUN", "austrian": "AUT",
  "belgian": "BEL", "czech": "CZE", "slovak": "SVK", "slovenian": "SVN",
  "croatian": "HRV", "serbian": "SRB", "albanian": "ALB", "bosnian": "BIH",
  "maltese": "MLT", "cypriot": "CYP", "estonian": "EST", "latvian": "LVA",
  "lithuanian": "LTU", "colombian": "COL", "venezuelan": "VEN", "ecuadorian": "ECU",
  "bolivian": "BOL", "paraguayan": "PRY", "uruguayan": "URY", "guatemalan": "GTM",
  "honduran": "HND", "salvadoran": "SLV", "nicaraguan": "NIC", "costa rican": "CRI",
  "panamanian": "PAN", "dominican": "DOM", "jamaican": "JAM",
};

// Words that must never fuzzy-match to a country/topic (too common).
const FUZZY_STOPWORDS = new Set(("about media radio trust trends trend where which what should could would there their world " +
  "global country countries region regions people online social news best most least top how when who why whom " +
  "compare versus against between audience audiences platform platforms content campaign campaigns publish reach " +
  "target young youth women rural urban digital internet mobile phone television broadcast press freedom score " +
  "data source sources right now week today please thanks hello focus strategy channel channels format formats " +
  "highest lowest largest smallest better worse worst rising falling popular attention interest interested local " +
  "national levels level rates rate percent percentage share tell show give list find help plan advice info " +
  "trending comparing ranking targeting reaching publishing measuring growing changing " +
  "child children woman women man men adult adults human humans person little large small major minor " +
  // Gender vocabulary is core to audience segmentation here, so it must never
  // resolve to a place: the Maldives' capital normalises to "male", which made
  // "how do we reach male audiences in Brazil?" pull the Maldives into the
  // answer alongside Brazil. The Maldives stays reachable by name.
  "male female males females boy boys girl girls").split(/\s+/));

function buildNameIndex() {
  NAME_TO_ISO = {};
  for (const [iso, c] of Object.entries(COUNTRIES)) {
    if (!c || !c.name) continue;
    const full = c.name.toLowerCase().trim();
    NAME_TO_ISO[full] = iso;
    // normalize() turns hyphens into spaces, so hyphenated names need a
    // space-separated variant too ("guinea-bissau" → "guinea bissau")
    if (full.includes("-")) NAME_TO_ISO[full.replace(/-/g, " ")] = iso;
    const short = full.replace(/,.*$/, "").trim();     // "Tanzania, United Rep." -> "tanzania"
    if (short.length >= 3) NAME_TO_ISO[short] = iso;
    if (short.includes("-")) NAME_TO_ISO[short.replace(/-/g, " ")] = iso;
    // Capital cities resolve to their country ("policy audiences in Brussels")
    // — exact-match only (GENERATED) so they never pollute fuzzy matching.
    //
    // Six countries record more than one seat of government, with the role in
    // brackets ("Pretoria (executive), Cape Town (legislative), Bloemfontein
    // (judicial)"). Indexing the whole string made every one of those cities
    // unfindable, so each is split out and indexed on its own; the bracketed
    // qualifier is dropped because nobody types it.
    for (const part of String(c.capital || "").split(",")) {
      const cap = part.replace(/\(.*?\)/g, " ")
        .toLowerCase().replace(/[?!.,;:()"]/g, " ").replace(/\s+/g, " ").trim();
      if (cap.length >= 4 && !(cap in NAME_TO_ISO) && !FUZZY_STOPWORDS.has(cap)) {
        NAME_TO_ISO[cap] = iso;
        GENERATED.add(cap);
      }
    }
    // generated demonyms for single-word names: kenya->kenyan, chad->chadian…
    if (!short.includes(" ") && short.length >= 4) {
      const gens = [short + "n", short + "an", short + "ian",
                    short.replace(/y$/, "ian"), short.replace(/a$/, "an"),
                    short.replace(/e$/, "ian"), short + "ese", short + "i"];
      for (const g of gens) {
        if (g !== short && g.length >= 5 && !(g in NAME_TO_ISO) && !FUZZY_STOPWORDS.has(g)) {
          NAME_TO_ISO[g] = iso;
          GENERATED.add(g);   // catch "kenyan" typed exactly, but never fuzzy-match to it
        }
      }
    }
  }
  Object.assign(NAME_TO_ISO, COUNTRY_ALIASES);
  Object.assign(NAME_TO_ISO, DEMONYMS);      // explicit demonyms win over generated
}

// ---------------------------------------------------------------------------
// Fuzzy matching (typo tolerance)
// ---------------------------------------------------------------------------
function levenshtein(a, b, cap) {
  // Damerau-Levenshtein (optimal string alignment): counts a swap of two
  // adjacent letters ("nigerai" → "nigeria") as ONE edit — the most common typo.
  if (Math.abs(a.length - b.length) > cap) return cap + 1;
  let prev2 = null, prev = new Array(b.length + 1), cur = new Array(b.length + 1);
  for (let j = 0; j <= b.length; j++) prev[j] = j;
  for (let i = 1; i <= a.length; i++) {
    cur[0] = i;
    let rowMin = i;
    for (let j = 1; j <= b.length; j++) {
      cur[j] = Math.min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (a[i - 1] === b[j - 1] ? 0 : 1));
      if (prev2 && i > 1 && j > 1 && a[i - 1] === b[j - 2] && a[i - 2] === b[j - 1])
        cur[j] = Math.min(cur[j], prev2[j - 2] + 1);
      if (cur[j] < rowMin) rowMin = cur[j];
    }
    if (rowMin > cap) return cap + 1;
    prev2 = prev.slice();
    [prev, cur] = [cur, prev];
  }
  return prev[b.length];
}

const fuzzyCap = (len) => len >= 9 ? 2 : len >= 5 ? 1 : 0;

/**
 * Find the single best fuzzy match for `phrase` among `keys`.
 * `canon` maps a key to its canonical id (e.g. "nigeria"→NGA, "nigerian"→NGA);
 * ties are only fatal when the tied keys point to DIFFERENT canonical ids.
 */
function bestFuzzy(phrase, keys, canon) {
  const cap = fuzzyCap(phrase.length);
  if (cap === 0) return null;
  const c = canon || ((k) => k);
  let best = null, bestD = cap + 1, conflict = false;
  for (const k of keys) {
    const d = levenshtein(phrase, k, cap);
    if (d < bestD) { bestD = d; best = k; conflict = false; }
    else if (d === bestD && best && c(k) !== c(best)) conflict = true;
  }
  return (best && bestD <= cap && !conflict) ? best : null;
}

// ---------------------------------------------------------------------------
// Vocabulary: regions, topics, attributes, platforms, audiences
// ---------------------------------------------------------------------------
// Continent membership is built from SUBREGIONS, never from the data's
// `region` field. That field comes from the World Bank's country groupings,
// where "Europe & Central Asia" is collapsed to "Europe" — so Armenia,
// Azerbaijan, Georgia and the five Central Asian republics are filed under
// region "Europe" even though their subregion says Western/Central Asia.
// Trusting `region` put Uzbekistan at the top of "European countries by trust
// in news" and left every Central Asian country out of "Asia". The subregion
// values are correct, so they are what membership is defined from.
const EUROPE_SUBREGIONS = ["Northern Europe", "Western Europe", "Southern Europe", "Eastern Europe", "Central Europe"];
const ASIA_SUBREGIONS = ["Eastern Asia", "South-Eastern Asia", "Southern Asia", "Western Asia", "Central Asia"];
// The Balkans and Scandinavia cut across UN subregions, so they get explicit
// country lists like the Sahel and the Nordics do. "Southern Europe" was
// standing in for the Balkans, which made Spain, Andorra, San Marino and Malta
// the top "Balkan" markets while leaving Bulgaria and Romania out entirely.
const BALKANS = ["ALB", "BIH", "BGR", "GRC", "HRV", "MKD", "MNE", "ROU", "SRB", "SVN"];
const SCANDINAVIA = ["DNK", "NOR", "SWE"];
const GCC = ["SAU", "ARE", "QAT", "KWT", "BHR", "OMN"];

const REGION_MAP = {
  "east africa": { subregion: "Eastern Africa" }, "eastern africa": { subregion: "Eastern Africa" },
  "west africa": { subregion: "Western Africa" }, "western africa": { subregion: "Western Africa" },
  "north africa": { subregion: "Northern Africa" }, "northern africa": { subregion: "Northern Africa" },
  "southern africa": { subregion: "Southern Africa" },
  "central africa": { subregion: "Middle Africa" }, "middle africa": { subregion: "Middle Africa" },
  // Both spellings are listed because normalize() replaces hyphens with
  // spaces before lookup: the hyphenated key alone could never match, and
  // the question silently fell through to "africa" — quietly folding North
  // Africa into a Sub-Saharan answer.
  "sub-saharan africa": { subregions: ["Eastern Africa", "Western Africa", "Southern Africa", "Middle Africa"] },
  "sub saharan africa": { subregions: ["Eastern Africa", "Western Africa", "Southern Africa", "Middle Africa"] },
  "africa": { region: "Africa" },
  "western europe": { subregion: "Western Europe" }, "eastern europe": { subregion: "Eastern Europe" },
  "northern europe": { subregion: "Northern Europe" }, "southern europe": { subregion: "Southern Europe" },
  "central europe": { subregion: "Central Europe" },
  "scandinavia": { isos: SCANDINAVIA }, "the balkans": { isos: BALKANS },
  "balkans": { isos: BALKANS }, "balkan": { isos: BALKANS },
  "europe": { subregions: EUROPE_SUBREGIONS },
  "south asia": { subregion: "Southern Asia" }, "southern asia": { subregion: "Southern Asia" },
  "southeast asia": { subregion: "South-Eastern Asia" }, "south-east asia": { subregion: "South-Eastern Asia" },
  "south east asia": { subregion: "South-Eastern Asia" },
  "east asia": { subregion: "Eastern Asia" }, "eastern asia": { subregion: "Eastern Asia" },
  "central asia": { subregion: "Central Asia" },
  "middle east": { subregion: "Western Asia" }, "western asia": { subregion: "Western Asia" },
  // "the Gulf" means the six GCC states in UN comms usage — the same list the
  // "gulf states"/"gcc" keys below already carry. Left as the whole Western
  // Asia subregion it returned Türkiye, Iraq, Syria and Azerbaijan as Gulf
  // markets and buried the actual Gulf states.
  "gulf": { isos: GCC }, "the gulf": { isos: GCC },
  "mena": { subregions: ["Western Asia", "Northern Africa"] },
  "asia": { subregions: ASIA_SUBREGIONS },
  "latin america": { subregions: ["South America", "Central America", "Caribbean"] },
  "south america": { subregion: "South America" }, "central america": { subregion: "Central America" },
  "caribbean": { subregion: "Caribbean" }, "north america": { subregion: "Northern America" },
  "oceania": { region: "Oceania" }, "pacific": { region: "Oceania" },
  "the americas": { region: "Americas" }, "americas": { region: "Americas" },
  // adjective forms ("African countries", "European audiences")
  "african": { region: "Africa" }, "european": { subregions: EUROPE_SUBREGIONS },
  "asian": { subregions: ASIA_SUBREGIONS },
  // European subregions need adjective forms too, or "Eastern European
  // countries" silently widens to the whole continent
  "eastern european": { subregion: "Eastern Europe" }, "western european": { subregion: "Western Europe" },
  "northern european": { subregion: "Northern Europe" }, "southern european": { subregion: "Southern Europe" },
  "central european": { subregion: "Central Europe" },
  "east african": { subregion: "Eastern Africa" },
  "west african": { subregion: "Western Africa" }, "north african": { subregion: "Northern Africa" },
  "southern african": { subregion: "Southern Africa" }, "central african": { subregion: "Middle Africa" },
  "middle eastern": { subregion: "Western Asia" }, "south asian": { subregion: "Southern Asia" },
  "southeast asian": { subregion: "South-Eastern Asia" }, "east asian": { subregion: "Eastern Asia" },
  "central asian": { subregion: "Central Asia" }, "latin american": { subregions: ["South America", "Central America", "Caribbean"] },
  "caribbean island": { subregion: "Caribbean" }, "south american": { subregion: "South America" },
  "oceanian": { region: "Oceania" }, "pacific island": { region: "Oceania" },
  // named zones that cut across UN subregions — explicit country lists
  "sahel": { isos: ["MRT", "SEN", "MLI", "BFA", "NER", "NGA", "TCD", "SDN", "ERI"] },
  "the sahel": { isos: ["MRT", "SEN", "MLI", "BFA", "NER", "NGA", "TCD", "SDN", "ERI"] },
  "horn of africa": { isos: ["ETH", "ERI", "DJI", "SOM"] },
  "the horn of africa": { isos: ["ETH", "ERI", "DJI", "SOM"] },
  "maghreb": { isos: ["MAR", "DZA", "TUN", "LBY", "MRT"] },
  "the gulf states": { isos: GCC },
  "gulf states": { isos: GCC },
  "gcc": { isos: GCC },
  "nordics": { isos: ["DNK", "NOR", "SWE", "FIN", "ISL"] },
  "the nordics": { isos: ["DNK", "NOR", "SWE", "FIN", "ISL"] },
  "nordic": { isos: ["DNK", "NOR", "SWE", "FIN", "ISL"] },
  "nordic countries": { isos: ["DNK", "NOR", "SWE", "FIN", "ISL"] },
  "scandinavian": { isos: SCANDINAVIA },
  "mediterranean": { isos: ["ESP", "FRA", "ITA", "GRC", "TUR", "EGY", "MAR", "DZA", "TUN", "LBY", "ISR", "LBN", "CYP", "MLT", "HRV", "ALB", "MNE", "SVN"] },
  "brics": { isos: ["BRA", "RUS", "IND", "CHN", "ZAF"] },
  "g20": { isos: ["ARG", "AUS", "BRA", "CAN", "CHN", "FRA", "DEU", "IND", "IDN", "ITA", "JPN", "KOR", "MEX", "RUS", "SAU", "ZAF", "TUR", "GBR", "USA"] },
  "donor countries": { isos: ["USA", "DEU", "JPN", "GBR", "FRA", "CAN", "ITA", "NLD", "SWE", "NOR", "CHE", "AUS", "DNK", "ESP", "KOR"] },
  "pacific islands": { isos: ["FJI", "PNG", "SLB", "VUT", "WSM", "TON", "KIR", "FSM", "MHL", "PLW", "NRU", "TUV"] },
  "the pacific islands": { isos: ["FJI", "PNG", "SLB", "VUT", "WSM", "TON", "KIR", "FSM", "MHL", "PLW", "NRU", "TUV"] },
  "latam": { subregions: ["South America", "Central America", "Caribbean"] },
};

// Pretty display names for region keys whose key text is an adjective or
// lowercase phrase ("african" must never render as a region heading).
const REGION_DISPLAY = {
  "african": "Africa", "european": "Europe", "asian": "Asia", "oceanian": "Oceania",
  "eastern european": "Eastern Europe", "western european": "Western Europe",
  "northern european": "Northern Europe", "southern european": "Southern Europe",
  "central european": "Central Europe",
  "balkans": "the Balkans", "the balkans": "the Balkans", "balkan": "the Balkans",
  "gulf": "the Gulf states", "the gulf": "the Gulf states",
  "east african": "Eastern Africa", "west african": "Western Africa",
  "north african": "Northern Africa", "southern african": "Southern Africa",
  "central african": "Middle Africa", "middle eastern": "the Middle East",
  "south asian": "Southern Asia", "southeast asian": "South-Eastern Asia",
  "east asian": "Eastern Asia", "central asian": "Central Asia",
  "latin american": "Latin America", "south american": "South America",
  "caribbean island": "the Caribbean", "pacific island": "the Pacific",
  "mena": "the Middle East & North Africa", "sahel": "the Sahel", "the sahel": "the Sahel",
  "horn of africa": "the Horn of Africa", "the horn of africa": "the Horn of Africa",
  "maghreb": "the Maghreb", "the gulf states": "the Gulf states", "gulf states": "the Gulf states",
  "gcc": "the Gulf states", "nordics": "the Nordic countries", "the nordics": "the Nordic countries",
  "nordic": "the Nordic countries", "nordic countries": "the Nordic countries",
  "scandinavian": "Scandinavia", "mediterranean": "the Mediterranean",
  "brics": "the BRICS countries", "g20": "the G20", "donor countries": "major donor countries",
  "pacific islands": "the Pacific islands", "the pacific islands": "the Pacific islands",
  "latam": "Latin America",
};
/** Case-insensitive test: does country (iso, c) belong to a REGION_MAP spec? */
function inRegionSpec(spec, iso, c) {
  if (!c || !c.subregion) return false;
  const eq = (a, b) => String(a || "").toLowerCase() === String(b || "").toLowerCase();
  if (spec.isos) return spec.isos.includes(iso);
  if (spec.region) return eq(c.region, spec.region);
  if (spec.subregion) return eq(c.subregion, spec.subregion);
  return (spec.subregions || []).some(s2 => eq(c.subregion, s2));
}

const regionDisplay = (rk) => REGION_DISPLAY[rk] || titleCase(rk);

const TOPIC_SYNONYMS = {
  "ai": "Artificial intelligence", "artificial intelligence": "Artificial intelligence",
  "machine learning": "Artificial intelligence", "chatbots": "ChatGPT",
  "climate": "Climate change", "global warming": "Climate change", "climate crisis": "Climate change",
  "covid": "COVID-19", "coronavirus": "COVID-19", "pandemic": "COVID-19",
  "refugees": "Refugee", "refugee crisis": "Refugee",
  "migration": "Human migration", "migrants": "Human migration", "immigration": "Human migration",
  "vaccines": "Vaccine", "vaccination": "Vaccination", "vaccinations": "Vaccination",
  "misinformation": "Misinformation", "disinformation": "Disinformation",
  "fake news": "Fake news", "gender": "Gender equality", "gender equality": "Gender equality",
  "women's rights": "Women's rights", "womens rights": "Women's rights",
  "women rights": "Women's rights",
  "press freedom": "Freedom of the press", "media freedom": "Freedom of the press",
  "food": "Food security", "food security": "Food security", "hunger": "Hunger", "famine": "Famine",
  "sea level": "Sea level rise", "sea levels": "Sea level rise",
  "renewables": "Renewable energy", "renewable energy": "Renewable energy",
  "solar": "Solar energy", "nuclear": "Nuclear power",
  "crypto": "Cryptocurrency", "bitcoin": "Cryptocurrency",
  "mental health": "Mental health", "malaria": "Malaria", "hiv": "HIV/AIDS", "aids": "HIV/AIDS",
  "polio": "Polio", "cholera": "Cholera", "ebola": "Ebola",
  "drought": "Drought", "flooding": "Flood", "floods": "Flood",
  "deforestation": "Deforestation", "biodiversity": "Biodiversity",
  "plastic": "Plastic pollution", "plastic pollution": "Plastic pollution",
  "child labour": "Child labour", "child labor": "Child labour",
  "human trafficking": "Human trafficking", "corruption": "Corruption",
  "peacekeeping": "Peacekeeping", "terrorism": "Terrorism",
  "poverty": "Poverty", "inequality": "Economic inequality",
  "education": "Education", "literacy": "Literacy",
  "clean water": "Drinking water", "sanitation": "Sanitation", "water": "Drinking water",
  // labels too short for the ≥4-char label matcher — reachable via synonyms only
  "war": "War", "armed conflict": "War", "conflict": "War", "5g": "5G",
  // campaign-subject phrasings that must reach their tracked topic
  "trafficking": "Human trafficking", "anti trafficking": "Human trafficking",
  "cyclone": "Tropical cyclone", "cyclones": "Tropical cyclone", "cyclone preparedness": "Tropical cyclone",
  "hurricane": "Tropical cyclone", "hurricanes": "Tropical cyclone", "typhoon": "Tropical cyclone",
  "water sanitation": "Sanitation", "wash": "Sanitation",
  // precision synonyms: route to the EXACT tracked topic, not a broader cousin
  "climate adaptation": "Climate change adaptation", "climate change adaptation": "Climate change adaptation",
  "adaptation to climate change": "Climate change adaptation",
  "ai governance": "Regulation of artificial intelligence", "ai regulation": "Regulation of artificial intelligence",
  "regulation of ai": "Regulation of artificial intelligence", "ai safety": "Regulation of artificial intelligence",
  "ai policy": "Regulation of artificial intelligence",
  "humanitarian": "Humanitarian aid", "humanitarian topics": "Humanitarian aid", "humanitarian aid": "Humanitarian aid",
};

// Attributes the analyst can rank, look up, and compare on.
const ATTRIBUTES = {
  internet:   { label: "Internet penetration", unit: "%", get: f => f.internet,
                words: ["internet", "internet penetration", "internet access", "connectivity", "connected", "online access"],
                source: "World Bank (ITU data)" },
  // Every smartphone figure in the data is DataReportal's; GSMA supplies the
  // separate Mobile Connectivity Index below, not this number. Naming GSMA
  // here sent readers to a source that does not publish these figures.
  smartphone: { label: "Smartphone adoption", unit: "%", get: f => f.smartphone,
                words: ["smartphone", "smartphones", "phone ownership"],
                source: "DataReportal 2024 estimate — GSMA's Mobile Connectivity Index is the measured companion signal" },
  radio:      { label: "Radio as weekly news source", unit: "%", get: f => f.radio,
                words: ["radio"], source: "Afrobarometer R9 / national surveys", surveyMix: true },
  tv:         { label: "TV as weekly news source", unit: "%", get: f => f.tv,
                words: ["tv", "television", "broadcast tv"], source: "Reuters DNR 2026 / barometers", surveyMix: true },
  online:     { label: "Online news use (weekly)", unit: "%", get: f => f.online,
                words: ["online news", "digital news", "news websites"], source: "Reuters DNR 2026 / barometers", surveyMix: true },
  social:     { label: "Social media as news source", unit: "%", get: f => f.social,
                words: ["social media", "social networks", "social platforms"], source: "Reuters DNR 2026 / barometers", surveyMix: true },
  trust:      { label: "Trust in news", unit: "%", get: f => f.trust,
                words: ["trust", "trusts", "trusted", "trust in news", "news trust", "credibility", "believe the news",
                        "skepticism", "skeptical", "scepticism"], source: "Reuters DNR 2026 / barometers", surveyMix: true },
  press:      { label: "Press freedom (RSF, 0–100)", unit: "/100", get: f => f.rsf,
                words: ["press freedom", "media freedom", "rsf", "journalist safety", "press freedom score",
                        "journalists", "journalist", "reporters", "state controlled media", "state controlled",
                        "state media", "media control"],
                source: "RSF World Press Freedom Index 2025" },
  netfreedom: { label: "Internet freedom (FOTN, 0–100)", unit: "/100", get: f => f.fotn,
                words: ["internet freedom", "online freedom", "censorship", "internet censorship"],
                source: "Freedom House FOTN 2025 (70 countries)" },
  medianage:  { label: "Median age", unit: " years", get: f => f.medianAge,
                words: ["median age", "average age", "age"], source: "UN DESA WPP 2024" },
  under15:    { label: "Population under 15", unit: "%", get: f => f.under15,
                words: ["under 15", "children", "under-15"], source: "World Bank" },
  urban:      { label: "Urban population", unit: "%", get: f => f.urban,
                words: ["urban", "urbanisation", "urbanization", "cities"], source: "World Bank" },
  literacy:   { label: "Adult literacy", unit: "%", get: f => f.literacy,
                words: ["literacy", "literate", "literacy rate"], source: "World Bank (UNESCO UIS data)" },
  population: { label: "Population", unit: "", get: f => f.pop, fmt: v => fmtPop(v),
                words: ["population", "biggest country", "largest country", "most populous"], source: "World Bank" },
  mci:        { label: "Mobile connectivity index", unit: "/100", get: f => f.mci,
                words: ["mobile connectivity", "mobile internet", "mci"], source: "GSMA MCI 2024" },
  finaccount: { label: "Financial account ownership", unit: "%", get: f => f.finAccount,
                words: ["financial account", "bank account", "mobile money", "financial inclusion", "digital payments"],
                source: "World Bank Global Findex" },
  english:    { label: "English speakers", unit: "%", get: f => f.englishPct,
                words: ["english", "english speakers", "english speaking", "english-speaking", "anglophone"],
                source: "Unicode CLDR territory-language data (speaker capability — shares overlap with other languages)" },
};

const PLATFORMS = ["whatsapp", "facebook", "tiktok", "instagram", "youtube", "telegram", "x", "twitter", "wechat", "snapchat", "viber", "line"];
const PLATFORM_NAMES = { whatsapp: "WhatsApp", facebook: "Facebook", tiktok: "TikTok", instagram: "Instagram",
  youtube: "YouTube", telegram: "Telegram", x: "X (Twitter)", wechat: "WeChat", snapchat: "Snapchat", viber: "Viber", line: "LINE" };

/**
 * Does one entry in a country's leading-platform list name this platform?
 *
 * The list is free text ("WhatsApp, Facebook, X (Twitter), TikTok"), so a
 * plain startsWith() was used — which made every single-letter platform match
 * anything beginning with that letter: China's "Xiaohongshu" was counted as X
 * (Twitter), inflating X's footprint. Requiring the match to end on a word
 * boundary keeps "x (twitter)" working while rejecting "xiaohongshu".
 */
function platformMatches(entry, p) {
  const e = String(entry || "").trim().toLowerCase();
  const k = String(p || "").toLowerCase();
  if (!e || !k) return false;
  if (e === k) return true;
  return e.startsWith(k) && /[^a-z0-9]/.test(e.charAt(k.length));
}

const AUDIENCES = {
  youth: ["youth", "young", "young people", "under 25", "under-25", "gen z", "students", "teenagers", "teens"],
  women: ["women", "female", "girls", "mothers"],
  rural: ["rural", "villages", "countryside", "farmers"],
  older: ["older", "elderly", "seniors", "retirees", "over 45", "over 50", "over 55", "over 60", "over 65",
          "45+", "50+", "55+", "60+", "65+", "older adults"],
  displaced: ["displaced", "displaced populations", "refugees", "idps", "internally displaced"],
};

// ---------------------------------------------------------------------------
// Known data gaps — asks the Atlas can NEVER answer at $0. Each gets a
// specific, honest response naming what's missing and the nearest thing the
// Atlas DOES hold, instead of a generic refusal or a misleading clarify.
// ---------------------------------------------------------------------------
const GAPS = [
  { key: "campaign-history",
    re: /\b(our (last|previous|past|next)\b.{0,30}\bcampaigns?|past campaigns|similar campaigns|previous campaigns|campaigns? (x|achiev\w+|underperform\w+|results?|reach\w*)|best campaigns|benchmarks?|engagement (rates?|benchmarks?|numbers?)|a b test\w*|ab test\w*|trust lift|partnerships? (drove|drive|driving)|did (it|they) work)\b/,
    standalone: true,
    note: "**The Atlas holds no campaign archive.** It is a media-landscape evidence base — it cannot see any organisation's past campaigns, engagement numbers, or performance benchmarks (that data was never collected, and no free source provides it). What it *can* do is describe the current landscape wherever the next campaign will run: platform reach, trust, connectivity, languages, press-freedom risk." },
  { key: "media-cost",
    re: /\b(cheap(est|er)?|costs?\b|cost per|cpm|cpc|pric(e|es|ing)|budget.{0,30}(goes|go|stretch\w*|furthest|further)|where does it go (furthest|further)|value for money|affordab\w+|media buy\w*|ad rates?|how much .{0,20}(cost|spend|budget))\b/,
    standalone: true,
    note: "**The Atlas holds no media prices.** Nobody publishes per-country ad rates, CPMs or production costs for free — so it cannot tell you what a campaign costs anywhere, or rank markets by price. What it *does* hold that bears on value: the number of people each channel actually reaches in a market (reach × population), which is the denominator of any cost-per-person calculation, and industry ad-spend forecasts for a handful of large markets as a directional signal of where commercial money is going. Ask \"which countries should we prioritise for a radio campaign?\" and the screening reports estimated people reachable per market — pair that with quotes from your media buyer." },
  { key: "format-performance",
    re: /\b(podcasts?|infographics?|short form|long form|live video|live stream\w*|video (or|vs|versus) text|text (or|vs|versus) video|audio content|content formats?|what formats?|which formats?|formats? (perform\w*|work\w*|suit\w*)|format (data|performance)|by format|creator led)\b/,
    standalone: true,
    note: "**The Atlas has no format-level performance data** — no source, free or paid, reliably measures whether video, audio, text, or infographics perform better per country. The nearest evidence it holds: internet penetration and mobile connectivity (video feasibility), adult literacy (text reach), radio's weekly reach (audio habit), and each country's leading outlets by medium." },
  { key: "time-series",
    re: /\b(over \d+ years?|past (decade|\d+ years?)|last (quarter|year)|since (last year|\d{4})|year over year|seasonal\w*|peak(s|ed)? (seasonally|in|during|each)|month(ly)? patterns?|best (month|time of year)|day of week|weekday|weekend patterns?|how long (does|do|will).{0,30}(trend|stay|remain)|stays? trending|when (should|do|does|did).{0,40}(launch|spike|peak|shift)|what changed .{0,30}since|timing for|world \w+ day)\b/,
    standalone: true,
    note: "**The Atlas's trend history covers only ~120 days** — it holds no seasonal, quarterly, or multi-year archive, so timing questions beyond that window cannot be answered from its data. (A \"last quarter\" ask sits mostly inside the window — the attention profile below reflects it.) It *can* show what is rising right now, each topic's momentum against its 30-day baseline, and annual editions of the survey/freedom indices (current year only)." },
  { key: "blocking",
    re: /\b(blocked|blocking|throttl\w+|banned|bans?\b|censor\w+|shut ?downs?|blackouts?|firewall\w*)\b/,
    standalone: true,
    note: "**The Atlas does not track platform blocking or shutdowns in real time.** The nearest signals it holds: Freedom House's annual internet-freedom score and status, plus press-freedom and political-status flags — shown below where available." },
  { key: "misinfo-flow",
    re: /\b(misinformation|disinformation|fake news)\b.{0,50}\b(platforms?|carr(y|ies)|spread\w*|flows?|most|trending)\b|\bplatforms?\b.{0,50}\b(misinformation|disinformation|fake news)\b|\bwhere is (misinformation|disinformation)\b/,
    standalone: true,
    note: "**The Atlas measures attention to topics, not the flow of false content** — no free source measures which platforms carry the most misinformation per country. It can show where the misinformation topic itself draws reader attention, plus trust-in-news and press-freedom context." },
  { key: "crosstabs",
    re: /\b(gen z|older adults?|seniors|over \d\d|\d\d\+|aged? \d\d|gender gap|by gender|men (vs|versus|and) women|hardest to reach|segments?|audience overlap|overlap between|news avoid\w+|creator influenced|creator level|influencers?)\b/,
    standalone: false,
    note: "**The Atlas's surveys are not age- or gender-disaggregated, and hold no platform-overlap, news-avoidance, or creator-level data** — figures are population-level per country. Median age, under-15 share, urban/rural split, and literacy are the nearest structural signals for audience skew." },
  { key: "sentiment",
    re: /\b(politiciz\w+|backlash|framing|sentiment|legally sensitive|neutrality risks?|controvers\w+|skeptic\w+|sceptic\w+|perceptions?|public opinion|attitudes?)\b/,
    standalone: false,
    note: "**The Atlas holds no sentiment, framing, or legal-risk data.** For risk planning it offers: trust in news, press-freedom score, political status (\"Not Free\" flags), and internet-freedom scores — proxies for how carefully messaging must be handled." },
  { key: "broadcaster-trust",
    re: /\b(public (broadcasters?|media)|state broadcasters?)\b/,
    standalone: false,
    note: "**Trust is measured for news overall, not per broadcaster.** The leading-TV lists below name each country's main broadcasters (in much of Europe these are the public ones), and the overall trust-in-news ranking is the nearest available signal." },
  { key: "platform-timeseries",
    re: /\b(growing|fastest growing|gaining|momentum|declining)\b.{0,40}\b(platforms?|whatsapp|facebook|tiktok|instagram|youtube|telegram)\b|\b(platforms?|whatsapp|facebook|tiktok|instagram|youtube|telegram)\b.{0,40}\b(growing|gaining|fastest|momentum)\b/,
    standalone: false,
    note: "**The Atlas has no platform time-series** — it cannot say which platform is growing fastest; it holds only the current ordered leading-platform list per market (shown below where available)." },
  { key: "topic-linkage",
    re: /\b(topics? (that )?(link|connect|bridge)|linking|intersection of|link between)\b/,
    standalone: false,
    note: "**The Atlas can't measure links between topics** — attention is tracked per topic independently. Below are the named topics separately; overlap in where they draw attention is the nearest signal." },
  { key: "subnational",
    re: /\b(francophone|anglophone|north vs south|subnational|within (the )?country|by (province|state|region)s?\b)/,
    standalone: false,
    note: "**All Atlas figures are national-level** — it holds no subnational or language-community splits within a country. Language shares (below, where available) are the nearest signal for linguistic segmentation; treat any within-country split as needing local data." },
  { key: "source-conflicts",
    re: /\b(sources? disagree|disagree about|conflict\w* between sources|differ between sources|discrepanc\w+)\b/,
    standalone: true,
    note: "**Where sources disagree, the Atlas keeps both and documents the rule** (docs/DATA_SOURCES.md §3): smartphone % shows DataReportal's estimate with GSMA's measured index alongside; news-use figures always name their survey because DNR (online panels) and the barometers (face-to-face) aren't directly comparable; internet % uses the World Bank/ITU series exclusively. Every figure's own source is on each country's Sources tab." },
];

/** Which known gaps does this question hit? Returns [{key, note, standalone}]. */
function detectGaps(qNorm) {
  return GAPS.filter(g => g.re.test(qNorm));
}

// ---------------------------------------------------------------------------
// Entity + intent detection
// ---------------------------------------------------------------------------
function normalize(question) {
  return " " + question.toLowerCase()
    .replace(/[’‘]/g, "'").replace(/[“”]/g, '"')
    .replace(/'s\b/g, "")                       // "france's media" → "france media"
    .replace(/'(?=[^a-z0-9]|$)/g, "")           // trailing apostrophes: "girls'-education"
    .replace(/\bu\.s\.a?\.?/g, " usa ")         // U.S. / U.S.A.
    .replace(/\bu\.k\.?/g, " united kingdom ")
    .replace(/\bthe us\b/g, " the usa ")        // 2-letter aliases are ambiguous with
    .replace(/\bthe uk\b/g, " the united kingdom ")  // the pronoun "us" — resolve safe forms only
    .replace(/\bindian ocean\b/g, " the ocean ")     // geography ≠ the country India
    .replace(/\bniger delta\b/g, " the delta ")
    .replace(/[-/]/g, " ")                      // "radio-dependent", "A/B test"
    .replace(/[?!.,;:()"]/g, " ").replace(/\s+/g, " ").trim() + " ";
}

export function detectEntities(question) {
  const q = normalize(question);
  const found = { countries: [], regions: [], topics: [], attributes: [], platforms: [],
                  audiences: [], wantsTrends: false, wantsCompare: false, rankDir: null,
                  rankN: 5, intents: [] };

  // --- countries AND regions in ONE longest-phrase-first pass ---
  // Longer phrases claim their words first, which resolves both directions
  // of ambiguity: "latin america" (region) wins over "america"→USA, while
  // "south africa" (country) wins over "africa" (region).
  const names = Object.keys(NAME_TO_ISO);
  const regionKeys = Object.keys(REGION_MAP);
  const phrases = [
    ...names.filter(n => n.length >= 3).map(n => [n, "country"]),
    ...regionKeys.map(r => [r, "region"]),
  ].sort((a, b) => b[0].length - a[0].length);
  let scrub = q;
  for (const [phrase, kind] of phrases) {
    if (!scrub.includes(" " + phrase + " ")) continue;
    if (kind === "country") {
      const iso = NAME_TO_ISO[phrase];
      if (COUNTRIES[iso] && !found.countries.includes(iso)) found.countries.push(iso);
    } else if (!found.regions.includes(phrase)) {
      found.regions.push(phrase);
    }
    scrub = scrub.split(" " + phrase + " ").join(" ");
  }

  // --- fuzzy country pass for remaining words (typos: "Nigerai") ---
  const scrubTokens = scrub.trim().split(" ").filter(t => t.length >= 5 && !FUZZY_STOPWORDS.has(t) && !t.includes("'"));
  const nameKeys = names.filter(n => n.length >= 4 && !GENERATED.has(n));
  for (const tok of scrubTokens) {
    const hit = bestFuzzy(tok, nameKeys, (k) => NAME_TO_ISO[k]);
    if (hit) {
      const iso = NAME_TO_ISO[hit];
      if (COUNTRIES[iso] && !found.countries.includes(iso)) {
        found.countries.push(iso);
        scrub = scrub.split(" " + tok + " ").join(" ");
      }
    }
  }

  // --- topics: collect candidates from synonyms AND direct labels, then keep
  // only the MOST SPECIFIC matches — "climate change adaptation" in a question
  // must win over its substring "climate change", or the answer is about the
  // wrong (broader) topic and can even point the opposite direction.
  const topicCandidates = [];   // [{label, qid, matched}] — matched = text found in q
  for (const [syn, label] of Object.entries(TOPIC_SYNONYMS)) {
    if (q.includes(" " + syn + " ")) {
      const hit = REGISTRY.find(([l]) => l === label);
      if (hit) topicCandidates.push({ label: hit[0], qid: hit[1], matched: syn });
    }
  }
  for (const [label, qid] of REGISTRY) {
    const l = label.toLowerCase();
    if (l.length >= 4 && q.includes(l)) topicCandidates.push({ label, qid, matched: l });
  }
  topicCandidates.sort((a, b) => b.matched.length - a.matched.length);
  for (const cand of topicCandidates) {
    // skip if a longer, more specific match already covers this matched text
    const shadowed = found.topics.some(t => t.matched.includes(cand.matched) && t.qid !== cand.qid);
    if (!shadowed && !found.topics.some(t => t.qid === cand.qid)) found.topics.push(cand);
  }
  if (!found.topics.length) {
    const labelKeys = REGISTRY.map(([l]) => l.toLowerCase()).filter(l => l.length >= 6);
    for (const tok of scrub.trim().split(" ").filter(t => t.length >= 6 && !FUZZY_STOPWORDS.has(t))) {
      const hit = bestFuzzy(tok, labelKeys);
      if (hit) {
        const entry = REGISTRY.find(([l]) => l.toLowerCase() === hit);
        if (entry && !found.topics.some(t => t.qid === entry[1])) found.topics.push({ label: entry[0], qid: entry[1] });
      }
    }
  }
  found.topics = found.topics.slice(0, 3);

  // --- attributes ---
  for (const [key, attr] of Object.entries(ATTRIBUTES)) {
    if (attr.words.some(w => q.includes(" " + w + " "))) found.attributes.push(key);
  }
  // "age" alone is too weak — require a stronger cue
  if (found.attributes.includes("medianage") && !/median age|average age|how old/.test(q)) {
    found.attributes = found.attributes.filter(a => a !== "medianage");
  }
  // "english" is both the GBR demonym and the language attribute. When the
  // question is about the LANGUAGE ("produce English content for Nigeria"),
  // the demonym-derived GBR match is spurious — drop it unless the UK is
  // actually named. Without this, that question becomes a Nigeria-vs-UK
  // comparison instead of a language recommendation.
  if (found.attributes.includes("english") &&
      !/\b(uk|britain|united kingdom|england|british)\b/.test(q)) {
    found.countries = found.countries.filter(iso => iso !== "GBR");
  }

  // --- platforms ---
  for (const p of PLATFORMS) {
    if (!q.includes(" " + p + " ")) continue;
    // "line" is an ordinary English word long before it is a messaging app —
    // "front line workers", "the poverty line", "help line" — and normalize()
    // turns "front-line" into "front line". Treated as a platform it answered
    // UN health-comms questions with LINE's footprint in Japan. It therefore
    // counts only when the question names it as an app, or writes it in the
    // all-caps styling the platform itself uses; a bare lowercase "line" is
    // always the English word.
    if (p === "line" && !/\bline (app|messenger|messaging)\b/.test(q) && !/\bLINE\b/.test(question)) continue;
    const canon = p === "twitter" ? "x" : p;
    if (!found.platforms.includes(canon)) found.platforms.push(canon);
  }

  // --- audiences ---
  for (const [aud, words] of Object.entries(AUDIENCES)) {
    if (words.some(w => q.includes(" " + w + " "))) found.audiences.push(aud);
  }

  // --- intents ---
  found.wantsTrends = /\b(trend|trending|rising|right now|this week|currently|interest(ed)? in|care about|popular topic|talking about|paying attention|hot topic|buzz|resonat\w*|most read|top topics?|biggest topics?|concern\w* people|growing or declining)\b/.test(q);
  found.wantsCompare = /\b(compare|versus|vs|difference between|better than|or)\b/.test(q) && found.countries.length >= 2
    || /\b(compare|versus|vs|difference between)\b/.test(q) || found.countries.length >= 2;

  const rankMatch = q.match(/\b(top|highest|most|best|largest|greatest|leading|lowest|least|worst|smallest|bottom)\b/);
  if (rankMatch && (found.attributes.length || /\b(top|bottom) \d+\b/.test(q))) {
    found.rankDir = /\b(lowest|least|worst|smallest|bottom)\b/.test(q) ? "asc" : "desc";
    const n = q.match(/\b(?:top|bottom|first)\s+(\d{1,2})\b/);
    found.rankN = n ? Math.min(15, Math.max(1, parseInt(n[1], 10))) : 5;
    found.intents.push("rank");
  }

  if (/\b(recommend|should we|should i|how (do|can|should) we|best (way|channel|platform|format)|where (do|can|should)|how to reach|reach|engage|publish|promote|communicat\w*|campaign|advis\w*|strateg\w*)\b/.test(q)
      && (found.countries.length || found.regions.length)) found.intents.push("recommend");

  // meta only for questions genuinely ABOUT the analyst/data — "help me reach
  // farmers in India" or "how often do Kenyans..." must not be hijacked
  if (/\b(what (data|sources)|which sources|where (does|do) (the|this|your) data|how (fresh|current|recent) is|how often (is|are) (the|this|your) data|last updated|up to date|what can (you|i) ask|who are you|how do you work|methodology)\b/.test(q)
      || /^\s*help\s*$/.test(q))
    found.intents.push("meta");

  if (/^\s*(hi|hello|hey|good (morning|afternoon|evening)|thanks|thank you|thank you so much|ok|okay|great|cool|perfect|awesome)\s*[!.?…]*\s*$/i.test(question.trim()))
    found.intents.push("greeting");

  if (found.attributes.length && found.countries.length === 1 && !found.intents.includes("rank"))
    found.intents.push("lookup");

  // --- expand regions to concrete countries (largest populations first) ---
  const regionCountries = [];
  for (const rk of found.regions) {
    const spec = REGION_MAP[rk];
    for (const [iso, c] of Object.entries(COUNTRIES)) {
      if (!inRegionSpec(spec, iso, c)) continue;
      regionCountries.push([iso, c.population || 0]);
    }
  }
  regionCountries.sort((a, b) => b[1] - a[1]);
  found.regionCountries = [...new Set(regionCountries.map(x => x[0]))].slice(0, 8);
  return found;
}

// ---------------------------------------------------------------------------
// Conversation memory (for follow-ups: "what about radio there?")
// ---------------------------------------------------------------------------
let LAST = { isos: [], regions: [], topics: [], attributes: [], rankDir: null };

export function resetConversation() { LAST = { isos: [], regions: [], topics: [], attributes: [], rankDir: null }; }

function isFollowUp(question, ents) {
  const q = normalize(question);
  const hasPlace = ents.countries.length || ents.regions.length;
  if (hasPlace) return false;
  if (!LAST.isos.length && !LAST.regions.length) return false;
  if (/\b(there|they|them|that country|those countries|its|it s)\b/.test(q)) return true;
  if (/^\s*(what about|how about|and|also|why|what of)\b/.test(q.trim())) return true;
  // a bare attribute or trend question with no location → inherit the last one;
  // but a TOPIC question ("what's happening with sea level rise?") stands alone
  if (ents.topics.length) return false;
  if (ents.attributes.length && !ents.intents.includes("rank")) return true;
  if (ents.wantsTrends) return true;
  return false;
}

// ---------------------------------------------------------------------------
// Evidence store — clickable links (rendered as numbered footnotes under each answer)
// ---------------------------------------------------------------------------
function evidenceStore() {
  const items = [];
  const seen = new Map();
  return {
    add(title, detail, links) {
      const key = title + "|" + detail;
      if (seen.has(key)) return seen.get(key);
      const id = "E" + (items.length + 1);
      items.push({ id, title, detail, links: links || [] });
      seen.set(key, id);
      return id;
    },
    list: () => items,
  };
}

/** Parse "World Bank — https://…" source strings into {label, url}. */
function parseSource(s) {
  if (!s) return null;
  const m = String(s).match(/(https?:\/\/\S+)/);
  const url = m ? m[1].replace(/[).,]+$/, "") : null;
  // Citation format is "Org | detail | URL". A LINK LABEL wants only the
  // organisation (the first segment); the detail parts are for the profile's
  // Sources tab, not a compact footnote, and would drag the pipe into the
  // label. Strip the URL, then take the part before the first pipe.
  const label = String(s).replace(/\s*https?:\/\/\S+/, "")
    .split("|")[0].replace(/\s*[—–]\s*$/, "").trim();
  return { label: label || url || String(s), url };
}

function countryLinks(iso) {
  const c = COUNTRIES[iso];
  if (!c || !c.sources) return [];
  const pick = ["news_consumption", "news_radio", "press_freedom_rank", "political_freedom", "internet_freedom", "internet_pct", "median_age", "media_landscape", "languages_detail"];
  const links = [];
  const seen = new Set();
  for (const k of pick) {
    const p = parseSource(c.sources[k]);
    if (p && p.url && !seen.has(p.url)) { links.push({ label: p.label, url: p.url }); seen.add(p.url); }
  }
  return links.slice(0, 6);
}

const TREND_LINKS = [
  { label: "Wikimedia Pageviews API (demand signal)", url: "https://wikimedia.org/api/rest_v1/" },
  { label: "GDELT Project (news-coverage signal)", url: "https://www.gdeltproject.org/" },
  { label: "Topic Explorer (this site)", url: "topics.html" },
];

// ---------------------------------------------------------------------------
// Facts
// ---------------------------------------------------------------------------
function facts(iso) {
  const c = COUNTRIES[iso];
  if (!c) return null;
  const nc = c.news_consumption || {}, inf = c.information_freedom || {},
        conn = c.connectivity || {}, dem = c.demographics || {};
  const tr = TRENDS && TRENDS.countries ? TRENDS.countries[iso] : null;
  return {
    iso, name: c.name, pop: c.population, region: c.region, subregion: c.subregion,
    trust: nc.trust_in_news_pct, tv: nc.tv_as_news_source_pct,
    online: nc.online_as_news_source_pct, social: nc.social_as_news_source_pct,
    radio: nc.radio_as_news_source_pct, radioSource: nc.radio_source || null, surveyNote: nc.survey_note || null,
    survey: nc.source,
    internet: conn.internet_pct == null ? null : Math.round(conn.internet_pct),
    smartphone: conn.smartphone_pct, mci: conn.mobile_connectivity_index,
    medianAge: dem.median_age,
    rsf: inf.press_freedom_score, fh: inf.political_freedom_status,
    // Edition label travels with the score so prose can never name a
    // different year than the figure it is describing.
    rsfEdition: inf.press_freedom_edition || null,
    fotn: inf.internet_freedom_score, electoral: inf.electoral_democracy,
    under15: dem.age_0_14_pct, urban: dem.urban_pct, literacy: dem.literacy_pct,
    finAccount: conn.financial_account_pct,
    outlets: c.media || {}, languages: c.languages || [],
    // Extended station list (Wikipedia lists gated through Wikidata) — a
    // breadth layer; the curated top_tv line stays the leading-stations claim
    tvStations: (TV_STATIONS && TV_STATIONS[iso]) || null,
    languagesDetail: c.languages_detail || [],
    // CLDR speaker-capability share for English (overlaps with other languages
    // by design — invariant #6: language shares are capability, not additive)
    englishPct: (() => {
      const e = (c.languages_detail || []).find(l => l.code === "en");
      return e ? e.pct : null;
    })(),
    // CIA World Factbook "Broadcast media" narrative (public domain, weekly)
    landscapeNote: (c.media || {}).landscape_note || null,
    // Measured platform use (Latinobarometro 2024, LatAm only) — usage
    // construct, distinct from curated top_social and Statcounter referrals
    platformUse: c.platform_use || null,
    sourcesMap: c.sources || {}, retrievedOn: c.retrieved_on || null,
    rising: tr ? (tr.rising_topics || []) : [],
    distinctive: tr ? (tr.distinctive_topics || []) : [],
    topTopics: tr ? (tr.top_topics || []) : [],
  };
}

function addCountryEvidence(f, ev) {
  const bits = [`News use & trust: ${f.survey || "no survey integrated yet"}`];
  if (f.radio != null) bits.push(`radio reach: ${f.radioSource === "Afrobarometer Round 9 (2023)" ? "Afrobarometer Round 9 microdata (2023, weighted)" : (f.radioSource || "source unspecified")}`);
  bits.push("press freedom: RSF World Press Freedom Index 2025");
  bits.push("political & internet freedom: Freedom House 2026 official data files");
  bits.push("connectivity & demographics: World Bank CC BY 4.0 (ICT compiled by ITU; literacy by UNESCO UIS)");
  if (f.medianAge != null) bits.push("median age: UN DESA WPP 2024");
  if (f.mci != null) bits.push("mobile connectivity: GSMA MCI 2024");
  if (f.landscapeNote) bits.push("media landscape: CIA World Factbook (public domain, weekly)");
  if (TRENDS) bits.push(`live trends: Wikimedia Pageviews + GDELT, daily engine as of ${TRENDS.generated} (language-weight attribution — approximation)`);
  return ev.add(`${f.name} — country profile`, "Atlas record. " + bits.join("; ") + ".", countryLinks(f.iso));
}

function addTrendEvidence(name, ev) {
  return ev.add(`${name} — live trends`,
    `Daily trend engine as of ${TRENDS.generated}. Demand = Wikipedia reading patterns (what people look up); coverage = GDELT news monitoring (what media publish). Country attribution via language-population weights — a documented approximation.`,
    TREND_LINKS);
}

// ---------------------------------------------------------------------------
// Ad-market signal (data/ad_market.json — industry forecasts, annual update).
// Where commercial media money flows is a market-opportunity signal; these
// are directional industry estimates, never presented as surveys.
// ---------------------------------------------------------------------------
const AD_MARKET_LINKS = [
  { label: "WPP Media — This Year, Next Year", url: "https://www.wppmedia.com/" },
  { label: "Dentsu — Global Ad Spend Forecasts", url: "https://www.dentsu.com/" },
];

function adMarketSignal(f) {
  if (!AD_MARKET) return null;
  const m = (AD_MARKET.markets || {})[f.iso];
  if (!m) return null;
  const label = m.source === "wpp_tyny"
    ? "WPP Media 'This Year, Next Year', Dec 2025"
    : "Dentsu Global Ad Spend Forecasts, Dec 2025";
  const bits = [];
  if (m.ad_spend_2026_usd_bn != null) bits.push(`US$${m.ad_spend_2026_usd_bn}B forecast total ad spend in 2026`);
  if (m.growth_2026_pct != null) bits.push(`${m.growth_2026_pct >= 0 ? "+" : ""}${m.growth_2026_pct}% forecast ad-spend growth in 2026`);
  if (!bits.length) return null;
  return {
    text: `Commercial ad market: ${bits.join("; ")}${m.note ? ` — ${m.note}` : ""} (${label}). Rising commercial investment signals where paid attention is flowing — a directional market-opportunity indicator. [industry estimate — directional, not a survey]`,
    evTitle: `${f.name} — ad-market signal`,
    evDetail: `Industry forecast, hand-updated annually from the free year-end reports (${label}). ${AD_MARKET._meta ? AD_MARKET._meta.method_note : ""}`,
  };
}

const fmt = (v, suffix = "%") => v == null ? "no data" : `${Math.round(v * 10) / 10}${suffix}`;
const fmtPop = (v) => v == null ? "no data" : v >= 1e9 ? (v / 1e9).toFixed(2) + "B" : v >= 1e6 ? (v / 1e6).toFixed(1) + "M" : Math.round(v / 1000) + "k";
const titleCase = (s) => s.replace(/\b\w/g, ch => ch.toUpperCase());
/** Capitalise and end-stop a fragment so it reads as a sentence. */
const sentence = (s) => {
  const t = String(s || "").trim();
  if (!t) return "";
  return t.charAt(0).toUpperCase() + t.slice(1) + (/[.!?]$/.test(t) ? "" : ".");
};

function riskLines(f) {
  const risks = [];
  if (f.surveyNote) risks.push(`Survey caveat for ${f.name}: ${f.surveyNote}`);
  if (f.internet != null && f.internet < 40)
    risks.push(`Internet penetration is only ${f.internet}% in ${f.name} — digital-only campaigns will miss most of the population.`);
  if (f.rsf != null && f.rsf < 40)
    risks.push(`${f.name}'s press-freedom score is ${Math.round(f.rsf)}/100 (RSF ${f.rsfEdition || ""}) — a restrictive media environment; plan messenger and content review carefully.`);
  if (f.fh === "Not Free")
    risks.push(`Freedom House rates ${f.name} **Not Free** — state influence over media is likely.`);
  if (f.trust != null && f.trust < 30)
    risks.push(`Trust in news is low in ${f.name} (${f.trust}%) — trusted intermediaries may matter more than outlet reach.`);
  return risks;
}

function bestChannel(f) {
  const ch = [["TV", f.tv], ["radio", f.radio], ["online sources", f.online], ["social media", f.social]]
    .filter(x => x[1] != null).sort((a, b) => b[1] - a[1]);
  return ch.length ? ch[0] : null;
}

// ---------------------------------------------------------------------------
// Composers (no inline citation tags — sources are listed per answer)
// ---------------------------------------------------------------------------
function audienceNote(audiences, f) {
  if (!audiences.length) return null;
  const bits = [];
  if (audiences.includes("youth")) {
    bits.push(`For youth targeting: ${f.medianAge != null ? `median age is ${f.medianAge}` : "median age unknown"}${f.under15 != null ? `, ${fmt(f.under15)} of the population is under 15` : ""}. The Atlas has no youth-specific platform crosstabs — treat platform guidance as population-level.`);
  }
  if (audiences.includes("women")) bits.push("The Atlas's surveys are not gender-disaggregated — the figures above are population-level, not women-specific. Local partners can advise on gendered media habits.");
  if (audiences.includes("rural")) bits.push(`For rural audiences: ${f.urban != null ? `${fmt(100 - f.urban)} of the population is rural` : "urban share unknown"}${f.radio != null ? `; radio (${fmt(f.radio)} weekly reach measured nationally) is the strongest rural candidate` : "; industry practice (not Atlas-measured) is that radio and community channels out-reach digital in rural areas"} — the Atlas has no rural-specific media breakdown.`);
  if (audiences.includes("older")) bits.push("For older audiences: TV and radio typically out-reach social platforms; the Atlas has no age-segmented platform data to quantify this per country.");
  if (audiences.includes("displaced")) bits.push("For displaced populations: the Atlas holds no displacement-specific media data — figures are population-level. Radio and messaging apps typically matter most in displacement settings; pair these signals with humanitarian partners' on-the-ground assessments.");
  return bits.length ? bits.join(" ") : null;
}

function composeCountryBrief(f, ev, ents) {
  addCountryEvidence(f, ev);
  const lines = [];
  const top = bestChannel(f);
  const wantsTrends = ents.wantsTrends;

  if (wantsTrends && f.rising.length) {
    addTrendEvidence(f.name, ev);
    lines.push(`**Trending in ${f.name} right now** (as of ${TRENDS.generated}):`);
    for (const r of f.rising.slice(0, 5))
      lines.push(`- **${r.label_en}** +${Math.round(r.velocity * 100)}% vs its 30-day baseline`);
    if (f.distinctive.length)
      lines.push(`\nDistinctive interests vs the world average: ${f.distinctive.slice(0, 4).map(d => `**${d.label_en}** (${d.vs_global_avg}×)`).join(", ")}`);
    lines.push("");
  } else if (wantsTrends && (f.topTopics.length || f.distinctive.length)) {
    // nothing spiking, but the attention profile still answers "what resonates";
    // when the question names a theme (health, climate…), filter to it
    addTrendEvidence(f.name, ev);
    const theme = ents.themeFilter || null;
    const catOf = (qid) => (TRENDS.topics[qid] || {}).category || "";
    let top = f.topTopics;
    if (theme) {
      const themed = f.topTopics.filter(t => theme.includes(catOf(t.qid)));
      if (themed.length) {
        top = themed;
        lines.push(`**${theme.join("/")}-related attention in ${f.name}** (as of ${TRENDS.generated}):`);
      } else {
        lines.push(`**No ${theme.join("/")} topic makes ${f.name}'s measured top attention right now** (as of ${TRENDS.generated}) — the overall profile is below for context:`);
      }
    }
    if (!theme || !f.topTopics.some(t => theme.includes(catOf(t.qid))))
      lines.push(`**What draws attention in ${f.name}** (as of ${TRENDS.generated} — nothing is spiking sharply this week, so here is the standing attention profile):`);
    for (const t of top.slice(0, 5))
      lines.push(`- **${t.label_en}** — ${t.attention_share_pct}% of measured attention`);
    if (f.distinctive.length)
      lines.push(`\nFollowed notably more than the world average: ${f.distinctive.slice(0, 4).map(d => `**${d.label_en}** (${d.vs_global_avg}×)`).join(", ")}`);
    lines.push("");
  } else if (wantsTrends) {
    lines.push(`*No reliable trend signal is available for ${f.name} right now (below the measurement floor) — here is the country's media profile instead.*\n`);
  }

  if (ents.intents.includes("recommend") && top) {
    // audience-adjusted headline: a rural/older ask must not lead with a
    // population-level channel that the data itself contradicts for that group
    const rural = ents.audiences.includes("rural") && f.radio != null && f.radio > (f.online ?? -1);
    const older = ents.audiences.includes("older") && f.tv != null;
    if (rural)
      lines.push(`**Recommendation for ${f.name}: population-level lead is ${top[0]} (${fmt(top[1])}), but for rural audiences lead with radio (${fmt(f.radio)} weekly reach).**`);
    else if (older && top[0] !== "TV")
      lines.push(`**Recommendation for ${f.name}: population-level lead is ${top[0]} (${fmt(top[1])}); for older audiences TV (${fmt(f.tv)}) and radio typically out-reach social platforms.**`);
    else
      lines.push(`**Recommendation for ${f.name}: lead with ${top[0]} (${fmt(top[1])} weekly news reach)${f.internet != null && f.internet < 40 ? ", and avoid digital-only plans" : ""}.**`);
  } else if (ents.intents.includes("recommend") && !top) {
    lines.push(`**Recommendation for ${f.name}:** no news-source survey covers this country yet, so anchor on structure: internet penetration is ${fmt(f.internet)}${f.internet != null ? (f.internet >= 60 ? " (digital channels can reach most people)" : f.internet >= 35 ? " (pair digital with broadcast)" : " (broadcast and community channels first — digital-only would miss most people)") : ""}, and the leading outlets below are the practical entry points. Treat any channel mix as a hypothesis to validate with local partners.`);
  } else if (top && top[1] != null) {
    lines.push(`**${f.name}: ${top[0]} leads for news reach — ${fmt(top[1])} weekly.**`);
  } else {
    lines.push(`**${f.name} — media profile.**`);
  }
  lines.push("");
  if (f.radio != null) {
    const cap = f.radioSource === "Afrobarometer Round 9 (2023)" ? "Afrobarometer Round 9 — the leading channel in much of Africa" : (f.radioSource || "source unspecified");
    lines.push(`- Radio as a weekly news source: ${fmt(f.radio)} *(${cap})*`);
  }
  if (f.tv == null && f.online == null && f.social == null && f.radio == null) {
    lines.push(`- The Atlas has no news-source survey for ${f.name} yet (not covered by the Reuters Institute DNR or the regional barometers integrated so far) — the figures below are connectivity, freedom, and demographics.`);
  } else {
    lines.push(`- News sources (weekly reach): TV ${fmt(f.tv)}, online ${fmt(f.online)}, social media ${fmt(f.social)} *(survey: ${f.survey || "n/a"})*`);
  }
  if (f.trust != null) lines.push(`- Trust in news: ${f.trust}%`);
  lines.push(`- Connectivity: ${fmt(f.internet)} internet penetration${f.smartphone != null ? `, ${fmt(f.smartphone)} smartphone adoption` : ""}${f.mci != null ? `, GSMA mobile connectivity index ${f.mci}/100` : ""}`);
  if (f.rsf != null) lines.push(`- Press freedom: ${Math.round(f.rsf)}/100 (RSF ${f.rsfEdition || ""}); political status: ${f.fh || "n/a"}${f.electoral != null ? `; electoral democracy: ${f.electoral ? "yes" : "no"}` : ""}`);
  if (f.fotn != null) lines.push(`- Internet freedom: ${f.fotn}/100 (Freedom House FOTN)`);
  if (f.under15 != null || f.urban != null || f.medianAge != null)
    lines.push(`- Audience structure: ${f.medianAge != null ? `median age ${f.medianAge}, ` : ""}${f.under15 != null ? `${fmt(f.under15)} under 15, ` : ""}${f.urban != null ? `${fmt(f.urban)} urban` : ""}${f.literacy != null ? `, ${fmt(f.literacy)} literacy` : ""}`);
  if (f.languagesDetail.length)
    lines.push(`- Languages (share of population): ${langsByShare(f).slice(0, 5).map(l => `${prettyLang(l)} ${Math.round(l.pct)}%${l.official ? " (official)" : ""}`).join(", ")} *(Unicode CLDR)*`);
  const o = f.outlets;
  if (o.top_tv || o.top_radio) lines.push(`- Leading outlets — TV: ${o.top_tv || "n/a"}; radio: ${o.top_radio || "n/a"}; online: ${o.top_online_news || "n/a"}${o.top_social ? `; social platforms (in order): ${o.top_social}` : ""}`);
  if (f.tvStations && (f.tvStations.stations || []).length) {
    const names = f.tvStations.stations.map(s => s.name);
    lines.push(`- More active TV stations (beyond the leading outlets): ${names.join(", ")} *(Wikipedia station lists verified via Wikidata; ordered by international Wikipedia presence, not audience share)*`);
    const srcUrl = (String(f.tvStations.source || "").match(/https?:\/\/\S+/) || [null])[0];
    ev.add(`${f.name} — extended TV stations`,
      `Station names from Wikipedia's station-list pages; every entry gated through its Wikidata record (belongs to this country, carries no dissolution date, typed as a broadcaster). Ordering is international Wikipedia presence (sitelink count) — a presence proxy; no free source measures per-station audience share. ${f.tvStations.source || ""}`,
      srcUrl ? [{ label: "Wikipedia station list", url: srcUrl }] : []);
  }

  // if a specific platform was asked about, say where it stands in this market
  for (const p of ents.platforms || []) {
    const pretty = PLATFORM_NAMES[p] || p;
    // measured usage first (Latinobarometro battery), curated rank as fallback
    const measured = f.platformUse ? f.platformUse[p === "twitter" ? "x" : p] : null;
    if (measured != null) {
      lines.push(`- **${pretty}** is actively used by **${measured}% of adults** in ${f.name} *(${f.platformUse.source}, weighted survey, n=${(f.platformUse.n || 0).toLocaleString()})* — a measured figure, not an estimate`);
      continue;
    }
    const socials = (o.top_social || "").toLowerCase().split(",").map(s => s.trim());
    const pos = socials.findIndex(s => platformMatches(s, p));
    if (pos === 0) lines.push(`- **${pretty}** is the leading social platform in ${f.name} (${o.top_social})`);
    else if (pos > 0) lines.push(`- **${pretty}** ranks #${pos + 1} among ${f.name}'s top platforms (${o.top_social})`);
    else if (o.top_social) lines.push(`- **${pretty}** is not among ${f.name}'s leading platforms (${o.top_social})`);
  }

  if (!wantsTrends && f.rising.length) {
    addTrendEvidence(f.name, ev);
    lines.push(`- Rising topics this week: ${f.rising.slice(0, 3).map(r => `${r.label_en} (+${Math.round(r.velocity * 100)}%)`).join(", ")}`);
  }

  const aud = audienceNote(ents.audiences, f);
  if (aud) { lines.push(""); lines.push(`**Audience note:** ${aud}`); }

  const risks = riskLines(f);
  if (risks.length) {
    lines.push("");
    lines.push("**Risks & caveats:**");
    for (const r of risks) lines.push("- " + r);
  }
  return lines.join("\n");
}

function composeComparison(fs, ev, ents) {
  fs.forEach(f => addCountryEvidence(f, ev));
  const lines = [];

  // headline: use the asked-about attribute if there is one, else trust
  const attrKey = ents.attributes[0] || "trust";
  const attr = ATTRIBUTES[attrKey] || ATTRIBUTES.trust;
  const withVal = fs.filter(f => attr.get(f) != null);
  if (withVal.length >= 2) {
    const hi = withVal.reduce((a, b) => attr.get(a) > attr.get(b) ? a : b);
    const lo = withVal.reduce((a, b) => attr.get(a) < attr.get(b) ? a : b);
    if (hi.iso !== lo.iso)
      lines.push(`**${hi.name} leads on ${attr.label.toLowerCase()} (${fmt(attr.get(hi), attr.unit)} vs ${lo.name}'s ${fmt(attr.get(lo), attr.unit)}).**\n`);
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
  if (fs.some(f => f.fotn != null)) lines.push(row("Internet freedom (FOTN /100)", "fotn", ""));
  lines.push(`| Political status | ${fs.map(f => f.fh || "n/a").join(" | ")} |`);
  // a named platform gets its own rank row ("TikTok news use: IDN vs MYS vs PHL")
  for (const p of (ents.platforms || []).slice(0, 2)) {
    const pretty = PLATFORM_NAMES[p] || p;
    lines.push(`| ${pretty} rank among leading platforms | ${fs.map(f => {
      const list = ((f.outlets || {}).top_social || "").toLowerCase().split(",").map(s => s.trim());
      const pos = list.findIndex(s => platformMatches(s, p));
      return pos >= 0 ? "#" + (pos + 1) : "not listed";
    }).join(" | ")} |`);
  }
  lines.push("");
  const audComp = audienceNote(ents.audiences || [], fs[0] || {});
  if (audComp) lines.push(`**Audience note:** ${audComp}\n`);

  const digital = fs.filter(f => f.online != null && f.tv != null && f.online >= f.tv);
  const broadcast = fs.filter(f => f.online != null && f.tv != null && f.tv > f.online);
  if (digital.length && broadcast.length) {
    lines.push(`**Channel guidance:** online-first works in ${digital.map(f => f.name).join(", ")}; in ${broadcast.map(f => f.name).join(", ")} TV still out-reaches online — plan a split strategy.`);
  }
  const surveys = [...new Set(fs.map(f => f.survey).filter(Boolean))];
  if (surveys.length > 1)
    lines.push(`\n*Methodology note: these countries are measured by different surveys (${surveys.join(" / ")}) — compare direction, not decimal points.*`);

  const allRisks = fs.flatMap(f => riskLines(f));
  if (allRisks.length) {
    lines.push("");
    lines.push("**Risks & caveats:**");
    for (const r of allRisks) lines.push("- " + r);
  }
  return lines.join("\n");
}

function composeRegionBrief(fs, ev, ents, regionName) {
  const lines = [];
  fs.forEach(f => addCountryEvidence(f, ev));

  // transparency: region analysis covers the most populous countries, not all
  let totalInRegion = 0;
  if (ents.regions.length) {
    const spec = REGION_MAP[ents.regions[0]];
    for (const [iso, c] of Object.entries(COUNTRIES)) {
      if (inRegionSpec(spec, iso, c)) totalInRegion++;
    }
  }

  // tiering respects radio: a country where radio out-reaches online news is
  // never "digital-first", whatever its internet penetration says
  const tierOf = (f) => f.internet == null ? null
    : f.internet < 35 ? "broadcast"
    : (f.internet >= 55 && (f.radio == null || (f.online || 0) >= f.radio)) ? "digital"
    : "mixed";
  const digital = fs.filter(f => tierOf(f) === "digital").sort((a, b) => (b.online || 0) - (a.online || 0));
  const mixed = fs.filter(f => tierOf(f) === "mixed");
  const broadcast = fs.filter(f => tierOf(f) === "broadcast");

  lines.push(`**${regionName.charAt(0).toUpperCase() + regionName.slice(1)}: split the strategy by connectivity — the gap between countries is decisive.**\n`);
  const tierList = (label, arr, render, tail = "") => {
    if (!arr.length) return;
    lines.push(`**${label}:**`);
    for (const f of arr) lines.push(`- ${render(f)}`);
    if (tail) lines.push(tail);
  };
  tierList("Digital-first", digital,
    f => `${f.name} (online news ${fmt(f.online)}, internet ${f.internet}%${f.radio != null ? `, radio ${fmt(f.radio)}` : ""})`);
  tierList("Mixed digital + broadcast", mixed,
    f => `${f.name} (internet ${f.internet}%, TV ${fmt(f.tv)}${f.radio != null ? `, radio ${fmt(f.radio)}` : ""})`);
  tierList("Broadcast/community-first", broadcast,
    f => `${f.name} (internet only ${f.internet}%${f.radio != null ? `, radio ${fmt(f.radio)}` : ""}, TV ${fmt(f.tv)})`,
    "*Digital-only campaigns would structurally miss most people here.*");

  // when radio is the subject, answer the radio-vs-online question head-on
  if (ents.attributes.includes("radio")) {
    const radioWins = fs.filter(f => f.radio != null && f.online != null && f.radio > f.online);
    if (radioWins.length) {
      lines.push(`\n**Radio out-reaches online news in:**`);
      for (const f of radioWins) lines.push(`- ${f.name} (radio ${fmt(f.radio)} vs online ${fmt(f.online)})`);
    }
  }

  for (const topic of ents.topics.slice(0, 3)) {
    if (!TRENDS || !TRENDS.topics[topic.qid]) continue;
    const t = TRENDS.topics[topic.qid];
    addTrendEvidence(t.label_en, ev);
    lines.push("");
    lines.push(`**${t.label_en} right now:** globally ${t.momentum} (${t.global_velocity > 0 ? "+" : ""}${Math.round(t.global_velocity * 100)}% vs 30-day baseline). *(The Atlas sees ~120 days of attention history — no seasonal or multi-year timing data.)*`);
    const local = fs.filter(f => f.distinctive.some(d => d.label_en === t.label_en) || f.rising.some(r => r.label_en === t.label_en));
    if (local.length)
      lines.push(`Above-average or rising attention in: ${local.map(f => f.name).join(", ")} *(attribution approximation)*.`);
  }

  const aud = audienceNote(ents.audiences, fs[0] || {});
  if (aud) { lines.push(""); lines.push(`**Audience note:** ${aud}`); }

  const allRisks = fs.flatMap(f => riskLines(f)).slice(0, 8);
  if (allRisks.length) {
    lines.push("");
    lines.push("**Risks & caveats:**");
    for (const r of allRisks) lines.push("- " + r);
  }
  if (totalInRegion > fs.length) {
    lines.push("");
    lines.push(`*Scope: this analysis covers the region's ${fs.length} most populous countries of ${totalInRegion} total — ask about any specific country for its full profile.*`);
  }
  return lines.join("\n");
}

function composeTopicBrief(topic, ev, countriesFirst) {
  const t = TRENDS && TRENDS.topics ? TRENDS.topics[topic.qid] : null;
  if (!t) {
    return `**${topic.label}** is one of the Atlas's ${REGISTRY.length} tracked topics, but its measured attention is currently below the reliability floor, so no trend report is available right now. Country-level media data may still help — try naming a country or region alongside the topic.`;
  }
  addTrendEvidence(t.label_en, ev);
  const lines = [];
  lines.push(`**${t.label_en} — ${t.momentum} globally** (${t.global_velocity > 0 ? "+" : ""}${Math.round(t.global_velocity * 100)}% attention vs its 30-day baseline, as of ${TRENDS.generated})\n`);
  // "WHICH COUNTRIES show rising interest" → lead with the country list
  if (countriesFirst) {
    const hot0 = [];
    if (TRENDS.countries) {
      for (const [iso, tr] of Object.entries(TRENDS.countries)) {
        const d = (tr.distinctive_topics || []).find(x => x.label_en === t.label_en);
        if (d && COUNTRIES[iso]) hot0.push([COUNTRIES[iso].name, d.vs_global_avg]);
        const rz = (tr.rising_topics || []).find(x => x.label_en === t.label_en);
        if (rz && COUNTRIES[iso] && !hot0.some(h => h[0] === COUNTRIES[iso].name)) hot0.push([COUNTRIES[iso].name, null]);
      }
    }
    hot0.sort((a, b) => (b[1] || 99) - (a[1] || 99));
    if (hot0.length)
      lines.push(`**Countries with above-average or rising attention:** ${hot0.slice(0, 8).map(([n, x]) => x ? `${n} (${x}×)` : `${n} (rising)`).join(", ")}\n`);
    else
      lines.push(`*No country currently shows above-average attention to this topic in the Atlas's measurement (attention is attributed by language weights — a documented approximation).*\n`);
  }
  const langs = Object.entries(t.demand_by_language || {}).slice(0, 6);
  if (langs.length)
    lines.push(`**Demand by language** (daily lookups):`);
    for (const [l, v] of langs)
      lines.push(`- ${l.toUpperCase()} ${Math.round(v.weekly_daily_avg_views).toLocaleString()}/day (${v.velocity > 0 ? "+" : ""}${Math.round(v.velocity * 100)}%)`);
  if (t.news_articles_7d != null)
    lines.push(`- News coverage: ${t.news_articles_7d.toLocaleString()} articles in the last 7 days (GDELT)`);
  // GDELT's per-country figure is an INTENSITY, not a slice of world coverage:
  // it is the share of that country's own monitored news output matching this
  // topic. A small media market that covers a topic obsessively therefore
  // outranks a large one publishing far more articles about it — so this reads
  // "whose newsrooms give it the most airtime", never "who covers it most".
  const cov = (t.media_intensity_by_country || []).slice(0, 6);
  if (cov.length)
    lines.push(`- Covered most intensively by media in: ${cov.map(c => `${c.iso3} (${c.pct_of_country_news_volume}% of that country's news output)`).join(", ")}`);
  const hot = [];
  if (TRENDS.countries) {
    for (const [iso, tr] of Object.entries(TRENDS.countries)) {
      const d = (tr.distinctive_topics || []).find(x => x.label_en === t.label_en);
      if (d && COUNTRIES[iso]) hot.push([COUNTRIES[iso].name, d.vs_global_avg]);
    }
  }
  hot.sort((a, b) => b[1] - a[1]);
  if (hot.length)
    lines.push(`- Countries with above-average attention: ${hot.slice(0, 6).map(([n, x]) => `${n} (${x}×)`).join(", ")}`);
  return lines.join("\n");
}

function composeRanking(ents, ev) {
  const attrKey = ents.attributes[0];
  const attr = ATTRIBUTES[attrKey];
  if (!attr) return null;

  // Candidate pool: the countries the reader named, else a region filter,
  // else the whole Atlas. Naming countries explicitly used to be ignored
  // here — "top 5 by radio in Kenya, Nigeria and Ghana" ranked all 195 and
  // answered a question nobody asked. Explicit names are the strongest
  // signal of scope there is, so they win over a region if both appear.
  let pool = Object.keys(COUNTRIES);
  let scope = "all 195 countries";
  if (ents.countries.length >= 2) {
    pool = [...ents.countries];
    scope = pool.map(iso => (COUNTRIES[iso] || {}).name || iso).join(", ");
  } else if (ents.regions.length) {
    const spec = REGION_MAP[ents.regions[0]];
    pool = pool.filter(iso => inRegionSpec(spec, iso, COUNTRIES[iso]));
    scope = regionDisplay(ents.regions[0]);
  }

  const rows = pool.map(facts).filter(f => f && attr.get(f) != null);
  const missing = pool.length - rows.length;
  if (!rows.length) {
    return `The Atlas has no ${attr.label.toLowerCase()} data for ${scope} yet. (${attr.source} is the underlying source — its coverage doesn't include these countries.)`;
  }
  rows.sort((a, b) => ents.rankDir === "asc" ? attr.get(a) - attr.get(b) : attr.get(b) - attr.get(a));
  const top = rows.slice(0, ents.rankN);

  ev.add(`Ranking: ${attr.label} (${scope})`,
    `Computed from Atlas records for ${rows.length} countries with data (${missing} lacking this indicator). Underlying source: ${attr.source}.`,
    top.length ? countryLinks(top[0].iso) : []);

  const lines = [];
  const dirWord = ents.rankDir === "asc" ? "lowest" : "highest";
  lines.push(`**${titleCase(dirWord)} ${attr.label.toLowerCase()} — ${scope}** (${rows.length} countries with data):\n`);
  lines.push(`| # | Country | ${attr.label} |`);
  lines.push(`|---|---|---|`);
  top.forEach((f, i) => {
    const v = attr.get(f);
    lines.push(`| ${i + 1} | ${f.name} | ${attr.fmt ? attr.fmt(v) : fmt(v, attr.unit)} |`);
  });
  if (missing > 0)
    lines.push(`\n*${missing} countries in ${scope} have no ${attr.label.toLowerCase()} data in the Atlas — they are excluded, not ranked low.*`);
  if (attr.surveyMix)
    lines.push(`*Methodology note: news-consumption figures mix different surveys (Reuters DNR, Afrobarometer, national barometers) — treat cross-country gaps under ~5 points as noise.*`);
  return lines.join("\n");
}

function composeLookup(ents, ev, qNorm) {
  const iso = ents.countries[0];
  const f = facts(iso);
  if (!f || !ents.attributes.length) return null;
  addCountryEvidence(f, ev);
  const blocks = [];

  // answer EVERY asked-about measure ("internet and literacy in Chad"), not just the first
  for (const attrKey of ents.attributes.slice(0, 3)) {
    const attr = ATTRIBUTES[attrKey];
    if (!attr) continue;
    const v = attr.get(f);
    const lines = [];
    if (v == null) {
      lines.push(`**The Atlas has no ${attr.label.toLowerCase()} figure for ${f.name}.** The underlying source (${attr.source}) doesn't cover it${attr.surveyMix ? " — no integrated survey includes this country yet" : ""}.`);
      const alt = ["internet", "trust", "tv", "press"].map(k => ATTRIBUTES[k]).filter(a => a !== attr && a.get(f) != null);
      if (alt.length)
        lines.push(`\nWhat the Atlas does have for ${f.name}: ${alt.map(a => `${a.label.toLowerCase()} ${fmt(a.get(f), a.unit)}`).join(", ")}.`);
      blocks.push(lines.join("\n"));
      continue;
    }
    // rank among countries with data for context
    const all = Object.keys(COUNTRIES).map(facts).filter(x => x && attr.get(x) != null);
    all.sort((a, b) => attr.get(b) - attr.get(a));
    const rank = all.findIndex(x => x.iso === iso) + 1;
    const regionAll = all.filter(x => x.subregion === f.subregion && x.iso !== iso);
    const regionAvg = regionAll.length ? regionAll.reduce((s, x) => s + attr.get(x), 0) / regionAll.length : null;

    lines.push(`**${f.name}: ${attr.label.toLowerCase()} is ${attr.fmt ? attr.fmt(v) : fmt(v, attr.unit)}** — ranked ${rank} of ${all.length} countries with data.`);
    // name the exact source for THIS number — "what's the source for X" is a
    // first-class question for an evidence-first tool
    const srcField = { radio: "news_radio", trust: "news_consumption", tv: "news_consumption", online: "news_consumption",
      social: "news_consumption", internet: "internet_pct", press: "press_freedom_rank", netfreedom: "internet_freedom",
      literacy: "literacy_pct", medianage: "median_age", finaccount: "financial_account_pct", smartphone: "smartphone_pct",
      mci: "mobile_connectivity_index", urban: "urban_pct", under15: "age_0_14_pct", population: "population" }[attrKey];
    const rawSrc = srcField ? f.sourcesMap[srcField] : null;
    const srcLabel = rawSrc ? String(rawSrc).replace(/\s*[—–-]?\s*https?:\/\/\S+/, "").trim() : attr.source;
    lines.push(`- Source: ${srcLabel}${f.retrievedOn ? ` *(record refreshed ${f.retrievedOn})*` : ""}`);
    if (qNorm) {
      const named = ["afrobarometer", "reuters", "dnr", "rsf", "freedom house", "world bank", "gsma"].find(sname => qNorm.includes(sname));
      if (named && !srcLabel.toLowerCase().includes(named))
        lines.push(`*Note: ${named.charAt(0).toUpperCase() + named.slice(1)} is not the origin of this particular indicator — the source above is. (Afrobarometer contributes the radio/news-source figures for African countries; connectivity comes from the World Bank/ITU.)*`);
    }
    if (regionAvg != null)
      lines.push(`\nFor context, the ${f.subregion} average is ${attr.fmt ? attr.fmt(regionAvg) : fmt(regionAvg, attr.unit)} (${regionAll.length} neighbours with data).`);
    const risks = riskLines(f).filter(r => r.toLowerCase().includes(attrKey === "press" ? "press" : attrKey === "internet" ? "internet" : attrKey === "trust" ? "trust" : "~none~"));
    if (risks.length) { lines.push(""); risks.forEach(r => lines.push("- " + r)); }
    blocks.push(lines.join("\n"));
  }
  return blocks.length ? blocks.join("\n\n") : null;
}

function composePlatform(ents, ev) {
  const p = ents.platforms[0];
  const pretty = PLATFORM_NAMES[p] || (p.charAt(0).toUpperCase() + p.slice(1));
  const leaders = [], present = [];
  for (const [iso, c] of Object.entries(COUNTRIES)) {
    const socials = ((c.media || {}).top_social || "").toLowerCase();
    if (!socials) continue;
    const list = socials.split(",").map(s => s.trim());
    const idx = list.findIndex(s => platformMatches(s, p));
    if (idx === 0) leaders.push([iso, c.population || 0]);
    else if (idx > 0) present.push([iso, c.population || 0]);
  }
  leaders.sort((a, b) => b[1] - a[1]);
  ev.add(`${pretty} — platform footprint`,
    `Counted from the Atlas's per-country leading-platform lists. Those lists are an editorial compilation cross-referenced with national media directories — an ordering, not measured audience share, and not a survey ranking. For measured platform use, see the countries carrying a Latinobarómetro platform-use battery. Each country's Sources tab names this provenance under "Leading outlets".`,
    []);
  const lines = [];
  lines.push(`**${pretty} is the #1 social platform in ${leaders.length} of 195 Atlas markets**${present.length ? ` and appears in the top platforms of ${present.length} more` : ""}.`);
  if (leaders.length) {
    lines.push(`\nLargest markets where it leads: ${leaders.slice(0, 8).map(([iso]) => COUNTRIES[iso].name).join(", ")}.`);
    lines.push(`\n*Note: platform lists are editorially compiled per country — they show market presence, not measured reach percentages.*`);
  }
  return lines.join("\n");
}

function composeMeta(ev, iso) {
  const nCountries = META ? META.country_count : Object.keys(COUNTRIES).length;
  const gen = META ? String(META.generated_at || "").slice(0, 10) : "n/a";
  let countryLine = "";
  if (iso && COUNTRIES[iso]) {
    const f = facts(iso);
    addCountryEvidence(f, ev);
    countryLine = `**${f.name} specifically:** record last refreshed ${f.retrievedOn || "n/a"}; news figures come from ${f.survey || "no integrated survey yet"}${f.surveyNote ? ` — *caveat: ${f.surveyNote}*` : ""}. Platform lists are editorially compiled (market presence, not measured reach).\n\n`;
  }
  ev.add("Atlas data inventory", `countries.json _meta (generated ${gen}) + daily trend engine${TRENDS ? ` (as of ${TRENDS.generated})` : ""}.`,
    [{ label: "Methodology & sources (this site)", url: "index.html" }, { label: "Topic Explorer", url: "topics.html" }]);
  const srcList = META && META.data_sources ? META.data_sources.slice(0, 10) : [];
  const lines = [];
  if (countryLine) lines.push(countryLine.trimEnd());
  lines.push(`**What I know and where it comes from.** I cover **${nCountries} countries** and **${REGISTRY.length} tracked topics**, refreshed automatically (country data weekly, trends daily${TRENDS ? ` — currently as of ${TRENDS.generated}` : ""}).`);
  lines.push("");
  lines.push("**My sources:**");
  for (const s of srcList) lines.push("- " + s);
  lines.push("");
  lines.push("**What you can ask me:** country media profiles (\"How do people in Nigeria get news?\"), comparisons (\"France vs Germany on trust\"), rankings (\"Top 5 African countries by internet access\"), live trends (\"What's trending in Kenya?\"), topics (\"Who covers climate change most?\"), and campaign guidance (\"How should we reach rural audiences in Mali?\").");
  lines.push("");
  lines.push("**What I won't do:** guess beyond the data, answer political questions, or use sources outside the Atlas. When I have no data, I say so.");
  return lines.join("\n");
}

// ---------------------------------------------------------------------------
const LANG_BASE_NAMES = { pa: "Punjabi", pnb: "Western Panjabi", uz: "Uzbek", az: "Azerbaijani",
  kk: "Kazakh", ms: "Malay", mn: "Mongolian", sr: "Serbian", ku: "Kurdish", zh: "Chinese",
  bs: "Bosnian", tts: "Northeastern Thai", nod: "Northern Thai", apc: "Levantine Arabic",
  arz: "Egyptian Arabic", ary: "Moroccan Arabic", apd: "Sudanese Arabic", aeb: "Tunisian Arabic" };

function formatFeasibility(f) {
  const rows = [];
  const net = f.internet, phone = f.smartphone;
  if (net != null) {
    const vid = net >= 60 && (phone == null || phone >= 55) ? "strong — most of the audience can stream"
      : net >= 35 ? "mixed — favor short, low-bandwidth video with subtitles; don't rely on online video alone"
      : "limited — online video reaches a minority";
    const tvNote = net < 60 && f.tv != null && f.tv >= 40 ? ` — but broadcast-TV video is separately viable (TV reaches ${fmt(f.tv)} weekly)` : "";
    rows.push(`**Online/streamed video:** ${vid}${tvNote} *(internet ${fmt(net)}${phone != null ? `, smartphones ${fmt(phone)}` : ""})*`);
  }
  if (f.radio != null)
    rows.push(`**Audio/radio:** ${f.radio >= 60 ? "strong daily habit" : f.radio >= 35 ? "established habit" : "modest reach"} — radio reaches ${fmt(f.radio)} weekly *(${f.radioSource || "source unspecified"})*; audio formats ride an existing behavior`);
  else
    rows.push(`**Audio/radio:** no measured radio figure for this country — the leading radio outlets in the Where section are a proxy for the audio market`);
  if (f.literacy != null)
    rows.push(`**Text:** ${f.literacy >= 90 ? "fully viable" : f.literacy >= 70 ? "viable with plain-language writing" : "limited — " + fmt(100 - f.literacy) + " of adults can't read it; lead with audio/visual"} *(literacy ${fmt(f.literacy)})*`);
  else
    rows.push(`**Text:** no literacy figure for this country — validate text-led formats locally before committing`);
  rows.push(`**Visual/infographic:** literacy-independent and low-bandwidth — safe everywhere, essential where text is limited`);
  return rows;
}

function prettyLang(l) {
  if (l.language && l.language !== l.code) return l.language;
  const base = String(l.code || "").split("_")[0];
  const scriptNote = /(_arab)/i.test(l.code || "") ? " (Arabic script)" : "";
  return (LANG_BASE_NAMES[l.code] || LANG_BASE_NAMES[base] || l.code) + scriptNote;
}

/** Languages sorted by population share. */
function langsByShare(f) {
  return [...f.languagesDetail].sort((a, b) => (b.pct || 0) - (a.pct || 0));
}

/**
 * The language to produce in FIRST.
 *
 * Not simply the biggest share: CLDR shares measure speaker capability and
 * overlap, so a widely-taught second language can out-rank the country's own
 * official one. Ethiopia is the clearest case — English scores 43% capability
 * against Amharic's 33%, but Amharic is what Ethiopian media publish in.
 * Prefer an official language with real reach; fall back to the largest share
 * only when no official language clears the bar. Every part of the brief must
 * use this same choice, or the summary and the detail contradict each other.
 * Returns null when the country has no language data.
 */
function primaryProductionLanguage(f) {
  const by = langsByShare(f);
  if (!by.length) return null;
  return by.find(l => l.official && l.pct >= 25) || by[0];
}

// ---------------------------------------------------------------------------
// THE CONSULTING ENGINE (rebuilt 2026-07-21 to DGC specification)
// ===========================================================================
// ROLE: this is not a repository of media information. It is a strategic
// intelligence and decision-support system for the UN Department of Global
// Communications. Its purpose is to synthesise evidence into actionable,
// well-reasoned recommendations — not to retrieve and reformat data.
//
// GUIDING PRINCIPLE: do not answer the question that was asked — answer the
// DECISION that needs to be made.
//
// REASONING WORKFLOW (every strategic question runs all five steps):
//   1. Infer the objective — what is the user actually trying to accomplish?
//   2. Retrieve only decision-relevant evidence (what would CHANGE the advice)
//   3. Evaluate across audience / platform / geography / political sensitivity
//      / language / media consumption / accessibility / timing / risk
//   4. Identify tradeoffs — nothing is universally "best"
//   5. Rank recommendations by confidence, and say why
//
// EVIDENCE DISCIPLINE: every claim is tagged at one of three tiers —
//   [measured]  a real Atlas figure with a named source
//   [inferred]  a defensible judgement derived from measured figures
//   [unknown]   the Atlas cannot know this; say so and name what would answer it
// A senior consultant distinguishes "the data shows" from "in my judgement"
// from "we'd need to find out". Fabricating the third as the first is the one
// unforgivable failure, so the tiers are structural, not decorative.
// ---------------------------------------------------------------------------

/** The decisions a UN comms officer is actually making. */
const OBJECTIVES = {
  crisis: {
    label: "urgent/crisis communication",
    re: /\b(crisis|emergency|urgent|outbreak|evacuat\w+|early warning|warning|alert|disaster|cyclone|flood|earthquake|conflict|displac\w+|famine)\b/,
    priority: ["radio", "TV", "social media", "online news"],
    rationale: "In an emergency the binding constraint is speed and universality of reach, not engagement quality. Broadcast reaches people without electricity-dependent devices or data plans, and keeps working when networks are congested or restricted.",
  },
  policymakers: {
    label: "reaching policymakers and elites",
    re: /\b(policy ?makers?|policy audience|government officials?|ministers?|diplomat\w*|elite\w*|decision ?makers?|parliament\w*|donors?|delegates?)\b/,
    priority: ["online news", "TV", "social media", "radio"],
    rationale: "Elite audiences are reached through the outlets that set the agenda for institutions — national press and broadcast — rather than by mass reach.",
  },
  youth: {
    label: "engaging young people",
    re: /\b(youth|young people|under ?25|under ?30|gen ?z|adolescents?|teenagers?|students?)\b/,
    priority: ["social media", "online news", "TV", "radio"],
    rationale: "Younger audiences skew toward social and short-form digital in most markets — but the Atlas holds no age-segmented platform data, so this is a population-structure inference, not a measurement.",
  },
  rural: {
    label: "reaching rural and remote populations",
    re: /\b(rural|remote|village\w*|countryside|farmers?|smallholders?|hard to reach)\b/,
    priority: ["radio", "TV", "social media", "online news"],
    rationale: "Rural reach is constrained by infrastructure. Radio is the only channel that routinely works without electricity, data, or literacy.",
  },
  trust: {
    label: "countering misinformation / rebuilding credibility",
    // "counter" and its verb forms only — "counter\w*" also matched
    // "counterparts", which made "who are our counterparts in Kenya?" open a
    // brief announcing a counter-misinformation decision the user never raised.
    re: /\b(misinformation|disinformation|fake news|rumou?rs?|counter(ing|ed|s)?|myth\w*|debunk\w*|credibility|fact ?check\w*)\b/,
    priority: ["radio", "TV", "online news", "social media"],
    rationale: "Correction only works through channels the audience already trusts; amplifying a correction on a low-trust channel can entrench the belief it targets.",
  },
  behaviour: {
    label: "driving behaviour change",
    re: /\b(vaccinat\w+|immunis\w+|immuniz\w+|health campaign|hand ?washing|nutrition|sanitation|behaviou?r change|uptake|adherence|screening)\b/,
    priority: ["radio", "TV", "social media", "online news"],
    rationale: "Behaviour change needs repeated exposure through locally trusted voices, not a single high-reach impression.",
  },
  awareness: {
    label: "maximising awareness and reach",
    re: /\b(awareness|reach|visibility|amplif\w+|launch|promote|publicis\w+|publiciz\w+)\b/,
    priority: ["radio", "TV", "online news", "social media"],
    rationale: "With awareness as the goal the ranking follows measured weekly reach, adjusted for how much of the population each channel can physically reach.",
  },
};

// ---------------------------------------------------------------------------
// Market Finder — reverse search: "which countries best fit this campaign?"
// Deterministic multi-criteria screening over every country with usable
// media-survey data. Countries lacking the required data are EXCLUDED with an
// explicit reason — never silently ranked low (same honesty rule as
// composeRanking). Weights are fixed, disclosed, and renormalized over the
// criteria a given search actually uses.
// ---------------------------------------------------------------------------
const FINDER_WEIGHTS = { reach: 45, language: 20, audience: 15, momentum: 10, openness: 10 };

function langShare(c, code) {
  const e = (c.languages_detail || []).find(l => l.code === code);
  return e ? e.pct : null;
}

export function findMarkets(opts = {}) {
  const objective = OBJECTIVES[opts.objectiveKey] || OBJECTIVES.awareness;
  const audience = opts.audience || null;               // "youth" | "rural" | null
  const language = opts.language || null;               // CLDR code, e.g. "en"
  const topicQid = opts.topicQid || null;
  const channelOverride = opts.channel || null;         // "radio"|"TV"|"online news"|"social media"
  const limit = opts.limit || 15;

  // active criteria and renormalized weights
  const active = { reach: true, openness: true, language: !!language,
                   audience: audience === "youth" || audience === "rural",
                   momentum: !!(topicQid && TRENDS) };
  const totalW = Object.entries(FINDER_WEIGHTS).filter(([k]) => active[k]).reduce((a, [, w]) => a + w, 0);
  const W = {}; for (const [k, w] of Object.entries(FINDER_WEIGHTS)) W[k] = active[k] ? w / totalW : 0;

  let pool = Object.keys(COUNTRIES);
  if (opts.isos && opts.isos.length) pool = pool.filter(iso => opts.isos.includes(iso));
  else if (opts.region) pool = pool.filter(iso => (COUNTRIES[iso].region || "") === opts.region);

  const ranked = [], excluded = [];
  for (const iso of pool) {
    const c = COUNTRIES[iso];
    const f = facts(iso);
    if (!f) continue;
    const rows = evaluateChannels(f, objective);
    if (!rows.length) {
      excluded.push({ iso, name: f.name, reason: (c.platform_use ? "platform-use data only — no news-channel survey" : "no media survey data") });
      continue;
    }
    let lead = rows[0];
    if (channelOverride) {
      lead = rows.find(r => r.name === channelOverride);
      if (!lead) { excluded.push({ iso, name: f.name, reason: `no ${channelOverride} survey data` }); continue; }
    }

    const comp = {};
    comp.reach = lead.effective;                               // 0-100 (digital already capped at internet)
    comp.openness = f.rsf != null ? f.rsf : (f.fh != null && COUNTRIES[iso].information_freedom
      ? (COUNTRIES[iso].information_freedom.political_freedom_score ?? 50) : 50);
    let langPct = null;
    if (language) { langPct = langShare(c, language); comp.language = langPct ?? 0; }
    if (audience === "youth")
      comp.audience = f.under15 != null ? Math.max(0, Math.min(100, ((f.under15 - 12) / (47 - 12)) * 100)) : 0;
    else if (audience === "rural")
      comp.audience = f.urban != null ? (100 - f.urban) : 0;
    let risingHit = null;
    if (active.momentum) {
      risingHit = (f.rising || []).find(r => r.qid === topicQid) || null;
      comp.momentum = risingHit ? 100 : 0;
    }

    const score = Object.entries(comp).reduce((a, [k, v]) => a + (W[k] || 0) * v, 0);
    const flags = [];
    if (f.fh === "Not Free") flags.push("Not Free — vet partner outlets individually");
    if (f.rsf != null && f.rsf < 40) flags.push(`press freedom ${Math.round(f.rsf)}/100`);
    if (f.fotn != null && f.fotn < 40) flags.push(`internet freedom ${f.fotn}/100 — platform-restriction risk`);
    const constructNote = /Arab Barometer/.test(f.survey || "") ? "primary-source construct"
      : /Eurobarometer/.test(f.survey || "") ? "general media-use construct"
      : /World Values/.test(f.survey || "") ? "daily+weekly construct" : null;

    ranked.push({
      iso, name: f.name, flag: c.flag || "", score: Math.round(score * 10) / 10,
      components: comp, lead: { name: lead.name, effective: lead.effective, measured: lead.measured, capped: lead.capped },
      langPct, under15: f.under15, urban: f.urban, internet: f.internet,
      population: f.pop, reachPeople: f.pop != null ? Math.round((lead.effective / 100) * f.pop) : null,
      risingHit, flags, survey: f.survey, constructNote, rsf: f.rsf, fh: f.fh,
    });
  }
  ranked.sort((a, b) => b.score - a.score);
  return {
    objective, audience, language, topicQid, channel: channelOverride,
    weights: Object.fromEntries(Object.entries(W).filter(([, v]) => v > 0)
      .map(([k, v]) => [k, Math.round(v * 100)])),
    ranked, top: ranked.slice(0, limit), excluded,
    methodNote: "Scores mix survey constructs (Reuters DNR weekly use, WVS daily+weekly, Eurobarometer general media use, Arab Barometer primary source) — treat close scores as ties. Digital reach is capped at internet penetration. Excluded countries lack the required survey data; they are not ranked low.",
  };
}

// The languages the screen can weigh. Adding a line here is all it takes to
// teach it a new one — the question-matching below reads this table directly.
const LANG_NAMES_FINDER = { en: "English", fr: "French", es: "Spanish", ar: "Arabic", pt: "Portuguese", ru: "Russian", zh: "Chinese", sw: "Swahili", hi: "Hindi" };
// The "-phone" words that name a language without saying its name.
const LANG_CUES_FINDER = { en: "anglophone", fr: "francophone", es: "hispanophone", pt: "lusophone" };
// Audiences the Atlas can screen on are youth and rural (population structure
// gives a real per-country figure). These three have no per-country data at
// all, so a screen that mentions them must say it could not weigh them.
const UNSCREENABLE_AUDIENCES = { women: "gender", older: "audience age", displaced: "displacement status" };

/** "3 with no radio survey data; 12 with no media survey data" — reasons, counted. */
function exclusionReasons(excluded) {
  const byReason = {};
  excluded.forEach(x => { byReason[x.reason] = (byReason[x.reason] || 0) + 1; });
  return Object.entries(byReason).map(([r, n]) => `${n} with ${r}`).join("; ");
}
/** Names the excluded countries when the list is short enough to stay readable. */
const exclusionNames = (excluded) => excluded.length <= 10 ? ` (${excluded.map(x => x.name).join(", ")})` : "";

function composeMarketFinder(ents, ev, qNorm) {
  const objective = inferObjective(qNorm, ents);
  const audience = (ents.audiences || []).includes("youth") ? "youth"
    : (ents.audiences || []).includes("rural") ? "rural" : null;
  // language ask ("english-speaking", "francophone")
  let language = null;
  for (const [code, name] of Object.entries(LANG_NAMES_FINDER)) {
    const cue = LANG_CUES_FINDER[code];
    if (qNorm.includes(" " + name.toLowerCase() + " ") || (cue && qNorm.includes(" " + cue + " "))) { language = code; break; }
  }
  // Criteria the question asked for that this screen genuinely cannot weigh.
  // Naming them is the point: a ranking that quietly dropped "women" or
  // "older audiences" still looks like an answer to the whole question.
  const unscreenable = [];
  for (const a of (ents.audiences || [])) if (UNSCREENABLE_AUDIENCES[a]) unscreenable.push(UNSCREENABLE_AUDIENCES[a]);
  const langAsk = language ? null : qNorm.match(/\b([a-z]{4,}) (?:language|speaking)\b/);
  if (langAsk && !FUZZY_STOPWORDS.has(langAsk[1])) unscreenable.push(`${titleCase(langAsk[1])}-language reach`);
  const topic = ents.topics[0] || null;
  // explicit channel ask ("a RADIO health campaign") becomes a hard filter —
  // countries without that channel's survey data are excluded, not guessed
  const channel = /\bradio\b/.test(qNorm) ? "radio"
    : /\b(tv|television)\b/.test(qNorm) ? "TV"
    : /\bsocial media\b/.test(qNorm) ? "social media"
    : /\bonline news\b/.test(qNorm) ? "online news" : null;
  const regionKey = ents.regions[0] || null;
  let isos = null, scopeName = "all 195 countries";
  if (regionKey && REGION_MAP[regionKey]) {
    isos = Object.keys(COUNTRIES).filter(iso => inRegionSpec(REGION_MAP[regionKey], iso, COUNTRIES[iso]));
    scopeName = regionDisplay(regionKey);
  }
  const res = findMarkets({
    objectiveKey: objective.key, audience, language, channel,
    topicQid: topic ? topic.qid : null, isos, limit: 10,
  });
  if (!res.ranked.length) {
    // Say WHICH data is missing. "All lack a news-channel survey" was false
    // whenever a channel filter did the excluding: Sweden, Denmark and Norway
    // carry full Reuters surveys and were dropped only for missing a radio
    // figure, so a radio screen told an officer those markets had no survey
    // data at all.
    const why = res.excluded.length
      ? ` ${res.excluded.length} countries were checked${exclusionNames(res.excluded)}: ${exclusionReasons(res.excluded)}.` : "";
    return `The Atlas cannot rank markets in ${scopeName} for this ask — none of the countries in scope have the required media-survey data.${why} This is a data gap, not a judgement on those markets.`;
  }

  const L = [];
  L.push(`**Market screening — ${objective.label}${topic ? ` · ${topic.label}` : ""}${channel ? ` · ${channel}-led` : ""}${language ? ` · ${LANG_NAMES_FINDER[language]} content` : ""}${audience ? ` · ${audience} audience` : ""} · ${scopeName}**`);
  L.push("");
  L.push(`*How this ranking works: ${Object.entries(res.weights).map(([k, w]) => `${k} ${w}%`).join(" · ")} — weights fixed and disclosed; every input figure is cited in the country's profile. [method]*`);
  L.push("");
  L.push(`| # | Country | Score | Lead channel (effective reach) |${language ? ` ${LANG_NAMES_FINDER[language]} |` : ""} Est. people reachable | Risk notes |`);
  L.push(`|---|---|---|---|${language ? "---|" : ""}---|---|`);
  res.top.forEach((r, i) => {
    L.push(`| ${i + 1} | ${r.name} | ${r.score} | ${r.lead.name} ${fmt(r.lead.effective)}${r.lead.capped ? " *(capped at internet access)*" : ""} |${language ? ` ${r.langPct != null ? Math.round(r.langPct) + "%" : "no data"} |` : ""} ${r.reachPeople != null ? fmtPop(r.reachPeople) : "n/a"} | ${r.flags.length ? r.flags[0] : "—"} |`);
  });
  L.push("");
  L.push(`**Why the top picks:**`);
  res.top.slice(0, 5).forEach((r, i) => {
    const why = [];
    why.push(`${r.lead.name} reaches ${fmt(r.lead.effective)} effectively [measured${r.constructNote ? ` — ${r.constructNote}` : ""}]`);
    if (language && r.langPct != null) why.push(`${LANG_NAMES_FINDER[language]} reaches ~${Math.round(r.langPct)}% (CLDR speaker capability) [measured]`);
    if (audience === "youth" && r.under15 != null) {
      // The label has to follow the number. Calling Denmark (15.6% under 15,
      // among the oldest populations on earth) "youth-heavy" contradicted the
      // audience score the same run had just given it.
      const shape = r.under15 >= 30 ? "a youth-heavy population structure"
        : r.under15 >= 20 ? "a moderate youth share"
        : "an older population, so reach rather than youth fit is what put this market on the list";
      why.push(`${fmt(r.under15)} of the population is under 15 — ${shape} [measured, structural inference for youth fit]`);
    }
    if (audience === "rural" && r.urban != null) why.push(`${fmt(100 - r.urban)} rural population [measured]`);
    if (r.risingHit) why.push(`attention to ${topic.label} is currently rising in this market (+${Math.round(r.risingHit.velocity * 100)}% vs baseline) [measured, ~120-day window]`);
    if (r.flags.length) why.push(`caution: ${r.flags.join("; ")} [measured]`);
    L.push(`${i + 1}. **${r.name}** — ${why.join("; ")}.`);
    ev.add(`${r.name} — screening inputs`, `Score ${r.score}/100. Survey: ${r.survey || "n/a"}. All inputs from the Atlas country record.`, countryLinks(r.iso));
  });
  L.push("");
  if (res.excluded.length) {
    L.push(`**Not rankable (${res.excluded.length} countries)${exclusionNames(res.excluded)}:** ${exclusionReasons(res.excluded)}. They are excluded for missing data — not ranked low; the map's grey tier shows them.`);
    L.push("");
  }
  if (unscreenable.length) {
    L.push(`**This screen could not weigh ${unscreenable.join(" or ")}.** The Atlas holds no per-country data on ${unscreenable.length > 1 ? "those" : "that"} — the ranking above does NOT reflect ${unscreenable.length > 1 ? "them" : "it"}, so treat it as a shortlist on the criteria named in the weights, not an answer to the whole ask.`);
    L.push("");
  }
  L.push(`**Confidence: Medium.** ${res.methodNote}`);
  L.push("");
  L.push(`### Evidence used`);
  L.push(`*Every input figure traces to the numbered sources beneath this answer — each source name is a clickable link.*`);
  L.push("");
  L.push(`*Advisory. Screening is decision support for shortlisting, not a final market selection — validate top candidates with the full country brief ("How should we run this in [country]?") and local teams before committing budget.*`);
  ev.add("Market screening method", `Deterministic multi-criteria screen. Weights: ${JSON.stringify(res.weights)}. ${res.methodNote}`, []);
  return L.join("\n");
}

function inferObjective(qNorm, ents) {
  const hits = [];
  for (const [key, o] of Object.entries(OBJECTIVES)) if (o.re.test(qNorm)) hits.push(key);
  // audience qualifiers detected elsewhere are strong objective signals
  if (ents.audiences.includes("rural") && !hits.includes("rural")) hits.push("rural");
  if (ents.audiences.includes("youth") && !hits.includes("youth")) hits.push("youth");
  if (!hits.length) return { key: "awareness", inferred: true, ...OBJECTIVES.awareness };
  // crisis outranks everything; otherwise first match wins
  const key = hits.includes("crisis") ? "crisis" : hits[0];
  return { key, inferred: false, ...OBJECTIVES[key] };
}

/**
 * Score each channel against the inferred objective.
 * Effective reach caps digital channels at internet penetration: a survey can
 * report 94% online news use in a country where 41% are online, because it
 * surveyed the connected population. Treating that as national reach is the
 * single most expensive mistake this tool can prevent.
 */
function evaluateChannels(f, objective) {
  const raw = { "TV": f.tv, "radio": f.radio, "online news": f.online, "social media": f.social };
  const rows = [];
  for (const [name, measured] of Object.entries(raw)) {
    if (measured == null) continue;
    const digital = name === "online news" || name === "social media";
    const capped = digital && f.internet != null ? Math.min(measured, f.internet) : measured;
    const priorityIdx = objective.priority.indexOf(name);
    // objective fit: a small deliberate weighting, never enough to override a
    // large reach gap — the evidence leads, the objective breaks ties
    const fitBonus = priorityIdx >= 0 ? (objective.priority.length - priorityIdx) * 3 : 0;
    rows.push({
      name, measured, effective: capped, capped: digital && capped < measured,
      score: capped + fitBonus, priorityIdx: priorityIdx < 0 ? 99 : priorityIdx,
      fit: priorityIdx <= 1 ? "Strong" : priorityIdx === 2 ? "Moderate" : "Weak",
    });
  }
  // Rank by objective FIT first, then by effective reach inside each fit band.
  // Reach alone would recommend a channel the brief's own table calls "Weak"
  // for the job — e.g. leading a counter-misinformation push on the channel
  // most likely to amplify the rumour. Fit decides the band; reach decides
  // the order within it.
  const band = { Strong: 0, Moderate: 1, Weak: 2 };
  rows.sort((a, b) => (band[a.fit] - band[b.fit]) || (b.effective - a.effective));
  // Flag when fit and reach disagree — that tension is itself a finding the
  // brief must surface rather than bury.
  const biggestReach = [...rows].sort((a, b) => b.effective - a.effective)[0];
  if (biggestReach && rows[0] && biggestReach.name !== rows[0].name) {
    rows[0].reachTradeoff = biggestReach;
  }
  return rows;
}

/** Confidence in the recommendation, with the reason stated. */
function assessConfidence(f, channels, objective) {
  const reasons = [], caveats = [];
  let level = "High";
  const hasSurvey = channels.length > 0;
  const isEstimate = /estimate/i.test(f.survey || "");
  const nonRep = !!f.surveyNote;

  // "Compiled estimate" sources (DataReportal and similar) are NOT surveys —
  // calling them one was inflating confidence to High in several markets.
  const src = String(f.survey || "");
  const isCompilation = isEstimate || /datareportal|compiled|other:/i.test(src);
  const isRealSurvey = /reuters|dnr|afrobarometer|arab barometer|asian barometer|latinobar|eurobarometer|world values/i.test(src);

  if (!hasSurvey) {
    level = "Low";
    reasons.push(`no news-consumption survey covers ${f.name}, so no channel can be ranked from evidence`);
  } else if (isCompilation) {
    level = "Medium";
    reasons.push(`${f.name}'s channel figures are a compiled estimate (${src || "source unstated"}), not a national survey — treat the ordering as indicative and the exact values as soft`);
  } else if (nonRep) {
    level = "Medium";
    reasons.push(`the underlying survey (${src}) samples online, urban, and more-connected respondents in ${f.name} — it understates rural and offline audiences`);
  } else if (isRealSurvey) {
    reasons.push(`channel figures come from a national survey (${src})`);
  } else {
    level = "Medium";
    reasons.push(`channel figures come from ${src || "an unnamed source"}, whose sampling frame the Atlas cannot verify`);
  }

  // Afrobarometer fieldwork is 2023; in countries that have since entered
  // large-scale conflict or displacement, pre-crisis media habits are not a
  // safe basis for a crisis plan.
  const conflictAffected = ["SDN", "AFG", "MMR", "SYR", "YEM", "HTI", "MLI", "BFA", "NER", "SSD", "COD", "SOM", "LBY", "UKR", "PSE"];
  if (conflictAffected.includes(f.iso)) {
    level = "Low";
    reasons.push(`${f.name} has experienced major conflict or displacement since the survey fieldwork — pre-crisis media habits are a weak guide to current reach, and infrastructure may have changed materially`);
  }
  // A question about an elite/occupational/city audience cannot be answered by
  // national population data at High confidence, however good that data is.
  if (objective.key === "policymakers") {
    level = level === "High" ? "Medium" : level;
    reasons.push(`the request targets an elite/occupational audience and the Atlas holds only national population data — no elite-audience measurement exists`);
  }

  if (f.internet == null) { level = level === "High" ? "Medium" : level; caveats.push("no internet-penetration figure to sanity-check digital reach against"); }
  if (objective.key === "youth" || objective.key === "policymakers")
    caveats.push(`the objective targets a specific segment, and the Atlas holds no age, income, or occupation crosstabs — segment guidance here is inference from population structure, not measurement`);
  if (objective.key === "rural" && f.radio == null)
    caveats.push("no measured radio figure for this country, which is the channel that usually decides rural reach");
  if (f.languagesDetail.length === 0) caveats.push("no language-share data, so production-language advice is unavailable");

  if (caveats.length >= 3 && level === "High") level = "Medium";
  return { level, reasons, caveats };
}

/** Tradeoffs — nothing is universally best; name what each choice costs. */
function buildTradeoffs(f, channels, objective) {
  const t = [];
  const byName = Object.fromEntries(channels.map(c => [c.name, c]));
  const digital = [byName["online news"], byName["social media"]].filter(Boolean);
  const broadcast = [byName["radio"], byName["TV"]].filter(Boolean);

  for (const d of digital) {
    if (d.capped)
      t.push(`**${d.name}** reports ${fmt(d.measured)} weekly use, but only ${fmt(f.internet)} of the country is online — it is strong *among the connected*, and structurally cannot carry a national message alone. [inferred]`);
  }
  if (byName["radio"] && byName["online news"] && byName["radio"].effective > byName["online news"].effective)
    t.push(`**Radio out-reaches online news nationally** (${fmt(byName["radio"].measured)} vs an effective ${fmt(byName["online news"].effective)}) — but it is harder to target, harder to measure, and cannot carry links or visuals. [measured reach, inferred implication]`);
  if (byName["social media"] && f.rsf != null && f.rsf < 40)
    t.push(`**Social media** offers the cheapest scale, but with press freedom at ${Math.round(f.rsf)}/100 it also carries the highest exposure to takedowns, throttling, and coordinated pushback. [measured risk]`);
  if (byName["TV"] && byName["TV"].measured >= 40)
    t.push(`**TV** reaches ${fmt(byName["TV"].measured)} weekly and confers institutional credibility, but production and placement cost far more per asset than digital, and the Atlas holds no cost data to quantify that. [measured reach, cost unknown]`);
  if (f.trust != null && f.trust < 40)
    t.push(`Trust in news is ${f.trust}% — high-reach *outlet* placement buys less persuasion here than a lower-reach trusted intermediary would. Reach and credibility pull in opposite directions in this market. [measured]`);
  if (objective.key === "youth")
    t.push(`Youth-targeting pulls toward social platforms, but the Atlas cannot confirm youth platform preferences for this country — choosing social over broadcast here is a judgement call, not an evidence-backed one. [unknown]`);
  return t;
}

/** Ranked, justified opportunities — each one answers "why?". */
function buildOpportunities(f, channels, objective, ev) {
  const ops = [];
  const lead = channels[0];
  // In a state-influenced environment the curated outlet list is NOT a
  // recommendation — it names who has reach, which is a different question
  // from who is an appropriate UN partner. Never present it as a placement plan.
  const restricted = f.fh === "Not Free" || (f.rsf != null && f.rsf < 40);
  const outletFor = (ch) => ch === "radio" ? f.outlets.top_radio : ch === "TV" ? f.outlets.top_tv
    : ch === "online news" ? f.outlets.top_online_news : ch === "social media" ? f.outlets.top_social : null;

  if (lead) {
    const why = [];
    why.push(`reaches ${fmt(lead.measured)} weekly${lead.capped ? `, though its national-effective reach is nearer ${fmt(lead.effective)} once internet access is accounted for` : ""} [measured]`);
    if (lead.fit === "Weak")
      why.push(`chosen on reach despite a weak fit for this objective — ${objective.rationale.replace(/\.$/, "")}. Treat this as a reach-vs-fit tradeoff, not a natural match [inferred]`);
    else
      why.push(`fits the inferred objective — ${objective.rationale.replace(/\.$/, "")} [inferred]`);
    if (lead.reachTradeoff)
      why.push(`${lead.reachTradeoff.name} has higher raw reach (${fmt(lead.reachTradeoff.effective)} effective) but a weaker fit for ${objective.label}; if raw reach matters more than fit here, invert this ranking [inferred]`);
    const outlets = outletFor(lead.name);
    if (outlets && !restricted) why.push(`established outlets to place through: ${outlets} [measured]`);
    else if (outlets) why.push(`outlets with reach on this channel: ${outlets} — **listed for reach, not endorsed as partners**; vet each for independence before approaching [measured reach, independence unknown]`);
    ops.push({ title: `Lead on ${lead.name}`, why, confidence: lead.fit === "Weak" ? "Medium" : "High" });
  }
  const second = channels[1];
  if (second && lead) {
    const leadIsBroadcast = lead.name === "radio" || lead.name === "TV";
    const secondIsBroadcast = second.name === "radio" || second.name === "TV";
    let complement;
    if (leadIsBroadcast && !secondIsBroadcast) complement = "broadcast cannot carry links, forms, or shareable assets — digital closes that gap";
    else if (!leadIsBroadcast && secondIsBroadcast) complement = f.internet != null && f.internet < 60
      ? `digital cannot reach the ${fmt(100 - f.internet)} of the population that is offline — broadcast closes that gap`
      : "broadcast adds passive, lean-back exposure that digital's opt-in model misses";
    else complement = `both are ${leadIsBroadcast ? "broadcast" : "digital"} channels, so this adds frequency and a second audience slice rather than covering a different access gap`;
    ops.push({ title: `Pair with ${second.name} as the secondary channel`,
      why: [`adds ${fmt(second.measured)} weekly reach${second.capped ? ` (${fmt(second.effective)} effective)` : ""} [measured]`, `${complement} [inferred]`],
      confidence: "Medium" });
  }
  if (f.languagesDetail.length) {
    const by = langsByShare(f);
    // CLDR shares are speaker-CAPABILITY and overlap (a person counts in
    // several), so they never sum to 100 — see primaryProductionLanguage()
    // for why the biggest share is not automatically the one to produce in.
    const primary = primaryProductionLanguage(f);
    const secondL = by.find(l => l !== primary && l.pct >= 25 && (l.official || l.pct >= 40));
    const why = [`${prettyLang(primary)} is spoken by ${Math.round(primary.pct)}% of the population${primary.official ? " and is official" : ""} [measured, Unicode CLDR]`];
    if (secondL) why.push(`${prettyLang(secondL)} adds reach at ${Math.round(secondL.pct)}%${secondL.official ? " (also official)" : ""} — CLDR shares overlap, so these are speaker-capability figures, not additive audience slices [measured, inferred implication]`);
    const eng = f.languagesDetail.find(l => (l.code || "").split("_")[0] === "en");
    if (eng && eng.pct < 50 && primary !== eng) why.push(`English-only production would leave roughly ${Math.round(100 - eng.pct)}% of people without a version in a language they speak [inferred]`);
    ops.push({ title: `Produce in ${prettyLang(primary)}${secondL ? ` and ${prettyLang(secondL)}` : ""} first`, why, confidence: "High" });
  }
  if (f.trust != null && f.trust < 45)
    ops.push({ title: `Route through trusted intermediaries, not just outlets`,
      why: [`trust in news is ${f.trust}% — below the level at which outlet placement reliably persuades [measured]`,
            `community organisations, local creators and messaging apps carry credibility that mass channels do not [inferred — the Atlas has no intermediary-level data]`],
      confidence: "Medium" });
  if (!channels.length)
    ops.unshift({ title: `Establish a channel baseline before committing budget`,
      why: [`no news-consumption survey covers ${f.name}, so no channel can be ranked from evidence — any channel claim here would be invented [unknown]`,
            `the outlet lists and connectivity figures below are the starting point for a local media audit, not a substitute for one [measured]`],
      confidence: "Low" });
  // sequential numbering — a list that starts at 3 reads as though items were lost
  ops.forEach((o, i) => { o.rank = i + 1; });
  return ops;
}

/** The consulting brief. Structure is mandatory and identical every time. */
function composeConsultingBrief(f, ev, ents, qNorm) {
  addCountryEvidence(f, ev);
  const objective = inferObjective(qNorm, ents);
  const channels = evaluateChannels(f, objective);
  const conf = assessConfidence(f, channels, objective);
  const tradeoffs = buildTradeoffs(f, channels, objective);
  const ops = buildOpportunities(f, channels, objective, ev);
  const topic = ents.topics[0] || null;
  const t = topic && TRENDS && TRENDS.topics[topic.qid] ? TRENDS.topics[topic.qid] : null;
  if (t) addTrendEvidence(t.label_en, ev);
  const L = [];
  const lead = channels[0];

  L.push(`**Strategic brief — ${t ? `${t.label_en} in ` : topic ? `${topic.label} in ` : ""}${f.name}**`);
  L.push(`*Decision being addressed: ${objective.label}${objective.inferred ? " (inferred from your question — say the goal explicitly if it's different)" : ""}.*`);
  L.push("");

  // ---- EXECUTIVE SUMMARY: the 30-second version ----
  L.push(`### Executive summary`);
  const es = [];
  if (lead) es.push(`**Lead on ${lead.name}** (${fmt(lead.measured)} weekly reach${lead.capped ? `; ~${fmt(lead.effective)} nationally once internet access is accounted for` : ""}).`);
  const esLang = primaryProductionLanguage(f);
  if (esLang) es.push(`**Produce in ${prettyLang(esLang)} first** — ${Math.round(esLang.pct)}% of the population${esLang.official ? ", and official" : ""}.`);
  const headlineRisk = f.fh === "Not Free" ? `**Treat the media environment as constrained** — Freedom House rates ${f.name} Not Free; vet every partner outlet for independence.`
    : (f.internet != null && f.internet < 40) ? `**Do not run this digital-only** — ${fmt(f.internet)} internet penetration means a digital-only plan structurally misses most of the country.`
    : (f.trust != null && f.trust < 40) ? `**Credibility is the binding constraint**, not reach — trust in news is ${f.trust}%.`
    : conf.level !== "High" ? `**Validate locally before committing budget** — confidence in this recommendation is ${conf.level}.` : null;
  if (headlineRisk) es.push(headlineRisk);
  es.slice(0, 3).forEach((s, i) => L.push(`${i + 1}. ${s}`));
  L.push("");
  L.push(`**Confidence: ${conf.level}.** ${sentence(conf.reasons.join("; "))}`);
  L.push("");

  // ---- KEY INSIGHTS ----
  L.push(`### Key insights`);
  const ins = [];
  // only a digital channel is ever capped, so the sentence always names the
  // lead channel itself — spelling out which one keeps it a whole sentence
  if (lead && lead.capped)
    ins.push(`The obvious digital-first read is wrong here. ${lead.name.charAt(0).toUpperCase() + lead.name.slice(1)} figures describe the ${fmt(f.internet)} of the population that is online — not the country. [measured]`);
  const radio = channels.find(c => c.name === "radio"), online = channels.find(c => c.name === "online news");
  if (radio && online && radio.effective > online.effective)
    ins.push(`Radio out-reaches online news in national terms (${fmt(radio.measured)} vs an effective ${fmt(online.effective)}) — a broadcast-led plan is the higher-reach choice, not the conservative one. [measured]`);
  if (f.medianAge != null && f.medianAge <= 22)
    ins.push(`This is a very young country (median age ${f.medianAge}${f.under15 != null ? `, ${fmt(f.under15)} under 15` : ""}) — content aimed at adults reaches a smaller share of the population than in most markets. [measured]`);
  if (f.trust != null) ins.push(`Trust in news is ${f.trust}% — ${f.trust >= 50 ? "high enough that established outlets can lend credibility to the message" : "low enough that placement alone will not persuade; the messenger matters more than the outlet"}. [measured trust, inferred implication]`);
  if (f.rsf != null && f.rsf < 40) ins.push(`Press freedom is ${Math.round(f.rsf)}/100 — assume editorial interference and plan content review accordingly. [measured]`);
  if (t) {
    const vel = Math.round(t.global_velocity * 100);
    ins.push(`Attention to ${t.label_en} is ${t.momentum} globally (${vel > 0 ? "+" : ""}${vel}% against its 30-day baseline) — ${t.momentum === "rising" ? "the window is open now" : "this content will need its own news hook rather than riding existing attention"}. [measured, ~120-day window]`);
  }
  if (f.englishPct != null && /\benglish\b/.test(qNorm))
    // asked-about explicitly — must survive the 5-insight cap, so it leads
    ins.unshift(`English reaches about ${Math.round(f.englishPct)}% of ${f.name} — a CLDR speaker-capability share, so it overlaps with other languages rather than adding to them. [measured]`);
  const adm = adMarketSignal(f);
  if (adm) {
    ins.push(adm.text);
    ev.add(adm.evTitle, adm.evDetail, AD_MARKET_LINKS);
  }
  // a mandatory section must never render as a bare header — in a data-poor
  // market the absence of evidence IS the insight
  if (!ins.length) {
    ins.push(`The Atlas holds almost no measured data for ${f.name} — no news-consumption survey${f.internet == null ? ", no connectivity figure" : ""}${f.trust == null ? ", no trust measurement" : ""}. That absence is the finding: any confident channel claim about this market, from any tool, is not evidence-based. [unknown]`);
    if (f.outlets.top_tv || f.outlets.top_radio || f.outlets.top_online_news)
      ins.push(`What does exist is a curated list of the outlets operating there — a starting point for a local media audit, not a reach ranking. [measured]`);
    if (f.languagesDetail.length)
      ins.push(`Language shares are available and are the most actionable thing the Atlas can offer for ${f.name}. [measured, Unicode CLDR]`);
  }
  ins.slice(0, 5).forEach(s => L.push(`- ${s}`));
  L.push("");

  // ---- STRATEGIC ASSESSMENT ----
  L.push(`### Strategic assessment`);
  const bySize = [...channels].sort((a, b) => b.measured - a.measured);
  // never call a compiled estimate "measured"
  const reachWord = /estimate|datareportal|compiled|other:/i.test(String(f.survey || "")) ? "estimated" : "measured";
  const netClause = f.internet != null ? `${fmt(f.internet)} internet penetration` : `no internet-penetration figure on record`;
  L.push(`**What's happening:** ${f.name} has ${netClause}${f.smartphone != null ? ` and ${fmt(f.smartphone)} smartphone adoption` : ""}, with ${bySize.length ? `${reachWord} weekly news reach of ${bySize.map(c => `${c.name} ${fmt(c.measured)}`).join(", ")}` : "no integrated news-consumption survey"}. ${f.urban != null ? `${fmt(f.urban)} of people live in urban areas.` : ""} ${f.internet != null || bySize.length ? "[measured]" : "[unknown — these fields are empty for this territory]"}`);
  if (f.landscapeNote) {
    let note = f.landscapeNote;
    if (note.length > 340) note = note.slice(0, 340).replace(/[;,.\s]+\S*$/, "") + " …";
    L.push("");
    L.push(`**Media landscape:** ${note} *(CIA World Factbook)* [measured]`);
  }
  L.push("");
  L.push(`**Why it matters for this decision:** ${objective.rationale} [inferred]`);
  if (channels.length && lead) {
    L.push("");
    L.push(`**How the channels compare once corrected for who can actually be reached:**`);
    L.push(`| Channel | Weekly reach (measured) | Effective national reach | Fit for ${objective.label} |`);
    L.push(`|---|---|---|---|`);
    for (const c of channels) {
      L.push(`| ${c.name} | ${fmt(c.measured)} | ${fmt(c.effective)}${c.capped ? " *(capped at internet access)*" : ""} | ${c.fit} |`);
    }
    L.push("");
    L.push(`*Ranked by fit for this objective first, then by effective national reach — not by headline survey reach.*`);
  }
  L.push("");

  // ---- OPPORTUNITIES (ranked, justified) ----
  L.push(`### Opportunities — ranked`);
  ops.forEach(o => {
    L.push(`**${o.rank}. ${o.title}** — confidence: ${o.confidence}`);
    o.why.forEach(w => L.push(`   - Why: ${w}`));
  });
  L.push("");

  // ---- TRADEOFFS (always emitted — in a data-poor market the absence of a
  // basis for choosing IS the tradeoff, and hiding it would be the failure) ----
  L.push(`### Tradeoffs`);
  L.push(`*Nothing here is universally best — these are the costs of each choice.*`);
  if (tradeoffs.length) tradeoffs.slice(0, 5).forEach(x => L.push(`- ${x}`));
  else if (!channels.length)
    L.push(`- The binding tradeoff is that **no channel evidence exists for ${f.name}** — choosing any lead channel here trades measurable reach for a guess. Commissioning a small local media audit before spending is almost certainly cheaper than a misdirected campaign. [unknown]`);
  else
    L.push(`- No sharp tradeoffs surface in the available data for ${f.name}; the channel differences are small enough that execution quality will matter more than channel choice. [inferred]`);
  L.push("");

  // ---- RISKS ----
  L.push(`### Risks`);
  const risks = riskLines(f).map(r => `${r} [measured]`);
  if (f.fotn != null && f.fotn < 40) risks.push(`Internet freedom is ${f.fotn}/100 (Freedom House) — plan for platform restriction and keep a broadcast fallback. [measured]`);
  if (f.fh === "Not Free" || (f.rsf != null && f.rsf < 40))
    risks.push(`Partner outlets must be vetted individually for independence — state-influenced outlets carry reach but are usually inappropriate partners for content that conflicts with official policy. [inferred from measured freedom scores]`);
  if (!risks.length) risks.push(`No structural red flags in the Atlas's risk indicators for ${f.name}. [measured]`);
  risks.slice(0, 6).forEach(r => L.push(`- ${r}`));
  L.push("");

  // ---- CONFIDENCE + WHAT WOULD CHANGE THE ANSWER ----
  L.push(`### Confidence and limits`);
  L.push(`**Overall confidence: ${conf.level}** — ${conf.reasons.join("; ")}.`.replace(/\.\.$/, "."));
  if (conf.caveats.length) {
    L.push("");
    L.push(`**What the Atlas cannot tell you here** (and what would raise confidence):`);
    conf.caveats.forEach(c => L.push(`- ${c}`));
  }
  L.push("");
  L.push(`**Not available at any confidence level:** past campaign performance, format-level effectiveness (video vs text vs audio), age/gender breakdowns, cost per channel, and day-of-week or seasonal timing. No free data source measures these per country — treat any such claim from any tool with suspicion. [unknown]`);
  L.push("");

  // ---- EVIDENCE USED ----
  // Kept as a mandatory section header, but the listing itself is now the
  // numbered footnote block the app renders beneath every answer (2026-07-23
  // directive: cite sources footnote-style, not verbatim in the response).
  L.push(`### Evidence used`);
  L.push(`*Every figure above traces to the numbered sources beneath this answer${f.retrievedOn ? ` (country record refreshed ${f.retrievedOn})` : ""} — each source name is a clickable link.*`);
  L.push("");
  L.push(`*Advisory. This is evidence-based decision support produced by an automated system, not a final strategy. Every recommendation above is tagged [measured] where it rests on Atlas data and [inferred] where it is reasoned judgement; anything marked [unknown] needs human research. Validate with local teams before committing budget.*`);
  return L.join("\n");
}

/**
 * Region-level consulting brief. Same mandatory structure as the single-country
 * version; the strategic content is the SPREAD between countries, because that
 * is what actually decides a regional plan.
 */
function composeRegionConsultingBrief(fs, ev, ents, qNorm, regionName) {
  fs.forEach(f => addCountryEvidence(f, ev));
  const objective = inferObjective(qNorm, ents);
  const topic = ents.topics[0] || null;
  const t = topic && TRENDS && TRENDS.topics[topic.qid] ? TRENDS.topics[topic.qid] : null;
  if (t) addTrendEvidence(t.label_en, ev);
  const L = [];

  const withSurvey = fs.filter(f => f.tv != null || f.online != null || f.radio != null);
  const lowNet = fs.filter(f => f.internet != null && f.internet < 35);
  const strongRadio = fs.filter(f => f.radio != null && f.radio >= 50);
  const restricted = fs.filter(f => f.fh === "Not Free" || (f.rsf != null && f.rsf < 40));
  const conf = withSurvey.length === fs.length ? "Medium" : withSurvey.length >= fs.length / 2 ? "Medium" : "Low";
  const confWhy = `${withSurvey.length} of ${fs.length} covered countries have an integrated news-consumption survey; regional advice averages across very different media systems, so country-level briefs are always sharper`;

  L.push(`**Strategic brief — ${t ? `${t.label_en} across ` : ""}${regionName}**`);
  L.push(`*Decision being addressed: ${objective.label}${objective.inferred ? " (inferred from your question)" : ""}.*`);
  L.push("");

  L.push(`### Executive summary`);
  L.push(`1. **There is no single regional plan.** ${regionName} splits by connectivity — ${lowNet.length ? `${lowNet.map(f => f.name).join(", ")} ${lowNet.length === 1 ? "is" : "are"} below 35% internet and need broadcast-led distribution` : "connectivity is broadly comparable across the covered countries"}. [measured]`);
  if (strongRadio.length) L.push(`2. **Radio is the regional backbone** — ≥50% weekly reach in ${strongRadio.map(f => f.name).join(", ")}. A digital-only regional plan structurally under-delivers. [measured]`);
  else L.push(`2. **Lead country-by-country, not region-wide** — channel leadership differs across the covered markets. [measured]`);
  L.push(`3. **${restricted.length ? `Vet partners in ${restricted.map(f => f.name).join(", ")}` : "No systemic press-freedom red flags across the covered countries"}** — ${restricted.length ? "state-influenced media environments require partner-by-partner independence checks" : "partner selection can follow reach"}. [measured]`);
  L.push("");
  L.push(`**Confidence: ${conf}.** ${sentence(confWhy)}`);
  L.push("");

  L.push(`### Key insights`);
  L.push(composeRegionBrief(fs, ev, ents, regionName));
  L.push("");

  L.push(`### Strategic assessment`);
  L.push(`**Why the split matters for this decision:** ${objective.rationale} [inferred]`);
  L.push("");
  L.push(`**Format feasibility across the region** *(inferred from infrastructure and literacy — the Atlas measures no format performance)*:`);
  if (strongRadio.length) L.push(`- Audio-first is the safest regional bet — radio ≥50% weekly in ${strongRadio.map(f => f.name).join(", ")}. [measured reach, inferred implication]`);
  if (lowNet.length) L.push(`- Avoid online-video-led plans in ${lowNet.map(f => f.name).join(", ")} (internet <35%); broadcast TV remains viable where TV reach is strong. [inferred]`);
  L.push(`- Short, low-bandwidth video with subtitles is the format that travels across both connectivity tiers. [inferred]`);
  L.push("");

  L.push(`### Opportunities — ranked`);
  L.push(`**1. Segment the region before buying anything** — confidence: High`);
  L.push(`   - Why: the connectivity spread inside ${regionName} is wider than the gap between channels, so one regional buy wastes budget in half the markets. [measured]`);
  L.push(`**2. Lead broadcast where connectivity is low, digital where it is high** — confidence: ${conf}`);
  L.push(`   - Why: effective national reach, not survey headline reach, is what determines who actually sees the content. [inferred]`);
  L.push(`**3. Produce per-country language versions** — confidence: High`);
  L.push(`   - Why: ${fs.filter(f => f.languagesDetail.length).slice(0, 3).map(f => `${f.name} (${prettyLang(primaryProductionLanguage(f))})`).join(", ")} — the region has no shared majority language. [measured, Unicode CLDR]`);
  L.push("");

  L.push(`### Risks`);
  const rl = fs.flatMap(f => riskLines(f)).slice(0, 6).map(r => `${r} [measured]`);
  if (!rl.length) rl.push(`No structural red flags across the covered countries. [measured]`);
  rl.forEach(r => L.push(`- ${r}`));
  L.push("");

  L.push(`### Confidence and limits`);
  L.push(`**Overall confidence: ${conf}** — ${confWhy}.`);
  L.push(`- Coverage: this brief analyses the region's ${fs.length} most populous countries with data, not every country in ${regionName}.`);
  L.push(`**Not available at any confidence level:** past campaign performance, format effectiveness, age/gender breakdowns, cost, and seasonal timing. [unknown]`);
  L.push("");
  L.push(`### Evidence used`);
  L.push(`*Covers ${fs.map(f => f.name).join(", ")}. Every figure traces to the numbered sources beneath this answer — each source name is a clickable link.*`);
  L.push("");
  L.push(`*Advisory. Evidence-based decision support from an automated system, not a final strategy. Claims are tagged [measured] or [inferred]; [unknown] items need human research. Validate with local teams before committing budget.*`);
  return L.join("\n");
}

/** "What's trending in <region>?" — aggregate rising topics across the region. */
function composeRegionTrends(fs, ev, regionName) {
  if (!TRENDS) return null;
  const rising = [];
  for (const f of fs)
    for (const r of f.rising) rising.push({ label: r.label_en, velocity: r.velocity, country: f.name });
  rising.sort((a, b) => b.velocity - a.velocity);
  const seen = new Set(), top = [];
  for (const r of rising) {
    if (seen.has(r.label)) { top.find(x => x.label === r.label).countries.push(r.country); continue; }
    seen.add(r.label);
    top.push({ label: r.label, velocity: r.velocity, countries: [r.country] });
    if (top.length >= 8) break;
  }
  const distinct = [];
  for (const f of fs)
    for (const d of f.distinctive.slice(0, 2)) distinct.push(`**${d.label_en}** (${d.vs_global_avg}× in ${f.name})`);
  if (!top.length && !distinct.length) return null;
  addTrendEvidence(regionName, ev);
  const lines = [`**Trending across ${regionName}** (as of ${TRENDS.generated}):\n`];
  for (const t of top)
    lines.push(`- **${t.label}** +${Math.round(t.velocity * 100)}% vs its 30-day baseline (${t.countries.slice(0, 3).join(", ")})`);
  if (!top.length) lines.push("- No topics are spiking sharply this week across the region's covered countries.");
  if (distinct.length)
    lines.push(`\nStanding distinctive interests: ${[...new Set(distinct)].slice(0, 6).join(", ")}.`);
  lines.push(`\n*Coverage: the region's ${fs.length} most populous countries with trend data. Attention is measured from Wikipedia reading patterns — a documented approximation.*`);
  return lines.join("\n");
}

/** Region-vs-region aggregate comparison ("Nordic vs Mediterranean trust"). */
function composeRegionComparison(regionKeys, ev, ents) {
  const groups = regionKeys.slice(0, 3).map(rk => {
    const spec = REGION_MAP[rk];
    const isos = Object.keys(COUNTRIES).filter(iso => inRegionSpec(spec, iso, COUNTRIES[iso]));
    return { name: regionDisplay(rk), fs: isos.map(facts).filter(Boolean) };
  }).filter(g => g.fs.length);
  if (groups.length < 2) return null;

  const attrKeys = ents.attributes.length ? ents.attributes.slice(0, 4) : ["trust", "online", "tv", "internet", "press"];
  const agg = (fsArr, attr) => {
    const vals = fsArr.map(f => attr.get(f)).filter(v => v != null);
    return vals.length ? { mean: vals.reduce((a, b) => a + b, 0) / vals.length, n: vals.length } : null;
  };
  ev.add(`Group comparison: ${groups.map(g => g.name).join(" vs ")}`,
    `Unweighted country averages over each group's members with data. Underlying sources per indicator: Reuters DNR 2026 / regional barometers (news use, trust), World Bank (connectivity), RSF (press freedom), Freedom House (internet freedom).`,
    []);
  const lines = [];
  lines.push(`**${groups.map(g => g.name).join(" vs ")}** — group averages (countries with data in brackets):\n`);
  lines.push(`| | ${groups.map(g => g.name).join(" | ")} |`);
  lines.push(`|---|${groups.map(() => "---").join("|")}|`);
  for (const key of attrKeys) {
    const attr = ATTRIBUTES[key];
    if (!attr) continue;
    lines.push(`| ${attr.label} | ${groups.map(g => {
      const a = agg(g.fs, attr);
      return a ? `${Math.round(a.mean * 10) / 10}${attr.unit} (${a.n})` : "no data";
    }).join(" | ")} |`);
  }
  lines.push("");
  lines.push(`*Methodology: unweighted means across each group's countries; different surveys underlie different countries — compare direction, not decimals.*`);
  return lines.join("\n");
}

/** Topic coverage ranking — "which topics get the least/most news coverage". */
function composeCoverageRanking(ents, ev, qNorm) {
  if (!TRENDS) return null;
  const asc = /\b(least|lowest|under ?covered|least covered)\b/.test(qNorm);
  const rows = Object.values(TRENDS.topics)
    .filter(t => t.news_articles_7d != null)
    .sort((a, b) => asc ? a.news_articles_7d - b.news_articles_7d : b.news_articles_7d - a.news_articles_7d)
    .slice(0, 10);
  if (!rows.length) return null;
  ev.add("Topic news-coverage ranking",
    `GDELT 2.0 news-monitoring volume, articles in the last 7 days, as of ${TRENDS.generated}. Global coverage — the Atlas cannot slice coverage volume by publishing region.`,
    TREND_LINKS);
  const lines = [`**Topics with the ${asc ? "least" : "most"} global news coverage** (articles in the last 7 days, GDELT):\n`];
  lines.push(`| # | Topic | Articles (7d) |`);
  lines.push(`|---|---|---|`);
  rows.forEach((t, i) => lines.push(`| ${i + 1} | ${t.label_en} | ${t.news_articles_7d.toLocaleString()} |`));
  lines.push("");
  lines.push(`*Note: coverage volume is measured globally; the Atlas cannot restrict it to one region's media. Reader attention per country is a separate signal — ask "what's trending in …".*`);
  return lines.join("\n");
}

// ---------------------------------------------------------------------------
// Follow-up suggestions
// ---------------------------------------------------------------------------
function neighbourOf(iso) {
  const f = facts(iso);
  if (!f) return null;
  let best = null, bestPop = -1;
  for (const [i2, c] of Object.entries(COUNTRIES)) {
    if (i2 === iso || !c || c.subregion !== f.subregion) continue;
    if ((c.population || 0) > bestPop) { bestPop = c.population || 0; best = i2; }
  }
  return best;
}

function buildFollowups(ents, kind) {
  const chips = [];
  const iso = ents.countries[0] || ents.regionCountries[0];
  const cName = iso && COUNTRIES[iso] ? COUNTRIES[iso].name.replace(/,.*$/, "") : null;

  if (kind === "country" && cName) {
    if (!ents.wantsTrends) chips.push(`What's trending in ${cName}?`);
    const nb = neighbourOf(iso);
    if (nb && COUNTRIES[nb]) chips.push(`Compare ${cName} with ${COUNTRIES[nb].name.replace(/,.*$/, "")}`);
    chips.push(`How do we reach rural audiences in ${cName}?`);
  } else if (kind === "compare" && ents.countries.length >= 2) {
    const names = ents.countries.slice(0, 2).map(i => COUNTRIES[i].name.replace(/,.*$/, ""));
    chips.push(`What's trending in ${names[0]}?`);
    chips.push(`Press freedom risks in ${names.join(" and ")}`);
    const nb = neighbourOf(ents.countries[0]);
    if (nb) chips.push(`Add ${COUNTRIES[nb].name.replace(/,.*$/, "")} to the comparison`);
  } else if (kind === "region" && ents.regions.length) {
    const r = regionDisplay(ents.regions[0]);
    chips.push(`Top 5 countries by internet access in ${r}`);
    chips.push(`Which ${r} countries rely most on radio?`);
    if (ents.topics[0]) chips.push(`Where is ${ents.topics[0].label} trending now?`);
    else chips.push(`What's trending in ${r}'s largest country?`);
  } else if (kind === "topic" && ents.topics.length) {
    const t = ents.topics[0].label;
    chips.push(`Which countries pay most attention to ${t}?`);
    chips.push(`What's trending worldwide right now?`);
    chips.push(`Best channels for ${t} content in low-connectivity countries`);
  } else if (kind === "rank") {
    chips.push(ents.rankDir === "desc" ? "Show the bottom 5 instead" : "Show the top 5 instead");
    if (!ents.regions.length) chips.push(`Same ranking for Africa only`);
    else chips.push(`Same ranking worldwide`);
    if (cName) chips.push(`Full profile of ${cName}`);
  } else if (kind === "platform") {
    chips.push("Which platform leads in the most markets?");
    chips.push("Compare WhatsApp and Facebook reach");
  } else if (kind === "strategy" && cName) {
    chips.push(`Which languages should content use in ${cName}?`);
    const nb = neighbourOf(iso);
    if (nb && COUNTRIES[nb]) chips.push(`Same strategy brief for ${COUNTRIES[nb].name.replace(/,.*$/, "")}`);
    chips.push(`What's trending in ${cName}?`);
  } else {
    chips.push("What data do you have?");
    chips.push("What's trending in Kenya this week?");
    chips.push("Compare news trust in France and Germany");
    chips.push("Top 5 African countries by radio reliance");
  }
  return chips.slice(0, 3);
}

// ---------------------------------------------------------------------------
// Clarifying questions for vague asks
// ---------------------------------------------------------------------------
function maybeClarify(question, ents) {
  const q = normalize(question);
  // a rankable question never needs a location — "where/which countries" IS the ask
  if (ents.intents.includes("rank") && ents.attributes.length) return null;
  // market-discovery questions are deliberately placeless — the engine's job
  // is to PICK the places, so asking "which region?" would be backwards
  if (ents.discovery) return null;
  const noPlace = !ents.countries.length && !ents.regions.length;
  const noSubject = !ents.topics.length && !ents.attributes.length && !ents.platforms.length;

  // "Where should we focus?" / "Help me plan a campaign" — planning words, no anchors.
  // Known-gap questions skip this: "our last campaign" must get the honest
  // no-archive answer, not "which region?" (no region would make it answerable).
  if (noPlace && !detectGaps(q).length
      && /\b(focus|campaign|strategy|plan|planning|outreach|launch|priorit\w*|where should)\b/.test(q)) {
    return {
      question: "Happy to help plan. To ground the answer in data, I need at least a region — and a topic helps too. Where is this campaign aimed?",
      options: ["Where should we focus in Africa?", "Where should we focus in South Asia?",
                "Where should we focus in Latin America?", "What's trending worldwide right now?"],
    };
  }
  // audience given but no place: "how do we reach young people?"
  if (noPlace && ents.audiences.length) {
    const aud = ents.audiences[0];
    return {
      question: `Reaching ${aud === "youth" ? "young audiences" : aud + " audiences"} depends heavily on the country — connectivity and platform habits differ enormously. Which country or region are you targeting?`,
      options: [`How do we reach ${aud} audiences in Nigeria?`, `How do we reach ${aud} audiences in India?`,
                `How do we reach ${aud} audiences in East Africa?`],
    };
  }
  // attribute but no place and no ranking: "what about internet access?"
  // — but never when a known-gap note or a matched topic will carry the answer
  if (noPlace && ents.attributes.length && !ents.intents.includes("rank") && noFollowContext()
      && !ents.topics.length && !detectGaps(q).length) {
    const attr = ATTRIBUTES[ents.attributes[0]];
    return {
      question: `I have ${attr.label.toLowerCase()} data for most of the world. For which country or region?`,
      options: [`${attr.label} in Nigeria`, `Top 5 countries by ${attr.label.toLowerCase()}`,
                `Lowest ${attr.label.toLowerCase()} in Asia`],
    };
  }
  return null;
}

function noFollowContext() { return !LAST.isos.length && !LAST.regions.length; }

// ---------------------------------------------------------------------------
// SELF-KNOWLEDGE — the Atlas answering questions about itself.
//
// A quarter of the conversational questions people actually type are about the
// tool rather than the world: "what can you do", "how does this work", "how do
// your surveys differ", "how confident are you". Every one of those used to
// dead-end on "I couldn't match that", even though the answer sits in the
// engine's own tables. These routes read the live data — never a hardcoded
// count — so they cannot drift out of step with what is actually loaded.
// ---------------------------------------------------------------------------

/** Live coverage figures, counted from the loaded data at answer time. */
function atlasCoverage() {
  const isos = Object.keys(COUNTRIES || {});
  let news = 0, radio = 0, platform = 0, rsf = 0;
  const surveys = {};
  for (const iso of isos) {
    const c = COUNTRIES[iso] || {};
    const nc = c.news_consumption || {};
    if (nc.source) {
      news++;
      const fam = String(nc.source).replace(/,?\s*(weighted )?microdata.*$/i, "").replace(/\s*\(n=[\d,]+\).*$/, "").trim();
      surveys[fam] = (surveys[fam] || 0) + 1;
    }
    if (nc.radio_as_news_source_pct != null) radio++;
    if (c.platform_use) platform++;
    if ((c.information_freedom || {}).press_freedom_score != null) rsf++;
  }
  return { total: isos.length, news, radio, platform, rsf, surveys };
}

/** "What can you do?" — capabilities, grounded in what is actually loaded. */
function composeCapabilities(ev) {
  const cov = atlasCoverage();
  const L = [];
  L.push(`**What I can answer, and what I hold.**`);
  L.push("");
  L.push(`I'm the Atlas's analyst. I don't search the web and I don't write from memory — every answer is computed from the Atlas's published data files, in your browser, and every figure carries the source it came from.`);
  L.push("");
  L.push(`**Things I'm good at**`);
  L.push(`- **A country's media landscape** — "media habits in Indonesia", "tell me about Chad"`);
  L.push(`- **A recommendation** — "distribution strategy for vaccination content in Nigeria" gives a full brief: the decision, ranked opportunities, tradeoffs, risks, confidence`);
  L.push(`- **Which countries to choose** — "which countries should we prioritise for a radio campaign?"`);
  L.push(`- **Comparisons and rankings** — "compare news trust in France and Germany", "top 5 African countries by radio reliance"`);
  L.push(`- **What's being paid attention to** — "what's trending in Kenya this week?"`);
  L.push(`- **Questions about me** — how the surveys differ, how confident I am, what I can't do`);
  L.push("");
  L.push(`**What I hold right now** (counted from the loaded data, not a claim):`);
  L.push(`- ${cov.total} countries profiled; **${cov.news} with a real news-consumption survey** behind them`);
  L.push(`- ${cov.rsf} with a press-freedom score; ${cov.radio} with measured radio reach; ${cov.platform} with measured platform use`);
  L.push(`- ${REGISTRY.length} topics tracked daily${TRENDS && TRENDS.coverage ? `, of which ${TRENDS.coverage.topics_scored} are currently measurable` : ""}`);
  L.push("");
  L.push(`**What I will never do:** invent a number, or fill a gap with an estimate. Where the data stops, I say so and tell you what would answer it instead. That's the point of me.`);
  ev.add("Atlas coverage", `Counted live from data/countries.json (${cov.total} records) and the topic registry at the moment of asking.`, []);
  return L.join("\n");
}

/** "How do your surveys differ?" — the construct problem, in plain English. */
function composeMethodology(ev) {
  const cov = atlasCoverage();
  const L = [];
  L.push(`**How the Atlas knows what it knows.**`);
  L.push("");
  L.push(`Media-use figures come from national surveys — but *different* surveys ask different questions, and that matters more than it sounds:`);
  L.push("");
  const fams = Object.entries(cov.surveys).sort((a, b) => b[1] - a[1]);
  for (const [fam, n] of fams) {
    let construct = "";
    if (/Reuters/i.test(fam)) construct = "asks which sources you used **in the past week**. Its samples are online panels — in India, Kenya, Nigeria, South Africa and Morocco that skews urban, younger and more connected, and those countries carry a visible caveat.";
    else if (/Afrobarometer/i.test(fam)) construct = "face-to-face, nationally representative, asks **how often** you get news from each source. The reason radio leads across much of Africa in this Atlas is that this survey actually measures it.";
    else if (/Arab Barometer/i.test(fam)) construct = "asks for your **single most important** news source. Shares are therefore structurally lower than a 'used this week' figure and must not be compared with one directly.";
    else if (/Asian Barometer/i.test(fam)) construct = "also asks for the **single most important** channel, and its answer option combines internet and social media — so social media cannot be separated for those countries.";
    else if (/World Values/i.test(fam)) construct = "asks about **daily or weekly** use, a wider window than 'past week'.";
    else if (/Eurobarometer/i.test(fam)) construct = "asks about **general media use**, not news specifically.";
    L.push(`- **${fam}** — ${n} ${n === 1 ? "country" : "countries"}. ${construct}`);
  }
  L.push("");
  L.push(`**Why I keep saying "not directly comparable":** a country measured at 66% by one survey and 45% by another may have identical media habits — the questions differ. I name the survey on every figure so you can see when you are comparing like with like. Comparing across survey families is the single easiest way to draw a wrong conclusion from this data.`);
  L.push("");
  L.push(`**The one adjustment I make:** online and social reach are capped at a country's internet penetration. A survey can honestly report 94% online news use in a country where 41% are online — because it surveyed the people who are already online. Treating that as national reach is the most expensive mistake this tool exists to prevent.`);
  L.push("");
  L.push(`Everything else — connectivity, demographics, literacy — comes from the World Bank; press freedom from RSF; political and internet freedom from Freedom House; language shares from Unicode CLDR; live attention from Wikipedia reading patterns and the GDELT news monitor.`);
  ev.add("Survey constructs", `Construct notes are carried per country in data/countries.json (news_consumption.survey_note) and applied on every figure the analyst reports.`, []);
  return L.join("\n");
}

/** "How confident are you?" / "how accurate is this?" */
function composeTrustworthiness(ev) {
  const cov = atlasCoverage();
  const L = [];
  L.push(`**How much to trust what I tell you.**`);
  L.push("");
  L.push(`- **The figures are not mine.** I aggregate and cite; I don't generate. Every number traces to the World Bank, RSF, Freedom House, the Reuters Institute, or a named barometer survey.`);
  L.push(`- **Coverage is honest, not flattering.** ${cov.news} of ${cov.total} countries have a real news survey. The other ${cov.total - cov.news} show as "profile only" and are excluded from rankings **by name, with the reason** — never quietly ranked last.`);
  L.push(`- **Every brief states its own confidence** and lists what it cannot tell you at any confidence: past campaign performance, whether video beats text, age and gender breakdowns, cost per channel. No free source measures those.`);
  L.push(`- **I decline rather than guess.** About ten classes of question have no free data source; I name what's missing and offer the nearest real evidence instead.`);
  L.push(`- **What could still be wrong:** survey vintages differ (some figures are years old — the Sources tab shows each observation year), country attribution of topic trends is a documented approximation, and industry ad-spend figures are directional forecasts, labelled as such.`);
  L.push("");
  L.push(`If a number ever looks wrong, the Sources tab on that country's profile names the file, the organisation and the year it came from.`);
  ev.add("Confidence and limits", `Per-answer confidence is computed from survey type, sample representativeness and data completeness; gap classes are enumerated in the engine's GAPS table.`, []);
  return L.join("\n");
}

/**
 * THE REASONING TRACE — what the engine actually did, in plain English.
 *
 * This is not a narrative written to look like thinking: every line is read
 * back from the decisions the engine really made — which words it recognised,
 * which route it took, which sources the answer drew on. That makes it useful
 * three ways: a reader learns why they got this answer, someone whose question
 * was misread can see exactly where it went wrong, and a supervisor can see
 * the tool is not a black box. It costs nothing to produce because the work
 * has already happened by the time it is called.
 */
function reasoningTrace(question, ents, kind, ev) {
  const steps = [];

  // 1. What was recognised in the question.
  const seen = [];
  if (ents.countries && ents.countries.length)
    seen.push(`${ents.countries.length === 1 ? "country" : "countries"}: ${ents.countries.map(i => (COUNTRIES[i] || {}).name || i).join(", ")}`);
  if (ents.regions && ents.regions.length)
    seen.push(`region: ${ents.regions.map(regionDisplay).join(", ")}`);
  if (ents.topics && ents.topics.length)
    seen.push(`topic: ${ents.topics.map(t => t.label).join(", ")}`);
  if (ents.attributes && ents.attributes.length)
    seen.push(`measure: ${ents.attributes.map(a => (ATTRIBUTES[a] || {}).label || a).join(", ")}`);
  if (ents.platforms && ents.platforms.length)
    seen.push(`platform: ${ents.platforms.map(p => PLATFORM_NAMES[p] || p).join(", ")}`);
  if (ents.audiences && ents.audiences.length)
    seen.push(`audience: ${ents.audiences.join(", ")}`);
  steps.push(seen.length
    ? `**Read your question as** — ${seen.join(" · ")}.`
    : `**Read your question as** — a general question about the Atlas itself, with no country, topic or measure named.`);

  // 2. Which route was taken, and why that one.
  const routes = {
    strategy: "you are deciding what to *do*, not asking what a number is — so I built a full brief: decision, ranked opportunities, tradeoffs, risks, confidence",
    finder: "you asked *which* countries, not about one — so I screened every country with the required survey data and disclosed the weights",
    rank: "you asked for an ordering, so I ranked the countries that have this measure and said how many lack it",
    compare: "you named several places, so I put them side by side on the measures they share",
    country: "you asked about one place, so I pulled its landscape and the figures behind it",
    region: "you named a region, so I aggregated the countries in it that have data",
    topic: "you asked about a topic, so I used the live attention data rather than the survey data",
    platform: "you named a platform, so I looked at where it appears in countries' leading-platform lists",
    meta: "you asked where the numbers come from or how current they are, so I reported the Atlas's own inventory and the survey behind the figures rather than looking anything up in the world",
    greeting: "you said hello rather than asking anything, so there was nothing to look up",
    self: "you asked about the Atlas itself rather than about the world, so I answered from what is actually loaded — the counts below are read from the data at the moment you asked, not written in advance",
    gap: "the measure you asked for is one no free source publishes, so instead of guessing I named what is missing and what the Atlas holds nearest to it",
    help: "nothing in it mapped to a country, topic or measure, so I answered about what I can do instead",
  };
  if (routes[kind]) steps.push(`**Chose the ${kind} route** — ${routes[kind]}.`);

  // 3. What the answer actually rests on — the evidence titles, not a claim.
  const titles = (ev.list() || []).map(x => x.title).filter(Boolean);
  if (titles.length)
    steps.push(`**Drew on** — ${titles.slice(0, 4).join("; ")}${titles.length > 4 ? `; and ${titles.length - 4} more` : ""}. Each is listed with its source under the answer.`);

  // 4. The honesty step: name what was deliberately left out.
  const omitted = [];
  if (ents.countries && ents.countries.length > 6 && kind === "compare")
    omitted.push("countries beyond the first six, to keep the table readable");
  if (kind === "rank" || kind === "finder")
    omitted.push("countries with no data for this measure — excluded by name, never ranked low");
  if (omitted.length) steps.push(`**Left out** — ${omitted.join("; ")}.`);

  return steps;
}

/**
 * "What's notable right now?" — an open-ended ask, answered with findings the
 * Atlas can actually stand behind rather than a refusal. Every line is
 * computed live from the loaded data; nothing here is written in advance.
 */
function composeGlobalInsight(ev) {
  const L = [];
  L.push(`**What stands out in the Atlas right now.**`);
  L.push("");

  // 1. The capped-reach gap: the finding that changes campaign decisions most.
  const capped = [];
  for (const iso of Object.keys(COUNTRIES)) {
    const f = facts(iso);
    if (!f || f.online == null || f.internet == null || f.pop == null) continue;
    const gap = f.online - f.internet;
    if (gap >= 25 && f.pop >= 2e7) capped.push({ f, gap });
  }
  capped.sort((a, b) => b.gap - a.gap);
  if (capped.length) {
    const top = capped.slice(0, 4);
    L.push(`**Digital reach is overstated in ${capped.length} large markets.** A survey can report high online-news use in a country where far fewer people are online at all — it surveyed the connected. The widest gaps:`);
    for (const { f, gap } of top)
      L.push(`- **${f.name}** — ${fmt(f.online)} online news use, but only ${fmt(f.internet)} internet penetration (${Math.round(gap)} points of apparent reach that isn't national)`);
    L.push(`A digital-only plan in any of these misses most of the population. Ask for a strategy brief on one and the channel table shows the corrected figures.`);
    ev.add("Capped digital reach", `Computed from news_consumption.online_as_news_source_pct vs connectivity.internet_pct across all ${Object.keys(COUNTRIES).length} country records.`, capped.length ? countryLinks(capped[0].f.iso) : []);
    L.push("");
  }

  // 2. Where radio still leads — the recurring surprise for digital-first teams.
  const radioLed = [];
  for (const iso of Object.keys(COUNTRIES)) {
    const f = facts(iso);
    if (!f || f.radio == null) continue;
    const rivals = [f.tv, f.online, f.social].filter(v => v != null);
    if (rivals.length && f.radio >= Math.max(...rivals)) radioLed.push(f);
  }
  if (radioLed.length) {
    radioLed.sort((a, b) => (b.pop || 0) - (a.pop || 0));
    L.push(`**Radio still out-reaches every other channel in ${radioLed.length} countries**, including ${radioLed.slice(0, 3).map(f => `${f.name} (${fmt(f.radio)})`).join(", ")}. Radio is the only channel that works without electricity, data or literacy — which is why the Atlas never recommends digital-only in these markets.`);
    ev.add("Radio-led markets", `Counted where measured radio reach meets or exceeds TV, online and social in the same survey. Source per country: Afrobarometer Round 9 and the barometer surveys named on each profile.`, []);
    L.push("");
  }

  // 3. Live attention — only what is genuinely current.
  if (TRENDS && TRENDS.topics) {
    const rising = Object.entries(TRENDS.topics)
      .filter(([, t]) => t.momentum === "rising")
      .sort((a, b) => b[1].global_velocity - a[1].global_velocity).slice(0, 4);
    if (rising.length) {
      L.push(`**Rising attention worldwide** (7 days to ${TRENDS.measured_as_of || TRENDS.generated}): ${rising.map(([, t]) => `${t.label_en} (+${Math.round(t.global_velocity * 100)}%)`).join(", ")}.`);
      addTrendEvidence("Global", ev);
      L.push("");
    }
  }

  // 4. The honest coverage line — the limitation stated without being asked.
  const cov = atlasCoverage();
  L.push(`**And what the Atlas cannot see:** ${cov.total - cov.news} of ${cov.total} countries have no free national media survey at all. They are shown as profile-only and excluded from every ranking by name — not ranked low.`);
  L.push("");
  L.push(`*These are patterns in the data, not recommendations. Ask about a specific country or campaign and I'll give you the reasoning for that decision.*`);
  return L.join("\n");
}

/**
 * Route a question about the Atlas itself. Returns null when the question is
 * about the world rather than the tool.
 */
function composeSelfKnowledge(qNorm, ev) {
  const capability = /\b(what can (you|the atlas|this) do|what do you do|how can you help|what are you|who are you|what questions can i ask|how do i use|what should i ask|help me|^ *help *$|capabilities)\b/.test(qNorm);
  // No trailing \b on this one: it would fail on the plural — "difference
  // between the surveys" is the commonest phrasing of the question.
  const methodology = /\b(how (does|do) (the atlas|this|you) work|how do you know|what (data|sources) do you (have|use)|where does (your|the) data come from|explain .{0,24}(survey|method|source)|difference .{0,24}(survey|source)|how are .{0,20}(figures|numbers) (measured|collected)|methodology)/.test(qNorm);
  const trust = /\b(how (accurate|reliable|confident|trustworthy)|how confident are you|can i trust|how sure are you|margin of error|how good is (the|this) data|what (can.?t|cannot|don.?t) you (tell|do|know|answer)|what are your (limits|limitations|gaps)|what don.?t you (have|know|cover))\b/.test(qNorm);
  // Open-ended asks with no country, topic or measure attached — "anything
  // interesting?", "summarise the opportunities". Answerable from live data,
  // and far more useful than asking the reader to rephrase.
  const insight = /\b(tell me something|anything (interesting|notable|surprising)|what.{0,12}(interesting|notable|surprising|stands? out)|summar\w+ .{0,24}(opportunit|finding|globally|worldwide|overall)|biggest opportunit\w+|key (findings?|takeaways?|insights?)|overview of the data|what should i know)\b/.test(qNorm);
  if (trust) return composeTrustworthiness(ev);
  if (methodology) return composeMethodology(ev);
  if (capability) return composeCapabilities(ev);
  if (insight) return composeGlobalInsight(ev);
  return null;
}

// ---------------------------------------------------------------------------
// Main entry
// ---------------------------------------------------------------------------
export function answerQuestion(question) {
  const ev = evidenceStore();

  // The engine's vocabulary is English (the site UI is multilingual, the
  // analyst is not yet) — say so instead of returning a confusing refusal.
  const letters = (question.match(/[a-z]/gi) || []).length;
  const nonAscii = (question.match(/[^\x00-\x7F]/g) || []).length;
  if (nonAscii > letters && question.trim().length > 3) {
    return {
      answer: "For now I understand questions in **English** only — the rest of the Atlas is available in six languages, but my question-understanding is English-first. Try rephrasing in English, e.g. *\"What is trending in Kenya?\"*",
      evidence: [], followups: ["What data do you have?", "What's trending worldwide right now?"], clarify: null, entities: null,
    };
  }

  // Bare "Congo" is genuinely ambiguous — ask rather than guess
  const qPre = normalize(question);
  if (/ congo /.test(qPre) && !/(dr|dem|democratic|kinshasa|brazzaville|republic of the) /.test(qPre) && !/ congo (dr|kinshasa|brazzaville)/.test(qPre)) {
    return {
      answer: null, evidence: [], followups: [],
      clarify: {
        question: "There are two Congos — which one do you mean?",
        options: ["Democratic Republic of the Congo (Kinshasa)", "Republic of the Congo (Brazzaville)"],
      },
      entities: null,
    };
  }

  let ents = detectEntities(question);

  const qNorm = normalize(question);
  const gaps = detectGaps(qNorm);

  // theme filter for attention profiles ("what HEALTH topics concern Egypt")
  const THEMES = { health: /\bhealth\b|disease|medical/, climate: /\bclimate\b|environment\w*/,
    rights: /\brights\b|governance|democracy/, technology: /\btech\w*/, humanitarian: /humanitarian/,
    education: /\beducation\w*/, peace: /\bpeace\b|security topics/, development: /development topics|economy topics/ };
  ents.themeFilter = Object.keys(THEMES).filter(k => THEMES[k].test(qNorm));
  if (!ents.themeFilter.length) ents.themeFilter = null;

  // Press-risk phrasings imply "rank by press freedom, worst first"
  if (/\b(state controlled|at risk|most at risk|least free|most restricted|most dangerous)\b/.test(qNorm)
      && (ents.attributes.includes("press") || /\b(journalists?|reporters?|press|media environments?)\b/.test(qNorm))
      && (/\b(which|what) countries\b|\bwhere\b/.test(qNorm) || ents.intents.includes("rank"))) {
    ents.attributes = ["press"];
    ents.rankDir = "asc";
    if (!ents.intents.includes("rank")) ents.intents.push("rank");
    ents.intents = ents.intents.filter(i => i !== "lookup");
  }

  // "urban and rural audiences" is an audience question, not an urban-% lookup
  if (ents.attributes.length === 1 && ents.attributes[0] === "urban" && ents.audiences.length)
    ents.intents = ents.intents.filter(i => i !== "lookup");

  // "trusted OUTLETS to partner with" wants the outlet lists, not a trust number
  if (/\b(outlets?|broadcasters?|stations?|newspapers?|partner with)\b/.test(qNorm) && ents.countries.length)
    ents.intents = ents.intents.filter(i => i !== "lookup");

  // Full strategy-brief intent (DGC advisory mode): distribution/campaign/
  // strategy language anchored to a place → the who/what/where/when/how memo
  // A "decision-shaped" question: the user is deciding what to DO, not asking
  // what a number is. These all route to the consulting brief.
  const decisionVerb = /\b(strateg\w+|campaign|distribut\w+|roll ?out|launch\w*|opportunit\w+|memo|brief\b|content plan|media plan|outreach|disseminat\w+|amplif\w+|promote|publish|advertis\w+|marketing|communicat\w+|messag\w+|engag\w+|counter(ing|ed|s)?|combat\w*|raise awareness)\b/.test(qNorm);
  // These three are decision-shaped only sometimes. "Reach", "target" and
  // "market" are verbs in "how do we reach rural women in Mali", but ordinary
  // nouns in "what is the radio reach in Kenya?" — and on their own they were
  // turning the platform's most common vocabulary into five-page memos.
  const decisionNoun = /\b(reach\w*|target\w*|market\w*)\b/.test(qNorm);
  // A question asking what a number IS, asking for a ranking, or explicitly
  // asking for a comparison is not a decision question, however many domain
  // nouns it happens to carry.
  const factualAsk = ents.intents.includes("lookup") || ents.intents.includes("rank")
    || (/\b(compare|compared|versus|vs|difference between)\b/.test(qNorm) && ents.countries.length >= 2);
  const decisionFrame = /\b(how (do|should|would|can) (we|i|they|dgc|the un)|where should|what.{0,15}best (way|platform|channel|approach|mix)|what should (we|i|dgc)|help (us|me) (reach|plan|decide)|recommend\w*|advise|advice on|plan for)\b/.test(qNorm);
  // Market-discovery ("WHICH countries/markets for this campaign?") outranks
  // both the strategy briefs (which answer HOW for a place already chosen)
  // and attribute rankings — but only when no specific country is named and
  // a campaign verb makes the screening intent unambiguous.
  const discovery = ents.countries.length === 0
    && /\b(countries|markets|market)\b/.test(qNorm)
    && /\b(campaign|launch\w*|prioriti[sz]e|expand\w*|distribute|roll ?out|invest\w*|focus|pilot|deploy\w*|screen\w*|best fit)\b/.test(qNorm);
  if (discovery) {
    ents.discovery = true;
    ents.intents = ents.intents.filter(i => i !== "rank" && i !== "lookup");
  }
  const strategyIntent = !discovery && (decisionVerb || decisionFrame || (decisionNoun && !factualAsk))
    && (ents.countries.length > 0 || ents.regionCountries.length > 0);
  if (strategyIntent) {
    ents.intents = ents.intents.filter(i => i !== "lookup");
    if (!ents.intents.includes("strategy")) ents.intents.push("strategy");
  }

  // "which countries prefer audio" — radio reach is the audio-habit ranking
  if (/\b(audio|podcasts?)\b/.test(qNorm) && /\b(which countries|where)\b/.test(qNorm) && !ents.countries.length) {
    if (!ents.attributes.includes("radio")) ents.attributes.unshift("radio");
    ents.rankDir = ents.rankDir || "desc";
    if (!ents.intents.includes("rank")) ents.intents.push("rank");
  }

  // Ranking continuations from our own follow-up chips or natural phrasing:
  // "Show the bottom 5 instead", "Same ranking for Africa only", "top 10 instead"
  if (!ents.attributes.length && LAST.attributes.length
      && /\b(top|bottom|highest|lowest|same ranking|instead)\b/.test(qNorm)) {
    ents.attributes = [...LAST.attributes];
    if (!ents.regions.length && !/\bworldwide|world|globally|all countries\b/.test(qNorm)) {
      ents.regions = [...LAST.regions];
    }
    ents.rankDir = /\b(bottom|lowest|least|worst)\b/.test(qNorm) ? "asc"
      : /\b(top|highest|most|best)\b/.test(qNorm) ? "desc" : (LAST.rankDir || "desc");
    const n = qNorm.match(/\b(?:top|bottom|first)\s+(\d{1,2})\b/);
    ents.rankN = n ? Math.min(15, Math.max(1, parseInt(n[1], 10))) : ents.rankN;
    if (!ents.intents.includes("rank")) ents.intents.push("rank");
  }

  // "Add Ghana to the comparison" — merge the new country into the last set
  if (/\badd\b.*\b(comparison|compare)\b/.test(qNorm) && ents.countries.length && LAST.isos.length) {
    ents.countries = [...new Set([...LAST.isos, ...ents.countries])];
    ents.wantsCompare = true;
  }

  // Follow-up resolution: inherit the previous location if this looks like one
  if (isFollowUp(question, ents)) {
    ents.countries = [...LAST.isos];
    ents.regions = [...LAST.regions];
    if (!ents.topics.length) ents.topics = [...LAST.topics];
    // re-expand regions
    if (ents.regions.length) {
      const re = detectEntities(ents.regions.join(" and "));
      ents.regionCountries = re.regionCountries;
    }
    // re-derive intents that depend on knowing the location
    if (ents.attributes.length && ents.countries.length === 1 && !ents.intents.includes("rank") && !ents.intents.includes("lookup"))
      ents.intents.push("lookup");
  }

  // Greeting / small talk
  if (ents.intents.includes("greeting")) {
    const isThanks = /thank|great|perfect|awesome|cool/i.test(question);
    return {
      answer: isThanks
        ? "You're welcome! Anything else you'd like to look into?"
        : "Hello! I'm the Atlas analyst. Ask me where and how to communicate anywhere in the world — every answer comes from the Atlas's verified, cited data.",
      evidence: [], followups: buildFollowups(ents, "help"), clarify: null, entities: ents,
      reasoning: reasoningTrace(question, ents, "greeting", ev),
    };
  }

  // Meta: "what data do you have?" — but never when the question is really
  // about a place or measure ("help me reach farmers in India"). Exception:
  // hard meta-questions (methodology, freshness, confidence) stay meta even
  // when they name a country or metric — that IS the question.
  const hardMeta = /\b(methodology|last updated|last checked|how (confident|reliable|accurate)|data quality|how do you (measure|know))\b/.test(qNorm);
  if ((ents.intents.includes("meta") || hardMeta)
      && (hardMeta || (!ents.countries.length && !ents.regions.length && !ents.topics.length && !ents.attributes.length))) {
    let metaAns = composeMeta(ev, ents.countries[0] || null);
    for (const key of ents.attributes.slice(0, 2)) {
      const attr = ATTRIBUTES[key];
      if (attr) metaAns = `**How "${attr.label}" is measured:** ${attr.source}${attr.surveyMix ? " — different surveys underlie different countries (DNR online panels vs face-to-face barometers), so compare direction, not decimals; each country names its survey" : ""}.\n\n` + metaAns;
    }
    return { answer: metaAns, evidence: ev.list(), followups: buildFollowups(ents, "help"),
             clarify: null, entities: ents,
             reasoning: reasoningTrace(question, ents, "meta", ev) };
  }

  // Known-gap questions with nothing else to anchor on: answer honestly
  // instead of clarifying toward an answer that doesn't exist ("our last
  // campaign" must never get "which region?" — no region would help).
  const standaloneGap = gaps.find(g => g.standalone);
  if (standaloneGap && !ents.countries.length && !ents.regionCountries.length && !ents.topics.length
      && !(ents.intents.includes("rank") && ents.attributes.length)) {
    const noteParts = gaps.map(g => g.note);
    noteParts.push("Name a country or region and I'll pull the strongest landscape evidence the Atlas *does* hold for it.");
    return {
      answer: noteParts.join("\n\n"), evidence: [],
      followups: ["Full media profile of Nigeria", "Top 5 countries by radio reliance in Africa", "What's trending worldwide right now?"],
      clarify: null, entities: ents,
      reasoning: reasoningTrace(question, ents, "gap", ev),
    };
  }

  // Clarify vague questions instead of guessing
  const clar = maybeClarify(question, ents);
  if (clar) return { answer: null, evidence: [], followups: [], clarify: clar, entities: ents };

  const parts = [];
  let kind = null;
  const isoList = [...new Set([...ents.countries, ...ents.regionCountries])];

  // These specialised routes each FALL THROUGH when they can't compose —
  // a matched-but-empty branch must never swallow the question.
  // Topic coverage ranking ("which topics get the least media coverage")
  if (/\b(coverage|covered)\b/.test(qNorm) && /\b(least|most|lowest|highest|top|bottom|under)\b/.test(qNorm)
      && !ents.countries.length && (ents.topics.length || /\btopics?\b|\bsdgs?\b/.test(qNorm))) {
    const r = composeCoverageRanking(ents, ev, qNorm);
    if (r) { parts.push(r); kind = "topic"; }
  }
  // Region-vs-region aggregate comparison ("Nordic vs Mediterranean trust")
  if (!parts.length && ents.regions.length >= 2 && (ents.wantsCompare || ents.attributes.length) && !ents.countries.length) {
    const r = composeRegionComparison(ents.regions, ev, ents);
    if (r) { parts.push(r); kind = "compare"; }
  }
  // Regional trends ("what's trending in East Africa?")
  if (!parts.length && ents.regions.length && ents.wantsTrends && !ents.topics.length && isoList.length > 2) {
    const r = composeRegionTrends(isoList.map(facts).filter(Boolean), ev, ents.regions.map(regionDisplay).join(", "));
    if (r) { parts.push(r); kind = "region"; }
  }
  // Region-scoped comparison table ("Gulf states compared on internet freedom")
  if (!parts.length && ents.regions.length === 1 && ents.wantsCompare && ents.attributes.length && !ents.countries.length && isoList.length >= 2) {
    parts.push(composeComparison(isoList.slice(0, 6).map(facts).filter(Boolean), ev, ents));
    kind = "compare";
  }
  // Strategy brief — the full advisory memo for 1–2 named countries
  if (!parts.length && ents.intents.includes("strategy") && ents.countries.length >= 1 && ents.countries.length <= 2) {
    for (const iso of ents.countries.slice(0, 2)) {
      const f = facts(iso);
      if (f) parts.push(composeConsultingBrief(f, ev, ents, qNorm));
    }
    if (parts.length) kind = "strategy";
  }
  // Strategy over a region — same mandatory consulting structure as a single
  // country, aggregated. A region decision is still a decision.
  if (!parts.length && ents.intents.includes("strategy") && ents.regions.length && isoList.length > 2) {
    const fs = isoList.map(facts).filter(Boolean);
    const regionName = ents.regions.map(regionDisplay).join(", ");
    parts.push(composeRegionConsultingBrief(fs, ev, ents, qNorm, regionName));
    kind = "strategy";
  }
  // Ranking ("top 5 by radio in Africa")
  if (!parts.length && ents.intents.includes("rank") && ents.attributes.length) {
    const r = composeRanking(ents, ev);
    if (r) { parts.push(r); kind = "rank"; }
  }
  // Market Finder — reverse search; the discovery flag is computed upstream
  // (before strategy/rank routing) so region-scoped and attribute-flavoured
  // screening questions land here instead of being intercepted.
  else if (!parts.length && ents.discovery) {
    parts.push(composeMarketFinder(ents, ev, qNorm));
    kind = "finder";
  }
  // Single-fact lookup ("literacy rate in Chad")
  else if (!parts.length && ents.intents.includes("lookup")) {
    const r = composeLookup(ents, ev, qNorm);
    if (r) { parts.push(r); kind = "country"; }
  }
  // Platform question ("where does WhatsApp lead?")
  else if (!parts.length && ents.platforms.length && !isoList.length) {
    parts.push(composePlatform(ents, ev));
    kind = "platform";
  }
  // Region strategy
  else if (!parts.length && ents.regions.length && isoList.length > 2) {
    const fs = isoList.map(facts).filter(Boolean);
    parts.push(composeRegionBrief(fs, ev, ents, ents.regions.map(regionDisplay).join(", ")));
    kind = "region";
  }
  // Comparison
  else if (!parts.length && ents.wantsCompare && isoList.length >= 2) {
    // Six columns is the widest table that stays readable, but a reader who
    // named eight countries must be told which two are missing rather than
    // left to notice on their own.
    const shown = isoList.slice(0, 6), dropped = isoList.slice(6);
    parts.push(composeComparison(shown.map(facts).filter(Boolean), ev, ents));
    if (dropped.length)
      parts.push(`*Comparing the first ${shown.length} countries named — ${dropped.map(i => (COUNTRIES[i] || {}).name || i).join(", ")} ${dropped.length === 1 ? "is" : "are"} not shown, because a wider table stops being readable. Ask again naming ${dropped.length === 1 ? "it" : "them"} to compare those.*`);
    for (const t of ents.topics) parts.push(composeTopicBrief(t, ev));
    kind = "compare";
  }
  // Country brief(s)
  else if (!parts.length && isoList.length >= 1) {
    for (const iso of isoList.slice(0, 3)) {
      const f = facts(iso);
      if (f) parts.push(composeCountryBrief(f, ev, ents));
    }
    for (const t of ents.topics) parts.push(composeTopicBrief(t, ev));
    kind = "country";
  }
  // Topic only
  else if (!parts.length && ents.topics.length) {
    const countriesFirst = /\b(which|what) countries\b|\bwhere\b/.test(qNorm);
    for (const t of ents.topics) parts.push(composeTopicBrief(t, ev, countriesFirst));
    kind = "topic";
  }
  // Global trends ("what's trending worldwide?")
  else if (!parts.length && ents.wantsTrends && TRENDS) {
    const movers = Object.values(TRENDS.topics)
      .filter(t => t.momentum === "rising" || Math.abs(t.global_velocity) >= 0.2)
      .sort((a, b) => b.global_velocity - a.global_velocity).slice(0, 8);
    if (movers.length) {
      addTrendEvidence("Global", ev);
      const lines = [`**Trending worldwide** (as of ${TRENDS.generated}):\n`];
      for (const t of movers)
        lines.push(`- **${t.label_en}** ${t.global_velocity > 0 ? "+" : ""}${Math.round(t.global_velocity * 100)}% vs its 30-day baseline (${t.momentum})`);
      parts.push(lines.join("\n"));
      kind = "topic";
    }
  }

  // Questions about the Atlas itself, answered from its own loaded data. These
  // carry no country or topic, so without this they fell through every route
  // and hit the generic refusal — the tool unable to describe itself.
  if (!parts.length) {
    const self = composeSelfKnowledge(qNorm, ev);
    if (self) {
      return {
        answer: self, evidence: ev.list(),
        followups: ["What's trending worldwide right now?", "Media habits in Indonesia",
                    "Which countries should we prioritise for a radio campaign?"],
        clarify: null, entities: ents,
        reasoning: reasoningTrace(question, ents, "self", ev),
      };
    }
  }

  // Known-gap notes ride on top of whatever composed — honesty first, data second
  if (gaps.length && parts.length) {
    parts.unshift(gaps.map(g => g.note).join("\n\n"));
  }

  // Never dead-end: gap-specific honesty beats a generic refusal
  if (!parts.length && gaps.length) {
    return {
      answer: gaps.map(g => g.note).join("\n\n") + "\n\nName a country or region and I'll pull the strongest landscape evidence the Atlas *does* hold for it.",
      evidence: [], followups: buildFollowups(ents, "help"), clarify: null, entities: ents,
      reasoning: reasoningTrace(question, ents, "gap", ev),
    };
  }
  if (!parts.length) {
    return {
      answer: `I couldn't match that to the Atlas's data — but I likely *can* help if we rephrase. I know **${META ? META.country_count : 195} countries** and **${REGISTRY.length} topics**, and I can compare, rank, and track trends across them.\n\nTry naming a **country** ("media habits in Indonesia"), a **region** ("East Africa"), a **topic** ("climate change"), or a **measure** ("trust in news", "radio reach").`,
      evidence: [], followups: buildFollowups(ents, "help"), clarify: null, entities: ents,
      reasoning: reasoningTrace(question, ents, "help", ev),
    };
  }

  // Note for territories the UN lists under China: their media environments
  // differ substantially — say so rather than silently serving PRC data.
  if (/\b(taiwan|hong kong|macau|macao)\b/.test(qNorm) && ents.countries.includes("CHN")) {
    parts.push("*Note: the Atlas follows UN country designations, so Taiwan, Hong Kong, and Macau are listed under China — but their media environments (platforms, press freedom, censorship) differ substantially from the mainland's. Treat the figures above as mainland-China data.*");
  }

  // Remember context for follow-ups
  LAST = {
    isos: ents.countries.length ? [...ents.countries] : [...(ents.regionCountries || []).slice(0, 3)],
    regions: [...ents.regions],
    topics: [...ents.topics],
    attributes: [...ents.attributes],
    rankDir: ents.rankDir,
  };

  return {
    answer: parts.join("\n\n---\n\n"),
    evidence: ev.list(),
    followups: buildFollowups(ents, kind || "help"),
    clarify: null,
    entities: ents,
    reasoning: reasoningTrace(question, ents, kind, ev),
  };
}
