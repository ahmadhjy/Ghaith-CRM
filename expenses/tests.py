from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase

from accounts_core.models import Employee
from expenses.models import EmployeeSalaryEntry, OperatingExpense
from expenses.salary_services import (
    entry_amount_due,
    entry_balance_due,
    entry_total_paid,
    prepare_salary_entries,
    record_salary_payment,
)


class SalaryPayrollTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username="payroll1", password="test12345")
        self.employee = Employee.objects.create(
            name="Jane Doe",
            monthly_salary=Decimal("1500.00"),
            is_active=True,
        )

    def test_prepare_creates_open_rows_without_expense(self):
        created, skipped = prepare_salary_entries(2026, 6)
        self.assertEqual(created, 1)
        self.assertEqual(skipped, 0)
        entry = EmployeeSalaryEntry.objects.get(employee=self.employee, period_year=2026, period_month=6)
        self.assertEqual(entry.base_salary, Decimal("1500.00"))
        self.assertEqual(entry.status, EmployeeSalaryEntry.Status.OPEN)
        self.assertEqual(OperatingExpense.objects.count(), 0)

    def test_partial_payment_posts_expense_and_leaves_balance(self):
        entry = EmployeeSalaryEntry.objects.create(
            employee=self.employee,
            period_year=2026,
            period_month=6,
            base_salary=Decimal("1500.00"),
        )
        payment = record_salary_payment(
            entry,
            amount=Decimal("1000.00"),
            payment_date=date(2026, 6, 15),
            user=self.user,
        )
        entry.refresh_from_db()
        self.assertEqual(entry.status, EmployeeSalaryEntry.Status.PARTIAL)
        self.assertEqual(entry_total_paid(entry), Decimal("1000.00"))
        self.assertEqual(entry_balance_due(entry), Decimal("500.00"))
        self.assertEqual(OperatingExpense.objects.count(), 1)
        opex = payment.operating_expense
        self.assertEqual(opex.status, OperatingExpense.Status.POSTED)
        self.assertEqual(opex.amount, Decimal("1000.00"))
        self.assertTrue(hasattr(opex, "salary_payment"))

    def test_full_payment_with_bonus_settles(self):
        entry = EmployeeSalaryEntry.objects.create(
            employee=self.employee,
            period_year=2026,
            period_month=6,
            base_salary=Decimal("1500.00"),
            bonus=Decimal("200.00"),
        )
        self.assertEqual(entry_amount_due(entry), Decimal("1700.00"))
        record_salary_payment(
            entry,
            amount=Decimal("1700.00"),
            payment_date=date(2026, 6, 30),
            user=self.user,
        )
        entry.refresh_from_db()
        self.assertEqual(entry.status, EmployeeSalaryEntry.Status.SETTLED)
        self.assertEqual(entry_balance_due(entry), Decimal("0.00"))

    def test_expense_list_excludes_salary_linked_opex(self):
        entry = EmployeeSalaryEntry.objects.create(
            employee=self.employee,
            period_year=2026,
            period_month=6,
            base_salary=Decimal("500.00"),
        )
        record_salary_payment(
            entry,
            amount=Decimal("500.00"),
            payment_date=date(2026, 6, 1),
            user=self.user,
        )
        from purchases.models import ExpenseCategory

        cat, _ = ExpenseCategory.objects.get_or_create(code="RENT", defaults={"name": "Rent"})
        OperatingExpense.objects.create(
            category=cat,
            expense_date=date(2026, 6, 1),
            currency="USD",
            amount=Decimal("100.00"),
            amount_usd=Decimal("100.00"),
            description="Office rent",
            status=OperatingExpense.Status.POSTED,
        )
        other = OperatingExpense.objects.filter(salary_payment__isnull=True)
        self.assertEqual(other.count(), 1)
        self.assertEqual(other.first().description, "Office rent")
