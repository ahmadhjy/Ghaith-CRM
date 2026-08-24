"""Runnable Sophia daily pull (used by the management command and the manual trigger)."""

from __future__ import annotations

from datetime import timedelta
from zoneinfo import ZoneInfo

from django.utils import timezone

from display.lead_errors import LeadSyncError
from display.models import Department, SophiaSyncState
from display.services.sophia_client import SophiaClient, SophiaClientError
from display.services.sophia_sync import apply_sophia_chat

BEIRUT = ZoneInfo("Asia/Beirut")
BATCH_HOUR = 7


def last_seven_am_beirut(now=None) -> str:
    """ISO timestamp of the most recent 07:00 Asia/Beirut strictly before ``now``.

    Sync now at 13:25 → today 07:00. The scheduled 07:00 job → yesterday 07:00
    (status_changed_since is exclusive, so "today 07:00" would pull nothing).
    """
    local = timezone.localtime(now or timezone.now(), BEIRUT)
    today_seven = local.replace(hour=BATCH_HOUR, minute=0, second=0, microsecond=0)
    cutoff = today_seven if local > today_seven else today_seven - timedelta(days=1)
    return cutoff.isoformat()


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


def run_sophia_pull(*, since: str | None = None, dry_run: bool = False, assigned_agent: str | None = None) -> dict:
    """Pull changed chats from Sophia. Returns a JSON-serializable result dict.

    ``assigned_agent`` (optional): only apply chats for that Sophia agent id.
    Filtered / dry-run pulls do not advance the watermark, so a later full
    sync still picks up the other agents.
    """
    state = SophiaSyncState.load()
    client = SophiaClient()
    warnings: list[str] = []
    agent_filter = (assigned_agent or "").strip()

    if not client.is_configured:
        from display.services.sophia_client import sophia_config_status

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
            "debug": sophia_config_status(),
        }

    run_start = timezone.now()
    if not since:
        # Never backfill history. First run (and any run with no watermark) only
        # pulls chats whose status changed since the last 07:00 Asia/Beirut.
        # After a successful pull, last_pull_at is the watermark so we do not
        # re-fetch chats already applied.
        if state.last_pull_at:
            since = state.last_pull_at.isoformat()
        else:
            since = last_seven_am_beirut(run_start)

    try:
        _sync_departments(client)
    except SophiaClientError as exc:
        warnings.append(f"Department pull skipped: {exc}")

    created = updated = skipped = filtered = errors = 0
    error_details: list[str] = []
    try:
        for chat in client.iter_changed_chats(since):
            try:
                if agent_filter:
                    chat_agent = str(chat.get("assigned_agent") or "").strip()
                    if chat_agent != agent_filter:
                        filtered += 1
                        continue
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

    summary = (
        f"created={created} updated={updated} skipped={skipped} "
        f"filtered={filtered} errors={errors}"
    )
    # Do not move the watermark on a dry-run or an agent-scoped test pull.
    # Other agents in the same window must still be eligible for the next full sync.
    if not dry_run and not agent_filter:
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
        "assigned_agent": agent_filter or None,
        "since": since,
        "created": created,
        "updated": updated,
        "skipped": skipped,
        "filtered": filtered,
        "errors": errors,
        "error_details": error_details,
        "warnings": warnings,
        "summary": summary,
    }
