import uuid
from decimal import Decimal

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import ProtectedError
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_http_methods

from accounts_core.list_utils import parse_date
from accounts_core.export_names import export_filename, export_period_suffix
from accounts_core.pdf_utils import render_or_pdf
from auditlog.utils import log_audit
from expenses.category_forms import ExpenseCategoryForm
from expenses.forms import OperatingExpenseForm
from expenses.models import EmployeeSalaryEntry, EmployeeSalaryPayment, OperatingExpense, OperatingExpenseAttachment
from expenses.salary_forms import EmployeeSalaryEntryForm, SalaryPaymentForm
from expenses.salary_services import (
    entry_amount_due,
    entry_balance_due,
    entry_total_paid,
    parse_period,
    period_label,
    prepare_salary_entries,
    record_salary_payment,
    refresh_entry_status,
)
from purchases.models import ExpenseCategory


def _next_temp_expense_no():
    while True:
        candidate = f"TMP-OPEX-{uuid.uuid4().hex[:6].upper()}"
        if not OperatingExpense.objects.filter(expense_no=candidate).exists():
            return candidate


@login_required
def expense_list(request):
    from reporting.date_ranges import resolve_report_dates

    tab = (request.GET.get("tab") or "expenses").strip().lower()
    df, dt, _ = resolve_report_dates(request)
    year, month = parse_period(request.GET.get("payroll_month"))

    if tab == "salaries":
        salary_entries = (
            EmployeeSalaryEntry.objects.filter(period_year=year, period_month=month)
            .select_related("employee")
            .prefetch_related("payments__operating_expense")
            .order_by("employee__name")
        )
        rows = []
        for entry in salary_entries:
            due = entry_amount_due(entry)
            paid = entry_total_paid(entry)
            balance = entry_balance_due(entry)
            rows.append(
                {
                    "entry": entry,
                    "amount_due": due,
                    "total_paid": paid,
                    "balance_due": balance,
                }
            )
        return render(
            request,
            "expenses/expense_list.html",
            {
                "tab": "salaries",
                "salary_rows": rows,
                "payroll_year": year,
                "payroll_month": month,
                "payroll_month_value": period_label(year, month),
                "date_from": df,
                "date_to": dt,
                "categories": ExpenseCategory.objects.filter(is_active=True).order_by("code"),
            },
        )

    qs = (
        OperatingExpense.objects.select_related("category")
        .filter(salary_payment__isnull=True)
        .order_by("-expense_date", "-created_at")
    )
    if df:
        qs = qs.filter(expense_date__gte=df)
    if dt:
        qs = qs.filter(expense_date__lte=dt)
    cat = request.GET.get("category")
    if cat:
        qs = qs.filter(category_id=cat)
    return render_or_pdf(
        request,
        "expenses/expense_list.html",
        {
            "tab": "expenses",
            "expenses": qs[:500],
            "date_from": df,
            "date_to": dt,
            "categories": ExpenseCategory.objects.filter(is_active=True).order_by("code"),
            "selected_category": cat,
            "payroll_month_value": period_label(year, month),
            "pdf_report_title": "Operating Expenses",
        },
        export_filename("Operating_Expenses", export_period_suffix(df, dt)),
    )


@login_required
def expense_create(request):
    from datetime import date

    expense = OperatingExpense(expense_no=_next_temp_expense_no())
    if request.method == "POST":
        form = OperatingExpenseForm(request.POST, instance=expense)
        if form.is_valid():
            exp = form.save(commit=False)
            exp.expense_no = expense.expense_no
            exp.recalc_usd()
            exp.save()
            _save_attachments(request, exp)
            messages.success(request, f"Expense {exp.expense_no} created.")
            return redirect("expenses:expense_edit", expense_id=exp.id)
    else:
        form = OperatingExpenseForm(instance=expense, initial={"expense_date": date.today()})
    return render(
        request,
        "expenses/expense_form.html",
        {"form": form, "expense": expense, "attachments": [], "is_edit": False},
    )


