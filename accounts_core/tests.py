from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase

from accounting_bridge.models import PartyOpeningBalance
from accounts_core.client_querysets import clients_for_select, clients_with_accounting_activity, search_clients
from accounts_core.export_names import export_filename, export_period_suffix, slugify_filename_part
from accounts_core.models import Client, Employee, Supplier
from accounts_core.supplier_querysets import (
    search_suppliers,
    suppliers_for_select,
    suppliers_with_accounting_activity,
)
from catalog.models import ServiceType
from catalog.service_type_querysets import crm_predefined_service_types
from sales.models import SalesInvoice, SalesInvoiceLine
from treasury.models import MoneyAccount, Payment


class ExportFilenameTests(TestCase):
    def test_slugify_strips_unsafe_chars(self):
        self.assertEqual(slugify_filename_part("Acme Corp. (UK)"), "Acme_Corp_UK")

    def test_export_filename_joins_parts(self):
        name = export_filename("Statement", "Client A", "C0001", "2025")
        self.assertEqual(name, "Statement_Client_A_C0001_2025.pdf")

    def test_export_period_suffix_full_year(self):
        self.assertEqual(
            export_period_suffix(date(2025, 1, 1), date(2025, 12, 31)),
            "2025",
        )

    def test_export_period_suffix_range(self):
        self.assertEqual(
            export_period_suffix(date(2025, 3, 1), date(2025, 3, 31)),
            "2025-03-01_to_2025-03-31",
        )


class ClientVisibilityTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username="vis1", password="test12345")
        self.active = Client.objects.create(client_code="C-ACT", name_en="Active Client")
        self.inactive = Client.objects.create(client_code="C-INACT", name_en="Inactive Client")
        self.employee = Employee.objects.create(name="Emp", role=Employee.EmployeeRole.ACCOUNTING)
        self.account = MoneyAccount.objects.create(name="Cash", currency="USD")

    def test_inactive_client_hidden_from_active_queryset(self):
        self.assertFalse(clients_with_accounting_activity().filter(pk=self.inactive.pk).exists())

    def test_client_with_invoice_is_active(self):
        inv = SalesInvoice.objects.create(
            invoice_no="TMP-VIS",
            client=self.inactive,
            sales_employee=self.employee,
            issue_date=date.today(),
            currency="USD",
        )
        SalesInvoiceLine.objects.create(
            invoice=inv,
            line_employee=self.employee,
            qty=Decimal("1"),
            sell_price=Decimal("100"),
        )
        self.assertTrue(clients_with_accounting_activity().filter(pk=self.inactive.pk).exists())

    def test_client_with_opening_balance_is_active(self):
        PartyOpeningBalance.objects.create(
            party_type=PartyOpeningBalance.PartyType.CLIENT,
            client=self.inactive,
            debit_usd=Decimal("50.00"),
        )
        self.assertTrue(clients_with_accounting_activity().filter(pk=self.inactive.pk).exists())

    def test_clients_for_select_includes_extra_inactive(self):
        qs = clients_for_select(extra_pk=self.inactive.pk)
        self.assertIn(self.inactive, list(qs))
        self.assertNotIn(self.active, list(qs))

    def test_search_clients_finds_inactive(self):
        found = search_clients("Inactive")
        self.assertTrue(any(c.pk == self.inactive.pk for c in found))


class SupplierVisibilityTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username="supvis1", password="test12345")
        self.active = Supplier.objects.create(supplier_code="S-ACT", name="Active Supplier")
        self.inactive = Supplier.objects.create(supplier_code="S-INACT", name="Inactive Supplier")
        self.employee = Employee.objects.create(name="Emp", role=Employee.EmployeeRole.ACCOUNTING)
        self.account = MoneyAccount.objects.create(name="Cash", currency="USD")

    def test_inactive_supplier_hidden_from_active_queryset(self):
        self.assertFalse(suppliers_with_accounting_activity().filter(pk=self.inactive.pk).exists())

    def test_supplier_with_invoice_line_is_active(self):
        client = Client.objects.create(client_code="C-SUP", name_en="Client")
        inv = SalesInvoice.objects.create(
            invoice_no="TMP-SUP",
            client=client,
            sales_employee=self.employee,
            issue_date=date.today(),
            currency="USD",
        )
        SalesInvoiceLine.objects.create(
            invoice=inv,
            supplier=self.inactive,
            line_employee=self.employee,
            qty=Decimal("1"),
            sell_price=Decimal("100"),
            cost_price=Decimal("50"),
        )
        self.assertTrue(suppliers_with_accounting_activity().filter(pk=self.inactive.pk).exists())

    def test_supplier_with_payment_is_active(self):
        Payment.objects.create(
            receipt_no="RCP-SUP-1",
            party_type=Payment.PartyType.SUPPLIER,
            supplier=self.inactive,
            direction=Payment.Direction.OUT,
            money_account=self.account,
            date=date.today(),
            amount=Decimal("25.00"),
            currency="USD",
            status=Payment.Status.POSTED,
        )
        self.assertTrue(suppliers_with_accounting_activity().filter(pk=self.inactive.pk).exists())

    def test_suppliers_for_select_includes_extra_inactive(self):
        qs = suppliers_for_select(extra_pk=self.inactive.pk)
        self.assertIn(self.inactive, list(qs))
        self.assertNotIn(self.active, list(qs))

    def test_search_suppliers_finds_inactive(self):
        found = search_suppliers("Inactive")
        self.assertTrue(any(s.pk == self.inactive.pk for s in found))


class ServiceTypeVisibilityTests(TestCase):
    def setUp(self):
        from tasks.models import ServiceType as CrmServiceType

        self.crm_ticket = CrmServiceType.objects.create(name="Visa Application", is_active=True)
        self.crm_legacy = CrmServiceType.objects.create(name="Old Custom Tour", is_active=False)
        self.predefined, _ = ServiceType.objects.get_or_create(
            name="Visa Application",
            defaults={"code": "VISAAPP", "is_active": True},
        )
        self.legacy = ServiceType.objects.create(name="Random Manual Service", code="LEG", is_active=True)

    def test_only_crm_predefined_service_types_listed(self):
        names = set(crm_predefined_service_types().values_list("name", flat=True))
        self.assertIn("Visa Application", names)
        self.assertNotIn("Random Manual Service", names)

    def test_inactive_crm_type_excluded(self):
        names = set(crm_predefined_service_types().values_list("name", flat=True))
        self.assertNotIn("Old Custom Tour", names)

    def test_extra_pk_included_for_saved_line(self):
        qs = crm_predefined_service_types(extra_pk=self.legacy.pk)
        self.assertIn(self.legacy, list(qs))
