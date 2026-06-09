"""Helpers for saving lead passengers from form POST data."""


def save_lead_passengers(lead, names):
    """Replace all passengers for a lead with the given list of names."""
    cleaned = []
    seen = set()
    for raw in names:
        name = (raw or '').strip()
        if not name or name in seen:
            continue
        seen.add(name)
        cleaned.append(name[:100])

    lead.passengers.all().delete()
    for name in cleaned:
        lead.passengers.create(name=name)
