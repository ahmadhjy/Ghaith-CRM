from django.urls import include, path

urlpatterns = [
    path('', include('accounts_core.urls')),
    path('bridge/', include('accounting_bridge.urls')),
    path('catalog/', include('catalog.urls')),
    path('sales/', include('sales.urls')),
    path('purchases/', include('purchases.urls')),
    path('treasury/', include('treasury.urls')),
    path('expenses/', include('expenses.urls')),
    path('reporting/', include('reporting.urls')),
    path('api/', include('api.urls')),
]
