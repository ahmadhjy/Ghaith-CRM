from django.db import migrations


def seed_civil_marriage(apps, schema_editor):
    ServiceType = apps.get_model("tasks", "ServiceType")
    ServiceType.objects.get_or_create(name="Civil Marriage", defaults={"is_active": True})


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("tasks", "0014_mark_past_travel_services_issued"),
    ]

    operations = [
        migrations.RunPython(seed_civil_marriage, noop),
    ]
