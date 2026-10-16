"""HTTP client for pulling data from Sophia's API.

Sophia asked CRM clients to call with ``requests`` and this User-Agent:

    User-Agent: SofiiaAI-CRM-Sync/1.0 (+https://ucheed.dev)

Configured via settings: SOPHIA_BASE_URL, SOPHIA_API_TOKEN, SOPHIA_HTTP_TIMEOUT.
"""

from __future__ import annotations

import json
import os

import requests
from django.conf import settings

SOPHIA_USER_AGENT = "SofiiaAI-CRM-Sync/1.0 (+https://ucheed.dev)"
_SOFIA_HOST = "sofiiaai-prospect.ucheed.dev"


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


def normalize_sophia_base_url(url: str) -> str:
    """Insert ``/cms`` on the live Sofiia host.

    Their credentials PDF listed ``…/json-api/…``, but the JSON API is actually
    served at ``…/cms/json-api/…``. Without ``/cms``, Cloudflare returns the
    Prospect SPA HTML and the CRM reports invalid JSON.
    """
    url = (url or "").strip().rstrip("/")
    old = f"://{_SOFIA_HOST}/json-api/"
    new = f"://{_SOFIA_HOST}/cms/json-api/"
    if old in url and new not in url:
        url = url.replace(old, new, 1)
    return url


def sophia_config_status() -> dict:
    """Safe diagnostic (no secrets) for why the pull client is/isn't configured."""
    raw = _first_setting("SOPHIA_BASE_URL", "SOPHIIA_BASE_URL")
    base = normalize_sophia_base_url(raw)
    token = _first_setting("SOPHIA_API_TOKEN", "SOPHIIA_API_TOKEN")
    return {
        "settings_module": getattr(settings, "SETTINGS_MODULE", ""),
        "has_SOPHIA_BASE_URL": bool(getattr(settings, "SOPHIA_BASE_URL", "")),
        "has_SOPHIIA_BASE_URL": bool(getattr(settings, "SOPHIIA_BASE_URL", "")),
        "has_SOPHIA_API_TOKEN": bool(getattr(settings, "SOPHIA_API_TOKEN", "")),
        "base_url_length": len(str(base or "")),
        "base_has_cms_prefix": "/cms/json-api/" in str(base or ""),
        "token_length": len(str(token or "")),
        "configured": bool(base and token),
    }


def _unwrap(payload):
    """Sofia's live API wraps resources in ``{success, data: {…}}``."""
    if isinstance(payload, dict) and isinstance(payload.get("data"), dict):
        return payload["data"]
    return payload if isinstance(payload, dict) else {}


class SophiaClient:
    def __init__(self, base_url=None, token=None, timeout=None):
        raw = base_url or _first_setting("SOPHIA_BASE_URL", "SOPHIIA_BASE_URL") or ""
        self.base_url = normalize_sophia_base_url(raw)
        self.token = token or _first_setting("SOPHIA_API_TOKEN", "SOPHIIA_API_TOKEN") or ""
        self.timeout = timeout or int(_first_setting("SOPHIA_HTTP_TIMEOUT", default=30) or 30)

    @property
    def is_configured(self) -> bool:
        return bool(self.base_url and self.token)

    def _headers(self) -> dict:
        return {
            "User-Agent": SOPHIA_USER_AGENT,
            "Accept": "application/json",
            "Authorization": f"Bearer {self.token}",
        }

    def _get(self, path: str, params: dict | None = None) -> dict:
        if not self.is_configured:
            raise SophiaClientError(
                "Sophia client is not configured (set SOPHIA_BASE_URL and SOPHIA_API_TOKEN)."
            )
        url = f"{self.base_url}{path}"
        try:
            resp = requests.get(url, headers=self._headers(), params=params, timeout=self.timeout)
        except requests.RequestException as exc:
            raise SophiaClientError(f"Sophia GET {path} failed: {exc}") from exc

        content_type = resp.headers.get("Content-Type", "")
        body = resp.text or ""
        if resp.status_code >= 400:
            detail = body[:500]
            try:
                parsed = json.loads(body)
                detail = parsed.get("message") or parsed.get("error") or detail
            except json.JSONDecodeError:
                pass
            raise SophiaClientError(f"Sophia GET {path} -> HTTP {resp.status_code}: {detail}")

        snippet = body.lstrip()[:180].replace("\n", " ")
        if "html" in content_type.lower() or snippet.lower().startswith("<!") or "<html" in snippet.lower():
            raise SophiaClientError(
                f"Sophia GET {path} returned HTML ({content_type}): {snippet!r}. "
                "The JSON API is at /cms/json-api/…, not /json-api/…"
            )
        try:
            return json.loads(body or "{}")
        except json.JSONDecodeError as exc:
            kind = "HTML" if snippet.lower().startswith("<!") or "<html" in snippet.lower() else "non-JSON"
            raise SophiaClientError(
                f"Sophia GET {path} returned {kind} ({content_type}): {snippet!r}"
            ) from exc

    def fetch_departments(self) -> list[dict]:
        """GET {base}/departments — agents or departments list."""
        payload = _unwrap(self._get("/departments"))
        return payload.get("departments") or payload.get("agents") or []

    def iter_changed_chats(self, status_changed_since: str, *, max_pages: int = 1000):
        """Yield chat dicts across all pages, newest-changes pagination aware."""
        page = 1
        seen_pages = 0
        while page and seen_pages < max_pages:
            data = self._get(
                "/chats",
                params={
                    "status_changed_since": status_changed_since,
                    "page": page,
                    # Their /chats route 500s on lowercase "asc"; send the documented enum.
                    "order": "DESC",
                },
            )
            payload = _unwrap(data)
            for chat in payload.get("chats") or []:
                yield chat
            page = payload.get("next_page")
            seen_pages += 1
