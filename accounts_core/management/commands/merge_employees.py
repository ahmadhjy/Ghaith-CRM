"""Re-point accounting records from duplicate employees to one target, then remove sources."""

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.db.models import Q

from accounting_bridge.models import CrmEmployeeLink
from accounts_core.models import Employee
from expenses.models import EmployeeSalaryEntry, EmployeeSalaryPayment
from sales.models import SalesInvoice, SalesInvoiceLine


class Command(BaseCommand):
    help = "Merge employee records: transfer invoices, lines, payroll, then delete/deactivate sources."

    def add_arguments(self, parser):
        parser.add_argument(
            "--to",
            required=True,
            help='Target employee name (e.g. "Sara")',
        )
        parser.add_argument(
            "--from",
            dest="from_names",
            nargs="+",
            required=True,
            help='Source employee name(s) to merge away (e.g. "Saleh" "Mona")',
        )
        parser.add_argument(
            "--deactivate-only",
            action="store_true",
            help="Deactivate sources instead of deleting after merge.",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Show what would change without writing.",
        )

    def handle(self, *args, **options):
        target = self._find_employee(options["to"])
        sources = []
        for name in options["from_names"]:
            src = self._find_employee(name)
            if src.id == target.id:
                raise CommandError(f'Source "{name}" is the same as target "{target.name}".')
            sources.append(src)

        stats = {
            "invoices": 0,
            "lines": 0,
            "salary_entries_moved": 0,
            "salary_entries_merged": 0,
            "links_moved": 0,
            "links_dropped": 0,
        }

        if options["dry_run"]:
            self._report_plan(target, sources, stats)
            return

        with transaction.atomic():
            for src in sources:
                stats["invoices"] += SalesInvoice.objects.filter(sales_employee=src).update(sales_employee=target)
                stats["lines"] += SalesInvoiceLine.objects.filter(line_employee=src).update(line_employee=target)
                moved, merged = self._merge_salary_entries(src, target)
                stats["salary_entries_moved"] += moved
                stats["salary_entries_merged"] += merged
                moved_link, dropped_link = self._merge_crm_link(src, target)
                stats["links_moved"] += moved_link
                stats["links_dropped"] += dropped_link

                src.user_id = None
                src.is_active = False
                src.save(update_fields=["user", "is_active"])

                if options["deactivate_only"]:
                    self.stdout.write(self.style.WARNING(f'Deactivated "{src.name}" (not deleted).'))
                else:
                    src.delete()
                    self.stdout.write(self.style.SUCCESS(f'Deleted employee "{src.name}".'))

        self.stdout.write(
            self.style.SUCCESS(
                f'Merged into "{target.name}": '
                f'{stats["invoices"]} invoice(s), {stats["lines"]} line(s), '
                f'{stats["salary_entries_moved"]} salary row(s) moved, '
                f'{stats["salary_entries_merged"]} salary row(s) merged, '
                f'{stats["links_moved"]} CRM link(s) moved, {stats["links_dropped"]} dropped.'
            )
        )

    def _find_employee(self, name: str) -> Employee:
        name = name.strip()
        emp = Employee.objects.filter(name__iexact=name).first()
        if not emp:
            emp = Employee.objects.filter(Q(first_name__iexact=name) | Q(name__icontains=name)).first()
        if not emp:
            raise CommandError(f'Employee "{name}" not found.')
        return emp

    def _merge_salary_entries(self, src: Employee, target: Employee) -> tuple[int, int]:
        moved = 0
        merged = 0
        for entry in EmployeeSalaryEntry.objects.filter(employee=src).select_related().prefetch_related("payments"):
            conflict = EmployeeSalaryEntry.objects.filter(
                employee=target,
                period_year=entry.period_year,
                period_month=entry.period_month,
            ).first()
            if not conflict:
                entry.employee = target
                entry.save(update_fields=["employee"])
                moved += 1
                continue
            conflict.base_salary = (conflict.base_salary or 0) + (entry.base_salary or 0)
            conflict.bonus = (conflict.bonus or 0) + (entry.bonus or 0)
            if entry.notes:
                conflict.notes = "\n".join(filter(None, [conflict.notes, f"[from {src.name}] {entry.notes}"]))
            conflict.save(update_fields=["base_salary", "bonus", "notes"])
            EmployeeSalaryPayment.objects.filter(entry=entry).update(entry=conflict)
            entry.delete()
            merged += 1
        return moved, merged

    def _merge_crm_link(self, src: Employee, target: Employee) -> tuple[int, int]:
        try:
            link = CrmEmployeeLink.objects.get(employee=src)
        except CrmEmployeeLink.DoesNotExist:
            return 0, 0
        if CrmEmployeeLink.objects.filter(employee=target).exists():
            link.delete()
            return 0, 1
        link.employee = target
        link.save(update_fields=["employee"])
        return 1, 0

    def _report_plan(self, target, sources, stats):
        self.stdout.write(f'DRY RUN — merge into "{target.name}" ({target.id})')
        for src in sources:
            inv = SalesInvoice.objects.filter(sales_employee=src).count()
            lines = SalesInvoiceLine.objects.filter(line_employee=src).count()
            sal = EmployeeSalaryEntry.objects.filter(employee=src).count()
            self.stdout.write(f'  From "{src.name}": {inv} invoices, {lines} lines, {sal} salary rows')
