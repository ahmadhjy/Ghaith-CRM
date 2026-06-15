from django.core.management.base import BaseCommand

from tasks.constants import DEFAULT_SERVICE_NAMES
from tasks.models import ServiceType


class Command(BaseCommand):
    help = 'Seed predefined service types (idempotent).'

    def handle(self, *args, **options):
        created = 0
        for name in DEFAULT_SERVICE_NAMES:
            _, was_created = ServiceType.objects.get_or_create(name=name, defaults={'is_active': True})
            if was_created:
                created += 1
        self.stdout.write(self.style.SUCCESS(f'Done — {created} new service type(s).'))
