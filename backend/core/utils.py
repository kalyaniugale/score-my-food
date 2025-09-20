# backend/core/utils.py
from __future__ import annotations

import re
import requests
from typing import Dict, List, Optional, Tuple, Any

# =========================
# --------- Regex ---------
# =========================

# E/INS additive codes like: E621, E-621, e 621, INS150d, ins 150D, 150d (bare)
E_INS_RE = re.compile(r"\b(?:(?:E|INS)\s*[-\s]?)?(\d{3,4}[a-dA-D]?)\b", re.I)
DASH_RANGE = r"[\u2010-\u2015]"  # fancy dashes → '-'

# =========================
# ----- Static Data -------
# =========================

ALLERGENS = {
    "milk", "lactose", "butter", "ghee",
    "soy", "soya",
    "wheat", "gluten", "barley", "rye", "oats",
    "egg", "albumen",
    "peanut", "peanuts",
    "tree nuts", "almond", "hazelnut", "walnut", "cashew", "pecan", "pistachio",
    "macadamia", "brazil nut", "pine nut",
    "sesame",
    "mustard",
    "fish",
    "shellfish", "crustacean", "shrimp", "prawn", "crab", "lobster",
    "celery",
    "lupin",
    "sulfite", "sulphite", "sulphites", "sulfites",
}

BEVERAGE_HINTS = {
    "soft drink", "juice", "nectar", "soda", "cola", "tonic", "energy drink",
    "iced tea", "drink", "beverage", "water", "sparkling", "isotonic",
    "milk drink", "flavoured milk", "yogurt drink", "lassi", "buttermilk"
}

ADDITIVE_DB: Dict[str, Dict[str, str]] = {
    # Flavour enhancers
    "E621": {"name": "Monosodium glutamate (MSG)", "risk": "caution"},
    "E622": {"name": "Monopotassium glutamate", "risk": "caution"},
    "E623": {"name": "Calcium diglutamate", "risk": "caution"},
    "E624": {"name": "Monoammonium glutamate", "risk": "caution"},
    "E625": {"name": "Magnesium diglutamate", "risk": "caution"},
    "E627": {"name": "Disodium guanylate", "risk": "caution"},
    "E631": {"name": "Disodium inosinate", "risk": "caution"},

    # Colours
    "E110": {"name": "Sunset Yellow FCF", "risk": "avoid"},
    "E102": {"name": "Tartrazine", "risk": "avoid"},
    "E129": {"name": "Allura Red AC", "risk": "avoid"},
    "E150D": {"name": "Caramel colour IV (sulphite ammonia)", "risk": "moderate"},
    "INS150D": {"name": "Caramel colour IV (sulphite ammonia)", "risk": "moderate"},

    # Preservatives
    "E211": {"name": "Sodium benzoate", "risk": "moderate"},
    "E202": {"name": "Potassium sorbate", "risk": "moderate"},
    "E250": {"name": "Sodium nitrite", "risk": "avoid"},
    "E251": {"name": "Sodium nitrate", "risk": "avoid"},

    # Sweeteners
    "E950": {"name": "Acesulfame K", "risk": "moderate"},
    "E951": {"name": "Aspartame", "risk": "avoid"},
    "E955": {"name": "Sucralose", "risk": "moderate"},
    "E960": {"name": "Steviol glycosides", "risk": "generally safe"},

    # Low-concern processing aids
    "E296": {"name": "Malic acid", "risk": "generally safe"},
    "E330": {"name": "Citric acid", "risk": "generally safe"},
    "E331": {"name": "Sodium citrates", "risk": "generally safe"},
    "E327": {"name": "Calcium lactate", "risk": "generally safe"},
    "E170": {"name": "Calcium carbonate", "risk": "generally safe"},
    "E471": {"name": "Mono-/diglycerides of fatty acids", "risk": "moderate"},
}

MSG_LIKE = {"621", "622", "623", "624", "625", "627", "631"}

# =========================
# ---- Text Utilities -----
# =========================

def norm(s: str) -> str:
    if not s:
        return ""
    s = s.replace("\n", " ")
    s = re.sub(DASH_RANGE, "-", s)
    s = re.sub(r"\s+", " ", s)
    return s.strip()


