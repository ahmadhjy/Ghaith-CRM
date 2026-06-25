"""Prepare monthly salary rows (no automatic operating expenses)."""

from django.core.management.base import BaseCommand

from expenses.salary_services import parse_period, period_label, prepare_salary_entries


class Command(BaseCommand):
    help = "Create OPEN salary rows for active employees (payments are recorded manually in Operating Expenses → Salaries)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--month",
            help="Target month as YYYY-MM (default: current calendar month).",
        )

    def handle(self, *args, **options):
        year, month = parse_period(options.get("month"))
        created, skipped = prepare_salary_entries(year, month)
        self.stdout.write(
            self.style.SUCCESS(
                f"Salary rows for {period_label(year, month)}: {created} created, {skipped} already existed."
            )
        )
