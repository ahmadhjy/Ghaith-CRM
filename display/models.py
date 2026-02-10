from django.db import models
from django.contrib.auth.models import User
from tasks.models import LeadTask
from django.utils import timezone
import re

class Attachment(models.Model):
    attachment_name = models.CharField(max_length=100, blank=True)
    file = models.FileField(upload_to='static/attachments/%Y/%m/%d/')
    uploaded_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.attachment_name

class Destination(models.Model):
    name = models.CharField(max_length=200, unique=True)

    def __str__(self):
        return self.name

class Lead(models.Model):
    reason_of_travel = models.TextField(blank=True, null=True)
    why_this_destination = models.TextField(blank=True, null=True)
    travel_dates_flexible = models.BooleanField(blank=True, default=False)
    budget_range_from = models.PositiveIntegerField(blank=True, null=True)
    budget_range_to = models.PositiveIntegerField(blank=True, null=True)

    def get_destination_choices():
        choices = [('', 'Select Destination')]
        destinations = Destination.objects.all()
        choices.extend([(destination.name, destination.name) for destination in destinations])
        return choices

    name = models.CharField(max_length=100)
    # Optional email to store contact address coming from external systems/APIs
    email = models.EmailField(blank=True, null=True)
    country_code = models.CharField(max_length=5, default='+961')
    phone = models.CharField(max_length=15)
    
    CHANNEL_CHOICES = [
        ('', 'Select Channel'),
        ('Facebook', 'Facebook'),
        ('Whatsapp', 'Whatsapp'),
        ('Referral', 'Referral'),
        ('Direct', 'Direct'),
        ('Website', 'Website'),
        ('Instagram', 'Instagram'),
    ]
    channel = models.CharField(max_length=100, choices=CHANNEL_CHOICES, blank=True)

    SERVICE_CHOICES = [
        ('hotel', 'Hotel'),
        ('ticket', 'Ticket'),
        ('visa', 'Visa'),
        ('package', 'Package'),
        ('travel insurance', 'Travel Insurance'),
    ]

    STATUS_CHOICES = [
        ('onhold', 'On Hold'),
        ('processing', 'Processing'),
        ('negotiation', 'Negotiation'),
        ('finalized', 'Finalized'),
        ('followup', 'Follow-Up'),
        ('done', 'Unqualified'),
    ]

    type_of_service = models.CharField(max_length=50, choices=SERVICE_CHOICES, blank=True, default='')
    status = models.CharField(max_length=50, choices=STATUS_CHOICES, blank=True, default='onhold')
    status_changed_at = models.DateTimeField(null=True, blank=True)
    destination = models.CharField(max_length=200, blank=True, choices=get_destination_choices())
    # destination = models.CharField(max_length=200, blank=True)
    pax = models.CharField(max_length=100, blank=True, default='')
    duration = models.CharField(max_length=200, blank=True, default='')
    travel_date_from = models.DateField(blank=True, null=True)
    travel_date_to = models.DateField(blank=True, null=True)
    selling_price = models.CharField(max_length=200, blank=True)
    net = models.CharField(max_length=200, blank=True, default='')
    profit = models.CharField(max_length=200, blank=True)
    date_notes = models.TextField(blank=True, null=True)
    special_request = models.TextField(blank=True)
    urgent = models.BooleanField(default=False)
    assignment_notes = models.TextField(blank=True)
    supplier = models.CharField(max_length=200, blank=True)
    sold = models.BooleanField(blank=True, default=False)
    lost = models.BooleanField(blank=True, default=False)
    finalization_notes = models.TextField(blank=True, null=True)
    assigned_to = models.ForeignKey(User, on_delete=models.CASCADE, related_name="current")
    assigned_at = models.DateTimeField(null=True, blank=True)
    attachments = models.ManyToManyField(Attachment, blank=True)
    follow_up = models.DateField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True, editable=False)
    last_modified = models.DateTimeField(auto_now=True, editable=True)
    takeover = models.BooleanField(default=True)
    special_takeover = models.BooleanField(default=False)  # New field
    takeover_added_at = models.DateTimeField(null=True, blank=True)
    period = models.PositiveIntegerField(default=20)
    is_archived = models.BooleanField(default=False)
    offer_prepared = models.BooleanField(default=False)
    offer_details = models.TextField(blank=True, null=True)
    moved_to_negotiation = models.BooleanField(default=False)  # New field

    def save(self, *args, **kwargs):
        if self.pk is not None:
            original = Lead.objects.get(pk=self.pk)
            if original.status == 'onhold' and self.status != 'onhold':
                self.status_changed_at = timezone.now()
            elif self.status in ['processing', 'negotiation'] and self.status != original.status:
                self.status_changed_at = timezone.now()
                self.period = 4320
            elif self.offer_prepared and not original.offer_prepared:
                self.status_changed_at = timezone.now()
                self.period = 4320

            if original.status != 'negotiation' and self.status == 'negotiation':
                self.moved_to_negotiation = True  # Mark as moved to negotiation

            if original.assigned_to != self.assigned_to:
                self.assigned_at = timezone.now().date()

            if original.takeover is False and self.takeover is True:
                self.takeover_added_at = timezone.now()
        else:
            self.assigned_at = timezone.now()
            if self.takeover:
                self.takeover_added_at = timezone.now()

        if self.sold:
            selfleads = LeadTask.objects.filter(lead=self)
            if not selfleads:
                LeadTask.objects.create(
                    lead=self,
                    assigned_to=self.assigned_to,
                    status="onhold"
                )
        super(Lead, self).save(*args, **kwargs)

    @property
    def is_overdue(self):
        if self.status_changed_at and self.status not in ['done', 'finalized', 'onhold']:
            end_time = self.status_changed_at + timezone.timedelta(minutes=self.period)
            return timezone.now() > end_time
        return False

    def __str__(self):
        return self.name

    def get_numeric_profit(self):
        return int(re.sub(r'\D', '', self.profit)) if self.profit else 0