def find_section(text: str, start_keys: List[str], end_keys: List[str]) -> str:
    t = norm(text)
    if not t:
        return ""
    start_re = re.compile(r"(?i)" + r"|".join([re.escape(k).replace(r"\ ", r"\s*") for k in start_keys]))
    m = start_re.search(t)
    if not m:
        return ""
    start = m.end()
    end = len(t)
    for k in end_keys:
        mm = re.search(r"(?i)" + re.escape(k).replace(r"\ ", r"\s*"), t[start:])
        if mm:
            end = start + mm.start()
            break
    return t[start:end].strip(" :.-")


def split_top_level_commas(s: str) -> List[str]:
    parts, buf, depth = [], [], 0
    for ch in s:
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth = max(0, depth - 1)
        if ch == "," and depth == 0:
            part = "".join(buf).strip()
            if part:
                parts.append(part)
            buf = []
        else:
            buf.append(ch)
    last = "".join(buf).strip()
    if last:
        parts.append(last)
    return parts

# =========================
# ---- Additive Logic -----
# =========================

def _canon_additive(code: str) -> str:
    c = code.strip().upper().replace(" ", "")
    if c.startswith("E") or c.startswith("INS"):
        return c
    return f"E{c}"

def extract_additives(text: str) -> List[str]:
    if not text:
        return []
    raw = [m.group(1) for m in E_INS_RE.finditer(text)]
    out = []
    for c in raw:
        canon = _canon_additive(c)
        if re.search(rf"\bINS\s*[-\s]?{re.escape(c)}\b", text, flags=re.I):
            out.append(f"INS{c.upper() if not c.upper().startswith('INS') else c.upper()[3:]}")
        else:
            out.append(canon)
    seen, res = set(), []
    for c in out:
        cc = c.upper()
        if cc not in seen:
            seen.add(cc)
            res.append(cc)
    return res

def classify_additives(codes: List[str]) -> List[Dict[str, str]]:
    out = []
    for code in codes:
        key = code.upper()
        db_hit = (
            ADDITIVE_DB.get(key)
            or ADDITIVE_DB.get(key.replace("INS", "E"))
            or ADDITIVE_DB.get(key.replace("E", "INS"))
        )
        if not db_hit:
            bare = key.replace("INS", "").replace("E", "")
            db_hit = ADDITIVE_DB.get(f"E{bare}") or ADDITIVE_DB.get(f"INS{bare}")
        info = db_hit or {"name": "Unknown additive", "risk": "unknown"}
        out.append({"code": key, "name": info["name"], "risk": info["risk"]})
    return out

# =========================
# ---- Ingredient Parse ----
# =========================

def parse_ingredients(full_text: str) -> Dict[str, Any]:
    ingredients_block = find_section(
        full_text,
        start_keys=["ingredients", "ingredient", "ingedients", "ingr edients", "in gredients"],
        end_keys=["allergen", "allergy", "nutrition", "nutritional", "nutri tion", "storage", "best before", "manufactured", "packed by"]
    )

    items = []
    if ingredients_block:
        for tok in split_top_level_commas(ingredients_block):
            tok = tok.strip(" .;")
            m = re.search(r"(?i)\b(\d{1,3}(?:\.\d+)?)\s*%", tok)
            pct = float(m.group(1)) if m else None
            name = re.sub(r"\((\d{1,3}(?:\.\d+)?)\s*%\)", "", tok)
            name = re.sub(r"\s+", " ", name).strip(" ()")
            if name:
                items.append({"name": name, "percent": pct})

    low = full_text.lower()
    allergens = set()
    m_all = re.search(r"(?i)allerg(?:en|y)[^:]*:\s*([^.\n]+)", full_text)
    if m_all:
        chunk = m_all.group(1).lower()
        for w in re.split(r"[,\s;/]+", chunk):
            ww = w.strip().rstrip(".")
            if ww in ALLERGENS:
                allergens.add(ww)
    for a in ALLERGENS:
        if re.search(rf"\bcontains\b[^.\n]*\b{re.escape(a)}s?\b", low):
            allergens.add(a)

    codes = extract_additives(low)
    additives = classify_additives(codes)

    flags = {
        "palmOil": bool(re.search(r"\bpalm(olein| oil)?\b", low)),
        "addedSugar": any(w in low for w in ["sugar", "glucose", "fructose", "corn syrup", "hfcs", "invert syrup", "dextrose", "malt syrup"]),
        "addedSalt": "salt" in low or "sodium chloride" in low,
        "msgLikeEnhancer": any(re.search(rf"\b{c}\b", low) for c in ["msg", "monosodium glutamate"]) or any(k[1:].split()[0] in MSG_LIKE for k in codes),
        "artificialFlavour": bool(re.search(r"artificial flavour|flavor|nature[-\s]*identical|flavouring substances", low)),
        "artificialColour": bool(re.search(r"\bcolour\b|\bcolor\b|caramel colour|caramel color", low)),
    }

    return {
        "ingredients": items,
        "allergens": sorted(allergens),
        "additives": additives,
        "flags": flags,
    }

