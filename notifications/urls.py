from django.urls import path

from . import views

urlpatterns = [
    path('chat/', views.chat_page, name='notifications_chat'),
    path('api/count/', views.api_count, name='notifications_api_count'),
    path('api/list/', views.api_list, name='notifications_api_list'),
    path('api/mark-read/', views.api_mark_read, name='notifications_api_mark_read'),
    path('api/chat/users/', views.api_chat_users, name='notifications_api_chat_users'),
    path('api/chat/<int:user_id>/', views.api_chat_thread, name='notifications_api_chat_thread'),
    path('api/chat/send/', views.api_chat_send, name='notifications_api_chat_send'),
    path('api/vapid-public-key/', views.api_vapid_public_key, name='notifications_api_vapid'),
    path('api/push/subscribe/', views.api_push_subscribe, name='notifications_api_push_subscribe'),
    path('api/push/unsubscribe/', views.api_push_unsubscribe, name='notifications_api_push_unsubscribe'),
    path('api/broadcast/', views.api_broadcast, name='notifications_api_broadcast'),
]
