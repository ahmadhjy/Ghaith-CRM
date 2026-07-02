# Backfill Babylon sheet rows for existing BABYLON services.

from django.db import migrations


def backfill_babylon_entries(apps, schema_editor):
    Service = apps.get_model('tasks', 'Service')
    BabylonHotelEntry = apps.get_model('tasks', 'BabylonHotelEntry')
    LeadTask = apps.get_model('tasks', 'LeadTask')

    for service in Service.objects.filter(supplier__iexact='BABYLON').iterator():
        try:
            leadtask = LeadTask.objects.select_related('lead').get(pk=service.leadtask_id)
            client_name = leadtask.lead.name if leadtask.lead_id else ''
        except LeadTask.DoesNotExist:
            continue
        entry_date = service.created_at.date() if service.created_at else None
        if not entry_date:
            from django.utils import timezone
            entry_date = timezone.localdate()
        due_date = service.due_time.date() if service.due_time else None
        net = (service.issue_price or '').strip() or (service.net or '').strip()
        BabylonHotelEntry.objects.update_or_create(
            service_id=service.pk,
            defaults={
                'entry_date': entry_date,
                'client_name': client_name,
                'details': (service.details or '').strip(),
                'price': net,
                'due_date': due_date,
            },
        )


class Migration(migrations.Migration):

    dependencies = [
        ('tasks', '0011_babylon_hotel_entry'),
        ('display', '0012_seed_departments_and_profiles'),
    ]

    operations = [
        migrations.RunPython(backfill_babylon_entries, migrations.RunPython.noop),
    ]
