from django.contrib import admin

from accounting_bridge.models import (
    AccountingConfig,
    CrmDestinationLink,
    CrmEmployeeLink,
    CrmServiceTypeLink,
    CrmSupplierLink,
    InvoiceSyncQueue,
    LeadClientLink,
    PartyOpeningBalance,
)
from accounting_bridge.permissions import user_can_access_accounting_admin


class AccountingAdminMixin:
    def has_module_permission(self, request):
        return user_can_access_accounting_admin(request.user)

    def has_view_permission(self, request, obj=None):
        return user_can_access_accounting_admin(request.user)

    def has_add_permission(self, request):
        return user_can_access_accounting_admin(request.user)

    def has_change_permission(self, request, obj=None):
        return user_can_access_accounting_admin(request.user)

    def has_delete_permission(self, request, obj=None):
        return user_can_access_accounting_admin(request.user)


@admin.register(AccountingConfig)
class AccountingConfigAdmin(AccountingAdminMixin, admin.ModelAdmin):
    list_display = ('invoice_sync_from', 'master_data_sync_enabled', 'updated_at')

    def has_add_permission(self, request):
        if AccountingConfig.objects.exists():
            return False
        return super().has_add_permission(request)


@admin.register(LeadClientLink)
class LeadClientLinkAdmin(AccountingAdminMixin, admin.ModelAdmin):
    list_display = ('lead', 'client', 'phone_key', 'synced_at')
    search_fields = ('lead__name', 'client__name_en', 'phone_key')
    autocomplete_fields = ('lead', 'client')


@admin.register(CrmSupplierLink)
class CrmSupplierLinkAdmin(AccountingAdminMixin, admin.ModelAdmin):
    list_display = ('crm_supplier', 'acc_supplier', 'synced_at')
    autocomplete_fields = ('crm_supplier', 'acc_supplier')


@admin.register(CrmDestinationLink)
class CrmDestinationLinkAdmin(AccountingAdminMixin, admin.ModelAdmin):
    list_display = ('destination_name', 'acc_destination', 'synced_at')
    search_fields = ('destination_name',)


@admin.register(CrmServiceTypeLink)
class CrmServiceTypeLinkAdmin(AccountingAdminMixin, admin.ModelAdmin):
    list_display = ('crm_service_type', 'acc_service_type', 'synced_at')


@admin.register(CrmEmployeeLink)
class CrmEmployeeLinkAdmin(AccountingAdminMixin, admin.ModelAdmin):
    list_display = ('user', 'employee', 'synced_at')
    autocomplete_fields = ('user', 'employee')


@admin.register(PartyOpeningBalance)
class PartyOpeningBalanceAdmin(AccountingAdminMixin, admin.ModelAdmin):
    list_display = ('party_type', 'client', 'supplier', 'debit_usd', 'credit_usd', 'amount_usd', 'as_of_date', 'created_by')
    list_filter = ('party_type',)
    autocomplete_fields = ('client', 'supplier', 'created_by')


@admin.register(InvoiceSyncQueue)
class InvoiceSyncQueueAdmin(AccountingAdminMixin, admin.ModelAdmin):
    list_display = ('leadtask', 'status', 'sales_invoice', 'reviewed_by', 'reviewed_at', 'created_at')
    list_filter = ('status',)
    search_fields = ('leadtask__lead__name', 'sales_invoice__invoice_no')
    readonly_fields = ('created_at', 'last_crm_snapshot_at', 'reviewed_at')
