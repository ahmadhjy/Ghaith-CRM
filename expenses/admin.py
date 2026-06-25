from django.contrib import admin

from expenses.models import (
    EmployeeSalaryEntry,
    EmployeeSalaryPayment,
    OperatingExpense,
    OperatingExpenseAttachment,
)


class OperatingExpenseAttachmentInline(admin.TabularInline):
    model = OperatingExpenseAttachment
    extra = 0


@admin.register(OperatingExpense)
class OperatingExpenseAdmin(admin.ModelAdmin):
    list_display = ("expense_no", "category", "expense_date", "amount", "amount_usd", "currency", "status")
    list_filter = ("status", "category", "currency")
    inlines = [OperatingExpenseAttachmentInline]


@admin.register(EmployeeSalaryEntry)
class EmployeeSalaryEntryAdmin(admin.ModelAdmin):
    list_display = ("employee", "period_year", "period_month", "base_salary", "bonus", "status")
    list_filter = ("status", "period_year", "period_month")


@admin.register(EmployeeSalaryPayment)
class EmployeeSalaryPaymentAdmin(admin.ModelAdmin):
    list_display = ("entry", "amount", "payment_date", "operating_expense", "posted_at")
