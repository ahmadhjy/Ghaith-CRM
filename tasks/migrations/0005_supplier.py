from django.db import migrations, models


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


def seed_suppliers(apps, schema_editor):
    Supplier = apps.get_model("tasks", "Supplier")
    for name in DEFAULT_SUPPLIER_NAMES:
        Supplier.objects.get_or_create(name=name, defaults={"is_active": True})


class Migration(migrations.Migration):
    dependencies = [
        ("tasks", "0004_alter_leadtask_status"),
    ]

    operations = [
        migrations.CreateModel(
            name="Supplier",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=120, unique=True)),
                ("is_active", models.BooleanField(default=True)),
            ],
            options={"ordering": ["name"]},
        ),
        migrations.RunPython(seed_suppliers, migrations.RunPython.noop),
    ]

