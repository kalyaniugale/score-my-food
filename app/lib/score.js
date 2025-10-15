// app/lib/score.js
// Scientist-style, modular 0–100 health scoring with sub-scores.
// Exports: computeHealthScore(product), withClientScore(product)
//
// Expected product shape (missing fields are OK):
// {
//   name, categories|category, ingredients_text,
//   nutrition|nutriments: OFF-style per-100g/ml keys,
//   additives: [{code:'E330', name:'Citric acid', risk:'moderate'|'avoid'|'safe'}],
//   nova_group (optional), serving_size (optional)
// }

//////////////////////////////
// CONFIG (weights & bands) //
//////////////////////////////
const CFG = {
  weights: {
    // final score = Σ subscore * weight
    nutrientProfile: 0.55,     // energy/sugar/sat fat/salt penalties; fiber/protein/FVNL bonuses
    processing:      0.15,     // NOVA-like heuristics
    additives:       0.15,     // additive penalties (risk + specific codes + text detection)
    ingredientFlags: 0.10,     // palm oil, synthetic colors, high-intensity sweeteners, caffeine
    micronutrients:  0.05,     // meaningful fortification credit
  },

  // Per 100 g/ml thresholds (close to Nutri-Score/UK NPM styles; beverages stricter for sugar)
  thresholds: {
    sugars: { // total or free sugars (if free sugars available, extra penalty applied below)
      solids: { low: 5, high: 22.5, maxPenalty: 30 },
      bev:    { low: 2.5, high: 11,   maxPenalty: 38 }, // aligns with "low ≤2.5g/100ml" and "red >11g/100ml" bands
    },
    satFat: {
      solids: { low: 1.5, high: 5,   maxPenalty: 22 },
      bev:    { low: 0.75, high: 2.5, maxPenalty: 22 },
    },
    salt:    { low: 0.3, high: 1.5,  maxPenalty: 22 }, // as salt g/100g; inferred from sodium if needed
    energyKcal: {
      solids: { low: 150, high: 400, maxPenalty: 10 },
      bev:    { low: 20,  high: 70,  maxPenalty: 10 },
    },
    transFatG: { cutoff: 0.1, penalty: 18 }, // measurable trans fat

    fiber: {
      solids: { low: 3, high: 10, maxBonus: 16 },
      bev:    { low: 1.5, high: 5, maxBonus: 6 },
    },
    protein: { low: 8, high: 20, maxBonus: 10 },

    // If free sugars are explicitly provided, add a small extra penalty on top of total sugar penalty:
    freeSugars: {
      solids: { low: 5,   high: 15,  maxPenalty: 10 },
      bev:    { low: 2.5, high: 7.5, maxPenalty: 12 },
    },

    // FVNL (fruit/veg/nut/legume percent) if available
    fvnlBonus: [
      { min: 40, bonus: 3 },
      { min: 60, bonus: 6 },
      { min: 80, bonus: 10 },
    ],
  },

  // Gentle category tuning (kept modest to avoid gaming)
  categoryTuning: [
    { test: /(yogurt|curd)/i, sugarsTighten: 3, proteinBonus: 2 },
    { test: /(cereal|granola|muesli|oats)/i, fiberBonus: 4 },
    { test: /(cheese)/i, satFatRelax: 0.5 },
    { test: /(edible oil|oil|ghee)/i, energyIgnore: true, satFatRelax: 0.7 },
    { test: /(baby|infant|weaning)/i, sweetenerZeroTolerance: true, sweetenerPenalty: 15 },
  ],

  // Processing / NOVA-like signals (ingredients_text, lowercase)
  processing: {
    novaPenalty: { 1: 0, 2: 2, 3: 8, 4: 18 }, // if nova_group present
    signals: [
      { re: /(hydrogenated|interesterified)/, score: 12, label: "Hydrogenated/Interesterified fat" },
      { re: /\b(palm oil|palmolein)\b/,       score: 6,  label: "Palm oil" },
      { re: /(maltodextrin|glucose syrup|fructose syrup|invert sugar)/, score: 6, label: "Refined sugars/syrups" },
      { re: /(artificial\s*(flavour|flavor)|nature-identical)/, score: 6, label: "Artificial flavor" },
      { re: /\b(color|colour)\s*:? E1(0[0-9]|1[0-9])\b/i, score: 8, label: "Synthetic color" },
      { re: /\b(acésulfame|acesulfame|aspartame|sucralose|saccharin|cyclamate|neotame|advantame)\b/, score: 10, label: "High-intensity sweetener" },
      { re: /\b(MSG|monosodium glutamate|flavour enhancer|flavor enhancer)\b/i, score: 5, label: "Flavor enhancers" },
      { re: /(emulsifier|stabiliser|stabilizer|thickener)\b/, score: 4, label: "Texturizers" },
    ],
    maxPenalty: 24,
  },

  // Additives: risk ladder + specific E-code overrides + text detectors
  additives: {
    riskPenalty: { avoid: 10, moderate: 5, safe: 0 },
    codePenalty: {
      // synthetic colors (EU warnings)
      E102: 6, E104: 6, E110: 6, E122: 6, E124: 6, E129: 6,
      // preservatives / sensitivity
      E211: 6, E202: 3, E200: 3,
      // nitrites/nitrates
      E249: 10, E250: 10, E251: 6, E252: 6,
      // sweeteners (high-intensity)
      E950: 8, E951: 10, E954: 10, E955: 8, E960: 4, E962: 6, E961: 6,
      // phosphates (processed meats)
      E451: 6, E452: 6, E450: 4,
      // BHA/BHT/TBHQ
      E320: 8, E321: 8, E319: 8,
    },
    cap: 36, // cap total additive penalty
    // ingredient_text detectors to catch unexpanded mentions
    detectors: [
      { re: /\b(e32[019]|bha|bht|tbhq)\b/i, p: 8, label: "BHA/BHT/TBHQ" },
      { re: /\b(e249|e250|nitrite|nitrate)\b/i, p: 10, label: "Nitrites/Nitrates" },
      { re: /\b(e95[014]|aspartame|saccharin|sucralose|acesulfame|cyclamate)\b/i, p: 8, label: "High-intensity sweeteners" },
      { re: /\b(e45[012]|phosphate)\b/i, p: 6, label: "Phosphates" },
      { re: /\b(e10[0-9]|tartrazine|allura|ponceau|sunset yellow)\b/i, p: 6, label: "Synthetic colors" },
    ],
  },

  // Ingredient flags (non-additive)
  flags: {
    sweetenersRe: /\b(acesulfame|aspartame|sucralose|saccharin|cyclamate|neotame|advantame|stevia|steviol)\b/i,
    colorsRe:     /\b(red ?40|yellow ?5|yellow ?6|tartrazine|allura|ponceau|sunset yellow)\b/i,
    palmRe:       /\b(palm oil|palmolein)\b/i,
    caffeineRe:   /\b(caffeine|guarana|taurine)\b/i,
    sweetenersPenalty: 8,
    colorsPenalty:     6,
    palmPenalty:       5,
    caffeinePenalty:   4,
    beverageSweetenerMultiplier: 1.3,
  },

  // Micronutrients (%DV) credit
  micronutrients: {
    keys: ["vitamin-c", "vitamin_c", "vitamin-d", "vitamin_d", "calcium", "iron"],
    threshold: 15,   // ≥15% DV per 100g/ml
    perKeyBonus: 2,
    cap: 8,
    base: 50,        // baseline subscore
    scale: 6,        // each 2% bonus → +6 to subscore
  },

  simpleIngredients: { maxCount: 6, bonus: 5 },
};

