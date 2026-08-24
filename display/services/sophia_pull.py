"""Runnable Sophia daily pull (used by the management command and the manual trigger)."""

from __future__ import annotations

from django.conf import settings
from django.utils import timezone

from display.lead_errors import LeadSyncError
from display.models import Department, SophiaSyncState
from display.services.sophia_client import SophiaClient, SophiaClientError
from display.services.sophia_sync import apply_sophia_chat


def _sync_departments(client: SophiaClient) -> int:
    items = client.fetch_departments()
    dept_upserts = 0
    for item in items:
        if not isinstance(item, dict):
            continue
        if item.get("full_name") or item.get("email") or item.get("phone_number"):
            continue
        code = (item.get("id") or item.get("code") or "").strip()
        name = (item.get("name") or "").strip()
        if not code or not name:
            continue
        Department.objects.update_or_create(
            code=code,
            defaults={"name": name, "is_active": bool(item.get("is_active", True))},
        )
        dept_upserts += 1
    return dept_upserts


def run_sophia_pull(*, since: str | None = None, dry_run: bool = False) -> dict:
    """Pull changed chats from Sophia. Returns a JSON-serializable result dict."""
    state = SophiaSyncState.load()
    client = SophiaClient()
    warnings: list[str] = []

    if not client.is_configured:
        msg = "Sophia client not configured (set SOPHIA_BASE_URL and SOPHIA_API_TOKEN)."
        state.last_run_at = timezone.now()
        state.last_status = "error"
        state.last_message = msg
        state.save(update_fields=["last_run_at", "last_status", "last_message"])
        return {
            "ok": False,
            "configured": False,
            "error": msg,
            "code": "NOT_CONFIGURED",
        }

    run_start = timezone.now()
    if not since:
        if state.last_pull_at:
            since = state.last_pull_at.isoformat()
        else:
            since = getattr(settings, "SOPHIA_BACKFILL_SINCE", "2025-01-01T00:00:00+03:00")

    try:
        _sync_departments(client)
    except SophiaClientError as exc:
        warnings.append(f"Department pull skipped: {exc}")

    created = updated = skipped = errors = 0
    error_details: list[str] = []
    try:
        for chat in client.iter_changed_chats(since):
            try:
                if dry_run:
                    continue
                result = apply_sophia_chat(chat, source="pull")
                if not result["applied"]:
                    skipped += 1
                elif result["created"]:
                    created += 1
                else:
                    updated += 1
            except LeadSyncError as exc:
                errors += 1
                error_details.append(
                    f"{chat.get('external_id') or chat.get('phone')}: {exc.code}: {exc.message}"
                )
    except SophiaClientError as exc:
        state.last_run_at = timezone.now()
        state.last_status = "error"
        state.last_message = str(exc)
        state.save(update_fields=["last_run_at", "last_status", "last_message"])
        return {
            "ok": False,
            "configured": True,
            "error": str(exc),
            "code": "SOPHIA_PULL_FAILED",
            "since": since,
            "warnings": warnings,
        }

    summary = f"created={created} updated={updated} skipped={skipped} errors={errors}"
    if not dry_run:
        state.last_pull_at = run_start
        state.last_run_at = timezone.now()
        state.last_status = "ok" if errors == 0 else "partial"
        state.last_message = summary
        state.save(
            update_fields=["last_pull_at", "last_run_at", "last_status", "last_message"]
        )

    return {
        "ok": errors == 0,
        "configured": True,
        "dry_run": dry_run,
        "since": since,
        "created": created,
        "updated": updated,
        "skipped": skipped,
        "errors": errors,
        "error_details": error_details,
        "warnings": warnings,
        "summary": summary,
    }
