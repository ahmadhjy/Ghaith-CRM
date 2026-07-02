from django.core.management.base import BaseCommand

from display.lead_api_views import seed_departments


class Command(BaseCommand):
    help = "Seed or refresh CRM sales departments used for WhatsApp dashboard routing."

    def handle(self, *args, **options):
        seed_departments()
        self.stdout.write(self.style.SUCCESS("Departments seeded."))
