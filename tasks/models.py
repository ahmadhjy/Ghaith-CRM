import uuid

from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone


class Tag(models.Model):
    tag_name = models.CharField(max_length=200)

    def __str__(self):
        return self.tag_name


class Task(models.Model):
    STATUS_CHOICES = [
        ('onhold', 'On Hold'),
        ('progress', 'In Progress'),
        ('done', 'Done'),
    ]

    title = models.CharField(max_length=100)
    details = models.TextField(blank=True)
    # TODO for filter
    tag = models.ForeignKey(Tag, blank=True, on_delete=models.DO_NOTHING)
    due_time = models.DateTimeField(null=True, blank=True)
    assigned_to = models.ForeignKey(User, on_delete=models.CASCADE)

    # edit
    what_happened = models.TextField(blank=True,null=True)
    status = models.CharField(max_length=100, choices=STATUS_CHOICES)

    def __str__(self):
        return self.title


# installment ??
# checklist

class LeadTask(models.Model):
    PAYMENT_CH = [
        ('installment', 'Installment'),
        ('full', 'Full'),
    ]
    STATUS_CHOICES = [
        ('onhold', 'On Hold'),
        ('progress', 'In Progress'),
        ('done', 'Done'),
        ('cancelled', 'Cancelled'),
    ]
    lead = models.ForeignKey('display.Lead', on_delete=models.CASCADE)
    assigned_to = models.ForeignKey(User, on_delete=models.CASCADE)
    payment = models.CharField(max_length=100, choices=PAYMENT_CH, blank=True)
    status = models.CharField(max_length=100, choices=STATUS_CHOICES)
    notes = models.TextField(blank=True, null=True)
    travel_date = models.DateTimeField(null=True, blank=True)
    return_date = models.DateTimeField(null=True, blank=True)
    date_of_birth = models.DateField(null=True, blank=True)
    passport_expiry_date = models.DateField(null=True, blank=True)

    def __str__(self):
        return self.lead.name


class ServiceType(models.Model):
    name = models.CharField(max_length=120, unique=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class Supplier(models.Model):
    name = models.CharField(max_length=120, unique=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class Service(models.Model):
    leadtask = models.ForeignKey(LeadTask, on_delete=models.CASCADE)
    service_name = models.CharField(max_length=100, blank=True)
    supplier = models.CharField(max_length=100, blank=True)
    details = models.TextField(blank=True)
    net = models.CharField(max_length=100, blank=True)
    issue_price = models.CharField(max_length=100, blank=True, help_text='Actual net at issue date; overrides net when set')
    selling = models.CharField(max_length=100, blank=True)
    due_time = models.DateTimeField(null=True, blank=True)
    voucher_id = models.CharField(max_length=300, blank=True)
    is_checked = models.BooleanField(default=False)
    processed = models.BooleanField(default=False)
    send_to_client = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True, null=True)  # Add this line

    def __str__(self):
        return self.service_name


# models.py
class Payment(models.Model):
    leadtask = models.ForeignKey(LeadTask,
                                 on_delete=models.CASCADE,
                                 related_name='lead_pay')
    date = models.DateTimeField()
    amount = models.PositiveIntegerField()
    is_checked = models.BooleanField(default=False)
    is_refund = models.BooleanField(default=False)
    processed = models.BooleanField(default=False)  # Add this field
    created_at = models.DateTimeField(auto_now_add=True, null=True)  # Add this field

    def __str__(self):
        return f'{self.leadtask.lead.name} - {self.amount}'


class Attachment(models.Model):
    attachment_name = models.CharField(max_length=120)
    file = models.FileField(upload_to='static/attachments/%Y/%m/%d/')
    uploaded_at = models.DateTimeField(auto_now_add=True)
    parentleadtask = models.ForeignKey('LeadTask', on_delete=models.CASCADE, blank=True, null=True)

    def __str__(self):
        self.attachment_name



class TaskAttachment(models.Model):
    task = models.ForeignKey(Task, on_delete=models.CASCADE, related_name='task_attachments', blank=True, null=True)
    attachment_name = models.CharField(max_length=120)
    file = models.FileField(upload_to='static/attachments/%Y/%m/%d/')
    uploaded_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.attachment_name


class ClientMediaUploadLink(models.Model):
    token = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    leadtask = models.ForeignKey(LeadTask, on_delete=models.CASCADE, related_name='media_upload_links')
    client_name = models.CharField(max_length=200)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    submitted_at = models.DateTimeField(null=True, blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.client_name} ({self.token})'

    @property
    def is_submitted(self):
        return self.submitted_at is not None


class ClientMediaFile(models.Model):
    upload_link = models.ForeignKey(
        ClientMediaUploadLink, on_delete=models.CASCADE, related_name='files'
    )
    file = models.FileField(upload_to='static/client_media/%Y/%m/%d/')
    original_name = models.CharField(max_length=255)
    uploaded_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.original_name

    @property
    def is_video(self):
        return self.original_name.lower().endswith(
            ('.mp4', '.mov', '.avi', '.webm', '.mkv', '.m4v')
        )


class PdfPolicy(models.Model):
    """Rich-text policy block attachable to one or more CRM PDF exports."""

    title = models.CharField(max_length=200, default='Booking Terms & Travel Policy')
    content = models.TextField(blank=True, help_text='Formatted policy text (edited with the rich text editor).')
    show_on_client_invoice = models.BooleanField(
        default=False, verbose_name='Client invoice PDF',
        help_text='Append to the client invoice downloaded from edit invoice.',
    )
    show_on_internal_invoice = models.BooleanField(
        default=False, verbose_name='Internal invoice PDF',
    )
    show_on_purchases_report = models.BooleanField(
        default=False, verbose_name='Purchases report PDF',
    )
    show_on_client_payments_report = models.BooleanField(
        default=False, verbose_name='Client payments report PDF',
    )
    show_on_travellers_report = models.BooleanField(
        default=False, verbose_name='Travellers report PDF',
    )
    is_active = models.BooleanField(default=True)
    sort_order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ['sort_order', 'title']
        verbose_name = 'PDF policy'
        verbose_name_plural = 'PDF policies'

    def __str__(self):
        return self.title

