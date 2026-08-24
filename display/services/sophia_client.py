"""Minimal HTTP client for pulling data from Sophia's API.

Uses the standard library only (``urllib``) so no extra dependency is required on
PythonAnywhere. Configured via settings: SOPHIA_BASE_URL, SOPHIA_API_TOKEN,
SOPHIA_HTTP_TIMEOUT.
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.parse
import urllib.request

from django.conf import settings


class SophiaClientError(Exception):
    """Raised when a call to Sophia fails or returns a non-2xx response."""


def _first_setting(*names, default=""):
    """Return the first non-empty Django setting or environment variable."""
    for name in names:
        value = getattr(settings, name, None)
        if value not in (None, ""):
            return value
        env = os.environ.get(name)
        if env:
            return env
    return default


def sophia_config_status() -> dict:
    """Safe diagnostic (no secrets) for why the pull client is/isn't configured."""
    base = _first_setting("SOPHIA_BASE_URL", "SOPHIIA_BASE_URL")
    token = _first_setting("SOPHIA_API_TOKEN", "SOPHIIA_API_TOKEN")
    return {
        "settings_module": getattr(settings, "SETTINGS_MODULE", ""),
        "has_SOPHIA_BASE_URL": bool(getattr(settings, "SOPHIA_BASE_URL", "")),
        "has_SOPHIIA_BASE_URL": bool(getattr(settings, "SOPHIIA_BASE_URL", "")),
        "has_SOPHIA_API_TOKEN": bool(getattr(settings, "SOPHIA_API_TOKEN", "")),
        "base_url_length": len(str(base or "")),
        "token_length": len(str(token or "")),
        "configured": bool(base and token),
    }


class SophiaClient:
    def __init__(self, base_url=None, token=None, timeout=None):
        self.base_url = (base_url or _first_setting("SOPHIA_BASE_URL", "SOPHIIA_BASE_URL") or "").rstrip("/")
        self.token = token or _first_setting("SOPHIA_API_TOKEN", "SOPHIIA_API_TOKEN") or ""
        self.timeout = timeout or int(_first_setting("SOPHIA_HTTP_TIMEOUT", default=30) or 30)

    @property
    def is_configured(self) -> bool:
        return bool(self.base_url and self.token)

    def _get(self, path: str, params: dict | None = None) -> dict:
        if not self.is_configured:
            raise SophiaClientError(
                "Sophia client is not configured (set SOPHIA_BASE_URL and SOPHIA_API_TOKEN)."
            )
        url = f"{self.base_url}{path}"
        if params:
            url = f"{url}?{urllib.parse.urlencode(params)}"
        req = urllib.request.Request(url, method="GET")
        req.add_header("Authorization", f"Bearer {self.token}")
        req.add_header("Accept", "application/json")
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                body = resp.read().decode("utf-8")
        except urllib.error.HTTPError as exc:
            detail = ""
            try:
                detail = exc.read().decode("utf-8")[:500]
            except Exception:
                pass
            raise SophiaClientError(f"Sophia GET {path} -> HTTP {exc.code}: {detail}") from exc
        except urllib.error.URLError as exc:
            raise SophiaClientError(f"Sophia GET {path} failed: {exc.reason}") from exc
        try:
            return json.loads(body or "{}")
        except json.JSONDecodeError as exc:
            raise SophiaClientError(f"Sophia GET {path} returned invalid JSON") from exc

    def fetch_departments(self) -> list[dict]:
        """GET {base}/departments — returns the raw list (agents or departments).

        Per Sophia's go-live spec the base URL already includes
        ``…/prospect-crm/v1/consumer``, so the path here is just ``/departments``.
        """
        data = self._get("/departments")
        return data.get("departments") or data.get("agents") or []

    def iter_changed_chats(self, status_changed_since: str, *, max_pages: int = 1000):
        """Yield chat dicts across all pages, newest-changes pagination aware."""
        page = 1
        seen_pages = 0
        while page and seen_pages < max_pages:
            data = self._get(
                "/chats",
                params={"status_changed_since": status_changed_since, "page": page},
            )
            for chat in data.get("chats") or []:
                yield chat
            page = data.get("next_page")
            seen_pages += 1
