"""One fail-closed switch for all external WhatsApp dashboard lead writes."""

from django.conf import settings

from display.lead_errors import LeadSyncError


PAUSED_CODE = "SOPHIA_SYNC_PAUSED"
PAUSED_MESSAGE = (
    "Sophia WhatsApp synchronization is paused. No leads or orders were changed."
)


def sophia_sync_enabled() -> bool:
    # Production preserves its settings.py during deployment. Missing settings
    # MUST therefore mean paused, not enabled.
    value = getattr(settings, "SOPHIA_SYNC_ENABLED", False)
    return value is True or (
        isinstance(value, str) and value.strip().lower() in {"true", "1", "yes", "on"}
    )


def paused_result() -> dict:
    return {
        "ok": False,
        "paused": True,
        "code": PAUSED_CODE,
        "error": PAUSED_MESSAGE,
        "summary": PAUSED_MESSAGE,
    }


def require_sophia_sync_enabled() -> None:
    if not sophia_sync_enabled():
        raise LeadSyncError(PAUSED_MESSAGE, code=PAUSED_CODE)
