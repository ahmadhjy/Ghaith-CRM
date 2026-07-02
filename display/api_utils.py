"""Shared helpers for CRM JSON API endpoints."""

from __future__ import annotations

import json

from django.conf import settings
from django.http import JsonResponse


def check_api_key(request) -> bool:
    configured_key = getattr(settings, "EXTERNAL_API_KEY", None)
    if not configured_key:
        return False
    provided_key = request.headers.get("X-API-Key") or request.META.get("HTTP_X_API_KEY")
    return provided_key == configured_key


def auth_or_401(request):
    if not check_api_key(request):
        return JsonResponse(
            {"error": "Unauthorized", "code": "INVALID_API_KEY"},
            status=401,
        )
    return None


def json_error(message, status=400, code=None, extra=None):
    payload = {"error": message}
    if code:
        payload["code"] = code
    if extra:
        payload["details"] = extra
    return JsonResponse(payload, status=status)


def parse_json_body(request) -> tuple[dict | None, JsonResponse | None]:
    try:
        return json.loads(request.body.decode("utf-8") or "{}"), None
    except json.JSONDecodeError:
        return None, json_error("Invalid JSON body", status=400, code="INVALID_JSON")


def normalize_phone(country_code, mobile_number) -> str:
    mobile_number = (mobile_number or "").strip()
    country_code = (country_code or "").strip()
    if not mobile_number:
        return ""
    if mobile_number.startswith("+"):
        return mobile_number
    if country_code:
        return f"{country_code}{mobile_number}"
    return mobile_number
