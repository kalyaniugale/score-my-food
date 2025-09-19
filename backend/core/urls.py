from django.urls import path
from . import views

urlpatterns = [
    path("ping", views.ping),
    path("products/<str:barcode>/", views.product_lookup),
    path("ocr/analyze-text/", views.ocr_analyze_text),
    path("ocr/analyze/", views.ocr_analyze),
   
]
