from django.core.management.base import BaseCommand

from tasks.calendar_sync import sync_travel_event
from tasks.models import LeadTask


class Command(BaseCommand):
    help = 'Create/update calendar travel events for orders with a travel date.'

    def handle(self, *args, **options):
        qs = LeadTask.objects.filter(travel_date__isnull=False).select_related('lead', 'assigned_to')
        count = 0
        for leadtask in qs:
            sync_travel_event(leadtask)
            count += 1
        self.stdout.write(self.style.SUCCESS(f'Synced travel calendar events for {count} order(s).'))
