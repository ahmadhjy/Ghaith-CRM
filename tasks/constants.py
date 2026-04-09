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


def get_supplier_choices():
    """
    Supplier choices from admin-managed Supplier model.
    Falls back to defaults when DB/migrations are not ready.
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
