"""Keep CRM destination choices in sync with the accounting catalog."""

from __future__ import annotations


def ensure_crm_destination(name: str) -> None:
    """Ensure a display.Destination row exists for CRM lead dropdowns."""
    from display.models import Destination

    cleaned = (name or "").strip()
    if not cleaned:
        return
    Destination.objects.get_or_create(name=cleaned)


def sync_catalog_destinations_to_crm() -> int:
    """Copy active catalog destinations into display.Destination (by name)."""
    from display.models import Destination

    try:
        from catalog.models import Destination as CatalogDestination
    except ImportError:
        return 0

    created = 0
    for row in CatalogDestination.objects.filter(is_active=True).order_by("name"):
        _, was_created = Destination.objects.get_or_create(name=row.name)
        if was_created:
            created += 1
    return created
