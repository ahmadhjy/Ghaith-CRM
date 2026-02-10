from django.contrib import admin
from django.utils import timezone
from .models import Lead, Destination, DailyReport, MonthlyTarget, Offer, UserMonthlyTarget
from django.db.models import Q, Sum
from django.contrib.auth.admin import UserAdmin
from django.contrib.auth.models import User

class IsOverdueFilter(admin.SimpleListFilter):
    title = 'overdue'
    parameter_name = 'is_overdue'

    def lookups(self, request, model_admin):
        return (
            ('Yes', 'Yes'),
            ('No', 'No'),
        )

    def queryset(self, request, queryset):
        if self.value() == 'Yes':
            return queryset.filter(
                status_changed_at__isnull=False,
                status__in=['processing', 'negotiation'],
                status_changed_at__lte=timezone.now() - timezone.timedelta(minutes=Lead.period.field.default)
            )
        if self.value() == 'No':
            return queryset.filter(
                Q(status_changed_at__isnull=True) |
                Q(status__in=['done', 'finalized', 'onhold']) |
                Q(status_changed_at__gt=timezone.now() - timezone.timedelta(minutes=Lead.period.field.default))
            )
        return queryset

class OnHoldNotTakeoverFilter(admin.SimpleListFilter):
    title = 'On Hold and Not Takeover'
    parameter_name = 'on_hold_not_takeover'

    def lookups(self, request, model_admin):
        return (
            ('Yes', 'Yes'),
            ('No', 'No'),
        )

    def queryset(self, request, queryset):
        if self.value() == 'Yes':
            return queryset.filter(
                status='onhold',
                takeover=False
            )
        if self.value() == 'No':
            return queryset.exclude(
                status='onhold',
                takeover=False
            )
        return queryset

class TakeoverFilter(admin.SimpleListFilter):
    title = 'Takeover'
    parameter_name = 'takeover'

    def lookups(self, request, model_admin):
        return (
            ('Yes', 'Yes'),
            ('No', 'No'),
        )

    def queryset(self, request, queryset):
        if self.value() == 'Yes':
            return queryset.filter(takeover=True)
        if self.value() == 'No':
            return queryset.filter(takeover=False)
        return queryset

class LeadAdmin(admin.ModelAdmin):
    search_fields = ['name', 'destination', 'phone']
    list_display = ['__str__', 'status', 'destination', 'phone',
                    'assigned_to', 'finalization_notes',
                    'created_at', 'last_modified', 'is_overdue', 'takeover_added_at']
    list_filter = ['assigned_to__username', 'type_of_service',
                   'status', 'sold', 'lost', IsOverdueFilter, OnHoldNotTakeoverFilter, TakeoverFilter]
    ordering = ['-last_modified']

    exclude = ['attachments', 'assignment_notes']

    def is_overdue(self, obj):
        return obj.is_overdue
    is_overdue.boolean = True  # Displays a tick or cross icon

class DailyReportAdmin(admin.ModelAdmin):
    search_fields = ['user__username', 'date']
    list_display = ['user', 'date', 'created_at']
    list_filter = ['date', 'user__username']
    ordering = ['-created_at']

class OfferAdmin(admin.ModelAdmin):
    search_fields = ['title', 'lead__name', 'created_by__username']
    list_display = ['title', 'lead', 'created_by', 'created_at', 'sent', 'sold']
    list_filter = ['sent', 'sold', 'created_by__username']
    ordering = ['-created_at']

class UserMonthlyTargetAdmin(admin.ModelAdmin):
    search_fields = ['user__username', 'month']
    list_display = ['user', 'month', 'target_profit']
    list_filter = ['user__username', 'month']
    ordering = ['-month']

class CustomUserAdmin(UserAdmin):
    fieldsets = UserAdmin.fieldsets + (
        (None, {'fields': ('is_sales',)}),
    )

admin.site.register(Lead, LeadAdmin)
admin.site.register(Destination)
admin.site.register(DailyReport, DailyReportAdmin)
admin.site.register(MonthlyTarget)
admin.site.register(UserMonthlyTarget, UserMonthlyTargetAdmin)
admin.site.register(Offer, OfferAdmin)
admin.site.unregister(User)
admin.site.register(User, CustomUserAdmin)

admin.site.site_header = "Ghaith Travel Administration"
