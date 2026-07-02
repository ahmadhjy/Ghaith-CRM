"""Assign leads to CRM users based on department membership."""

from __future__ import annotations

from django.contrib.auth.models import User
from django.db.models import Count, Q

from display.models import Department


def assign_user_for_department(
    department: Department | None,
    *,
    explicit_username: str | None = None,
) -> User | None:
    """
    Pick the active CRM user in the department with the fewest open leads.

    Priority:
      1) explicit_username when provided and user belongs to the department
      2) active users in department with receives_lead_assignments=True
      3) first active user in department (any)
      4) first active user in CRM (fallback)
    """
    users_qs = User.objects.filter(is_active=True)

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
