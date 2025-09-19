import requests
import re

# Regex to detect additive codes like E621, INS 150d
E_RE = re.compile(r'\b(?:E|INS)\s*[-\s]?(\d{3,4}[a-d]?)\b', re.I)

def extract_additives(text: str):
    """Find additive codes (E numbers / INS codes) in ingredient text"""
    if not text:
        return []
    raw = [m.group(1).upper() for m in E_RE.finditer(text)]
    out = []
    for c in raw:
        out.append(c if c.startswith("E") else f"INS{c}")
    # dedupe keep order
    seen, res = set(), []
    for c in out:
        if c not in seen:
            seen.add(c)
            res.append(c)
    return res


# --- Additives Database (expandable) ---
ADDITIVE_DB = {
    "E621": {"name": "Monosodium glutamate (MSG)", "risk": "avoid"},
    "E627": {"name": "Disodium guanylate", "risk": "moderate"},
    "E631": {"name": "Disodium inosinate", "risk": "moderate"},
    "E110": {"name": "Sunset Yellow FCF", "risk": "avoid"},
    "E102": {"name": "Tartrazine", "risk": "avoid"},
    "E129": {"name": "Allura Red AC", "risk": "avoid"},
    "E150D": {"name": "Caramel color IV", "risk": "moderate"},
    "INS150D": {"name": "Caramel color IV", "risk": "moderate"},
    "E211": {"name": "Sodium benzoate", "risk": "moderate"},
    "E250": {"name": "Sodium nitrite", "risk": "avoid"},
    "E251": {"name": "Sodium nitrate", "risk": "avoid"},
    "E202": {"name": "Potassium sorbate", "risk": "moderate"},
    "E330": {"name": "Citric acid", "risk": "safe"},
    "E331": {"name": "Sodium citrates", "risk": "safe"},
    "E327": {"name": "Calcium lactate", "risk": "safe"},
    "E950": {"name": "Acesulfame K", "risk": "moderate"},
    "E951": {"name": "Aspartame", "risk": "avoid"},
    "E955": {"name": "Sucralose", "risk": "moderate"},
    "E960": {"name": "Steviol glycosides", "risk": "safe"},
}

def classify_additives(codes: list[str]):
    out = []
    for code in codes:
        info = ADDITIVE_DB.get(code.upper(), {"name": "Unknown additive", "risk": "unknown"})
        out.append({
            "code": code.upper(),
            "name": info["name"],
            "risk": info["risk"],
        })
    return out


# --- Keyword penalties (like a nutritionist would) ---
def keyword_penalties(ingredients: str):
    penalties = []
    text = ingredients.lower()

    if "palm oil" in text:
        penalties.append(("Palm oil", -8))
    if "hydrogenated" in text:
        penalties.append(("Hydrogenated/partially hydrogenated oils", -20))
    if any(word in text for word in ["sugar", "glucose", "fructose", "hfcs", "corn syrup"]):
        penalties.append(("Added sugars/syrups", -10))
    if "salt" in text or "sodium chloride" in text:
        penalties.append(("High salt content", -5))
    if any(word in text for word in ["acesulfame", "sucralose", "aspartame"]):
        penalties.append(("Artificial sweeteners", -5))

    return penalties


# --- Scoring logic ---
def compute_score(nutrition: dict, additives: list[str], ingredients_text: str):
    s = 50  # neutral baseline

    try:
        if nutrition.get("sugar_g") is not None:
            s -= float(nutrition["sugar_g"]) * 1.0
        if nutrition.get("sodium_mg") is not None:
            s -= float(nutrition["sodium_mg"]) * 0.005
        if nutrition.get("sat_fat_g") is not None:
            s -= float(nutrition["sat_fat_g"]) * 1.5
        if nutrition.get("trans_fat_g") is not None:
            s -= float(nutrition["trans_fat_g"]) * 15

        if nutrition.get("fiber_g") is not None:
            s += float(nutrition["fiber_g"]) * 2.5
        if nutrition.get("protein_g") is not None:
            s += float(nutrition["protein_g"]) * 1.2
    except Exception:
        pass

    # additive penalties
    for code in additives:
        c = code.replace(" ", "").upper()
        if c in ["E621", "E110", "E102", "E129", "E951"]:
            s -= 18
        elif c in ["INS150D", "E150D", "E211", "E250", "E251"]:
            s -= 8

    # keyword penalties
    for _label, penalty in keyword_penalties(ingredients_text):
        s += penalty

    return max(0, min(100, round(s)))


def analyze_product(p: dict, barcode: str):
    nutr = p.get("nutriments", {}) or {}
    nutrition = {
        "sugar_g": nutr.get("sugars_100g"),
        "sodium_mg": (nutr.get("sodium_100g") or 0) * 1000 if nutr.get("sodium_100g") is not None else None,
        "trans_fat_g": nutr.get("trans_fat_100g"),
        "sat_fat_g": nutr.get("saturated_fat_100g"),
        "fiber_g": nutr.get("fiber_100g"),
        "protein_g": nutr.get("proteins_100g"),
    }

    ingredients_text = (
        p.get("ingredients_text")
        or p.get("ingredients_text_en")
        or p.get("ingredients_text_fr")
        or ""
    )
    additives = extract_additives(ingredients_text)
    additives_info = classify_additives(additives)
    score = compute_score(nutrition, additives, ingredients_text)

    positives, negatives = [], []
    if nutrition.get("fiber_g") and nutrition["fiber_g"] > 3:
        positives.append("High in fiber")
    if nutrition.get("protein_g") and nutrition["protein_g"] > 5:
        positives.append("Good source of protein")
    if nutrition.get("sugar_g") and nutrition["sugar_g"] > 15:
        negatives.append("High in sugar")
    if nutrition.get("sodium_mg") and nutrition["sodium_mg"] > 400:
        negatives.append("High in sodium")
    if nutrition.get("sat_fat_g") and nutrition["sat_fat_g"] > 5:
        negatives.append("High in saturated fat")
    if nutrition.get("trans_fat_g") and nutrition["trans_fat_g"] > 0:
        negatives.append("Contains trans fats")

    for a in additives_info:
        if a["risk"] == "avoid":
            negatives.append(f"Contains {a['name']} ({a['code']})")

    for label, penalty in keyword_penalties(ingredients_text):
        if penalty < 0:
            negatives.append(label)

    return {
        "barcode": barcode,
        "name": p.get("product_name") or "Unknown",
        "brand": (p.get("brands") or "").split(",")[0].strip() or None,
        "score": score,
        "image": p.get("image_front_url") or p.get("image_url"),
        "ingredients_text": ingredients_text,
        "nutrition": nutrition,
        "additives": additives_info,
        "positives": positives,
        "negatives": negatives,
        "source": "openfoodfacts",
    }


def off_lookup(barcode: str):
    url = f"https://world.openfoodfacts.org/api/v2/product/{barcode}.json"
    r = requests.get(url, timeout=8)
    if r.status_code != 200:
        return None
    data = r.json()
    if data.get("status") != 1:
        return None
    return analyze_product(data["product"], barcode)