class CrmNotification(models.Model):
    """
    Lightweight record to track CRM notifications created when a summary is sent
    or when a new qualified prospect is created through the API.
    """
    lead = models.ForeignKey(
        'Lead',
        on_delete=models.CASCADE,
        related_name='crm_notifications',
        null=True,
        blank=True,
    )
    phone = models.CharField(max_length=20, blank=True)
    summary_section = models.TextField(blank=True)
    department = models.CharField(max_length=100, blank=True)
    channel = models.CharField(max_length=50, blank=True)
    # Arbitrary extra data from the caller (e.g. originating system, UUIDs, etc.)
    metadata = models.JSONField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    is_read = models.BooleanField(default=False)

    def __str__(self):
        target = self.lead.name if self.lead else self.phone or "Unknown"
        return f"Notification for {target} at {self.created_at:%Y-%m-%d %H:%M}"

class DailyReport(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    date = models.DateField(default=timezone.now)
    took_over_leads_today = models.IntegerField(default=0)
    offers_sent = models.TextField(blank=True, null=True)
    offers_sold = models.TextField(blank=True, null=True)
    offers_prepared = models.TextField(blank=True, null=True)
    unqualified_leads = models.TextField(blank=True, null=True)
    modified_leads_today = models.IntegerField(default=0)  # New field
    notes = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(default=timezone.now)

    def __str__(self):
        return f"{self.user.username} - {self.date}"

class Offer(models.Model):
    lead = models.ForeignKey('Lead', on_delete=models.CASCADE, related_name='offers')
    title = models.CharField(max_length=200)
    description = models.TextField()
    inclusions = models.TextField()
    exclusions = models.TextField(blank=True)
    itinerary = models.TextField()
    accommodation_options = models.TextField(blank=True)
    flight_details = models.TextField(blank=True)
    pricing_usd = models.TextField(blank=True)
    assigned_to = models.ForeignKey(User, on_delete=models.CASCADE, related_name="offer_assigned_to")
    created_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name="offer_created_by")
    created_at = models.DateTimeField(auto_now_add=True)
    sent = models.BooleanField(default=False)
    sold = models.BooleanField(default=False)
    sold_at = models.DateTimeField(null=True, blank=True)

    def save(self, *args, **kwargs):
        if self.sold and self.sold_at is None:
            self.sold_at = timezone.now()
        super().save(*args, **kwargs)

    def __str__(self):
        return self.title

class MonthlyTarget(models.Model):
    month = models.DateField(unique=True)
    target_profit = models.PositiveIntegerField()

    def __str__(self):
        return f"Target for {self.month.strftime('%B %Y')}: {self.target_profit}"

class UserMonthlyTarget(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    month = models.DateField()
    target_profit = models.PositiveIntegerField()

    class Meta:
        unique_together = ('user', 'month')

    def __str__(self):
        return f"{self.user.username} - {self.month.strftime('%B %Y')} - {self.target_profit}"

# Adding is_sales field to User model
User.add_to_class('is_sales', models.BooleanField(default=False))

# Signal to create user profile with is_sales set to False by default
from django.db.models.signals import post_save
from django.dispatch import receiver

@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    if created:
        instance.is_sales = False
        instance.save()
