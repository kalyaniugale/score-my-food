# backend/core/views.py
from PIL import Image
import pytesseract

from rest_framework.decorators import api_view, parser_classes
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework.response import Response
from rest_framework import status

from core.utils import (
    parse_ingredients,
    off_lookup,
    compute_health_score,
    summarize_pros_cons,
    grade_from_score,
)

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

@api_view(["POST"])
@parser_classes([MultiPartParser, FormParser])
def ocr_analyze(request):
    """
    POST /api/ocr/analyze/
    form-data: image=<file>  (also accepts 'file' as alias)
    Returns a "product-like" JSON so the mobile app can reuse ProductDetail.
    """
    file = request.FILES.get("image") or request.FILES.get("file")
    if not file:
        return Response({"detail": "image is required (form field 'image')"}, status=status.HTTP_400_BAD_REQUEST)

    try:
        img = Image.open(file).convert("RGB")
    except Exception as e:
        return Response({"detail": f"invalid image: {e}"}, status=status.HTTP_400_BAD_REQUEST)

    try:
        text = pytesseract.image_to_string(img) or ""
    except Exception as e:
        return Response({"detail": f"OCR failed: {e}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    ingredients_text = text.strip()

    # Parse + score (OCR-only → we can't reliably tell beverage; assume solid)
    parsed = parse_ingredients(ingredients_text)
    additives_info = parsed.get("additives", [])
    nutrition = _empty_nutrition()
    beverage = False

    score = compute_health_score(nutrition, additives_info, ingredients_text, beverage)
    positives, negatives = summarize_pros_cons(nutrition, additives_info, ingredients_text, beverage)

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
        "source": "ocr",
    }
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

    parsed = parse_ingredients(ingredients_text)
    additives_info = parsed.get("additives", [])
    nutrition = _empty_nutrition()
    beverage = False

    score = compute_health_score(nutrition, additives_info, ingredients_text, beverage)
    positives, negatives = summarize_pros_cons(nutrition, additives_info, ingredients_text, beverage)

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
    return Response(data, status=status.HTTP_200_OK)
