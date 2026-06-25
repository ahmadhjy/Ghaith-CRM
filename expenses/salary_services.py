"""Prepare monthly salary rows and post manual payments to operating expenses."""

from calendar import monthrange
from datetime import date
from decimal import Decimal

from django.db import transaction
from django.db.models import Sum
from django.utils import timezone

from accounts_core.models import Employee
from expenses.models import EmployeeSalaryEntry, EmployeeSalaryPayment, OperatingExpense
from purchases.models import ExpenseCategory


def salary_category():
    return ExpenseCategory.objects.get_or_create(
        code="SALARY",
        defaults={"name": "Salaries", "is_active": True},
    )[0]


def parse_period(month_str: str | None) -> tuple[int, int]:
    """Return (year, month) from YYYY-MM or current month."""
    if month_str and len(month_str) == 7 and month_str[4] == "-":
        year, mon = map(int, month_str.split("-"))
        if 1 <= mon <= 12:
            return year, mon
    today = timezone.localdate()
    return today.year, today.month


def period_label(year: int, month: int) -> str:
    return f"{year}-{month:02d}"


def period_end_date(year: int, month: int) -> date:
    return date(year, month, monthrange(year, month)[1])


def prepare_salary_entries(year: int, month: int) -> tuple[int, int]:
    """Create OPEN salary rows for active employees (skip existing). Returns (created, skipped)."""
    created = 0
    skipped = 0
    employees = Employee.objects.filter(is_active=True, monthly_salary__gt=Decimal("0")).order_by("name")
    with transaction.atomic():
        for emp in employees:
            _, was_created = EmployeeSalaryEntry.objects.get_or_create(
                employee=emp,
                period_year=year,
                period_month=month,
                defaults={
                    "base_salary": emp.monthly_salary,
                    "bonus": Decimal("0.00"),
                },
            )
            if was_created:
                created += 1
            else:
                skipped += 1
    return created, skipped


def entry_total_paid(entry: EmployeeSalaryEntry) -> Decimal:
    agg = entry.payments.aggregate(total=Sum("amount"))
    return (agg["total"] or Decimal("0.00")).quantize(Decimal("0.01"))


def entry_amount_due(entry: EmployeeSalaryEntry) -> Decimal:
    base = entry.base_salary or Decimal("0.00")
    bonus = entry.bonus or Decimal("0.00")
    return (base + bonus).quantize(Decimal("0.01"))


def entry_balance_due(entry: EmployeeSalaryEntry) -> Decimal:
    return (entry_amount_due(entry) - entry_total_paid(entry)).quantize(Decimal("0.01"))


def refresh_entry_status(entry: EmployeeSalaryEntry) -> None:
    due = entry_amount_due(entry)
    paid = entry_total_paid(entry)
    if paid <= 0:
        status = EmployeeSalaryEntry.Status.OPEN
    elif paid < due:
        status = EmployeeSalaryEntry.Status.PARTIAL
    else:
        status = EmployeeSalaryEntry.Status.SETTLED
    if entry.status != status:
        entry.status = status
        entry.save(update_fields=["status", "updated_at"])


@transaction.atomic
def record_salary_payment(
    entry: EmployeeSalaryEntry,
    *,
    amount: Decimal,
    payment_date: date,
    notes: str = "",
    user=None,
) -> EmployeeSalaryPayment:
    """Post a salary payment as a posted operating expense."""
    amount = Decimal(amount).quantize(Decimal("0.01"))
    if amount <= 0:
        raise ValueError("Payment amount must be greater than zero.")

    cat = salary_category()
    period = period_label(entry.period_year, entry.period_month)
    desc_parts = [f"Salary {entry.employee.name} ({period})"]
    if entry.bonus and entry.bonus > 0:
        desc_parts.append(f"bonus incl. {entry.bonus}")
    if notes.strip():
        desc_parts.append(notes.strip())
    description = " — ".join(desc_parts)

    opex = OperatingExpense.objects.create(
        category=cat,
        expense_date=payment_date,
        currency="USD",
        amount=amount,
        amount_usd=amount,
        description=description,
        status=OperatingExpense.Status.DRAFT,
    )
    opex.post(user=user)

    payment = EmployeeSalaryPayment.objects.create(
        entry=entry,
        amount=amount,
        payment_date=payment_date,
        operating_expense=opex,
        notes=notes.strip(),
        posted_by=user,
    )
    refresh_entry_status(entry)
    return payment
