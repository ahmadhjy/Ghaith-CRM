from django.contrib.auth.models import User
from django.db import models


class NotificationKind(models.TextChoices):
    MESSAGE = 'message', 'New message'
    CLIENT_PAYMENT_DUE = 'client_payment_due', 'Client payment due'
    SUPPLIER_PAYMENT_DUE = 'supplier_payment_due', 'Supplier payment due'
    CLIENT_TRAVELLING = 'client_travelling', 'Client travelling'
    CLIENT_RETURN = 'client_return', 'Client return'
    MEDIA_UPLOAD = 'media_upload', 'Client media upload'
    TAKEOVER_LEAD = 'takeover_lead', 'Take over list'
    BROADCAST = 'broadcast', 'Notice for all'


class UserNotification(models.Model):
    recipient = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name='crm_user_notifications'
    )
    kind = models.CharField(max_length=40, choices=NotificationKind.choices)
    title = models.CharField(max_length=255)
    message = models.TextField(blank=True)
    url = models.CharField(max_length=500, blank=True)
    lead = models.ForeignKey(
        'display.Lead', on_delete=models.CASCADE, null=True, blank=True
    )
    leadtask = models.ForeignKey(
        'tasks.LeadTask', on_delete=models.CASCADE, null=True, blank=True
    )
    dedupe_key = models.CharField(max_length=255, blank=True, db_index=True)
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['recipient', 'is_read', '-created_at']),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=['recipient', 'dedupe_key'],
                condition=models.Q(dedupe_key__gt=''),
                name='unique_notification_dedupe_per_user',
            ),
        ]

    def __str__(self):
        return f'{self.get_kind_display()} → {self.recipient.username}'


class ChatMessage(models.Model):
    sender = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name='chat_sent'
    )
    recipient = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name='chat_received'
    )
    body = models.TextField()
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['created_at']

    def __str__(self):
        return f'{self.sender.username} → {self.recipient.username}'


class PushSubscription(models.Model):
    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name='push_subscriptions'
    )
    endpoint = models.TextField(unique=True)
    p256dh = models.CharField(max_length=255)
    auth = models.CharField(max_length=255)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f'Push for {self.user.username}'
