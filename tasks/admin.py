from django.contrib import admin
from .models import (
    Task, LeadTask, Payment, Tag, Supplier, ServiceType, Service,
    ClientMediaUploadLink, ClientMediaFile,
)

admin.site.register(Task)
admin.site.register(Tag)
admin.site.register(LeadTask)


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


@admin.register(Service)
class ServiceAdmin(admin.ModelAdmin):
    list_display = ("service_name", "supplier", "leadtask", "due_time", "is_checked", "send_to_client", "processed")
    search_fields = ("service_name", "supplier", "leadtask__lead__name")
    list_filter = ("is_checked", "send_to_client", "processed")


class ClientMediaFileInline(admin.TabularInline):
    model = ClientMediaFile
    extra = 0
    readonly_fields = ("original_name", "file", "uploaded_at")


@admin.register(ClientMediaUploadLink)
class ClientMediaUploadLinkAdmin(admin.ModelAdmin):
    list_display = ("client_name", "leadtask", "created_at", "submitted_at", "is_active")
    search_fields = ("client_name", "leadtask__lead__name", "token")
    list_filter = ("is_active", "submitted_at")
    inlines = [ClientMediaFileInline]