"""Create and update Lead rows from the WhatsApp AI dashboard API."""

from __future__ import annotations

from datetime import datetime

from django.contrib.auth.models import User
from django.utils import timezone
from django.utils.dateparse import parse_datetime

from display.api_utils import normalize_phone
from display.constants import DEPARTMENT_ALIASES, LEAD_STATUS_API_VALUES
from display.destinations import ensure_crm_destination
from display.lead_errors import LeadSyncError
from display.models import Department, Lead
from display.services.lead_assignment import assign_user_for_department
from display.services.lead_close_deal import apply_close_deal, resolve_close_outcome
from display.services.lead_qualification import (
    apply_qualification_action,
    apply_qualification_fields,
    resolve_qualification_action,
)


def _parse_api_datetime(value) -> datetime | None:
    if value in (None, ""):
        return None
    if isinstance(value, datetime):
        dt = value
    else:
        dt = parse_datetime(str(value).strip())
    if not dt:
        return None
    if timezone.is_naive(dt):
        return timezone.make_aware(dt, timezone.get_current_timezone())
    return dt


def _chat_label_from_payload(data: dict) -> str | None:
    label = (data.get("chat_label") or "").strip()
    if label:
        return label
    received = (data.get("whatsapp_received_on") or "").strip()
    if received.lower() in {"alaa", "fouad"}:
        return received
    return None


def _sync_summary_fields(lead: Lead, text: str) -> None:
    cleaned = (text or "").strip()
    lead.chat_summary = cleaned
    lead.reason_of_travel = cleaned
    lead.finalization_notes = cleaned


def resolve_department(value: str | None) -> Department | None:
    raw = (value or "").strip()
    if not raw:
        return None
    code = DEPARTMENT_ALIASES.get(raw.lower())
    if code:
        dept = Department.objects.filter(code=code, is_active=True).first()
        if dept:
            return dept
    return Department.objects.filter(name__iexact=raw, is_active=True).first()


def parse_lead_name(data: dict) -> str:
    name = (data.get("name") or "").strip()
    if name:
        return name
    first_name = (data.get("first_name") or "").strip()
    last_name = (data.get("last_name") or "").strip()
    combined = f"{first_name} {last_name}".strip()
    if combined:
        return combined
    return ""


def parse_phone_fields(data: dict) -> tuple[str, str]:
    phone = (data.get("phone") or "").strip()
    country_code = (data.get("country_code") or "+961").strip()
    mobile_number = (data.get("mobile_number") or "").strip()
    if phone:
        return country_code, phone if phone.startswith("+") else normalize_phone(country_code, phone)
    if mobile_number:
        return country_code, normalize_phone(country_code, mobile_number)
    return country_code, ""


def parse_status(value: str | None, *, default: str = "onhold") -> str:
    status = (value or default).strip().lower()
    if status not in LEAD_STATUS_API_VALUES:
        raise LeadSyncError(
            f"Invalid status '{value}'. Allowed: {', '.join(sorted(LEAD_STATUS_API_VALUES))}",
            code="INVALID_STATUS",
        )
    return status


def serialize_lead(lead: Lead) -> dict:
    dept = lead.department
    return {
        "id": lead.id,
        "external_id": lead.external_id,
        "name": lead.name,
        "phone": lead.phone,
        "country_code": lead.country_code,
        "whatsapp_received_on": lead.whatsapp_received_on,
        "department": dept.code if dept else None,
        "department_name": dept.name if dept else None,
        "destination": lead.destination,
        "chat_summary": lead.chat_summary,
        "status": lead.status,
        "status_label": lead.get_status_display(),
        "channel": lead.channel,
        "email": lead.email,
        "what_happened": lead.finalization_notes or lead.reason_of_travel or "",
        "finalization_notes": lead.finalization_notes,
        "special_request": lead.special_request,
        "assignment_notes": lead.assignment_notes,
        "sold": lead.sold,
        "lost": lead.lost,
        "selling_price": lead.selling_price,
        "net": lead.net,
        "profit": lead.profit,
        "follow_up_date": lead.follow_up.isoformat() if lead.follow_up else None,
        "takeover": lead.takeover,
        "assigned_to": {
            "id": lead.assigned_to_id,
            "username": lead.assigned_to.username,
            "full_name": lead.assigned_to.get_full_name().strip() or lead.assigned_to.username,
        },
        "created_at": lead.created_at.isoformat() if lead.created_at else None,
        "last_modified": lead.last_modified.isoformat() if lead.last_modified else None,
        "last_customer_message_at": (
            lead.last_customer_message_at.isoformat() if lead.last_customer_message_at else None
        ),
        "last_agent_action_at": (
            lead.last_agent_action_at.isoformat() if lead.last_agent_action_at else None
        ),
    }


def _find_existing_lead(data: dict, phone: str) -> Lead | None:
    external_id = (data.get("external_id") or "").strip()
    if external_id:
        lead = Lead.objects.filter(external_id=external_id).first()
        if lead:
            return lead
    if phone:
        return Lead.objects.filter(phone=phone).order_by("-created_at").first()
    return None


