# core/views.py
from PIL import Image
import pytesseract

from rest_framework.decorators import api_view, parser_classes
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework.response import Response
from rest_framework import status

from .utils import off_lookup, extract_additives, classify_additives, keyword_penalties, compute_score

# If you created OCRAnalyzeResponse you can import & use it.
# Otherwise we simply return the dict (simpler and avoids validation 400s).
# from .serializers import OCRAnalyzeResponse


@api_view(["POST"])
@parser_classes([MultiPartParser, FormParser])
def ocr_analyze(request):
    """
    POST /api/ocr/analyze/
    form-data: image=<file>  (also accepts 'file' as alias)
    Returns a "product-like" JSON so the mobile app can reuse ProductDetail.
    """
    # 1) get file (support both 'image' and 'file')
    file = request.FILES.get("image") or request.FILES.get("file")
    if not file:
        return Response({"detail": "image is required (form field 'image')"}, status=status.HTTP_400_BAD_REQUEST)

    # 2) open image
    try:
        img = Image.open(file).convert("RGB")
    except Exception as e:
        return Response({"detail": f"invalid image: {e}"}, status=status.HTTP_400_BAD_REQUEST)

    # 3) OCR
    try:
        text = pytesseract.image_to_string(img) or ""
    except Exception as e:
        return Response({"detail": f"OCR failed: {e}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    ingredients_text = text.strip()

    # 4) analyze using existing utils (no nutrition from OCR)
    additives_codes = extract_additives(ingredients_text)
    additives_info = classify_additives(additives_codes)
    nutrition = {}
    score = compute_score(nutrition, additives_codes, ingredients_text)

    positives = []
    negatives = [label for (label, penalty) in keyword_penalties(ingredients_text) if penalty < 0]
    negatives += [f"Contains {a['name']} ({a['code']})" for a in additives_info if a.get("risk") == "avoid"]

    data = {
        "barcode": "",                 # unknown in OCR-only
        "name": "Ingredients scan",
        "brand": None,
        "image": None,
        "score": score,
        "ingredients_text": ingredients_text,
        "nutrition": nutrition,
        "positives": positives,
        "negatives": negatives,
        "additives": additives_info,
        "source": "ocr",
    }

    # If you prefer serializer validation, uncomment:
    # s = OCRAnalyzeResponse(data=data)
    # s.is_valid(raise_exception=True)
    # return Response(s.data, status=status.HTTP_200_OK)

    return Response(data, status=status.HTTP_200_OK)


@api_view(["GET"])
def ping(_request):
    return Response({"app": "score-my-food", "ok": True})


@api_view(["GET"])
def product_lookup(_request, barcode: str):
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

    additives_codes = extract_additives(ingredients_text)
    additives_info = classify_additives(additives_codes)
    nutrition = {}
    score = compute_score(nutrition, additives_codes, ingredients_text)

    positives = []
    negatives = [label for (label, penalty) in keyword_penalties(ingredients_text) if penalty < 0]
    negatives += [f"Contains {a['name']} ({a['code']})" for a in additives_info if a.get("risk") == "avoid"]

    data = {
        "barcode": "",
        "name": name,
        "brand": brand,
        "image": None,
        "score": score,
        "ingredients_text": ingredients_text,
        "nutrition": nutrition,
        "positives": positives,
        "negatives": negatives,
        "additives": additives_info,
        "source": "ocr-text",
    }
    return Response(data, status=status.HTTP_200_OK)
