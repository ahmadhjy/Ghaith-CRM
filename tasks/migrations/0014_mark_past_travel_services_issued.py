# Mark purchases-list services as issued when CRM travel date is in 2024 or 2025.

from django.db import migrations

from tasks.purchases_issued import mark_past_travel_services_issued as _mark


def mark_past_travel_services_issued(apps, schema_editor):
    _mark(apps)


class Migration(migrations.Migration):

    dependencies = [
        ('tasks', '0013_babylon_entry_service_type'),
        ('dashboard', '0005_crm_invoice_overhaul'),
    ]

    operations = [
        migrations.RunPython(mark_past_travel_services_issued, migrations.RunPython.noop),
    ]
