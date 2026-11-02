"""Standalone payment tracker. Never posts accounting expenses automatically."""

from calendar import monthrange
from datetime import date

from django.db import transaction
from django.utils import timezone

from expenses.models import UpcomingExpensePayment, UpcomingExpensePlan


def monthly_date(start, offset):
    month_index = start.year * 12 + start.month - 1 + offset
    year, month_zero = divmod(month_index, 12)
    month = month_zero + 1
    return date(year, month, min(start.day, monthrange(year, month)[1]))


def ensure_installment(plan, scheduled_for):
    return UpcomingExpensePayment.objects.get_or_create(
        plan=plan, scheduled_for=scheduled_for,
        defaults={
            "payment_type": plan.payment_type,
            "description": plan.description,
            "amount": plan.amount,
            "due_date": scheduled_for,
        },
    )[0]


@transaction.atomic
def materialize_monthly_payments(today=None):
    """Accrue installments through this month, regardless of older unpaid rows."""
    today = today or timezone.localdate()
    through = today.replace(day=monthrange(today.year, today.month)[1])
    plans = UpcomingExpensePlan.objects.select_for_update().filter(
        frequency=UpcomingExpensePlan.Frequency.MONTHLY, is_active=True,
        start_date__lte=through,
    ).select_related("payment_type")
    for plan in plans:
        existing = set(plan.payments.values_list("scheduled_for", flat=True))
        missing = []
        offset = 0
        while monthly_date(plan.start_date, offset) <= through:
            scheduled_for = monthly_date(plan.start_date, offset)
            if scheduled_for not in existing:
                missing.append(UpcomingExpensePayment(
                    plan=plan, payment_type=plan.payment_type,
                    description=plan.description, amount=plan.amount,
                    scheduled_for=scheduled_for, due_date=scheduled_for,
                ))
            offset += 1
        if missing:
            UpcomingExpensePayment.objects.bulk_create(missing)


@transaction.atomic
def set_payment_paid(payment_id, paid, user):
    # Same lock order as generation/stop: plan first, then payment.
    plan_id = UpcomingExpensePayment.objects.values_list("plan_id", flat=True).get(pk=payment_id)
    UpcomingExpensePlan.objects.select_for_update().get(pk=plan_id)
    payment = UpcomingExpensePayment.objects.select_for_update().get(pk=payment_id)
    payment.is_paid = paid
    payment.paid_at = timezone.now() if paid else None
    payment.paid_by = user if paid else None
    payment.save(update_fields=["is_paid", "paid_at", "paid_by"])
    return payment
