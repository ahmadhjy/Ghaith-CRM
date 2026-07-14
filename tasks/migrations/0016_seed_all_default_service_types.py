from django.db import migrations

# Keep in sync with tasks.constants.DEFAULT_SERVICE_NAMES
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


def seed_default_service_types(apps, schema_editor):
    ServiceType = apps.get_model("tasks", "ServiceType")
    for name in DEFAULT_SERVICE_NAMES:
        ServiceType.objects.get_or_create(name=name, defaults={"is_active": True})


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("tasks", "0015_seed_civil_marriage_service_type"),
    ]

    operations = [
        migrations.RunPython(seed_default_service_types, noop),
    ]
