from django.contrib import admin
from auditlog.models import AuditEvent, DocumentEventLog


@admin.register(AuditEvent)
class AuditEventAdmin(admin.ModelAdmin):
    list_display = ('when', 'who', 'action', 'model', 'object_id')
    list_filter = ('action', 'model')
    search_fields = ('action', 'model', 'object_id', 'reason')
    date_hierarchy = 'when'
    readonly_fields = ('id', 'who', 'when', 'action', 'model', 'object_id', 'before_json', 'after_json', 'reason', 'request_id', 'ip')

    def has_add_permission(self, request):
        return False


@admin.register(DocumentEventLog)
class DocumentEventLogAdmin(admin.ModelAdmin):
    list_display = ('created_at', 'event_type', 'model', 'object_id', 'actor')
    list_filter = ('event_type', 'model')
    search_fields = ('model', 'object_id')
    date_hierarchy = 'created_at'
    readonly_fields = ('id', 'event_type', 'model', 'object_id', 'actor', 'created_at', 'metadata')

    def has_add_permission(self, request):
        return False
