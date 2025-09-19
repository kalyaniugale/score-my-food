from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status
from .utils import off_lookup

@api_view(["GET"])
def ping(_request):
    return Response({"app": "score-my-food", "ok": True})

@api_view(["GET"])
def product_lookup(_request, barcode: str):
    data = off_lookup(barcode)
    if not data:
        return Response({"detail": "Not found"}, status=status.HTTP_404_NOT_FOUND)
    return Response(data, status=status.HTTP_200_OK)
