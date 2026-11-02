"""Standalone payment tracker. Never posts accounting expenses automatically."""

from calendar import monthrange
from datetime import date

from django.db import transaction
from django.core.exceptions import ValidationError
from decimal import Decimal, InvalidOperation
from uuid import UUID
from django.utils import timezone

from expenses.models import UpcomingExpensePayment, UpcomingExpensePlan, UpcomingExpenseReceipt


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
def materialize_monthly_payments(today=None, *, plan_id=None):
    """Accrue installments through this month, regardless of older unpaid rows."""
    today = today or timezone.localdate()
    through = today.replace(day=monthrange(today.year, today.month)[1])
    plans = UpcomingExpensePlan.objects.select_for_update().filter(
        frequency=UpcomingExpensePlan.Frequency.MONTHLY, is_active=True, is_deleted=False,
        start_date__lte=through,
    ).select_related("payment_type")
    if plan_id is not None:
        plans = plans.filter(pk=plan_id)
    for plan in plans:
        existing = {(d.year, d.month) for d in plan.payments.values_list("scheduled_for", flat=True)}
        missing = []
        offset = 0
        while monthly_date(plan.start_date, offset) <= through:
            scheduled_for = monthly_date(plan.start_date, offset)
            if (scheduled_for.year, scheduled_for.month) not in existing:
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
    payment = UpcomingExpensePayment.objects.select_for_update().get(pk=payment_id, is_deleted=False)
    if paid and payment.balance:
        UpcomingExpenseReceipt.objects.create(payment=payment, amount=payment.balance, recorded_by=user)
    if not paid:
        payment.receipts.filter(is_reversed=False).update(is_reversed=True)
    payment.amount_paid = payment.amount if paid else Decimal("0.00")
    payment.is_paid = paid
    payment.paid_at = timezone.now() if paid else None
    payment.paid_by = user if paid else None
    payment.save(update_fields=["amount_paid", "is_paid", "paid_at", "paid_by"])
    return payment


@transaction.atomic
def record_partial_payment(payment_id, raw_amount, user, request_id=None):
    plan_id = UpcomingExpensePayment.objects.values_list("plan_id", flat=True).get(pk=payment_id)
    UpcomingExpensePlan.objects.select_for_update().get(pk=plan_id)
    payment = UpcomingExpensePayment.objects.select_for_update().get(pk=payment_id, is_deleted=False)
    if request_id:
        try:
            request_id = UUID(str(request_id))
        except ValueError:
            raise ValidationError("Invalid payment request. Reload the page and try again.")
        previous = UpcomingExpenseReceipt.objects.filter(request_id=request_id).first()
        if previous:
            if previous.payment_id != payment.pk:
                raise ValidationError("This request was already used. Reload the page.")
            return payment
    try:
        amount = Decimal(raw_amount)
        valid = amount.is_finite() and amount > 0 and amount <= payment.balance and amount == amount.quantize(Decimal(".01"))
    except (InvalidOperation, TypeError, ValueError):
        valid = False
    if not valid:
        raise ValidationError("Enter a positive payment with up to two decimals, no more than the remaining balance.")
    UpcomingExpenseReceipt.objects.create(payment=payment, amount=amount, recorded_by=user, request_id=request_id)
    payment.amount_paid += amount
    payment.is_paid = payment.balance == 0
    payment.paid_at = timezone.now() if payment.is_paid else None
    payment.paid_by = user if payment.is_paid else None
    payment.save(update_fields=["amount_paid", "is_paid", "paid_at", "paid_by"])
    return payment


@transaction.atomic
def update_expense_plan(plan_id, values, today=None):
    plan = UpcomingExpensePlan.objects.select_for_update().get(pk=plan_id, is_deleted=False)
    for field in ("payment_type", "description", "amount", "start_date", "frequency"):
        setattr(plan, field, values[field])
    plan.save()
    today = today or timezone.localdate()
    through = today.replace(day=monthrange(today.year, today.month)[1])
    for payment in plan.payments.select_for_update().all():
        # Never rewrite payments already made or deliberately deleted installments.
        if payment.amount_paid or payment.is_paid or payment.is_deleted:
            continue
        offset = (payment.scheduled_for.year-plan.start_date.year)*12 + payment.scheduled_for.month-plan.start_date.month
        due = monthly_date(plan.start_date, offset) if offset >= 0 else None
        wanted = due is not None and (
            (plan.frequency == "monthly" and (due <= through or due == plan.start_date))
            or (plan.frequency == "once" and due == plan.start_date)
        )
        if not wanted:
            payment.is_deleted = True
        else:
            payment.scheduled_for = due
            payment.due_date = due
            payment.amount = plan.amount
            payment.description = plan.description
            payment.payment_type = plan.payment_type
        payment.save()
    # A paid or deleted occurrence in the starting month must not be duplicated.
    if not plan.payments.filter(scheduled_for__year=plan.start_date.year, scheduled_for__month=plan.start_date.month).exists():
        ensure_installment(plan, plan.start_date)
    materialize_monthly_payments(today, plan_id=plan.pk)
    return plan


@transaction.atomic
def delete_expense(payment_id=None, plan_id=None):
    if payment_id:
        plan_id = UpcomingExpensePayment.objects.values_list("plan_id", flat=True).get(pk=payment_id)
    plan = UpcomingExpensePlan.objects.select_for_update().get(pk=plan_id, is_deleted=False)
    payments = plan.payments.select_for_update().filter(is_deleted=False)
    if payment_id:
        payments = payments.filter(pk=payment_id)
    if payments.filter(amount_paid__gt=0).exists():
        raise ValidationError("This expense has payment history. Restore it to unpaid before deleting, or stop recurrence to keep the history.")
    payments.update(is_deleted=True)
    if not payment_id or plan.frequency == "once":
        plan.is_active = False
        plan.is_deleted = True
        plan.save(update_fields=["is_active", "is_deleted"])