# =========================
# ---- Nutrition Utils ----
# =========================

def _to_float(x: Any) -> Optional[float]:
    try:
        return float(x)
    except (TypeError, ValueError):
        return None

def coerce_nutrition(nutr: Dict[str, Any]) -> Dict[str, Optional[float]]:
    sodium_100g = nutr.get("sodium_100g")
    sodium_mg = None
    if sodium_100g is not None:
        try:
            sodium_mg = float(sodium_100g) * 1000.0
        except Exception:
            sodium_mg = None

    return {-
        "energy_kj": _to_float(nutr.get("energy-kj_100g") or nutr.get("energy_100g")),
        "sugar_g": _to_float(nutr.get("sugars_100g")),
        "sodium_mg": sodium_mg,
        "sat_fat_g": _to_float(nutr.get("saturated_fat_100g")),
        "trans_fat_g": _to_float(nutr.get("trans_fat_100g")),
        "fiber_g": _to_float(nutr.get("fiber_100g")),
        "protein_g": _to_float(nutr.get("proteins_100g")),
        "fruit_pct": _to_float(nutr.get("fruits-vegetables-nuts-estimate-from-ingredients_100g") or nutr.get("fruits-vegetables-nuts_100g")),
    }

def is_beverage(p: Dict[str, Any]) -> bool:
    name = (p.get("product_name") or "").lower()
    cats = " ".join((p.get("categories") or "").lower().split(","))
    for blob in (name, cats):
        if any(h in blob for h in BEVERAGE_HINTS):
            return True
    qty = (p.get("quantity") or "").lower()
    if "ml" in qty or "l" in qty:
        if not any(w in name for w in ["oil", "ghee"]):
            return True
    return False

# =========================
# ---- Traffic Lights -----
# =========================

def traffic_light_sugar(value_g_per_100: Optional[float], beverage: bool) -> str:
    if value_g_per_100 is None:
        return "unknown"
    if beverage:
        if value_g_per_100 <= 2.5: return "low"
        if value_g_per_100 <= 11.25: return "medium"
        return "high"
    else:
        if value_g_per_100 <= 5: return "low"
        if value_g_per_100 <= 22.5: return "medium"
        return "high"

def traffic_light_salt_from_sodium(sodium_mg_per_100: Optional[float], beverage: bool) -> str:
    if sodium_mg_per_100 is None:
        return "unknown"
    salt_g = (sodium_mg_per_100 / 1000.0) * 2.5
    if beverage:
        if salt_g <= 0.3: return "low"
        if salt_g <= 1.5: return "medium"
        return "high"
    else:
        if salt_g <= 0.3: return "low"
        if salt_g <= 1.5: return "medium"
        return "high"

def traffic_light_satfat(value_g_per_100: Optional[float], _beverage: bool) -> str:
    if value_g_per_100 is None:
        return "unknown"
    if value_g_per_100 <= 1.5: return "low"
    if value_g_per_100 <= 5: return "medium"
    return "high"

# =========================
# ---- Scoring (0–100) ----
# =========================

