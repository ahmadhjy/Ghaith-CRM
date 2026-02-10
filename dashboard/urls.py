from django.urls import path, re_path
from . import views
from .views import delete_event, mark_event_done

urlpatterns = [
    path('', views.index, name='dashboard'),
    re_path(r'^calendar/$', views.CalendarView.as_view(), name='calendar'),
    re_path(r'^event/new/$', views.event, name='event_new'),
    re_path(r'^event/edit/(?P<event_id>\d+)/$', views.event, name='event_edit'),
    path('event/delete/<int:event_id>/', delete_event, name='event_delete'),
    path('event/done/<int:event_id>/', mark_event_done, name='event_done'),
    path('calendar/supplier-payments/', views.supplier_payments_list, name='supplier_payments_list'),
    path('calendar/client-payments/', views.client_payments_list, name='client_payments_list'),
]
