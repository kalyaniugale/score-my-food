# backend/core/utils.py
from __future__ import annotations

import re
import time
import requests
from typing import Dict, List, Optional, Tuple, Any

# =========================
# --------- Regex ---------
# =========================

# E/INS additive codes like: E621, E-621, e 621, INS150d, ins 150D
# Also allow *bare* 150a-d only (to avoid matching "150 g" or dates).
E_INS_RE = re.compile(
    r"""
    \b(?:
        (?:E|INS)\s*[-\s]?(?P<code1>\d{3,4}[a-dA-D]?)    # E/INS-prefixed codes
        |
        (?P<bare>1[0-9]{2}[a-dA-D])                      # bare 150a-d style only
    )\b
    """,
    re.I | re.X,
)
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

NON_BEVERAGE_LIQUIDS = (
    "oil", "ghee", "sauce", "ketchup", "vinegar", "dressing",
    "soy sauce", "syrup", "chutney", "pickle", "rel\ufeffish"
)

# Expanded additive knowledge (selected high-signal codes)
ADDITIVE_DB: Dict[str, Dict[str, str]] = {
    # Flavour enhancers (MSG-like)
    "E621": {"name": "Monosodium glutamate (MSG)", "risk": "caution"},
    "E622": {"name": "Monopotassium glutamate", "risk": "caution"},
    "E623": {"name": "Calcium diglutamate", "risk": "caution"},
    "E624": {"name": "Monoammonium glutamate", "risk": "caution"},
    "E625": {"name": "Magnesium diglutamate", "risk": "caution"},
    "E627": {"name": "Disodium guanylate", "risk": "caution"},
    "E631": {"name": "Disodium inosinate", "risk": "caution"},

    # Colours (synthetic notable)
    "E102": {"name": "Tartrazine", "risk": "avoid"},
    "E104": {"name": "Quinoline Yellow", "risk": "avoid"},
    "E110": {"name": "Sunset Yellow FCF", "risk": "avoid"},
    "E122": {"name": "Carmoisine", "risk": "avoid"},
    "E124": {"name": "Ponceau 4R", "risk": "avoid"},
    "E129": {"name": "Allura Red AC", "risk": "avoid"},
    "E150D": {"name": "Caramel colour IV (sulphite ammonia)", "risk": "moderate"},
    "INS150D": {"name": "Caramel colour IV (sulphite ammonia)", "risk": "moderate"},

    # Preservatives
    "E211": {"name": "Sodium benzoate", "risk": "moderate"},
    "E202": {"name": "Potassium sorbate", "risk": "moderate"},
    "E200": {"name": "Sorbic acid", "risk": "moderate"},
    "E249": {"name": "Potassium nitrite", "risk": "avoid"},
    "E250": {"name": "Sodium nitrite", "risk": "avoid"},
    "E251": {"name": "Sodium nitrate", "risk": "avoid"},
    "E252": {"name": "Potassium nitrate", "risk": "avoid"},

    # Sweeteners
    "E950": {"name": "Acesulfame K", "risk": "moderate"},
    "E951": {"name": "Aspartame", "risk": "avoid"},
    "E954": {"name": "Saccharin", "risk": "moderate"},
    "E952": {"name": "Cyclamates", "risk": "avoid"},
    "E955": {"name": "Sucralose", "risk": "moderate"},
    "E960": {"name": "Steviol glycosides", "risk": "generally safe"},
    "E961": {"name": "Neotame", "risk": "moderate"},
    "E962": {"name": "Aspartame-acesulfame salt", "risk": "moderate"},

    # Phosphates / emulsifiers / antioxidants
    "E471": {"name": "Mono-/diglycerides of fatty acids", "risk": "moderate"},
    "E450": {"name": "Diphosphates", "risk": "moderate"},
    "E451": {"name": "Triphosphates", "risk": "moderate"},
    "E452": {"name": "Polyphosphates", "risk": "moderate"},
    "E319": {"name": "Tertiary butylhydroquinone (TBHQ)", "risk": "avoid"},
    "E320": {"name": "Butylated hydroxyanisole (BHA)", "risk": "avoid"},
    "E321": {"name": "Butylated hydroxytoluene (BHT)", "risk": "avoid"},

    # Low-concern processing aids
    "E296": {"name": "Malic acid", "risk": "generally safe"},
    "E330": {"name": "Citric acid", "risk": "generally safe"},
    "E331": {"name": "Sodium citrates", "risk": "generally safe"},
    "E327": {"name": "Calcium lactate", "risk": "generally safe"},
    "E170": {"name": "Calcium carbonate", "risk": "generally safe"},
}

