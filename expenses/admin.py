from django.contrib import admin

from expenses.models import (
    EmployeeSalaryEntry,
    EmployeeSalaryPayment,
    OperatingExpense,
    OperatingExpenseAttachment,
    UpcomingExpenseType, UpcomingExpensePlan, UpcomingExpensePayment,
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


class SuperuserExpenseAdmin(admin.ModelAdmin):
    def has_module_permission(self, request):
        return request.user.is_active and request.user.is_superuser

    def has_view_permission(self, request, obj=None):
        return self.has_module_permission(request)

    def has_add_permission(self, request):
        return self.has_module_permission(request)

    def has_change_permission(self, request, obj=None):
        return self.has_module_permission(request)

    def has_delete_permission(self, request, obj=None):
        return self.has_module_permission(request)


@admin.register(UpcomingExpenseType)
class UpcomingExpenseTypeAdmin(SuperuserExpenseAdmin):
    search_fields = ("name",)


@admin.register(UpcomingExpensePlan)
class UpcomingExpensePlanAdmin(SuperuserExpenseAdmin):
    list_display = ("payment_type", "amount", "start_date", "frequency", "is_active")
    list_filter = ("frequency", "is_active", "payment_type")
    readonly_fields = ("created_by", "created_at", "start_date", "frequency", "payment_type", "amount", "description", "is_deleted")

    def has_add_permission(self, request):
        return False  # Use the planner to create the first installment atomically.

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(UpcomingExpensePayment)
class UpcomingExpensePaymentAdmin(SuperuserExpenseAdmin):
    list_display = ("payment_type", "description", "amount", "due_date", "is_paid")
    list_filter = ("is_paid", "payment_type")
    readonly_fields = ("plan", "scheduled_for", "is_paid", "amount_paid", "is_deleted", "paid_at", "paid_by", "created_at")

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def get_readonly_fields(self, request, obj=None):
        if obj and obj.is_paid:
            return self.readonly_fields + ("payment_type", "amount", "description", "due_date")
        return self.readonly_fields
