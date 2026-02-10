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
    ]
    lead = models.ForeignKey('display.Lead', on_delete=models.CASCADE)
    assigned_to = models.ForeignKey(User, on_delete=models.CASCADE)
    payment = models.CharField(max_length=100, choices=PAYMENT_CH, blank=True)
    status = models.CharField(max_length=100, choices=STATUS_CHOICES)
    notes = models.TextField(blank=True, null=True)
    travel_date = models.DateTimeField(null=True, blank=True)
    date_of_birth = models.DateField(null=True, blank=True)
    passport_expiry_date = models.DateField(null=True, blank=True)
    def __str__(self):
        return self.lead.name


class Service(models.Model):
    leadtask = models.ForeignKey(LeadTask, on_delete=models.CASCADE)
    service_name = models.CharField(max_length=100, blank=True)
    supplier = models.CharField(max_length=100, blank=True)
    details = models.TextField(blank=True)
    net = models.CharField(max_length=100, blank=True)
    selling = models.CharField(max_length=100, blank=True)
    due_time = models.DateTimeField(null=True, blank=True)
    voucher_id = models.CharField(max_length=300, blank=True)
    is_checked = models.BooleanField(default=False)
    processed = models.BooleanField(default=False)
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