# Codes that behave like MSG
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
    """
    Extract additive codes from a *targeted* text (ideally just the ingredients block).
    Avoid scanning whole labels to reduce false positives from dates/weights.
    """
    if not text:
        return []
    raw: List[str] = []
    for m in E_INS_RE.finditer(text):
        c = m.group("code1") or m.group("bare")
        if not c:
            continue
        raw.append(c)

    out = []
    for c in raw:
        canon = _canon_additive(c)
        if re.search(rf"\bINS\s*[-\s]?{re.escape(c)}\b", text, flags=re.I):
            out.append(f"INS{c.upper()}")
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
        key = code.upper().replace(" ", "")
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
        start_keys=["ingredients", "ingredient", "ingedients", "ingr edients", "in gredients", "contains"],
        end_keys=["allergen", "allergy", "nutrition", "nutritional", "nutri tion", "storage", "best before", "manufactured", "packed by", "net weight"]
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

    # Normalize milk synonyms to 'milk'
    if {"lactose", "butter", "ghee"} & allergens:
        allergens.add("milk")

    # Critically: only scan additives in the ingredients block to avoid false positives
    codes = extract_additives(ingredients_block or "")
    additives = classify_additives(codes)

    flags = {
        "palmOil": bool(re.search(r"\bpalm(olein| oil)?\b", low)),
        "addedSugar": any(w in low for w in ["sugar", "glucose", "fructose", "corn syrup", "hfcs", "invert syrup", "dextrose", "malt syrup"]),
        "addedSalt": "salt" in low or "sodium chloride" in low,
        "msgLikeEnhancer": bool(re.search(r"\b(msg|monosodium glutamate)\b", low)) or any(k.replace("INS","").replace("E","")[:3] in MSG_LIKE for k in codes),
        "artificialFlavour": bool(re.search(r"\b(artificial|nature[-\s]*identical)\s+flavo(u)?r", low)),
        "artificialColour": bool(re.search(r"\b(artificial|synthetic)\s+colou?r\b|caramel colou?r", low)),
        "fried": bool(re.search(r"\b(fried|deep[-\s]?fried|fried snack)\b", low)),
        "extruded": bool(re.search(r"\b(extruded|puffed)\b", low)),
    }

    return {
        "ingredients": items,
        "allergens": sorted(allergens),
        "additives": additives,
        "flags": flags,
        "ingredients_block": ingredients_block or "",
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
    # Sodium (mg/100g) with salt fallback
    sodium_mg: Optional[float] = None
    if nutr.get("sodium_100g") is not None:
        sodium_mg = _to_float(nutr.get("sodium_100g")) * 1000.0
    elif nutr.get("sodium_mg_100g") is not None:
        sodium_mg = _to_float(nutr.get("sodium_mg_100g"))
    elif nutr.get("salt_100g") is not None:
        salt = _to_float(nutr.get("salt_100g"))
        sodium_mg = salt * 393.0 if salt is not None else None  # 1 g salt ≈ 393 mg sodium

    # Energy (kJ/100g) with kcal fallback (×4.184)
    energy_kj = (nutr.get("energy-kj_100g")
                 or nutr.get("energy_kj_100g")
                 or nutr.get("energy_100g"))  # energy_100g is often kJ on OFF
    if energy_kj is None and nutr.get("energy-kcal_100g") is not None:
        kcal = _to_float(nutr.get("energy-kcal_100g"))
        energy_kj = kcal * 4.184 if kcal is not None else None

    # Saturated fat
    sat_fat = nutr.get("saturated-fat_100g")
    if sat_fat is None:
        sat_fat = nutr.get("saturated_fat_100g")

    # Trans fat
    trans_fat = nutr.get("trans-fat_100g")
    if trans_fat is None:
        trans_fat = nutr.get("trans_fat_100g")

    return {
        "energy_kj": _to_float(energy_kj),
        "sugar_g": _to_float(nutr.get("sugars_100g")),
        "sodium_mg": _to_float(sodium_mg),
        "sat_fat_g": _to_float(sat_fat),
        "trans_fat_g": _to_float(trans_fat),
        "fiber_g": _to_float(nutr.get("fiber_100g")),
        "protein_g": _to_float(nutr.get("proteins_100g")),
        "fruit_pct": _to_float(
            nutr.get("fruits-vegetables-nuts-estimate-from-ingredients_100g")
            or nutr.get("fruits-vegetables-nuts_100g")
        ),
    }

def is_beverage(p: Dict[str, Any]) -> bool:
    name = (p.get("product_name") or "").lower()
    cats = " ".join((p.get("categories") or "").lower().split(","))
    # obvious hints
    for blob in (name, cats):
        if any(h in blob for h in BEVERAGE_HINTS):
            return True
        if any(nb in blob for nb in NON_BEVERAGE_LIQUIDS):
            return False
    # quantity heuristic (avoid oils/sauces)
    qty = (p.get("quantity") or "").lower()
    if ("ml" in qty or "l" in qty) and not any(w in name for w in NON_BEVERAGE_LIQUIDS):
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

def traffic_light_salt_from_sodium(sodium_mg_per_100: Optional[float], _beverage: bool) -> str:
    # Same thresholds for beverages/solids in UK FOP
    if sodium_mg_per_100 is None:
        return "unknown"
    salt_g = (sodium_mg_per_100 / 1000.0) * 2.5
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
    """
    Higher = worse. Tuned but bounded so it can't overwhelm everything.
    """
    pts = 0.0
    if energy_kj is not None:
        # Map ~0–1880 kJ (0–450 kcal) to ~0–10
        pts += min(10.0, max(0.0, energy_kj / 188.0))
    if sugar_g is not None:
        if beverage:
            pts += min(10.0, sugar_g / 1.8)    # ~18 g → ~10
        else:
            pts += min(10.0, sugar_g / 2.8)    # ~28 g → ~10
    if sat_fat_g is not None:
        pts += min(10.0, sat_fat_g / 1.3)      # ~13 g → ~10
    if sodium_mg is not None:
        pts += min(10.0, sodium_mg / 230.0)    # ~2300 mg → ~10
    return min(30.0, pts)  # absolute cap

def _positive_points(fiber_g: Optional[float], protein_g: Optional[float], fruit_pct: Optional[float]) -> float:
    pts = 0.0
    if fiber_g is not None:
        pts += min(6.0, fiber_g / 1.2)
    if protein_g is not None:
        pts += min(5.0, protein_g / 2.2)
    if fruit_pct is not None:
        if fruit_pct >= 80: pts += 5
        elif fruit_pct >= 60: pts += 4
        elif fruit_pct >= 40: pts += 3
        elif fruit_pct >= 20: pts += 2
        elif fruit_pct >= 5:  pts += 1
    return min(16.0, pts)

def _additive_penalties(additives: List[Dict[str, str]]) -> float:
    """
    Accumulate penalties from additives; harsher on avoid/synthetic colours/nitrites/antioxidants.
    Capped to avoid zeroing scores.
    """
    penalty = 0.0
    for a in additives or []:
        tier = (a.get("risk") or "").lower()
        code = (a.get("code") or "").upper().replace(" ", "")

        # baseline by risk tier
        if tier == "avoid":
            penalty += 10
        elif tier == "moderate":
            penalty += 5
        elif tier == "caution":
            penalty += 4
        elif tier == "generally safe":
            penalty += 0
        elif tier == "unknown":
            penalty += 1

        # MSG-like bump
        bare = code.replace("INS", "").replace("E", "")
        if bare[:3] in MSG_LIKE:
            penalty += 2

        # specific harsher codes
        if code in {"E102","E104","E110","E122","E124","E129"}:
            penalty += 5
        if code in {"E249","E250","E251","E252"}:  # nitrites/nitrates
            penalty += 10
        if code in {"E319","E320","E321"}:  # TBHQ/BHA/BHT
            penalty += 8

    return min(penalty, 36.0)

def _processing_penalty(text: str, flags: Dict[str, bool]) -> float:
    """
    Penalize fried/extruded, palm oil, and flavour enhancer mentions.
    Softer and capped so it doesn't dominate.
    """
    t = (text or "").lower()
    p = 0.0
    if flags.get("fried"):
        p += 5
    if flags.get("extruded"):
        p += 4
    if flags.get("palmOil"):
        p += 4
    if re.search(r"\b(flavo(u)?r\s*enhancer|enhanced with|taste enhancer)\b", t):
        p += 2
    return min(12.0, p)

def _keyword_penalties(ingredients_text: str) -> List[Tuple[str, int]]:
    penalties: List[Tuple[str, int]] = []
    text = (ingredients_text or "").lower()

    if re.search(r"\bpalm(olein| oil)?\b", text):
        penalties.append(("Palm oil", -6))
    if "hydrogenated" in text or "partially hydrogenated" in text:
        penalties.append(("Hydrogenated/partially hydrogenated oils", -20))
    if any(word in text for word in ["sugar", "glucose", "fructose", "hfcs", "corn syrup", "invert syrup", "malt syrup", "dextrose"]):
        penalties.append(("Added sugars/syrups", -8))
    if "salt" in text or "sodium chloride" in text:
        penalties.append(("Added salt", -4))
    if any(word in text for word in ["acesulfame", "sucralose", "aspartame", "saccharin", "cyclamate", "neotame", "advantame"]):
        penalties.append(("Artificial sweeteners", -5))
    if re.search(r"\b(artificial|nature[-\s]*identical)\s+flavo(u)?r", text):
        penalties.append(("Artificial flavour", -5))
    if re.search(r"\b(artificial|synthetic)\s+colou?r\b|caramel colou?r", text):
        penalties.append(("Added colours", -5))
    if re.search(r"\b(fried|deep[-\s]?fried|extruded|puffed)\b", text):
        penalties.append(("Fried/extruded processing", -6))
    if re.search(r"\b(msg|monosodium glutamate)\b", text):
        penalties.append(("MSG", -6))

    return penalties

def compute_health_score(nutrition: Dict[str, Optional[float]],
                         additives: List[Dict[str, str]],
                         ingredients_text: str,
                         beverage: bool) -> int:
    """
    Final 0–100 score (higher is better). Balanced so typical foods land 35–85,
    junky snacks <40, minimally processed >70 when warranted.
    """
    energy_kj = nutrition.get("energy_kj")
    sugar_g = nutrition.get("sugar_g")
    sat_fat_g = nutrition.get("sat_fat_g")
    sodium_mg = nutrition.get("sodium_mg")
    fiber_g = nutrition.get("fiber_g")
    protein_g = nutrition.get("protein_g")
    fruit_pct = nutrition.get("fruit_pct")

    neg = _negative_points(energy_kj, sugar_g, sat_fat_g, sodium_mg, beverage)
    pos = _positive_points(fiber_g, protein_g, fruit_pct)

    # Base + scaling
    s = 78.0 - (neg * 2.0) + (pos * 1.8)

    # Additive + processing penalties (with caps)
    add_pen = _additive_penalties(additives or [])
    proc_pen = _processing_penalty(ingredients_text, {
        "palmOil": bool(re.search(r"\bpalm(olein| oil)?\b", (ingredients_text or "").lower())),
        "fried": bool(re.search(r"\b(fried|deep[-\s]?fried|fried snack)\b", (ingredients_text or "").lower())),
        "extruded": bool(re.search(r"\b(extruded|puffed)\b", (ingredients_text or "").lower())),
    })
    s -= min(28.0, add_pen)   # slightly softer than before
    s -= min(10.0, proc_pen)

    # Keyword penalties (already small, negative numbers)
    for _label, pen in _keyword_penalties(ingredients_text):
        s += pen

    # Trans fat explicit with threshold to avoid label noise
    if (nutrition.get("trans_fat_g") or 0) > 0.1:
        s -= 18

    # ---- Hard caps for red flags (kept, but balanced) ----
    t = (ingredients_text or "").lower()
    additive_codes = { (a.get("code") or "").upper() for a in (additives or []) }

    if any((a.get("risk") or "").lower() == "avoid" for a in (additives or [])):
        s = min(s, 50)  # max C for "avoid" additives
    if any(c in additive_codes for c in {"E249","E250","E251","E252"}):
        s = min(s, 40)  # processed meat nitrites/nitrates
    if any(c in additive_codes for c in {"E102","E110","E129","E124","E122","E104"}):
        s = min(s, 58)  # synthetic colours
    if re.search(r"\b(msg|monosodium glutamate)\b", t) or any(c.replace("INS","").replace("E","")[:3] in MSG_LIKE for c in additive_codes):
        s -= 5
    if re.search(r"\b(palm oil|palmolein)\b", t):
        s = min(s, 62)

    # Sparse-data guardrails: when most nutrition is missing, keep in mid band
    known = [x for x in [energy_kj, sugar_g, sat_fat_g, sodium_mg, fiber_g, protein_g] if x is not None]
    if len(known) <= 1:
        s = max(35, min(65, s))

    return max(0, min(100, int(round(s))))

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

    if nutrition.get("trans_fat_g") and nutrition["trans_fat_g"] and nutrition["trans_fat_g"] > 0.1:
        negatives.append("Contains trans fats (>0.1g/100g)")

    for a in additives or []:
        if (a.get("risk") or "").lower() == "avoid":
            negatives.append(f"Contains {a['name']} ({a['code']})")
    for label, pen in _keyword_penalties(ingredients_text):
        if pen < 0 and label not in negatives:
            negatives.append(label)

    # Deduplicate
    seen_p, seen_n = set(), set()
    pos, neg = [], []
    for x in positives:
        if x not in seen_p:
            pos.append(x); seen_p.add(x)
    for x in negatives:
        if x not in seen_n:
            neg.append(x); seen_n.add(x)

    return pos, neg

def analyze_product(p: Dict[str, Any], barcode: str, debug: bool = False) -> Dict[str, Any]:
    nutr_raw = p.get("nutriments", {}) or {}
    nutrition = coerce_nutrition(nutr_raw)

    ingredients_text = (
        p.get("ingredients_text")
        or p.get("ingredients_text_en")
        or p.get("ingredients_text_fr")
        or ""
    )
    parsed = parse_ingredients(ingredients_text or (p.get("ingredients_text_debug") or ""))

    additives_info = parsed["additives"] if parsed.get("additives") else classify_additives(extract_additives(parsed.get("ingredients_block","")))
    beverage = is_beverage(p)

    score = compute_health_score(nutrition, additives_info, parsed.get("ingredients_block","") or ingredients_text, beverage)
    positives, negatives = summarize_pros_cons(nutrition, additives_info, parsed.get("ingredients_block","") or ingredients_text, beverage)

    traffic = {
        "sugars": traffic_light_sugar(nutrition.get("sugar_g"), beverage),
        "sat_fat": traffic_light_satfat(nutrition.get("sat_fat_g"), beverage),
        "salt": traffic_light_salt_from_sodium(nutrition.get("sodium_mg"), beverage),
    }

    data = {
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

    if debug:
        data["__debug"] = {
            "nutrition": nutrition,
            "additives": additives_info,
            "isBeverage": beverage,
            "ingredients_snippet": (ingredients_text or "")[:400],
        }
    return data

# =========================
# ---- OFF Lookup ---------
# =========================

def _http_get(url: str, timeout: float = 6.0, retries: int = 1) -> Optional[requests.Response]:
    headers = {"User-Agent": "ScoreMyFood/1.0 (+https://example.com)"}
    for attempt in range(retries + 1):
        try:
            r = requests.get(url, timeout=timeout, headers=headers)
            if r.status_code == 200:
                return r
            # Backoff on transient errors
            if r.status_code in (429, 500, 502, 503, 504) and attempt < retries:
                time.sleep(0.4 * (attempt + 1))
                continue
            return None
        except Exception:
            if attempt < retries:
                time.sleep(0.2 * (attempt + 1))
                continue
            return None
    return None

def off_lookup(barcode: str) -> Optional[Dict[str, Any]]:
    url = f"https://world.openfoodfacts.org/api/v2/product/{barcode}.json"
    r = _http_get(url, timeout=7.5, retries=1)
    if not r:
        return None
    try:
        data = r.json()
    except Exception:
        return None
    if data.get("status") != 1 or "product" not in data:
        return None
    return analyze_product(data["product"], barcode)
