"""CRM constants for external lead sync (WhatsApp AI dashboard)."""

DEPARTMENT_DEFINITIONS = [
    ("reservation", "Reservation Department"),
    ("honeymoon_far_east", "Honeymoon & Far East Department"),
    ("sharm", "Sharm Department"),
    ("civil_marriage", "Civil Marriage Department"),
    ("turkey", "Turkey Department"),
]

# Dashboard may send human-readable names; map to canonical codes.
DEPARTMENT_ALIASES = {
    "reservation": "reservation",
    "reservation department": "reservation",
    "honeymoon_far_east": "honeymoon_far_east",
    "honeymoon & far east": "honeymoon_far_east",
    "honeymoon & far east department": "honeymoon_far_east",
    "honeymoon and far east": "honeymoon_far_east",
    "honeymoon and far east department": "honeymoon_far_east",
    "sharm": "sharm",
    "sharm department": "sharm",
    "civil_marriage": "civil_marriage",
    "civil marriage": "civil_marriage",
    "civil marriage department": "civil_marriage",
    "turkey": "turkey",
    "turkey department": "turkey",
}

LEAD_STATUS_API_VALUES = {
    "onhold",
    "processing",
    "negotiation",
    "finalized",
    "followup",
    "done",
}

LEAD_STATUS_API_LABELS = {
    "onhold": "On Hold",
    "processing": "Processing",
    "negotiation": "Negotiation",
    "finalized": "Finalized",
    "followup": "Follow-Up",
    "done": "Unqualified",
}

# Sophia dashboard status labels → CRM internal stage + sold/lost flags.
# Sophia is the source of truth for status; agents pick only from this fixed list.
#   value: (internal_status, sold, lost)
SOPHIA_STATUS_MAP = {
    "new": ("onhold", False, False),
    "progress": ("processing", False, False),
    "offer_sent": ("negotiation", False, False),
    "sold": ("finalized", True, False),
    "lost": ("finalized", False, True),
    "unqualified": ("done", False, False),
}

