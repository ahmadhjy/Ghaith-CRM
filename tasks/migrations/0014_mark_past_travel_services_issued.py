# Mark purchases-list services with 2024/2025 travel dates as issued.

from django.db import migrations


def mark_past_travel_services_issued(apps, schema_editor):
    Service = apps.get_model('tasks', 'Service')
    Event = apps.get_model('dashboard', 'Event')

    qs = Service.objects.filter(
        is_checked=False,
        due_time__isnull=False,
        leadtask__travel_date__isnull=False,
        leadtask__travel_date__year__in=[2024, 2025],
    )
    service_ids = list(qs.values_list('pk', flat=True))
    if not service_ids:
        return

    Service.objects.filter(pk__in=service_ids).update(is_checked=True)
    Event.objects.filter(service_id__in=service_ids).update(done=True)


class Migration(migrations.Migration):

    dependencies = [
        ('tasks', '0013_babylon_entry_service_type'),
        ('dashboard', '0005_crm_invoice_overhaul'),
    ]

    operations = [
        migrations.RunPython(mark_past_travel_services_issued, migrations.RunPython.noop),
    ]
