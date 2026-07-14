# Default supplier list used to seed admin-managed Supplier records.
DEFAULT_SUPPLIER_NAMES = [
    "YARDS",
    "CONCORD",
    "SAMAD",
    "NAKHAL",
    "TRAVELBOOOK",
    "SIA",
    "ELDORADO",
    "EBOOKING",
    "Layover",
    "TVG",
    "BABYLON",
    "PRIME",
    "Online",
    "Chadi Service",
    "Sun Safari -ADEL",
    "LAITH",
    "SAYOURI",
    "Mercan",
    "Black Pearl",
    "Lady Zanzibar",
    "Translation",
]

DEFAULT_SERVICE_NAMES = [
    "Ticket",
    "Hotel",
    "Transfer",
    "Tours",
    "Visa",
    "Benefits",
    "Visa Application",
    "Train",
    "Travel Insurance",
    "Ready Package",
    "Bank Charges",
    "Commission",
    "Transfers & Tours",
    "Crusie",
    "Translation",
    "Civil Marriage",
]


def _merge_choice_names(defaults, extra_names):
    """Keep predefined order, then append any extras from admin."""
    ordered = list(defaults)
    seen = {n.casefold() for n in ordered}
    for name in extra_names:
        key = (name or "").strip()
        if not key or key.casefold() in seen:
            continue
        ordered.append(key)
        seen.add(key.casefold())
    return ordered


def get_supplier_choices():
    """Supplier choices from admin-managed Supplier model (unchanged behavior).

    Active Supplier rows from Django admin populate the dropdown.
    One-off / historical values on a service stay as the existing note outside
    the list — they are not auto-merged into the choices.
    """
    try:
        from .models import Supplier

        names = list(
            Supplier.objects.filter(is_active=True)
            .order_by("name")
            .values_list("name", flat=True)
        )
        if names:
            return [(n, n) for n in names]
    except Exception:
        pass
    return [(n, n) for n in DEFAULT_SUPPLIER_NAMES]


def get_service_choices():
    """Built-in service types plus any extra active rows from Django admin.

    The predefined list always shows (Ticket, Hotel, …, Civil Marriage).
    Add more under Admin → Service types; they appear after the defaults.
    """
    extras = []
    try:
        from .models import ServiceType

        extras = list(
            ServiceType.objects.filter(is_active=True)
            .order_by("name")
            .values_list("name", flat=True)
        )
    except Exception:
        pass
    return [(n, n) for n in _merge_choice_names(DEFAULT_SERVICE_NAMES, extras)]


def effective_service_net(service):
    """Issue price overrides net when set."""
    issue = (getattr(service, 'issue_price', None) or '').strip()
    if issue:
        return issue
    return (service.net or '').strip()


def parse_money(value):
    if value is None:
        return 0.0
    s = str(value).strip()
    if not s:
        return 0.0
    cleaned = ''.join(c for c in s if c.isdigit() or c in '.-')
    try:
        return float(cleaned) if cleaned else 0.0
    except ValueError:
        return 0.0


def service_has_issue_override(service):
    """True when a service has an issue price that differs from its booking net."""
    issue = (getattr(service, 'issue_price', None) or '').strip()
    if not issue:
        return False
    return parse_money(issue) != parse_money(getattr(service, 'net', '') or '')
