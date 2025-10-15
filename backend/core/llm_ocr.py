# core/llm_ocr.py
import os, io, base64, json, math
from typing import Dict, Tuple, Optional, Any
from PIL import Image

USE_MODEL = os.getenv("GEMINI_MODEL", "gemini-1.5-flash")

PROMPT = """You read a photo of a packaged food label.
Return ONLY JSON matching this schema (no extra text):

{
  "name": "string | null",
  "brand": "string | null",
  "beverage": true/false,
  "ingredients_text": "clean, comma-separated; exclude nutrition table/addresses",
  "nutrition": {
    "basis": "per_100g" | "per_100ml" | "per_serving" | "unknown",
    "serving_size": {"value": number | null, "unit": "g|ml|oz|unknown"},
    "energy": {"value": number | null, "unit": "kJ|kcal|unknown"},
    "sugars": {"value": number | null, "unit": "g|mg|unknown"},
    "sodium": {"value": number | null, "unit": "mg|g|unknown"},
    "saturated_fat": {"value": number | null, "unit": "g|mg|unknown"},
    "trans_fat": {"value": number | null, "unit": "g|mg|unknown"},
    "fiber": {"value": number | null, "unit": "g|mg|unknown"},
    "protein": {"value": number | null, "unit": "g|mg|unknown"},
    "fruit_pct": {"value": number | null, "unit": "percent"}
  },
  "notes": "short diagnostics"
}

Rules:
- Prefer the column that is per 100 g/ml. If only per-serving is present, set basis="per_serving".
- Fill null if a value is not visible.
- Use numbers only in value (no unit symbols).
- 'fruit_pct' is the % fruit/veg/pulse content if explicitly stated (else null).
- beverage=true for drinks (water, soda, juice, tea, coffee, milk, smoothies, etc.).
- Ingredients: normalize punctuation, keep commas between items, drop nutrition table and addresses.
"""

def _pil_to_b64_jpeg(img: Image.Image, quality: int = 90) -> str:
    buf = io.BytesIO()
    img.convert("RGB").save(buf, format="JPEG", quality=quality, optimize=True)
    return base64.b64encode(buf.getvalue()).decode("ascii")

def _parse_num(x: Any) -> Optional[float]:
    try:
        if x is None:
            return None
        s = str(x).strip().replace(",", ".")
        return float(s)
    except Exception:
        return None

def _to_mg(value: Optional[float], unit: Optional[str]) -> Optional[float]:
    if value is None or not unit:
        return None
    u = unit.lower()
    if u == "mg":
        return value
    if u == "g":
        return value * 1000.0
    return None

def _to_g(value: Optional[float], unit: Optional[str]) -> Optional[float]:
    if value is None or not unit:
        return None
    u = unit.lower()
    if u == "g":
        return value
    if u == "mg":
        return value / 1000.0
    return None

def _energy_to_kj(value: Optional[float], unit: Optional[str]) -> Optional[float]:
    if value is None or not unit:
        return None
    u = unit.lower()
    if u == "kj":
        return value
    if u == "kcal":
        return value * 4.184
    return None

def _normalize_nutrition(block: Dict[str, Any]) -> Dict[str, Optional[float]]:
    """
    Convert the model's raw nutrition into your exact schema, per 100g/ml when possible.
    If basis is per_serving and serving size is known, we approximate per 100.
    """
    basis = (block.get("basis") or "unknown").lower()
    serving = block.get("serving_size") or {}
    sv, su = _parse_num(serving.get("value")), (serving.get("unit") or "").lower()

    # Helpers to scale to per 100 g/ml if needed
    def scale_to_100(v: Optional[float]) -> Optional[float]:
        if v is None:
            return None
        if basis in ("per_100g", "per_100ml"):
            return v
        if basis == "per_serving" and sv and su in ("g", "ml") and sv > 0:
            return v * (100.0 / sv)
        # unknown: just return as-is
        return v

    energy_kj = _energy_to_kj(_parse_num((block.get("energy") or {}).get("value")),
                              (block.get("energy") or {}).get("unit"))

    sugars_g = _to_g(_parse_num((block.get("sugars") or {}).get("value")),
                     (block.get("sugars") or {}).get("unit"))
    sodium_mg = _to_mg(_parse_num((block.get("sodium") or {}).get("value")),
                       (block.get("sodium") or {}).get("unit"))
    sat_fat_g = _to_g(_parse_num((block.get("saturated_fat") or {}).get("value")),
                      (block.get("saturated_fat") or {}).get("unit"))
    trans_fat_g = _to_g(_parse_num((block.get("trans_fat") or {}).get("value")),
                        (block.get("trans_fat") or {}).get("unit"))
    fiber_g = _to_g(_parse_num((block.get("fiber") or {}).get("value")),
                    (block.get("fiber") or {}).get("unit"))
    protein_g = _to_g(_parse_num((block.get("protein") or {}).get("value")),
                      (block.get("protein") or {}).get("unit"))
    fruit_pct = _parse_num((block.get("fruit_pct") or {}).get("value"))

    # Scale to per 100 if we can
    energy_kj = scale_to_100(energy_kj)
    sugars_g = scale_to_100(sugars_g)
    sodium_mg = scale_to_100(sodium_mg)
    sat_fat_g = scale_to_100(sat_fat_g)
    trans_fat_g = scale_to_100(trans_fat_g)
    fiber_g = scale_to_100(fiber_g)
    protein_g = scale_to_100(protein_g)

    return {
        "energy_kj": energy_kj,
        "sugar_g": sugars_g,
        "sodium_mg": sodium_mg,
        "sat_fat_g": sat_fat_g,
        "trans_fat_g": trans_fat_g,
        "fiber_g": fiber_g,
        "protein_g": protein_g,
        "fruit_pct": fruit_pct,
    }

def gemini_extract_label(img: Image.Image) -> Tuple[Optional[Dict[str, Any]], Dict[str, Any]]:
    """
    Returns (payload, diagnostics). payload keys:
      - name, brand, beverage, ingredients_text, nutrition (normalized)
    """
    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        return None, {"ok": False, "reason": "NO_API_KEY"}

    try:
        import google.generativeai as genai
    except Exception as e:
        return None, {"ok": False, "reason": f"SDK_IMPORT_FAIL: {e}"}

    genai.configure(api_key=api_key)
    model = genai.GenerativeModel(USE_MODEL)

    parts = [
        {"text": PROMPT},
        {
            "inline_data": {
                "mime_type": "image/jpeg",
                "data": _pil_to_b64_jpeg(img),
            }
        },
    ]

    try:
        resp = model.generate_content(
            parts,
            safety_settings=None,
            generation_config={
                "temperature": 0.0,
                "max_output_tokens": 1024,
                "response_mime_type": "application/json",
            },
        )
        raw = resp.text or ""
        data = json.loads(raw)
    except Exception as e:
        return None, {"ok": False, "reason": f"API_ERROR_OR_BAD_JSON: {e}"}

    # Normalize to your exact schema
    result = {
        "name": (data.get("name") or None),
        "brand": (data.get("brand") or None),
        "beverage": bool(data.get("beverage", False)),
        "ingredients_text": (data.get("ingredients_text") or "").strip(),
        "nutrition": _normalize_nutrition(data.get("nutrition") or {}),
        "notes": data.get("notes"),
        "model": USE_MODEL,
    }
    return result, {"ok": True, "model": USE_MODEL}