//////////////////////
// Utility helpers  //
//////////////////////
const clamp = (n, lo, hi) => Math.max(lo, Math.min(hi, n));
const lerp = (x, a, b, lo, hi) => {
  if (x <= a) return lo;
  if (x >= b) return hi;
  const t = (x - a) / (b - a);
  return lo + t * (hi - lo);
};
const asNum = (v, d = null) => (v == null || v === "" || isNaN(Number(v)) ? d : Number(v));

function readNutr(n, keys, d = null) {
  for (const k of keys) {
    const v = n?.[k];
    if (v != null && !isNaN(Number(v))) return Number(v);
  }
  return d;
}
function isBeverage(product = {}) {
  const name = (product.name || "").toLowerCase();
  const cats = (product.category || product.categories || "").toLowerCase();
  return /drink|beverage|juice|soda|cola|tea|coffee|water|milk|lassi|shake/.test(name + " " + cats);
}
function categoryTuning(product) {
  const name = (product.name || "").toLowerCase();
  const cats = (product.category || product.categories || "").toLowerCase();
  const text = name + " " + cats;
  const adj = { sugarsTighten: 0, proteinBonus: 0, fiberBonus: 0, satFatRelax: 1, energyIgnore: false, sweetenerZeroTolerance: false, sweetenerPenalty: 0 };
  for (const rule of CFG.categoryTuning) {
    if (rule.test.test(text)) {
      if (rule.sugarsTighten) adj.sugarsTighten = Math.max(adj.sugarsTighten, rule.sugarsTighten);
      if (rule.proteinBonus)  adj.proteinBonus += rule.proteinBonus;
      if (rule.fiberBonus)    adj.fiberBonus += rule.fiberBonus;
      if (rule.satFatRelax)   adj.satFatRelax = Math.min(adj.satFatRelax, rule.satFatRelax);
      if (rule.energyIgnore)  adj.energyIgnore = true;
      if (rule.sweetenerZeroTolerance) adj.sweetenerZeroTolerance = true;
      if (rule.sweetenerPenalty)       adj.sweetenerPenalty = Math.max(adj.sweetenerPenalty, rule.sweetenerPenalty);
    }
  }
  return adj;
}
function saltFromSodium(n) {
  const sodiumMg = readNutr(n, ["sodium_100g", "sodium"], null);
  if (sodiumMg != null) return (sodiumMg * 2.5) / 1000;
  return readNutr(n, ["salt_100g", "salt"], null);
}
function normalizeE(code) {
  if (!code) return null;
  let s = String(code).toUpperCase().trim();
  if (/^E\d+/.test(s)) return s;
  const m = s.match(/(\d{3,4})/);
  return m ? `E${m[1]}` : null;
}