def _negative_points(energy_kj: Optional[float], sugar_g: Optional[float],
                     sat_fat_g: Optional[float], sodium_mg: Optional[float],
                     beverage: bool) -> float:
    pts = 0.0
    if energy_kj is not None:
        pts += min(10.0, max(0.0, energy_kj / 335.0))
    if sugar_g is not None:
        if beverage:
            pts += min(10.0, sugar_g / 1.5)
        else:
            pts += min(10.0, sugar_g / 2.2)
    if sat_fat_g is not None:
        pts += min(10.0, sat_fat_g / 1.0)
    if sodium_mg is not None:
        pts += min(10.0, sodium_mg / 180.0)
    return pts

def _positive_points(fiber_g: Optional[float], protein_g: Optional[float], fruit_pct: Optional[float]) -> float:
    pts = 0.0
    if fiber_g is not None:
        pts += min(5.0, fiber_g / 1.2)
    if protein_g is not None:
        pts += min(5.0, protein_g / 2.0)
    if fruit_pct is not None:
        if fruit_pct >= 80: pts += 5
        elif fruit_pct >= 60: pts += 4
        elif fruit_pct >= 40: pts += 3
        elif fruit_pct >= 20: pts += 2
        elif fruit_pct >= 5:  pts += 1
    return pts

def _additive_penalties(additives: List[Dict[str, str]]) -> float:
    penalty = 0.0
    for a in additives:
        tier = (a.get("risk") or "").lower()
        code = (a.get("code") or "").upper().replace(" ", "")
        if tier == "avoid":
            penalty += 14
        elif tier == "moderate":
            penalty += 8
        elif tier == "caution":
            penalty += 6
        elif tier == "generally safe":
            penalty += 0
        elif tier == "unknown":
            penalty += 2
        bare = code.replace("INS", "").replace("E", "")
        if bare[:3] in MSG_LIKE:
            penalty += 2
    return penalty

def _keyword_penalties(ingredients_text: str) -> List[Tuple[str, int]]:
    penalties: List[Tuple[str, int]] = []
    text = (ingredients_text or "").lower()

    if re.search(r"\bpalm(olein| oil)?\b", text):
        penalties.append(("Palm oil", -8))
    if "hydrogenated" in text or "partially hydrogenated" in text:
        penalties.append(("Hydrogenated/partially hydrogenated oils", -25))
    if any(word in text for word in ["sugar", "glucose", "fructose", "hfcs", "corn syrup", "invert syrup", "malt syrup", "dextrose"]):
        penalties.append(("Added sugars/syrups", -12))
    if "salt" in text or "sodium chloride" in text:
        penalties.append(("Added salt", -5))
    if any(word in text for word in ["acesulfame", "sucralose", "aspartame"]):
        penalties.append(("Artificial sweeteners", -5))
    if "artificial flavour" in text or "artificial flavor" in text:
        penalties.append(("Artificial flavour", -4))
    if "colour" in text or "color" in text:
        penalties.append(("Added colours", -3))

    return penalties

def compute_health_score(nutrition: Dict[str, Optional[float]],
                         additives: List[Dict[str, str]],
                         ingredients_text: str,
                         beverage: bool) -> int:
    energy_kj = nutrition.get("energy_kj")
    sugar_g = nutrition.get("sugar_g")
    sat_fat_g = nutrition.get("sat_fat_g")
    sodium_mg = nutrition.get("sodium_mg")
    fiber_g = nutrition.get("fiber_g")
    protein_g = nutrition.get("protein_g")
    fruit_pct = nutrition.get("fruit_pct")

    neg = _negative_points(energy_kj, sugar_g, sat_fat_g, sodium_mg, beverage)
    pos = _positive_points(fiber_g, protein_g, fruit_pct)

    s = 100.0 - (neg * 4.0) + (pos * 3.0)
    s -= _additive_penalties(additives)
    for _label, pen in _keyword_penalties(ingredients_text):
        s += pen
    if nutrition.get("trans_fat_g") and nutrition["trans_fat_g"] > 0:
        s -= 25

    return max(0, min(100, round(s)))

def grade_from_score(score: int) -> str:
    if score >= 85: return "A+"
    if score >= 75: return "A"
    if score >= 65: return "B"
    if score >= 50: return "C"
    if score >= 35: return "D"
    return "E"

