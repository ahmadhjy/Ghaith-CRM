from django.contrib import admin

from .models import ChatMessage, PushSubscription, UserNotification


@admin.register(UserNotification)
class UserNotificationAdmin(admin.ModelAdmin):
    list_display = ('title', 'recipient', 'kind', 'is_read', 'created_at')
    list_filter = ('kind', 'is_read')
    search_fields = ('title', 'message', 'recipient__username')


@admin.register(ChatMessage)
class ChatMessageAdmin(admin.ModelAdmin):
    list_display = ('sender', 'recipient', 'body', 'is_read', 'created_at')
    search_fields = ('body', 'sender__username', 'recipient__username')


@admin.register(PushSubscription)
class PushSubscriptionAdmin(admin.ModelAdmin):
    list_display = ('user', 'endpoint', 'created_at')
    search_fields = ('user__username', 'endpoint')