//////////////////////
// Sub-score blocks //
//////////////////////
function scoreNutrientProfile(product, notes) {
  const bev = isBeverage(product);
  const n = product.nutrition || product.nutriments || {};
  const adj = categoryTuning(product);

  // read nutrients
  const freeSugars = readNutr(n, ["free_sugars_100g", "free-sugars_100g"], null);
  const sugars = asNum(freeSugars, null) ?? asNum(readNutr(n, ["sugars_100g", "sugar_100g", "sugars"], 0), 0);
  const sat    = asNum(readNutr(n, ["saturated-fat_100g", "saturated_fat_100g", "saturated-fat"], 0), 0);
  const salt   = asNum(saltFromSodium(n), 0);
  const kcalRaw = readNutr(n, ["energy-kcal_100g", "energy_kcal_100g", "energy-kcal"], null);
  const kcal   = asNum(kcalRaw != null ? kcalRaw : readNutr(n, ["energy_100g"], 0) / 4.184, 0);
  const trans  = asNum(readNutr(n, ["trans-fat_100g", "trans_fat_100g", "trans-fat"], 0), 0);
  const fiber  = asNum(readNutr(n, ["fiber_100g", "fibers_100g", "fibre_100g", "fiber"], 0), 0);
  const protein= asNum(readNutr(n, ["proteins_100g", "protein_100g", "proteins"], 0), 0);
  const fvnl   = asNum(readNutr(n, ["fruits-vegetables-nuts_100g", "fvnl_100g", "fvnl_percent"], null), null);

  // thresholds
  const S = CFG.thresholds;
  const Sug = bev ? S.sugars.bev : S.sugars.solids;
  const Sat = bev ? S.satFat.bev : S.satFat.solids;
  const En  = bev ? S.energyKcal.bev : S.energyKcal.solids;
  const Fib = bev ? S.fiber.bev : S.fiber.solids;

  // penalties
  const sugarsLow = Math.max(0, Sug.low - adj.sugarsTighten);
  const sugarPenalty = lerp(sugars, sugarsLow, Sug.high, 0, Sug.maxPenalty);
  const satPenalty   = lerp(sat,   Sat.low * adj.satFatRelax, Sat.high * adj.satFatRelax, 0, Sat.maxPenalty);
  const saltPenalty  = lerp(salt,  S.salt.low, S.salt.high, 0, S.salt.maxPenalty);
  const energyPenalty= adj.energyIgnore ? 0 : lerp(kcal, En.low, En.high, 0, En.maxPenalty);
  const transPenalty = trans >= CFG.thresholds.transFatG.cutoff ? CFG.thresholds.transFatG.penalty : 0;

  // free sugars extra
  const fsCfg = bev ? CFG.thresholds.freeSugars.bev : CFG.thresholds.freeSugars.solids;
  const freeSugarsExtra = freeSugars != null ? lerp(asNum(freeSugars, 0), fsCfg.low, fsCfg.high, 0, fsCfg.maxPenalty) : 0;

  // bonuses
  const fiberBonus   = lerp(fiber,   Fib.low, Fib.high, 0, Fib.maxBonus) + adj.fiberBonus;
  const proteinBonus = lerp(protein, S.protein.low, S.protein.high, 0, S.protein.maxBonus) + adj.proteinBonus;

  let fvnlBonus = 0;
  if (fvnl != null) {
    for (const tier of S.fvnlBonus) if (fvnl >= tier.min) fvnlBonus = Math.max(fvnlBonus, tier.bonus);
  }

  const negatives = sugarPenalty + satPenalty + saltPenalty + energyPenalty + transPenalty + freeSugarsExtra;
  const positives = fiberBonus + proteinBonus + fvnlBonus;

  // 0..100 subscore (higher is better)
  const sub = clamp(100 - negatives + positives, 0, 100);

  notes.push(
    ...(sugars > Sug.high ? ["High sugar"] : sugars > sugarsLow ? ["Moderate sugar"] : []),
    ...(sat > Sat.high ? ["High saturated fat"] : sat > Sat.low ? ["Moderate saturated fat"] : []),
    ...(salt > S.salt.high ? ["High salt"] : salt > S.salt.low ? ["Moderate salt"] : []),
    ...(transPenalty ? ["Contains trans fat"] : []),
    ...(fiberBonus >= (bev ? 3 : 6) ? ["Good fiber"] : []),
    ...(proteinBonus >= 4 ? ["Good protein"] : []),
    ...(fvnlBonus ? ["High fruit/veg/nuts/legumes"] : [])
  );

  return { sub, detail: { sugars, sat, salt, kcal, trans, fiber, protein, fvnl,
    penalties: { sugarPenalty, satPenalty, saltPenalty, energyPenalty, transPenalty, freeSugarsExtra },
    bonuses:   { fiberBonus, proteinBonus, fvnlBonus }
  }};
}

