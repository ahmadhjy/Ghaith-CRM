"""Daily 07:00 Asia/Beirut pull of changed Sophia chats into CRM leads.

Schedule this once per day (e.g. PythonAnywhere scheduled task):

    python manage.py sync_sophia_leads
"""

from django.core.management.base import BaseCommand

from display.services.sophia_pull import run_sophia_pull


class Command(BaseCommand):
    help = "Pull changed chats from Sophia and sync them into CRM leads (daily 07:00 batch)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--since",
            help="Override the watermark (ISO 8601 with offset). Default: stored watermark.",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Fetch and report but do not write leads or advance the watermark.",
        )
        parser.add_argument(
            "--assigned-agent",
            help="Only apply chats for this Sophia agent id (does not advance the watermark).",
        )

    def handle(self, *args, **options):
        result = run_sophia_pull(
            since=options.get("since"),
            dry_run=options.get("dry_run", False),
            assigned_agent=options.get("assigned_agent"),
        )
        if not result.get("configured"):
            self.stderr.write(self.style.ERROR(result.get("error") or "Not configured"))
            return
        for warning in result.get("warnings") or []:
            self.stderr.write(self.style.WARNING(warning))
        for detail in result.get("error_details") or []:
            self.stderr.write(self.style.WARNING(f"  skip chat {detail}"))
        if not result.get("ok") and result.get("code") == "SOPHIA_PULL_FAILED":
            self.stderr.write(self.style.ERROR(f"Sophia pull failed: {result.get('error')}"))
            return
        self.stdout.write(self.style.SUCCESS(f"Sophia sync done: {result.get('summary')}"))
