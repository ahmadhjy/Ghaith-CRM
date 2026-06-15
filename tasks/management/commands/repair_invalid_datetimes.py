from django.core.management.base import BaseCommand

from tasks.datetime_safety import repair_invalid_datetimes


class Command(BaseCommand):
    help = 'Clear out-of-range datetime values that crash Django (year -1 errors).'

    def handle(self, *args, **options):
        repairs = repair_invalid_datetimes(verbose=True)
        if not repairs:
            self.stdout.write(self.style.SUCCESS('No invalid datetimes found.'))
            return
        total = sum(repairs.values())
        self.stdout.write(self.style.SUCCESS(f'Repaired {total} invalid datetime value(s).'))