# =========================
# ---- Product Analysis ----
# =========================

def summarize_pros_cons(nutrition: Dict[str, Optional[float]],
                        additives: List[Dict[str, str]],
                        ingredients_text: str,
                        beverage: bool) -> Tuple[List[str], List[str]]:
    positives: List[str] = []
    negatives: List[str] = []

    if nutrition.get("fiber_g") and nutrition["fiber_g"] and nutrition["fiber_g"] >= 3:
        positives.append("High in fiber (≥3g/100g)")
    if nutrition.get("protein_g") and nutrition["protein_g"] and nutrition["protein_g"] >= 5:
        positives.append("Good source of protein (≥5g/100g)")

    if traffic_light_sugar(nutrition.get("sugar_g"), beverage) == "high":
        negatives.append("High in total sugars")
    if traffic_light_salt_from_sodium(nutrition.get("sodium_mg"), beverage) == "high":
        negatives.append("High in salt (from sodium)")
    if traffic_light_satfat(nutrition.get("sat_fat_g"), beverage) == "high":
        negatives.append("High in saturated fat")

    if nutrition.get("trans_fat_g") and nutrition["trans_fat_g"] and nutrition["trans_fat_g"] > 0:
        negatives.append("Contains trans fats")

    for a in additives:
        if (a.get("risk") or "").lower() == "avoid":
            negatives.append(f"Contains {a['name']} ({a['code']})")

    for label, pen in _keyword_penalties(ingredients_text):
        if pen < 0:
            negatives.append(label)

    seen_p, seen_n = set(), set()
    pos, neg = [], []
    for x in positives:
        if x not in seen_p:
            pos.append(x); seen_p.add(x)
    for x in negatives:
        if x not in seen_n:
            neg.append(x); seen_n.add(x)

    return pos, neg

def analyze_product(p: Dict[str, Any], barcode: str) -> Dict[str, Any]:
    nutr_raw = p.get("nutriments", {}) or {}
    nutrition = coerce_nutrition(nutr_raw)

    ingredients_text = (
        p.get("ingredients_text")
        or p.get("ingredients_text_en")
        or p.get("ingredients_text_fr")
        or ""
    )
    parsed = parse_ingredients(ingredients_text or (p.get("ingredients_text_debug") or ""))

    additives_info = parsed["additives"] if parsed.get("additives") else classify_additives(extract_additives(ingredients_text))
    beverage = is_beverage(p)

    score = compute_health_score(nutrition, additives_info, ingredients_text, beverage)
    positives, negatives = summarize_pros_cons(nutrition, additives_info, ingredients_text, beverage)

    traffic = {
        "sugars": traffic_light_sugar(nutrition.get("sugar_g"), beverage),
        "sat_fat": traffic_light_satfat(nutrition.get("sat_fat_g"), beverage),
        "salt": traffic_light_salt_from_sodium(nutrition.get("sodium_mg"), beverage),
    }

    return {
        "barcode": barcode,
        "name": p.get("product_name") or "Unknown",
        "brand": (p.get("brands") or "").split(",")[0].strip() or None,
        "score": score,
        "grade": grade_from_score(score),
        "isBeverage": beverage,
        "traffic": traffic,
        "image": p.get("image_front_url") or p.get("image_url"),
        "ingredients_text": ingredients_text,
        "structured_ingredients": parsed.get("ingredients", []),
        "nutrition": nutrition,
        "additives": additives_info,
        "allergens": parsed.get("allergens", []),
        "positives": positives,
        "negatives": negatives,
        "source": "openfoodfacts",
    }

# =========================
# ---- OFF Lookup ---------
# =========================

def off_lookup(barcode: str) -> Optional[Dict[str, Any]]:
    url = f"https://world.openfoodfacts.org/api/v2/product/{barcode}.json"
    try:
        r = requests.get(url, timeout=8)
    except Exception:
        return None
    if r.status_code != 200:
        return None
    try:
        data = r.json()
    except Exception:
        return None
    if data.get("status") != 1 or "product" not in data:
        return None
    return analyze_product(data["product"], barcode)
