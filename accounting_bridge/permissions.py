"""Access control for the embedded accounting module."""

ACCOUNTING_GROUP_NAMES = ('Accounting', 'Admin')


def user_is_accountant(user) -> bool:
    """Only main accountant users (or superusers) may access /accounting/."""
    if not user.is_authenticated:
        return False
    if user.is_superuser:
        return True
    profile = getattr(user, 'profile', None)
    return bool(profile and profile.is_main_accountant)


def user_can_access_accounting_admin(user) -> bool:
    return user_is_accountant(user)
