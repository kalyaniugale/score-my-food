# backend/core/views.py
import os
from PIL import Image

from rest_framework.decorators import api_view, parser_classes
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework.response import Response
from rest_framework import status

# ----- Try robust local OCR if you added it; fallback to raw pytesseract -----
try:
    # recommended: ROI crop + cleaning + beverage heuristic
    from core.ocr import extract_ingredients as local_extract, looks_like_beverage
except Exception:
    local_extract = None
    looks_like_beverage = None

# optional: UI prettifier; if missing, we still return the core fields
try:
    from core.present import build_ui_block
except Exception:
    build_ui_block = None

# raw pytesseract fallback
import pytesseract

from core.utils import (
    parse_ingredients,
    off_lookup,
    compute_health_score,
    summarize_pros_cons,
    grade_from_score,
)

# -------- utilities -----------------------------------------------------------

MAX_DIMENSION = int(os.getenv("OCR_MAX_DIMENSION", "2200"))  # keep images reasonable

def _empty_nutrition():
    return {
        "energy_kj": None,
        "sugar_g": None,
        "sodium_mg": None,
        "sat_fat_g": None,
        "trans_fat_g": None,
        "fiber_g": None,
        "protein_g": None,
        "fruit_pct": None,
    }

def _downscale_if_huge(img: Image.Image) -> Image.Image:
    """Prevent huge uploads from causing timeouts/memory spikes."""
    w, h = img.size
    m = max(w, h)
    if m <= MAX_DIMENSION:
        return img
    scale = MAX_DIMENSION / float(m)
    new_size = (int(w * scale), int(h * scale))
    return img.resize(new_size, Image.BICUBIC)

def _local_ocr_pipeline(img: Image.Image):
    """
    Try robust local_extract -> pytesseract, never raises.
    Returns (ingredients_text:str, beverage:bool, diagnostics:dict)
    """
    text, diag = "", {"used_local_extract": False, "avg_conf": None}
    # 1) robust helper if you added core/ocr.py
    if local_extract is not None:
        try:
            text, diag_local = local_extract(img)  # may return (text, diag)
            diag.update({"used_local_extract": True, **(diag_local or {})})
        except Exception:
            pass

    # 2) fallback to raw pytesseract if needed
    if not text:
        try:
            text = pytesseract.image_to_string(img) or ""
            text = (text or "").strip()
        except Exception as e:
            # don't raise; return empty and let downstream handle
            diag["pytesseract_error"] = str(e)
            text = ""

    # beverage heuristic if available
    if looks_like_beverage is not None:
        beverage = looks_like_beverage(None, None, text)
    else:
        beverage = False

    return text, beverage, diag

# -------- views ---------------------------------------------------------------

@api_view(["POST"])
@parser_classes([MultiPartParser, FormParser])
def ocr_analyze(request):
    """
    POST /api/ocr/analyze/
    form-data: image=<file>  (also accepts 'file' as alias)
    Fully local OCR (no network). Returns product-like JSON.
    """
    file = request.FILES.get("image") or request.FILES.get("file")
    if not file:
        return Response({"detail": "image is required (form field 'image')"}, status=status.HTTP_400_BAD_REQUEST)

    try:
        img = Image.open(file).convert("RGB")
        img = _downscale_if_huge(img)
    except Exception as e:
        return Response({"detail": f"invalid image: {e}"}, status=status.HTTP_400_BAD_REQUEST)

    # Local OCR only (no network)
    ingredients_text, beverage, diag = _local_ocr_pipeline(img)

    # Parse + score (nutrition stays empty unless you populate it elsewhere)
    parsed = parse_ingredients(ingredients_text or "")
    additives_info = parsed.get("additives", [])
    nutrition = _empty_nutrition()

    score = compute_health_score(nutrition, additives_info, ingredients_text, beverage)
    positives, negatives = summarize_pros_cons(nutrition, additives_info, ingredients_text, beverage)

    # Optional UI block for nicer rendering
    ui = None
    if build_ui_block is not None:
        try:
            ui = build_ui_block(
                ingredients_text=ingredients_text or "",
                allergens_from_parser=parsed.get("allergens", []),
                additives_info=additives_info,
                nutrition=nutrition,
                beverage=beverage,
            )
        except Exception:
            ui = None  # never block response on formatting

    data = {
        "barcode": "",
        "name": "Ingredients scan",
        "brand": None,
        "image": None,
        "score": score,
        "grade": grade_from_score(score),
        "ingredients_text": ingredients_text,
        "structured_ingredients": parsed.get("ingredients", []),
        "allergens": parsed.get("allergens", []),
        "nutrition": nutrition,
        "positives": positives,
        "negatives": negatives,
        "additives": additives_info,
        "source": "ocr-local",
        "diagnostics": {"ocr": diag},  # keep while debugging
    }
    if ui is not None:
        data["ui"] = ui

    return Response(data, status=status.HTTP_200_OK)

@api_view(["GET"])
def ping(_request):
    return Response({"app": "score-my-food", "ok": True})

@api_view(["GET"])
def product_lookup(_request, barcode: str):
    """
    GET /api/product/<barcode>/
    Looks up OFF and returns standardized analysis.
    """
    data = off_lookup(barcode)
    if not data:
        return Response({"detail": "Not found"}, status=status.HTTP_404_NOT_FOUND)
    return Response(data, status=status.HTTP_200_OK)

@api_view(["POST"])
def ocr_analyze_text(request):
    """
    POST /api/ocr/analyze-text/
    JSON: { "ingredients_text": "..." , optional "name", "brand" }
    """
    ingredients_text = (request.data.get("ingredients_text") or "").strip()
    if not ingredients_text:
        return Response({"detail": "ingredients_text is required"}, status=status.HTTP_400_BAD_REQUEST)

    name = request.data.get("name") or "Ingredients scan"
    brand = request.data.get("brand") or None

    # beverage guess if helper exists; else solid
    if looks_like_beverage is not None:
        beverage = looks_like_beverage(name, brand, ingredients_text)
    else:
        beverage = False

    parsed = parse_ingredients(ingredients_text)
    additives_info = parsed.get("additives", [])
    nutrition = _empty_nutrition()

    score = compute_health_score(nutrition, additives_info, ingredients_text, beverage)
    positives, negatives = summarize_pros_cons(nutrition, additives_info, ingredients_text, beverage)

    ui = None
    if build_ui_block is not None:
        try:
            ui = build_ui_block(
                ingredients_text=ingredients_text,
                allergens_from_parser=parsed.get("allergens", []),
                additives_info=additives_info,
                nutrition=nutrition,
                beverage=beverage,
            )
        except Exception:
            ui = None

    data = {
        "barcode": "",
        "name": name,
        "brand": brand,
        "image": None,
        "score": score,
        "grade": grade_from_score(score),
        "ingredients_text": ingredients_text,
        "structured_ingredients": parsed.get("ingredients", []),
        "allergens": parsed.get("allergens", []),
        "nutrition": nutrition,
        "positives": positives,
        "negatives": negatives,
        "additives": additives_info,
        "source": "ocr-text",
    }
    if ui is not None:
        data["ui"] = ui

    return Response(data, status=status.HTTP_200_OK)
