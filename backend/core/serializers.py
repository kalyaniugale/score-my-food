# backend/api/serializers.py
from rest_framework import serializers

class OCRAnalyzeResponse(serializers.Serializer):
    barcode = serializers.CharField(required=False, allow_blank=True)
    name = serializers.CharField(required=False, allow_blank=True)
    brand = serializers.CharField(required=False, allow_blank=True)
    image = serializers.CharField(required=False, allow_blank=True)
    score = serializers.IntegerField(required=False)
    ingredients_text = serializers.CharField(required=False, allow_blank=True)
    nutrition = serializers.DictField(required=False)
    positives = serializers.ListField(child=serializers.CharField(), required=False)
    negatives = serializers.ListField(child=serializers.CharField(), required=False)
    additives = serializers.ListField(child=serializers.DictField(), required=False)
    source = serializers.CharField(required=False, allow_blank=True)