@login_required
def expense_edit(request, expense_id):
    expense = get_object_or_404(OperatingExpense, pk=expense_id)
    if expense.status != OperatingExpense.Status.DRAFT:
        messages.warning(request, "Only draft expenses can be edited.")
        return redirect("expenses:expense_list")
    if request.method == "POST":
        form = OperatingExpenseForm(request.POST, instance=expense)
        if form.is_valid():
            exp = form.save(commit=False)
            exp.recalc_usd()
            exp.save()
            _save_attachments(request, exp)
            messages.success(request, f"Expense {exp.expense_no} updated.")
            return redirect("expenses:expense_edit", expense_id=exp.id)
    else:
        form = OperatingExpenseForm(instance=expense)
    return render(
        request,
        "expenses/expense_form.html",
        {
            "form": form,
            "expense": expense,
            "attachments": expense.attachments.all(),
            "is_edit": True,
        },
    )


def _save_attachments(request, expense):
    files = request.FILES.getlist("attachments")
    for f in files:
        if f.size > 10 * 1024 * 1024:
            messages.warning(request, f"Skipped {f.name}: file exceeds 10 MB.")
            continue
        OperatingExpenseAttachment.objects.create(
            expense=expense,
            file=f,
            original_name=f.name,
        )


@login_required
@require_http_methods(["POST"])
def expense_delete_attachment(request, expense_id, attachment_id):
    expense = get_object_or_404(OperatingExpense, pk=expense_id, status=OperatingExpense.Status.DRAFT)
    att = get_object_or_404(OperatingExpenseAttachment, pk=attachment_id, expense=expense)
    att.file.delete(save=False)
    att.delete()
    messages.success(request, "Attachment removed.")
    return redirect("expenses:expense_edit", expense_id=expense.id)


@login_required
def post_expense(request, expense_id):
    expense = get_object_or_404(OperatingExpense, pk=expense_id)
    try:
        expense.post(request.user)
        log_audit("POST_OPERATING_EXPENSE", expense, actor=request.user)
        messages.success(request, f"Expense {expense.expense_no} posted.")
    except Exception as exc:
        messages.error(request, str(exc))
    return redirect("expenses:expense_list")


@login_required
@require_http_methods(["POST"])
def void_expense(request, expense_id):
    expense = get_object_or_404(OperatingExpense, pk=expense_id)
    reason = request.POST.get("reason") or "Manual void"
    if expense.status != OperatingExpense.Status.POSTED:
        messages.error(request, "Only posted expenses can be voided.")
    else:
        from django.utils import timezone

        expense.status = OperatingExpense.Status.VOIDED
        expense.void_reason = reason
        expense.voided_at = timezone.now()
        expense.save()
        messages.success(request, f"Expense {expense.expense_no} voided.")
    return redirect("expenses:expense_list")


@login_required
def expense_category_list(request):
    qs = ExpenseCategory.objects.order_by("code")
    if request.GET.get("show_inactive") != "1":
        qs = qs.filter(is_active=True)
    return render(
        request,
        "expenses/category_list.html",
        {"categories": qs},
    )


@login_required
def expense_category_create(request):
    if request.method == "POST":
        form = ExpenseCategoryForm(request.POST)
        if form.is_valid():
            cat = form.save()
            messages.success(request, f"Category {cat.name} created.")
            return redirect("expenses:expense_category_edit", category_id=cat.id)
    else:
        form = ExpenseCategoryForm(initial={"is_active": True})
    return render(
        request,
        "expenses/category_form.html",
        {"form": form, "category": None, "is_edit": False},
    )


@login_required
def expense_category_edit(request, category_id):
    category = get_object_or_404(ExpenseCategory, pk=category_id)
    if request.method == "POST":
        form = ExpenseCategoryForm(request.POST, instance=category)
        if form.is_valid():
            form.save()
            messages.success(request, f"Category {category.name} updated.")
            return redirect("expenses:expense_category_list")
    else:
        form = ExpenseCategoryForm(instance=category)
    return render(
        request,
        "expenses/category_form.html",
        {"form": form, "category": category, "is_edit": True},
    )


@login_required
@require_http_methods(["POST"])
def expense_category_deactivate(request, category_id):
    category = get_object_or_404(ExpenseCategory, pk=category_id)
    category.is_active = False
    category.save(update_fields=["is_active"])
    messages.success(request, f"Category {category.name} deactivated.")
    return redirect("expenses:expense_category_list")


