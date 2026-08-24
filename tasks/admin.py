from django.contrib import admin
from django import forms
from .admin_widgets import RichTextAdminWidget
from .models import (
    LeadTask, Payment, Supplier, ServiceType, Service,
    ClientMediaUploadLink, ClientMediaFile, PdfPolicy, BabylonHotelEntry,
)


@admin.register(LeadTask)
class LeadTaskAdmin(admin.ModelAdmin):
    list_display = ('id', 'lead', 'assigned_to', 'status', 'travel_date', 'created_at')
    list_filter = ('status', 'assigned_to')
    search_fields = ('lead__name', 'lead__phone', 'notes')
    autocomplete_fields = ('lead', 'assigned_to')
    date_hierarchy = 'created_at'
    list_per_page = 40
    fieldsets = (
        (None, {
            'fields': ('lead', 'assigned_to', 'status', 'payment', 'notes'),
        }),
        ('Travel', {
            'fields': ('travel_date', 'return_date', 'date_of_birth', 'passport_expiry_date'),
        }),
    )


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ('leadtask', 'date', 'amount', 'is_refund', 'is_checked', 'processed')
    list_filter = ('is_refund', 'is_checked', 'processed')
    search_fields = ('leadtask__lead__name',)
    autocomplete_fields = ('leadtask',)
    date_hierarchy = 'date'


@admin.register(Supplier)
class SupplierAdmin(admin.ModelAdmin):
    list_display = ("name", "is_active")
    search_fields = ("name",)
    list_filter = ("is_active",)


@admin.register(ServiceType)
class ServiceTypeAdmin(admin.ModelAdmin):
    list_display = ("name", "is_active")
    search_fields = ("name",)
    list_filter = ("is_active",)
    ordering = ("name",)


@admin.register(Service)
class ServiceAdmin(admin.ModelAdmin):
    list_display = ("service_name", "supplier", "leadtask", "due_time", "is_checked")
    search_fields = ("service_name", "supplier", "leadtask__lead__name")
    list_filter = ("is_checked", "send_to_client", "processed")
    autocomplete_fields = ("leadtask",)
    list_per_page = 40


@admin.register(BabylonHotelEntry)
class BabylonHotelEntryAdmin(admin.ModelAdmin):
    list_display = ("client_name", "service_type", "entry_date", "price", "due_date", "confirmation_number")
    search_fields = ("client_name", "service_type", "details", "confirmation_number")
    list_filter = ("entry_date",)
    raw_id_fields = ("service",)


class ClientMediaFileInline(admin.TabularInline):
    model = ClientMediaFile
    extra = 0
    readonly_fields = ("original_name", "file", "uploaded_at")


@admin.register(ClientMediaUploadLink)
class ClientMediaUploadLinkAdmin(admin.ModelAdmin):
    list_display = ("client_name", "leadtask", "created_at", "submitted_at", "is_active")
    search_fields = ("client_name", "leadtask__lead__name", "token")
    list_filter = ("is_active",)
    inlines = [ClientMediaFileInline]
    autocomplete_fields = ("leadtask",)


@admin.register(PdfPolicy)
class PdfPolicyAdmin(admin.ModelAdmin):
    class PdfPolicyForm(forms.ModelForm):
        class Meta:
            model = PdfPolicy
            fields = '__all__'
            widgets = {
                'content': RichTextAdminWidget(),
            }

    form = PdfPolicyForm
    list_display = (
        'title', 'is_active', 'sort_order',
        'show_on_client_invoice', 'show_on_internal_invoice',
    )
    list_filter = ('is_active',)
    list_editable = ('is_active', 'sort_order')
    search_fields = ('title',)
    fieldsets = (
        (None, {
            'fields': ('title', 'content', 'is_active', 'sort_order'),
        }),
        ('Show on PDFs', {
            'fields': (
                'show_on_client_invoice',
                'show_on_internal_invoice',
                'show_on_purchases_report',
                'show_on_client_payments_report',
                'show_on_travellers_report',
            ),
        }),
    )
