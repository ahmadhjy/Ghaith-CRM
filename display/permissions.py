"""Permissions shared by CRM management dashboards."""


MANAGEMENT_DASHBOARD_USERS = frozenset({
    "sara",
    "developer",
    "accounting",
})


def user_can_view_management_dashboards(user) -> bool:
    """Allow only the explicitly approved dashboard users."""
    return bool(
        user.is_authenticated
        and user.username.casefold() in MANAGEMENT_DASHBOARD_USERS
    )