function scoreProcessing(product, notes) {
  const ing = (product.ingredients_text || "").toLowerCase();
  let penalty = 0;
  const hits = [];

  const nova = asNum(product.nova_group, null) ?? asNum((product.nutrition||product.nutriments||{}).nova_group, null);
  if (nova && CFG.processing.novaPenalty[nova] != null) {
    penalty += CFG.processing.novaPenalty[nova];
    if (nova >= 3) hits.push(`Processed (NOVA ${nova})`);
  }
  for (const s of CFG.processing.signals) {
    if (s.re.test(ing)) { penalty += s.score; hits.push(s.label); }
  }
  penalty = Math.min(penalty, CFG.processing.maxPenalty);
  if (hits.length) notes.push(...hits);

  const sub = clamp(100 - penalty * 3, 0, 100); // expand to 0..100
  return { sub, detail: { nova: nova ?? null, penalty, hits: Array.from(new Set(hits)) } };
}

function scoreAdditives(product, notes) {
  let penalty = 0;
  const seen = [];
  if (Array.isArray(product.additives)) {
    for (const a of product.additives) {
      const code = normalizeE(a?.code);
      const risk = (a?.risk || "").toLowerCase();
      let p = 0;
      if (risk && CFG.additives.riskPenalty[risk] != null) p = CFG.additives.riskPenalty[risk];
      if (code && CFG.additives.codePenalty[code] != null) p = Math.max(p, CFG.additives.codePenalty[code]);
      if (p > 0) { penalty += p; seen.push(code || a?.name || "additive"); }
    }
  }
  // catch text-only mentions
  const ing = (product.ingredients_text || "").toLowerCase();
  for (const d of CFG.additives.detectors) {
    if (d.re.test(ing)) { penalty += d.p; seen.push(d.label); }
  }

  penalty = Math.min(penalty, CFG.additives.cap);
  if (seen.length) notes.push(`Additives: ${Array.from(new Set(seen)).slice(0,6).join(", ")}${seen.length>6?"…":""}`);
  const sub = clamp(100 - penalty * 2.5, 0, 100);
  return { sub, detail: { penalty, seen: Array.from(new Set(seen)) } };
}

