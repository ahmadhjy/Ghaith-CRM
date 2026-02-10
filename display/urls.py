from django.urls import path, include
from . import views
from django.contrib.auth import views as auth_views

urlpatterns = [
    # Existing web views
    path('dashboard/', include('dashboard.urls')),
    path('input/', views.input_data, name='input_data'),
    path('create/', views.create_lead, name='create_lead'),
    path('creation/<int:pk>/', views.create_lead, name='edit_creation_lead'),
    path('qualify/<int:lead_id>/', views.qualify_lead, name='qualify_lead'),
    path('sendoffer/<int:lead_id>/', views.send_offer, name='send_offer_lead'),
    path('closedeal/<int:lead_id>/', views.closing_deal, name='deal_lead'),
    path('login/', auth_views.LoginView.as_view(), name='login_user'),
    path('logout/', views.logout_user, name='logout-user'),
    path('', views.display_data, name='display_data'),
    path('edit/<int:pk>/', views.edit_model, name='edit-model'),
    path('lead/<int:lead_id>/attachment/<int:attachment_id>/delete/', views.delete_attachment, name='delete_attachment'),
    path('attach/<int:pk>/', views.add_attachment, name='add_attachment'),
    path('takeover/', views.takeover_list, name='takeover_list'),
    path('takeover_lead/<int:lead_id>/', views.takeover_lead, name='takeover_lead'),
    path('archive_lead/<int:lead_id>/', views.archive_lead, name='archive_lead'),
    path('unarchive_lead/<int:lead_id>/', views.unarchive_lead, name='unarchive_lead'),
    path('archived_leads/', views.display_archived, name='archived_leads'),
    path('daily_report/', views.daily_report, name='daily_report'),
    path('daily_reports/', views.list_daily_reports, name='list_daily_reports'),
    path('daily_report/<int:pk>/', views.view_daily_report, name='view_daily_report'),
    path('offers/create/<int:lead_id>/', views.create_offer, name='create_offer'),
    path('offers/', views.list_offers, name='list_offers'),
    path('offers/<int:pk>/', views.view_offer, name='view_offer'),
    path('offers/<int:pk>/pdf/', views.download_offer_pdf, name='download_offer_pdf'),
    path('stats_dashboard/', views.stats_dashboard, name='stats_dashboard'),  # New URL pattern

    # JSON API endpoints for external systems (no login required)
    path('api/contacts/', views.api_create_contact, name='api_create_contact'),  # POST
    path('api/contacts/search/', views.api_search_contact_by_phone, name='api_search_contact_by_phone'),  # GET
    path('api/contacts/by-phone/', views.api_get_contact_by_phone, name='api_get_contact_by_phone'),  # GET
    path('api/contacts/<int:lead_id>/follow-up/', views.api_create_followup, name='api_create_followup'),  # POST
    path('api/destinations/', views.api_list_destinations, name='api_list_destinations'),  # GET
    path('api/departures/', views.api_list_departures, name='api_list_departures'),  # GET
    path('api/crm/notifications/', views.api_create_crm_notification, name='api_create_crm_notification'),  # POST
]
