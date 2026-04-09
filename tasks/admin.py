from django.contrib import admin
from .models import Task, LeadTask, Payment, Tag, Supplier, Service

admin.site.register(Task)
admin.site.register(Tag)
admin.site.register(LeadTask)


@admin.register(Supplier)
class SupplierAdmin(admin.ModelAdmin):
    list_display = ("name", "is_active")
    search_fields = ("name",)
    list_filter = ("is_active",)


@admin.register(Service)
class ServiceAdmin(admin.ModelAdmin):
    list_display = ("service_name", "supplier", "leadtask", "due_time", "is_checked", "processed")
    search_fields = ("service_name", "supplier", "leadtask__lead__name")
    list_filter = ("is_checked", "processed")