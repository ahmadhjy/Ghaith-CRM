from django.urls import path

from accounting_bridge import views

app_name = 'accounting_bridge'

urlpatterns = [
    path('review/', views.review_queue, name='review_queue'),
    path('review/<uuid:queue_id>/', views.review_detail, name='review_detail'),
    path('review/<uuid:queue_id>/approve/', views.review_approve, name='review_approve'),
    path('review/<uuid:queue_id>/reject/', views.review_reject, name='review_reject'),
    path('opening-balances/', views.opening_balances_list, name='opening_balances'),
    path('opening-balances/new/', views.opening_balance_create, name='opening_balance_create'),
    path('opening-balances/<uuid:row_id>/edit/', views.opening_balance_edit, name='opening_balance_edit'),
    path('opening-balances/<uuid:row_id>/delete/', views.opening_balance_delete, name='opening_balance_delete'),
]
