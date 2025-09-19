# backend/core/urls.py
from django.urls import path
from . import views

urlpatterns = [
    path("ping", views.ping),
    path("products/<str:barcode>/", views.product_lookup),
]
