"""Superuser-only expense planning, separate from invoices and accounting."""

from decimal import Decimal

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied, SuspiciousOperation
from django.core.paginator import Paginator
from django.db import IntegrityError, transaction
from django.db.models import Q, Sum
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_http_methods

from expenses.models import UpcomingExpensePayment, UpcomingExpensePlan
from expenses.upcoming_forms import (
    UpcomingExpenseForm, UpcomingFilterForm, UpcomingPaymentEditForm, UpcomingTypeForm,
)
from expenses.upcoming_services import ensure_installment, materialize_monthly_payments, set_payment_paid


def _positive_id(value):
    try:
        result = int(value)
        if result > 0:
            return result
    except (TypeError, ValueError):
        pass
    raise SuspiciousOperation("Invalid expense identifier.")


@login_required(login_url="/login/")
@require_http_methods(["GET", "POST"])
def expense_planner(request):
    if not request.user.is_active or not request.user.is_superuser:
        raise PermissionDenied("Access restricted. Expense Planner is available to superusers only.")

    today = timezone.localdate()
    create_form = UpcomingExpenseForm(initial={"start_date": today}, auto_id="new_%s")
    type_form = UpcomingTypeForm(prefix="type")
    edit_form = None
    edit_payment = None
    open_dialog = ""
    if request.method == "POST":
        action = request.POST.get("action")
        if action == "create":
            create_form = UpcomingExpenseForm(request.POST, auto_id="new_%s")
            if create_form.is_valid():
                with transaction.atomic():
                    plan = create_form.save(commit=False)
                    plan.created_by = request.user
                    plan.save()
                    ensure_installment(plan, plan.start_date)
                messages.success(request, "Payment added. Monthly installments keep their own paid status.")
            else:
                open_dialog = "addExpense"
        elif action == "create_type":
            type_form = UpcomingTypeForm(request.POST, prefix="type")
            if type_form.is_valid():
                try:
                    with transaction.atomic():
                        type_form.save()
                    messages.success(request, "Payment type added.")
                except IntegrityError:
                    type_form.add_error("name", "This payment type already exists.")
                    open_dialog = "addType"
            else:
                open_dialog = "addType"
        elif action == "paid":
            payment = get_object_or_404(UpcomingExpensePayment, pk=_positive_id(request.POST.get("payment_id")))
            desired = request.POST.get("paid")
            if desired not in ("yes", "no"):
                raise PermissionDenied("Invalid payment action.")
            set_payment_paid(payment.pk, desired == "yes", request.user)
            messages.success(request, "Payment marked paid." if desired == "yes" else "Payment restored to outstanding.")
        elif action == "edit":
            with transaction.atomic():
                edit_payment = get_object_or_404(
                    UpcomingExpensePayment.objects.select_for_update(),
                    pk=_positive_id(request.POST.get("payment_id")),
                )
                if edit_payment.is_paid:
                    messages.error(request, "Mark this payment unpaid before editing it.")
                else:
                    edit_form = UpcomingPaymentEditForm(request.POST, instance=edit_payment, prefix="edit")
                    if edit_form.is_valid():
                        edit_form.save()
                        messages.success(request, "Installment updated. Other months are unchanged.")
                    else:
                        open_dialog = "editExpense"
        elif action == "stop":
            with transaction.atomic():
                plan = get_object_or_404(
                    UpcomingExpensePlan.objects.select_for_update(),
                    pk=_positive_id(request.POST.get("plan_id")), frequency="monthly",
                )
                plan.is_active = False
                plan.save(update_fields=["is_active"])
            messages.success(request, "Monthly recurrence stopped. Existing payments remain in your list.")
        else:
            raise PermissionDenied("Invalid payment action.")
        if not open_dialog:
            query = request.GET.copy()
            query.pop("edit", None)
            return redirect(reverse("expense_planner") + ("?" + query.urlencode() if query else ""))

    materialize_monthly_payments(today)
    if request.GET.get("edit") and not edit_form:
        edit_payment = get_object_or_404(UpcomingExpensePayment, pk=_positive_id(request.GET["edit"]), is_paid=False)
        edit_form = UpcomingPaymentEditForm(instance=edit_payment, prefix="edit")
        open_dialog = "editExpense"

    filters = UpcomingFilterForm(request.GET)
    payments = UpcomingExpensePayment.objects.select_related("payment_type", "plan", "paid_by")
    if filters.is_valid():
        values = filters.cleaned_data
        status = values.get("status") or "unpaid"
        if status != "all":
            payments = payments.filter(is_paid=status == "paid")
        if values.get("payment_type"):
            payments = payments.filter(payment_type=values["payment_type"])
        if values.get("due_from"):
            payments = payments.filter(due_date__gte=values["due_from"])
        if values.get("due_to"):
            payments = payments.filter(due_date__lte=values["due_to"])
        if values.get("repeat"):
            payments = payments.filter(plan__frequency=values["repeat"])
        if values.get("overdue"):
            payments = payments.filter(is_paid=False, due_date__lt=today)
        if values.get("search"):
            payments = payments.filter(
                Q(description__icontains=values["search"]) |
                Q(payment_type__name__icontains=values["search"])
            )
        ordering = {"-due": "-due_date", "amount": "-amount"}.get(values.get("sort"), "due_date")
        payments = payments.order_by(ordering, "pk")
    else:
        payments = payments.none()

    totals = payments.aggregate(
        outstanding=Sum("amount", filter=Q(is_paid=False)),
        overdue_total=Sum("amount", filter=Q(is_paid=False, due_date__lt=today)),
        paid_total=Sum("amount", filter=Q(is_paid=True)),
    )
    totals = {key: value or Decimal("0.00") for key, value in totals.items()}
    query = request.GET.copy()
    query.pop("page", None)
    query.pop("edit", None)
    page = Paginator(payments, 50).get_page(request.GET.get("page"))
    return render(request, "expense_planner.html", {
        "create_form": create_form, "type_form": type_form, "edit_form": edit_form,
        "edit_payment": edit_payment, "filters": filters, "page": page,
        "totals": totals, "today": today, "filter_query": query.urlencode(),
        "plans": UpcomingExpensePlan.objects.filter(frequency="monthly", is_active=True).select_related("payment_type"),
        "open_dialog": open_dialog,
    })