@login_required
@require_http_methods(["POST"])
def expense_category_delete(request, category_id):
    category = get_object_or_404(ExpenseCategory, pk=category_id)
    try:
        name = category.name
        category.delete()
        messages.success(request, f"Category {name} deleted.")
        return redirect("expenses:expense_category_list")
    except ProtectedError:
        messages.error(request, "Cannot delete: category is used on expenses. Deactivate instead.")
        return redirect("expenses:expense_category_edit", category_id=category_id)


@login_required
@require_http_methods(["POST"])
def expense_category_quick_create(request):
    import json

    from django.http import JsonResponse

    try:
        payload = json.loads(request.body.decode("utf-8") or "{}")
    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON."}, status=400)

    code = (payload.get("code") or "").strip().upper()
    name = (payload.get("name") or "").strip()
    if not code or not name:
        return JsonResponse({"error": "Code and name are required."}, status=400)
    if ExpenseCategory.objects.filter(code=code).exists():
        return JsonResponse({"error": f"Category code {code} already exists."}, status=400)

    cat = ExpenseCategory.objects.create(code=code, name=name, is_active=True)
    return JsonResponse({"id": str(cat.id), "code": cat.code, "name": cat.name})


@login_required
@require_http_methods(["POST"])
def salary_prepare_month(request):
    year, month = parse_period(request.POST.get("payroll_month"))
    created, skipped = prepare_salary_entries(year, month)
    messages.success(
        request,
        f"Payroll {period_label(year, month)}: {created} row(s) created, {skipped} already existed.",
    )
    return redirect(
        f"{reverse('expenses:expense_list')}?tab=salaries&payroll_month={period_label(year, month)}"
    )


@login_required
def salary_entry_edit(request, entry_id):
    from datetime import date

    entry = get_object_or_404(EmployeeSalaryEntry.objects.select_related("employee"), pk=entry_id)
    if entry.status == EmployeeSalaryEntry.Status.SETTLED and entry_total_paid(entry) >= entry_amount_due(entry):
        messages.info(request, "This salary row is fully settled. Adjust amounts only if you need to correct data before another payment.")

    if request.method == "POST" and "save_entry" in request.POST:
        form = EmployeeSalaryEntryForm(request.POST, instance=entry)
        payment_form = SalaryPaymentForm(entry=entry, initial={"payment_date": date.today()})
        if form.is_valid():
            form.save()
            refresh_entry_status(entry)
            messages.success(request, f"Updated salary row for {entry.employee.name}.")
            return redirect("expenses:salary_entry_edit", entry_id=entry.id)
    elif request.method == "POST" and "record_payment" in request.POST:
        form = EmployeeSalaryEntryForm(instance=entry)
        payment_form = SalaryPaymentForm(request.POST, entry=entry)
        if payment_form.is_valid():
            try:
                payment = record_salary_payment(
                    entry,
                    amount=payment_form.cleaned_data["amount"],
                    payment_date=payment_form.cleaned_data["payment_date"],
                    notes=payment_form.cleaned_data.get("notes") or "",
                    user=request.user,
                )
                log_audit("POST_SALARY_PAYMENT", payment, actor=request.user)
                messages.success(
                    request,
                    f"Recorded payment of {payment.amount} USD → expense {payment.operating_expense.expense_no}.",
                )
                return redirect(
                    f"{reverse('expenses:expense_list')}?tab=salaries&payroll_month={period_label(entry.period_year, entry.period_month)}"
                )
            except Exception as exc:
                messages.error(request, str(exc))
    else:
        form = EmployeeSalaryEntryForm(instance=entry)
        payment_form = SalaryPaymentForm(entry=entry, initial={"payment_date": date.today()})

    due = entry_amount_due(entry)
    paid = entry_total_paid(entry)
    return render(
        request,
        "expenses/salary_entry_form.html",
        {
            "entry": entry,
            "form": form,
            "payment_form": payment_form,
            "amount_due": due,
            "total_paid": paid,
            "balance_due": entry_balance_due(entry),
            "payments": entry.payments.select_related("operating_expense").all(),
        },
    )
