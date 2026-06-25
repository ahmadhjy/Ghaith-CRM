from django.core.management.base import BaseCommand

from accounting_bridge.services.master_data import sync_all_crm_master_data


class Command(BaseCommand):
    help = (
        'Deployment seed: sync CRM master data into accounting from orders (LeadTask). '
        'Creates clients (from order leads), suppliers, service types, destinations, and employees. '
        'Does not import historical invoices — use opening balances + manual per-invoice sync instead.'
    )

    def handle(self, *args, **options):
        stats = sync_all_crm_master_data()
        self.stdout.write(
            self.style.SUCCESS(
                'Synced '
                f"{stats['clients']} accounting clients, "
                f"{stats['destinations']} destinations, "
                f"{stats['suppliers']} catalog suppliers, "
                f"{stats['service_types']} catalog service types, "
                f"{stats['employees']} employees, "
                f"{stats['orders']} CRM orders scanned, "
                f"{stats['service_lines']} service lines."
            )
        )
