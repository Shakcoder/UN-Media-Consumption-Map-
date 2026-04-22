/*
 * Country data — Phase 1 pilot set (10 countries).
 *
 * All figures marked "preliminary" must be re-verified against their primary
 * source (URL + retrieval date) before the site is promoted publicly.
 *
 * Keyed by ISO 3166-1 alpha-3 code so we can match against the GeoJSON
 * boundaries file, which uses the same codes in its "ISO_A3" property.
 */
window.COUNTRY_DATA = {

  "USA": {
    name: "United States of America",
    capital: "Washington, D.C.",
    region: "Americas",
    subregion: "North America",
    flag: "🇺🇸",
    overview:
      "The world's largest economy and the primary exporter of global media and digital platforms. Home to the companies that define much of the world's online information environment.",
    population: 334_914_895,
    population_year: 2023,
    area_km2: 9_833_517,
    gdp_per_capita_usd: 82_769,
    currency: "United States Dollar (USD)",
    languages: ["English (de facto)", "Spanish (widely spoken)"],
    government: "Federal presidential republic",
    dominant_industries: ["Technology & software", "Financial services", "Healthcare", "Manufacturing", "Entertainment & media", "Aerospace & defense"],
    focus_areas: ["AI and semiconductor policy", "Energy transition", "Re-shoring of manufacturing", "Regulation of large platforms"],
    demographics: {
      age_0_14_pct: 17.8,
      age_15_64_pct: 64.9,
      age_65_plus_pct: 17.3,
      urban_pct: 83.3,
      literacy_pct: 99.0
    },
    connectivity: {
      internet_pct: 97,
      mobile_per_100: 110,
      smartphone_pct: 91,
      fixed_broadband_per_100: 38
    },
    media: {
      top_tv: "CBS, NBC, ABC, Fox, CNN, MSNBC",
      top_radio: "NPR, iHeartRadio network, SiriusXM",
      top_online_news: "New York Times, CNN, Washington Post, Fox News",
      top_social: "YouTube, Facebook, Instagram, TikTok, X",
      press_freedom_rank: 55,
      press_freedom_source: "RSF 2024"
    },
    topics_of_interest: ["Politics", "Business", "Sports", "Entertainment", "Technology"],
    sources: {
      population: "World Bank — https://data.worldbank.org/indicator/SP.POP.TOTL?locations=US",
      gdp: "World Bank — https://data.worldbank.org/indicator/NY.GDP.PCAP.CD?locations=US",
      internet: "ITU — https://datahub.itu.int/",
      press_freedom: "RSF — https://rsf.org/en/country/united-states"
    },
    confidence: "preliminary"
  },

  "GBR": {
    name: "United Kingdom",
    capital: "London",
    region: "Europe",
    subregion: "Northern Europe",
    flag: "🇬🇧",
    overview:
      "Globally influential media market historically anchored by the BBC. Strong public-service broadcasting tradition sits alongside one of the world's most competitive commercial press markets.",
    population: 67_596_281,
    population_year: 2023,
    area_km2: 243_610,
    gdp_per_capita_usd: 50_778,
    currency: "Pound Sterling (GBP)",
    languages: ["English", "Welsh", "Scottish Gaelic"],
    government: "Parliamentary constitutional monarchy",
    dominant_industries: ["Financial services", "Creative industries", "Aerospace", "Pharmaceuticals", "Professional services", "Tech"],
    focus_areas: ["Post-Brexit trade", "Net zero by 2050", "AI safety leadership", "Public-service broadcasting reform"],
    demographics: {
      age_0_14_pct: 17.4,
      age_15_64_pct: 63.5,
      age_65_plus_pct: 19.1,
      urban_pct: 84.4,
      literacy_pct: 99.0
    },
    connectivity: {
      internet_pct: 97,
      mobile_per_100: 118,
      smartphone_pct: 92,
      fixed_broadband_per_100: 42
    },
    media: {
      top_tv: "BBC, ITV, Channel 4, Sky",
      top_radio: "BBC Radio (1/2/4), Global Radio (Capital, Heart)",
      top_online_news: "BBC News, The Guardian, Mail Online, Sky News",
      top_social: "WhatsApp, Facebook, YouTube, Instagram, TikTok",
      press_freedom_rank: 23,
      press_freedom_source: "RSF 2024"
    },
    topics_of_interest: ["Politics", "International news", "Sports", "Business", "Climate"],
    sources: {
      population: "World Bank — https://data.worldbank.org/indicator/SP.POP.TOTL?locations=GB",
      gdp: "World Bank — https://data.worldbank.org/indicator/NY.GDP.PCAP.CD?locations=GB",
      internet: "ITU — https://datahub.itu.int/",
      press_freedom: "RSF — https://rsf.org/en/country/united-kingdom"
    },
    confidence: "preliminary"
  },

  "BRA": {
    name: "Brazil",
    capital: "Brasília",
    region: "Americas",
    subregion: "South America",
    flag: "🇧🇷",
    overview:
      "Latin America's largest media market, with television and WhatsApp both playing outsized roles in news distribution. Rich linguistic uniformity (Portuguese) makes it one of the most cohesive large media markets in the world.",
    population: 216_422_446,
    population_year: 2023,
    area_km2: 8_515_767,
    gdp_per_capita_usd: 10_412,
    currency: "Brazilian Real (BRL)",
    languages: ["Portuguese"],
    government: "Federal presidential republic",
    dominant_industries: ["Agribusiness", "Mining", "Manufacturing", "Oil & gas", "Services", "Renewable energy"],
    focus_areas: ["Amazon conservation", "Green hydrogen", "Disinformation regulation", "Digital inclusion"],
    demographics: {
      age_0_14_pct: 20.1,
      age_15_64_pct: 69.7,
      age_65_plus_pct: 10.2,
      urban_pct: 87.6,
      literacy_pct: 94.3
    },
    connectivity: {
      internet_pct: 84,
      mobile_per_100: 99,
      smartphone_pct: 84,
      fixed_broadband_per_100: 22
    },
    media: {
      top_tv: "Globo, SBT, Record, Band",
      top_radio: "Jovem Pan, Bandeirantes, CBN",
      top_online_news: "G1 (Globo), UOL, Folha de S.Paulo, Estadão",
      top_social: "WhatsApp, Instagram, YouTube, TikTok, Facebook",
      press_freedom_rank: 82,
      press_freedom_source: "RSF 2024"
    },
    topics_of_interest: ["Politics", "Sports (football)", "Entertainment", "Local news", "Religion"],
    sources: {
      population: "World Bank — https://data.worldbank.org/indicator/SP.POP.TOTL?locations=BR",
      gdp: "World Bank — https://data.worldbank.org/indicator/NY.GDP.PCAP.CD?locations=BR",
      internet: "ITU — https://datahub.itu.int/",
      press_freedom: "RSF — https://rsf.org/en/country/brazil"
    },
    confidence: "preliminary"
  },

  "NGA": {
    name: "Nigeria",
    capital: "Abuja",
    region: "Africa",
    subregion: "Western Africa",
    flag: "🇳🇬",
    overview:
      "Africa's most populous country and the continent's largest media and entertainment market. Home to Nollywood, Afrobeats, and some of Africa's most influential digital journalism platforms.",
    population: 223_804_632,
    population_year: 2023,
    area_km2: 923_768,
    gdp_per_capita_usd: 2_163,
    currency: "Naira (NGN)",
    languages: ["English (official)", "Hausa", "Yoruba", "Igbo", "500+ others"],
    government: "Federal presidential republic",
    dominant_industries: ["Oil & gas", "Agriculture", "Telecommunications", "Film (Nollywood)", "Financial services", "Fintech"],
    focus_areas: ["Economic diversification away from oil", "Fintech and digital payments growth", "Security in the north", "Youth unemployment"],
    demographics: {
      age_0_14_pct: 42.5,
      age_15_64_pct: 54.5,
      age_65_plus_pct: 3.0,
      urban_pct: 54.4,
      literacy_pct: 62.0
    },
    connectivity: {
      internet_pct: 55,
      mobile_per_100: 99,
      smartphone_pct: 52,
      fixed_broadband_per_100: 0.04
    },
    media: {
      top_tv: "NTA, Channels TV, Arise News, TVC",
      top_radio: "Wazobia FM, Cool FM, BBC Hausa",
      top_online_news: "Premium Times, Sahara Reporters, Punch, Vanguard",
      top_social: "WhatsApp, Facebook, Instagram, TikTok, X",
      press_freedom_rank: 112,
      press_freedom_source: "RSF 2024"
    },
    topics_of_interest: ["Politics", "Religion", "Entertainment (Afrobeats/Nollywood)", "Sports (football)", "Business"],
    sources: {
      population: "World Bank — https://data.worldbank.org/indicator/SP.POP.TOTL?locations=NG",
      gdp: "World Bank — https://data.worldbank.org/indicator/NY.GDP.PCAP.CD?locations=NG",
      internet: "ITU — https://datahub.itu.int/",
      press_freedom: "RSF — https://rsf.org/en/country/nigeria"
    },
    confidence: "preliminary"
  },

  "KEN": {
    name: "Kenya",
    capital: "Nairobi",
    region: "Africa",
    subregion: "Eastern Africa",
    flag: "🇰🇪",
    overview:
      "East Africa's digital hub and a pioneer of mobile money (M-Pesa). A vibrant independent press coexists with government pressure that has grown in recent years.",
    population: 55_100_586,
    population_year: 2023,
    area_km2: 580_367,
    gdp_per_capita_usd: 2_203,
    currency: "Kenyan Shilling (KES)",
    languages: ["Swahili", "English"],
    government: "Presidential republic",
    dominant_industries: ["Agriculture (tea, coffee, horticulture)", "Tourism", "Financial services", "Telecommunications", "Manufacturing", "Technology"],
    focus_areas: ["Digital ID and e-government", "Affordable housing", "Climate adaptation", "Regional trade via AfCFTA"],
    demographics: {
      age_0_14_pct: 37.4,
      age_15_64_pct: 60.0,
      age_65_plus_pct: 2.6,
      urban_pct: 29.0,
      literacy_pct: 82.6
    },
    connectivity: {
      internet_pct: 42,
      mobile_per_100: 130,
      smartphone_pct: 62,
      fixed_broadband_per_100: 1
    },
    media: {
      top_tv: "Citizen TV, KTN, NTV, K24",
      top_radio: "Radio Citizen, Radio Maisha, Classic 105",
      top_online_news: "Nation.Africa, Standard Media, Tuko, The Star",
      top_social: "WhatsApp, Facebook, TikTok, X, Instagram",
      press_freedom_rank: 102,
      press_freedom_source: "RSF 2024"
    },
    topics_of_interest: ["Politics", "Sports (athletics, football)", "Religion", "Business", "Local news"],
    sources: {
      population: "World Bank — https://data.worldbank.org/indicator/SP.POP.TOTL?locations=KE",
      gdp: "World Bank — https://data.worldbank.org/indicator/NY.GDP.PCAP.CD?locations=KE",
      internet: "ITU — https://datahub.itu.int/",
      press_freedom: "RSF — https://rsf.org/en/country/kenya"
    },
    confidence: "preliminary"
  },

  "IND": {
    name: "India",
    capital: "New Delhi",
    region: "Asia",
    subregion: "Southern Asia",
    flag: "🇮🇳",
    overview:
      "The world's most populous country and its fastest-growing major media market. Extraordinary linguistic diversity drives a multi-language news ecosystem unmatched anywhere else.",
    population: 1_428_627_663,
    population_year: 2023,
    area_km2: 3_287_263,
    gdp_per_capita_usd: 2_612,
    currency: "Indian Rupee (INR)",
    languages: ["Hindi", "English", "+22 scheduled languages"],
    government: "Federal parliamentary republic",
    dominant_industries: ["Information technology & services", "Pharmaceuticals", "Textiles & apparel", "Agriculture", "Film (Bollywood + regional)", "Automotive"],
    focus_areas: ["Digital Public Infrastructure (Aadhaar, UPI)", "Manufacturing via Make in India", "Green energy transition", "Press freedom concerns"],
    demographics: {
      age_0_14_pct: 24.9,
      age_15_64_pct: 67.8,
      age_65_plus_pct: 7.3,
      urban_pct: 36.4,
      literacy_pct: 76.3
    },
    connectivity: {
      internet_pct: 52,
      mobile_per_100: 82,
      smartphone_pct: 71,
      fixed_broadband_per_100: 2.6
    },
    media: {
      top_tv: "Doordarshan, Star India, Zee, Sun TV, Republic, NDTV",
      top_radio: "All India Radio, Radio Mirchi, Red FM",
      top_online_news: "Times of India, Hindustan Times, The Hindu, NDTV.com",
      top_social: "WhatsApp, YouTube, Instagram, Facebook, X",
      press_freedom_rank: 159,
      press_freedom_source: "RSF 2024"
    },
    topics_of_interest: ["Politics", "Cricket", "Bollywood & regional cinema", "Religion", "Business"],
    sources: {
      population: "World Bank — https://data.worldbank.org/indicator/SP.POP.TOTL?locations=IN",
      gdp: "World Bank — https://data.worldbank.org/indicator/NY.GDP.PCAP.CD?locations=IN",
      internet: "ITU — https://datahub.itu.int/",
      press_freedom: "RSF — https://rsf.org/en/country/india"
    },
    confidence: "preliminary"
  },

  "CHN": {
    name: "China",
    capital: "Beijing",
    region: "Asia",
    subregion: "Eastern Asia",
    flag: "🇨🇳",
    overview:
      "The world's second-largest economy and a uniquely self-contained digital ecosystem. Major global platforms (Google, Facebook, Twitter) are inaccessible; domestic super-apps dominate every aspect of media consumption.",
    population: 1_410_710_000,
    population_year: 2023,
    area_km2: 9_596_961,
    gdp_per_capita_usd: 12_720,
    currency: "Renminbi (CNY)",
    languages: ["Mandarin (official)", "Cantonese", "Shanghainese", "+many regional"],
    government: "One-party socialist republic",
    dominant_industries: ["Manufacturing", "Technology & telecommunications", "Construction", "Automotive (incl. EV)", "E-commerce", "Clean energy"],
    focus_areas: ["Semiconductor self-sufficiency", "Common Prosperity policy", "Domestic consumption growth", "AI and advanced manufacturing"],
    demographics: {
      age_0_14_pct: 17.0,
      age_15_64_pct: 68.7,
      age_65_plus_pct: 14.3,
      urban_pct: 64.6,
      literacy_pct: 96.8
    },
    connectivity: {
      internet_pct: 76,
      mobile_per_100: 122,
      smartphone_pct: 68,
      fixed_broadband_per_100: 44
    },
    media: {
      top_tv: "CCTV, provincial satellite channels",
      top_radio: "China National Radio (CNR)",
      top_online_news: "People's Daily, Xinhua, Sina, Toutiao",
      top_social: "WeChat, Douyin, Weibo, Xiaohongshu, Kuaishou (domestic)",
      press_freedom_rank: 172,
      press_freedom_source: "RSF 2024"
    },
    topics_of_interest: ["National news", "Economy", "Entertainment (drama, variety)", "Sports", "Technology"],
    sources: {
      population: "World Bank — https://data.worldbank.org/indicator/SP.POP.TOTL?locations=CN",
      gdp: "World Bank — https://data.worldbank.org/indicator/NY.GDP.PCAP.CD?locations=CN",
      internet: "ITU — https://datahub.itu.int/",
      press_freedom: "RSF — https://rsf.org/en/country/china"
    },
    confidence: "preliminary"
  },

  "IDN": {
    name: "Indonesia",
    capital: "Jakarta (Nusantara being developed as successor capital)",
    region: "Asia",
    subregion: "South-Eastern Asia",
    flag: "🇮🇩",
    overview:
      "The world's fourth-most-populous country, spread across 17,000+ islands. One of the world's heaviest social-media-using populations, with TikTok and Instagram central to daily media diets.",
    population: 277_534_122,
    population_year: 2023,
    area_km2: 1_904_569,
    gdp_per_capita_usd: 4_941,
    currency: "Rupiah (IDR)",
    languages: ["Indonesian (Bahasa Indonesia)", "Javanese", "Sundanese"],
    government: "Presidential republic",
    dominant_industries: ["Palm oil & agriculture", "Mining (nickel, coal)", "Manufacturing", "Tourism", "Textiles", "Digital economy"],
    focus_areas: ["Capital relocation to Nusantara", "EV battery supply chain (nickel)", "Digital economy growth", "Disaster resilience"],
    demographics: {
      age_0_14_pct: 25.3,
      age_15_64_pct: 67.4,
      age_65_plus_pct: 7.3,
      urban_pct: 58.6,
      literacy_pct: 96.0
    },
    connectivity: {
      internet_pct: 69,
      mobile_per_100: 128,
      smartphone_pct: 74,
      fixed_broadband_per_100: 6
    },
    media: {
      top_tv: "SCTV, Indosiar, RCTI, TransTV, MetroTV",
      top_radio: "RRI, Prambors, Elshinta",
      top_online_news: "Detik.com, Kompas.com, Tribunnews, CNN Indonesia",
      top_social: "WhatsApp, Instagram, TikTok, Facebook, YouTube",
      press_freedom_rank: 111,
      press_freedom_source: "RSF 2024"
    },
    topics_of_interest: ["Politics", "Entertainment", "Religion (Islam)", "Sports (football, badminton)", "Lifestyle"],
    sources: {
      population: "World Bank — https://data.worldbank.org/indicator/SP.POP.TOTL?locations=ID",
      gdp: "World Bank — https://data.worldbank.org/indicator/NY.GDP.PCAP.CD?locations=ID",
      internet: "ITU — https://datahub.itu.int/",
      press_freedom: "RSF — https://rsf.org/en/country/indonesia"
    },
    confidence: "preliminary"
  },

  "DEU": {
    name: "Germany",
    capital: "Berlin",
    region: "Europe",
    subregion: "Western Europe",
    flag: "🇩🇪",
    overview:
      "Europe's largest economy, with one of the world's strongest public-service broadcasters (ARD/ZDF) funded by a household media levy. High trust in traditional news relative to most peer democracies.",
    population: 84_482_267,
    population_year: 2023,
    area_km2: 357_022,
    gdp_per_capita_usd: 52_746,
    currency: "Euro (EUR)",
    languages: ["German"],
    government: "Federal parliamentary republic",
    dominant_industries: ["Automotive & engineering", "Chemicals & pharmaceuticals", "Electrical equipment", "Machinery", "Finance", "IT & software"],
    focus_areas: ["Energy transition (Energiewende)", "Industrial competitiveness", "Migration policy", "Defense modernization"],
    demographics: {
      age_0_14_pct: 14.0,
      age_15_64_pct: 63.9,
      age_65_plus_pct: 22.1,
      urban_pct: 77.8,
      literacy_pct: 99.0
    },
    connectivity: {
      internet_pct: 93,
      mobile_per_100: 128,
      smartphone_pct: 88,
      fixed_broadband_per_100: 45
    },
    media: {
      top_tv: "ARD, ZDF, RTL, ProSieben, Sat.1",
      top_radio: "Deutschlandfunk, regional ARD stations, Antenne Bayern",
      top_online_news: "Bild, Der Spiegel, Süddeutsche Zeitung, Tagesschau",
      top_social: "WhatsApp, Instagram, Facebook, YouTube, TikTok",
      press_freedom_rank: 10,
      press_freedom_source: "RSF 2024"
    },
    topics_of_interest: ["Politics", "Business", "Sports (football)", "Climate", "International news"],
    sources: {
      population: "World Bank — https://data.worldbank.org/indicator/SP.POP.TOTL?locations=DE",
      gdp: "World Bank — https://data.worldbank.org/indicator/NY.GDP.PCAP.CD?locations=DE",
      internet: "ITU — https://datahub.itu.int/",
      press_freedom: "RSF — https://rsf.org/en/country/germany"
    },
    confidence: "preliminary"
  },

  "MEX": {
    name: "Mexico",
    capital: "Mexico City",
    region: "Americas",
    subregion: "Central America",
    flag: "🇲🇽",
    overview:
      "Latin America's second-largest economy, with a media market historically dominated by a small number of large broadcasters. One of the most dangerous countries in the world to practice journalism.",
    population: 128_455_567,
    population_year: 2023,
    area_km2: 1_964_375,
    gdp_per_capita_usd: 13_926,
    currency: "Mexican Peso (MXN)",
    languages: ["Spanish", "68 recognised indigenous languages"],
    government: "Federal presidential republic",
    dominant_industries: ["Manufacturing (esp. automotive, electronics)", "Oil & gas", "Agriculture", "Tourism", "Financial services", "Remittances from abroad"],
    focus_areas: ["Nearshoring from USMCA trade", "Energy sovereignty", "Security and cartel violence", "Journalist safety"],
    demographics: {
      age_0_14_pct: 25.4,
      age_15_64_pct: 66.6,
      age_65_plus_pct: 8.0,
      urban_pct: 81.4,
      literacy_pct: 95.4
    },
    connectivity: {
      internet_pct: 77,
      mobile_per_100: 98,
      smartphone_pct: 79,
      fixed_broadband_per_100: 19
    },
    media: {
      top_tv: "Televisa, TV Azteca, Imagen TV",
      top_radio: "Grupo Fórmula, Radio Centro, MVS Radio",
      top_online_news: "El Universal, Milenio, Reforma, Animal Político",
      top_social: "WhatsApp, Facebook, TikTok, Instagram, YouTube",
      press_freedom_rank: 121,
      press_freedom_source: "RSF 2024"
    },
    topics_of_interest: ["Politics", "Sports (football)", "Entertainment (telenovelas)", "Local news", "Crime"],
    sources: {
      population: "World Bank — https://data.worldbank.org/indicator/SP.POP.TOTL?locations=MX",
      gdp: "World Bank — https://data.worldbank.org/indicator/NY.GDP.PCAP.CD?locations=MX",
      internet: "ITU — https://datahub.itu.int/",
      press_freedom: "RSF — https://rsf.org/en/country/mexico"
    },
    confidence: "preliminary"
  }

};
