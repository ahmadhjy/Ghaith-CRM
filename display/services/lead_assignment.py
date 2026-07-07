"""Assign leads to CRM users based on department membership."""

from __future__ import annotations

from django.contrib.auth.models import User
from django.db.models import Count, Q

from display.models import Department

HONEYMOON_DEPT_CODE = "honeymoon_far_east"


def resolve_assignee_from_chat_label(
    department: Department | None,
    chat_label: str | None,
) -> str | None:
    """
    Honeymoon & Far East: route by WhatsApp chat label (Alaa / Fouad).
    Case-insensitive; Alaa is the fallback when the label is missing or unknown.
    """
    if not department or department.code != HONEYMOON_DEPT_CODE:
        return None
    label = (chat_label or "").strip().lower()
    if label == "fouad":
        return "fouad"
    return "alaa"


def assign_user_for_department(
    department: Department | None,
    *,
    explicit_username: str | None = None,
    chat_label: str | None = None,
) -> User | None:
    """
    Pick the active CRM user in the department with the fewest open leads.

    Priority:
      1) explicit_username when provided and user belongs to the department
      2) chat_label routing for Honeymoon & Far East (Alaa / Fouad)
      3) active users in department with receives_lead_assignments=True
      4) first active user in department (any)
      5) first active user in CRM (fallback)
    """
    users_qs = User.objects.filter(is_active=True)

    if not explicit_username:
        explicit_username = resolve_assignee_from_chat_label(department, chat_label)

    if explicit_username:
        user = users_qs.filter(username__iexact=explicit_username).first()
        if not user:
            user = users_qs.filter(first_name__iexact=explicit_username).first()
        if user and _user_in_department(user, department):
            return user

    if not department:
        return users_qs.order_by("id").first()

    dept_users = users_qs.filter(crm_profile__department=department)
    candidates = dept_users.filter(crm_profile__receives_lead_assignments=True)
    if not candidates.exists():
        candidates = dept_users
    if not candidates.exists():
        return users_qs.order_by("id").first()

    return (
        candidates.annotate(
            open_leads=Count(
                "current",
                filter=Q(current__is_archived=False) & ~Q(current__status="done"),
            )
        )
        .order_by("open_leads", "id")
        .first()
    )


def _user_in_department(user: User, department: Department | None) -> bool:
    if not department:
        return True
    profile = getattr(user, "crm_profile", None)
    return bool(profile and profile.department_id == department.pk)
