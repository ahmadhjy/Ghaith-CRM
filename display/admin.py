from django.contrib import admin
from django.utils import timezone
from django import forms
from .models import Lead, Destination, DailyReport, MonthlyTarget, Offer, UserMonthlyTarget, Department, CrmUserProfile, SophiaSyncState
from django.db.models import Q, Sum
from django.contrib.auth.admin import UserAdmin
from django.contrib.auth.models import User
from accounts_core.models import UserProfile

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
    search_fields = ['name', 'destination', 'phone', 'external_id']
    list_display = ['name', 'status', 'department', 'assigned_to', 'phone', 'sold', 'lost', 'last_modified']
    list_filter = ['status', 'department', 'sold', 'lost', 'assigned_to', IsOverdueFilter, TakeoverFilter]
    ordering = ['-last_modified']
    list_per_page = 40
    date_hierarchy = 'last_modified'
    autocomplete_fields = ['assigned_to', 'department']
    readonly_fields = ['created_at', 'last_modified', 'assigned_at', 'takeover_added_at', 'last_sync_at']
    exclude = ['attachments']
    fieldsets = (
        ('Contact', {
            'fields': ('name', 'phone', 'country_code', 'email', 'channel'),
        }),
        ('Pipeline', {
            'fields': (
                'status', 'department', 'assigned_to', 'destination', 'type_of_service',
                'sold', 'lost', 'urgent', 'follow_up',
            ),
        }),
        ('WhatsApp / Sophia', {
            'fields': (
                'external_id', 'whatsapp_received_on', 'chat_summary',
                'last_customer_message_at', 'last_agent_action_at',
                'status_changed_at', 'last_sync_at',
            ),
        }),
        ('Trip details', {
            'classes': ('collapse',),
            'fields': (
                'pax', 'duration', 'travel_date_from', 'travel_date_to', 'travel_dates_flexible',
                'reason_of_travel', 'why_this_destination', 'budget_range_from', 'budget_range_to',
                'special_request', 'date_notes', 'supplier',
            ),
        }),
        ('Pricing', {
            'classes': ('collapse',),
            'fields': ('selling_price', 'net', 'profit', 'finalization_notes'),
        }),
        ('Assignment & takeover', {
            'classes': ('collapse',),
            'fields': (
                'assignment_notes', 'takeover', 'special_takeover', 'takeover_added_at',
                'assigned_at', 'period', 'is_archived',
                'offer_prepared', 'offer_details', 'moved_to_negotiation',
            ),
        }),
        ('Timestamps', {
            'classes': ('collapse',),
            'fields': ('created_at', 'last_modified'),
        }),
    )

    def is_overdue(self, obj):
        return obj.is_overdue
    is_overdue.boolean = True


class DepartmentAdmin(admin.ModelAdmin):
    list_display = ['name', 'code', 'is_active', 'sort_order']
    list_filter = ['is_active']
    ordering = ['sort_order', 'name']
    search_fields = ['name', 'code']


class CrmUserProfileInline(admin.StackedInline):
    model = CrmUserProfile
    can_delete = False
    fk_name = 'user'
    verbose_name_plural = 'CRM profile'
    fields = ('department', 'receives_lead_assignments', 'sophia_agent_id')

class DailyReportAdmin(admin.ModelAdmin):
    search_fields = ['user__username', 'date']
    list_display = ['user', 'date', 'created_at']
    list_filter = ['date', 'user__username']
    ordering = ['-created_at']

class OfferAdmin(admin.ModelAdmin):
    search_fields = ['title', 'lead__name', 'created_by__username']
    list_display = ['title', 'lead', 'created_by', 'created_at', 'sent', 'sold']
    list_filter = ['sent', 'sold']
    ordering = ['-created_at']
    autocomplete_fields = ['lead', 'created_by']
    list_per_page = 40

class MonthPickerWidget(forms.DateInput):
    input_type = "month"
    format = "%Y-%m"

    def format_value(self, value):
        if value is None:
            return ""
        if hasattr(value, "strftime"):
            return value.strftime("%Y-%m")
        return value


class MonthlyTargetMonthForm(forms.ModelForm):
    month = forms.DateField(
        widget=MonthPickerWidget(),
        input_formats=["%Y-%m", "%Y-%m-%d"],
        help_text="Pick the month (including upcoming months). Stored as the 1st of that month.",
    )

    def clean_month(self):
        value = self.cleaned_data.get("month")
        if value:
            return value.replace(day=1)
        return value


class MonthlyTargetForm(MonthlyTargetMonthForm):
    class Meta:
        model = MonthlyTarget
        fields = "__all__"


class UserMonthlyTargetForm(MonthlyTargetMonthForm):
    class Meta:
        model = UserMonthlyTarget
        fields = "__all__"


class MonthlyTargetAdmin(admin.ModelAdmin):
    form = MonthlyTargetForm
    list_display = ["month", "target_profit"]
    ordering = ["-month"]


class UserMonthlyTargetAdmin(admin.ModelAdmin):
    form = UserMonthlyTargetForm
    search_fields = ["user__username", "month"]
    list_display = ["user", "month", "target_profit"]
    list_filter = ["user__username", "month"]
    ordering = ["-month"]
    autocomplete_fields = ["user"]

class UserProfileInline(admin.StackedInline):
    model = UserProfile
    can_delete = False
    fk_name = 'user'
    verbose_name_plural = 'Accounting profile'
    fields = ('is_main_accountant', 'is_accountant')


class CustomUserAdmin(UserAdmin):
    inlines = list(getattr(UserAdmin, 'inlines', ()) or ()) + [UserProfileInline, CrmUserProfileInline]
    list_display = UserAdmin.list_display + ('is_sales', 'administration')
    list_filter = UserAdmin.list_filter + ('is_sales', 'administration')
    fieldsets = UserAdmin.fieldsets + (
        ('CRM roles', {'fields': ('is_sales', 'administration')}),
    )

class DestinationAdmin(admin.ModelAdmin):
    search_fields = ["name"]

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        from display.destinations import ensure_crm_destination

        ensure_crm_destination(obj.name)


admin.site.register(Lead, LeadAdmin)
admin.site.register(Department, DepartmentAdmin)
admin.site.register(Destination, DestinationAdmin)
admin.site.register(DailyReport, DailyReportAdmin)
admin.site.register(MonthlyTarget, MonthlyTargetAdmin)
admin.site.register(UserMonthlyTarget, UserMonthlyTargetAdmin)
admin.site.register(Offer, OfferAdmin)
admin.site.unregister(User)
admin.site.register(User, CustomUserAdmin)


@admin.register(SophiaSyncState)
class SophiaSyncStateAdmin(admin.ModelAdmin):
    list_display = ['last_pull_at', 'last_run_at', 'last_status']
    readonly_fields = ['last_run_at', 'last_status', 'last_message']
    fields = ('last_pull_at', 'last_run_at', 'last_status', 'last_message')

    def has_add_permission(self, request):
        return not SophiaSyncState.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False

admin.site.site_header = "Ghaith Travel Administration"
