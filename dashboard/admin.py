from django.contrib import admin
from .models import Event


@admin.register(Event)
class EventAdmin(admin.ModelAdmin):
    list_display = ('title', 'user', 'when', 'event_type')
    list_filter = ('event_type',)
    search_fields = ('title', 'description', 'user__username')
    autocomplete_fields = ('user',)
    date_hierarchy = 'when'