def _apply_lead_fields(lead: Lead, data: dict, *, is_create: bool) -> None:
    name = parse_lead_name(data)
    if name:
        lead.name = name

    country_code, phone = parse_phone_fields(data)
    if phone:
        lead.country_code = country_code
        lead.phone = phone

    if data.get("whatsapp_received_on") is not None:
        lead.whatsapp_received_on = (data.get("whatsapp_received_on") or "").strip()

    if data.get("destination") is not None:
        dest = (data.get("destination") or "").strip()
        lead.destination = dest
        if dest:
            ensure_crm_destination(dest)

    if data.get("last_customer_message_at") is not None:
        lead.last_customer_message_at = _parse_api_datetime(data.get("last_customer_message_at"))

    if data.get("last_agent_action_at") is not None:
        lead.last_agent_action_at = _parse_api_datetime(data.get("last_agent_action_at"))

    if data.get("email") is not None:
        lead.email = (data.get("email") or None) or None

    if data.get("channel") is not None:
        lead.channel = (data.get("channel") or "").strip() or "Whatsapp"

    if data.get("type_of_service") is not None:
        lead.type_of_service = (data.get("type_of_service") or "").strip()

    chat_summary = data.get("chat_summary")
    if chat_summary is None and data.get("what_happened") is not None:
        chat_summary = data.get("what_happened")
    if chat_summary is not None:
        _sync_summary_fields(lead, chat_summary)
    elif data.get("what_happened") is not None and resolve_close_outcome(data) != "lost":
        _sync_summary_fields(lead, data.get("what_happened") or "")

    if data.get("notes") is not None:
        lead.assignment_notes = (data.get("notes") or "").strip()

    if data.get("status") is not None and not resolve_close_outcome(data):
        lead.status = parse_status(data.get("status"), default=lead.status or "onhold")
        if not is_create:
            lead.status_changed_at = timezone.now()

    external_id = (data.get("external_id") or "").strip()
    if external_id and not lead.external_id:
        lead.external_id = external_id

    if data.get("finalization_notes") is not None and resolve_close_outcome(data) != "lost":
        _sync_summary_fields(lead, data.get("finalization_notes") or "")

    if data.get("what_happened") is not None and resolve_close_outcome(data) != "lost":
        _sync_summary_fields(lead, data.get("what_happened") or "")


def create_or_update_lead_from_dashboard(data: dict) -> tuple[Lead, bool]:
    """
    Upsert a lead from dashboard payload.

    Returns (lead, created).
    """
    country_code, phone = parse_phone_fields(data)
    name = parse_lead_name(data)
    department_value = data.get("department")
    department = resolve_department(department_value)

    if not name:
        raise LeadSyncError(
            "name is required (or first_name + last_name)",
            code="MISSING_FIELDS",
        )
    if not phone:
        raise LeadSyncError(
            "phone is required (or country_code + mobile_number)",
            code="MISSING_FIELDS",
        )
    if not department:
        raise LeadSyncError(
            "department is required and must match a CRM department code or name",
            code="INVALID_DEPARTMENT",
            details={"department": department_value},
        )

    existing = _find_existing_lead(data, phone)
    explicit_username = (data.get("assigned_to") or "").strip() or None
    chat_label = _chat_label_from_payload(data)
    is_create = existing is None

    if is_create:
        assigned_to = assign_user_for_department(
            department,
            explicit_username=explicit_username,
            chat_label=chat_label,
        )
        if not assigned_to:
            raise LeadSyncError(
                "No active CRM user available for assignment",
                code="NO_USER",
            )
        lead = Lead(
            name=name,
            country_code=country_code,
            phone=phone,
            department=department,
            assigned_to=assigned_to,
            channel=(data.get("channel") or "Whatsapp").strip() or "Whatsapp",
            status=parse_status(data.get("status"), default="onhold"),
            takeover=True,
        )
    else:
        lead = existing
        lead.department = department
        if explicit_username or data.get("reassign", False) or chat_label:
            assigned_to = assign_user_for_department(
                department,
                explicit_username=explicit_username,
                chat_label=chat_label,
            )
            if assigned_to:
                lead.assigned_to = assigned_to

    _apply_lead_fields(lead, data, is_create=is_create)
    lead.save()
    return lead, is_create


def update_lead_from_dashboard(lead: Lead, data: dict) -> Lead:
    department_value = data.get("department")
    if department_value is not None:
        department = resolve_department(department_value)
        if not department:
            raise LeadSyncError(
                "Invalid department",
                code="INVALID_DEPARTMENT",
                details={"department": department_value},
            )
        lead.department = department
        if data.get("reassign", True):
            assigned_to = assign_user_for_department(
                department,
                explicit_username=(data.get("assigned_to") or "").strip() or None,
                chat_label=_chat_label_from_payload(data),
            )
            if assigned_to:
                lead.assigned_to = assigned_to

    explicit_username = (data.get("assigned_to") or "").strip() or None
    if explicit_username:
        user = User.objects.filter(username__iexact=explicit_username, is_active=True).first()
        if user:
            lead.assigned_to = user

    _apply_lead_fields(lead, data, is_create=False)

    if resolve_qualification_action(data):
        apply_qualification_action(lead, data)
    elif resolve_close_outcome(data):
        apply_close_deal(lead, data)
    else:
        apply_qualification_fields(lead, data)
        lead.save()

    return lead
