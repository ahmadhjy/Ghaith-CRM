"""Apply Sophia WhatsApp chat payloads to CRM leads.

This implements the agreed hybrid sync (see docs/WHATSAPP_SOPHIA_SYNC_API.md):

* Daily 07:00 batch pull calls :func:`apply_sophia_chat` for every changed chat.
* The real-time Sold webhook calls the same function for a single chat.

Assignment logic (confirmed with Sophia): a chat carries ``assigned_agent`` — the
stable Sophia agent id (the same id returned by Sophia's /departments). We map it
to a CRM user via ``CrmUserProfile.sophia_agent_id`` and take the lead's department
from that user's profile. If no agent is given (or it is unknown) we fall back to
the payload ``department`` and the existing auto-assignment.
"""

from __future__ import annotations

from django.utils import timezone

from display.constants import SOPHIA_STATUS_MAP
from display.destinations import ensure_crm_destination
from display.lead_errors import LeadSyncError
from display.models import CrmUserProfile, Department, Lead
from display.services.lead_assignment import assign_user_for_department
from display.services.lead_sync import (
    _parse_api_datetime,
    _sync_summary_fields,
    parse_lead_name,
    parse_phone_fields,
    resolve_department,
)


def _resolve_sophia_status(value):
    key = (value or "").strip().lower()
    if key not in SOPHIA_STATUS_MAP:
        raise LeadSyncError(
            f"Invalid status '{value}'. Allowed: {', '.join(sorted(SOPHIA_STATUS_MAP))}",
            code="INVALID_STATUS",
        )
    return SOPHIA_STATUS_MAP[key]


def _resolve_agent(agent_id):
    """Return (user, profile) for a Sophia agent id, or (None, None)."""
    agent_id = (str(agent_id).strip() if agent_id is not None else "")
    if not agent_id:
        return None, None
    profile = (
        CrmUserProfile.objects.select_related("user", "department")
        .filter(sophia_agent_id=agent_id, user__is_active=True)
        .first()
    )
    if profile:
        return profile.user, profile
    return None, None


def _find_lead(external_id, phone):
    if external_id:
        lead = Lead.objects.filter(external_id=external_id).first()
        if lead:
            return lead
    if phone:
        return Lead.objects.filter(phone=phone).order_by("-created_at").first()
    return None


def apply_sophia_chat(chat: dict, *, source: str = "pull") -> dict:
    """Create/update a lead from a Sophia chat payload.

    Returns a dict: {"lead": Lead|None, "created": bool, "applied": bool,
    "skipped_reason": str|None}. Raises :class:`LeadSyncError` on invalid input.
    """
    if not isinstance(chat, dict):
        raise LeadSyncError("Chat payload must be an object", code="INVALID_JSON")

    internal_status, sold, lost = _resolve_sophia_status(chat.get("status"))

    changed_at = _parse_api_datetime(chat.get("status_changed_at"))
    if not changed_at:
        raise LeadSyncError(
            "status_changed_at is required and must be ISO 8601 with an offset",
            code="INVALID_DATE",
        )

    external_id = (chat.get("external_id") or "").strip()
    country_code, phone = parse_phone_fields(chat)
    name = parse_lead_name(chat)

    lead = _find_lead(external_id, phone)
    is_create = lead is None

    # Idempotency: skip if we've already applied this (or a newer) change.
    if not is_create and lead.last_sync_at and changed_at <= lead.last_sync_at:
        return {"lead": lead, "created": False, "applied": False, "skipped_reason": "not_newer"}

    # Resolve assignment + department.
    agent_user, agent_profile = _resolve_agent(chat.get("assigned_agent"))
    department = None
    if agent_profile and agent_profile.department_id:
        department = agent_profile.department
    if department is None:
        department = resolve_department(chat.get("department"))

    assigned_user = agent_user
    if assigned_user is None:
        assigned_user = assign_user_for_department(department)

    if is_create:
        if not name:
            raise LeadSyncError("name is required on create", code="MISSING_FIELDS")
        if not phone:
            raise LeadSyncError("phone is required on create", code="MISSING_FIELDS")
        if department is None:
            raise LeadSyncError(
                "department could not be resolved (unknown agent and unknown department)",
                code="INVALID_DEPARTMENT",
                details={
                    "assigned_agent": chat.get("assigned_agent"),
                    "department": chat.get("department"),
                },
            )
        if assigned_user is None:
            raise LeadSyncError("No active CRM user available for assignment", code="NO_USER")
        lead = Lead(
            name=name,
            country_code=country_code or "+961",
            phone=phone,
            channel="Whatsapp",
            takeover=True,
            status="onhold",
        )

    # --- apply fields ---
    if name:
        lead.name = name
    if phone:
        lead.country_code = country_code or lead.country_code
        lead.phone = phone
    if external_id and not lead.external_id:
        lead.external_id = external_id
    if department is not None:
        lead.department = department
    if assigned_user is not None:
        lead.assigned_to = assigned_user

    if chat.get("email") is not None:
        lead.email = (chat.get("email") or None) or None
    if chat.get("destination") is not None:
        dest = (chat.get("destination") or "").strip()
        lead.destination = dest
        if dest:
            ensure_crm_destination(dest)
    if chat.get("chat_summary") is not None:
        _sync_summary_fields(lead, chat.get("chat_summary") or "")
    if chat.get("last_customer_message_at") is not None:
        lead.last_customer_message_at = _parse_api_datetime(chat.get("last_customer_message_at"))
    if chat.get("last_agent_action_at") is not None:
        lead.last_agent_action_at = _parse_api_datetime(chat.get("last_agent_action_at"))

    lead.status = internal_status
    lead.sold = sold
    lead.lost = lost
    lead.status_changed_at = changed_at
    lead.last_sync_at = changed_at

    if is_create and sold:
        # Lead.save() creates the order (LeadTask) when sold=True by querying
        # LeadTask.objects.filter(lead=self), which requires a saved lead. Persist
        # the base row first, then flip to sold so the order is created cleanly.
        lead.sold = False
        lead.save()
        lead.sold = True

    lead.save()
    return {"lead": lead, "created": is_create, "applied": True, "skipped_reason": None}
