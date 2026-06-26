from django.core.management.base import BaseCommand

from accounting_bridge.models import InvoiceSyncQueue
from accounting_bridge.services.invoices import SYNCABLE_QUEUE_STATUSES, refresh_accounting_invoice_from_crm


class Command(BaseCommand):
    help = (
        "Re-sync linked CRM orders into accounting invoices. "
        "Updates service lines and sets total selling from CRM lead.selling_price."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="List linked invoices that would be refreshed without saving.",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        queues = (
            InvoiceSyncQueue.objects.filter(
                sales_invoice__isnull=False,
                status__in=SYNCABLE_QUEUE_STATUSES,
            )
            .select_related("leadtask__lead", "sales_invoice")
            .order_by("leadtask_id")
        )
        refreshed = 0
        skipped = 0
        for queue in queues:
            lead = queue.leadtask.lead
            invoice = queue.sales_invoice
            label = (
                f"CRM order #{queue.leadtask_id} → {invoice.invoice_no} "
                f"(CRM selling: {lead.selling_price or '—'})"
            )
            if dry_run:
                self.stdout.write(f"Would refresh: {label}")
                refreshed += 1
                continue
            try:
                refresh_accounting_invoice_from_crm(queue)
                invoice.refresh_from_db()
                self.stdout.write(
                    f"Refreshed: {label} → accounting total {invoice.grand_total}"
                )
                refreshed += 1
            except Exception as exc:
                skipped += 1
                self.stderr.write(self.style.ERROR(f"Failed: {label} — {exc}"))

        if dry_run:
            self.stdout.write(self.style.SUCCESS(f"Dry run: {refreshed} invoice(s) would be refreshed."))
        else:
            self.stdout.write(
                self.style.SUCCESS(
                    f"Done: {refreshed} invoice(s) refreshed"
                    + (f", {skipped} failed" if skipped else "")
                    + "."
                )
            )