function scoreIngredientFlags(product, notes) {
  const bev = isBeverage(product);
  const ing = (product.ingredients_text || "").toLowerCase();
  const adj = categoryTuning(product);
  let penalty = 0;
  const hits = [];

  if (CFG.flags.sweetenersRe.test(ing)) {
    const base = adj.sweetenerZeroTolerance ? (adj.sweetenerPenalty || CFG.flags.sweetenersPenalty) : CFG.flags.sweetenersPenalty;
    const p = Math.round(base * (bev ? CFG.flags.beverageSweetenerMultiplier : 1));
    penalty += p; hits.push("Artificial/high-intensity sweeteners");
  }
  if (CFG.flags.colorsRe.test(ing))   { penalty += CFG.flags.colorsPenalty; hits.push("Synthetic colors"); }
  if (CFG.flags.palmRe.test(ing))     { penalty += CFG.flags.palmPenalty;   hits.push("Palm oil"); }
  if (CFG.flags.caffeineRe.test(ing) && bev) { penalty += CFG.flags.caffeinePenalty; hits.push("Caffeinated beverage"); }

  if (hits.length) notes.push(...hits);
  const sub = clamp(100 - penalty * 4, 0, 100);
  return { sub, detail: { penalty, hits: Array.from(new Set(hits)) } };
}

function scoreMicronutrients(product, notes) {
  const n = product.nutrition || product.nutriments || {};
  let bonus = 0;
  for (const k of CFG.micronutrients.keys) {
    const pct = readNutr(n, [`${k}_%dv_100g`, `${k}_%dv`], null);
    if (pct != null && pct >= CFG.micronutrients.threshold) {
      bonus += CFG.micronutrients.perKeyBonus;
    }
  }
  bonus = Math.min(bonus, CFG.micronutrients.cap);
  if (bonus > 0) notes.push("Fortified with micronutrients");
  const sub = clamp(CFG.micronutrients.base + bonus * CFG.micronutrients.scale, 0, 100);
  return { sub, detail: { bonus } };
}

//////////////////////
// Public API       //
//////////////////////
export function computeHealthScore(product = {}) {
  const pos = [];
  const neg = [];

  const npNotes = [];
  const { sub: NP,   detail: NPd }   = scoreNutrientProfile(product, npNotes);

  const prNotes = [];
  const { sub: PROC, detail: PROCd } = scoreProcessing(product, prNotes);

  const adNotes = [];
  const { sub: ADD,  detail: ADDd }  = scoreAdditives(product, adNotes);

  const flNotes = [];
  const { sub: FLAG, detail: FLAGd } = scoreIngredientFlags(product, flNotes);

  const miNotes = [];
  const { sub: MICRO,detail: MICROd }= scoreMicronutrients(product, miNotes);

  const w = CFG.weights;
  const total = NP*w.nutrientProfile + PROC*w.processing + ADD*w.additives + FLAG*w.ingredientFlags + MICRO*w.micronutrients;
  const score = Math.round(clamp(total, 0, 100));

  const grade = score >= 80 ? "A" : score >= 65 ? "B" : score >= 50 ? "C" : score >= 35 ? "D" : "E";

  // positives/negatives (dedup & limit)
  for (const n of npNotes.concat(miNotes))  if (/(good|high|fortified|fruit|veg|nuts|legumes)/i.test(n)) pos.push(n);
  for (const n of [].concat(prNotes, adNotes, flNotes, npNotes))
    if (/(high|moderate|processed|hydrogenated|sweetener|nitrite|color|palm|trans|additive|caffeinated)/i.test(n)) neg.push(n);

  const dedup = (arr) => Array.from(new Set(arr)).slice(0, 6);

  return {
    score,
    grade,
    positives: dedup(pos),
    negatives: dedup(neg),
    breakdown: {
      subScores: { nutrientProfile: NP, processing: PROC, additives: ADD, ingredientFlags: FLAG, micronutrients: MICRO },
      details:   { NP: NPd, PROC: PROCd, ADD: ADDd, FLAG: FLAGd, MICRO: MICROd },
      weights:   { ...w },
    },
  };
}

export function withClientScore(p) {
  if (!p) return p;
  if (typeof p?.score === "number") return p;
  const { score, grade, positives, negatives } = computeHealthScore(p);
  return { ...p, score, grade, positives, negatives };
}

// Optional: expose config for quick tuning at runtime (e.g., Dev screen)
export function __scoreConfig() { return CFG; }
