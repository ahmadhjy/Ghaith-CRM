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
]


def get_supplier_choices():
    """Supplier choices from admin-managed Supplier model."""
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
    """Service type choices from admin-managed ServiceType model."""
    try:
        from .models import ServiceType

        names = list(
            ServiceType.objects.filter(is_active=True)
            .order_by("name")
            .values_list("name", flat=True)
        )
        if names:
            return [(n, n) for n in names]
    except Exception:
        pass
    return [(n, n) for n in DEFAULT_SERVICE_NAMES]


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
