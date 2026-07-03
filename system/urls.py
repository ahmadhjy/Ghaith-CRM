from django.contrib import admin
from django.urls import path, include
from django.conf.urls.static import static
from django.conf import settings

from notifications.views import service_worker
from tasks import babylon_views

urlpatterns = [
    path('sw.js', service_worker, name='service_worker'),
    path('babylon/', babylon_views.babylon_portal_login, name='babylon_portal_login'),
    path('babylon/sheet/', babylon_views.babylon_portal_sheet, name='babylon_portal_sheet'),
    path('babylon/export/pdf/', babylon_views.babylon_portal_export_pdf, name='babylon_portal_export_pdf'),
    path('babylon/export/xlsx/', babylon_views.babylon_portal_export_xlsx, name='babylon_portal_export_xlsx'),
    path('babylon/other-hotels/', babylon_views.babylon_portal_other_hotels, name='babylon_portal_other_hotels'),
    path('babylon/other-hotels/pdf/', babylon_views.babylon_portal_other_hotels_export_pdf, name='babylon_portal_other_hotels_export_pdf'),
    path('babylon/other-hotels/xlsx/', babylon_views.babylon_portal_other_hotels_export_xlsx, name='babylon_portal_other_hotels_export_xlsx'),
    path('babylon/logout/', babylon_views.babylon_portal_logout, name='babylon_portal_logout'),
    path('', include('display.urls')),
    path('tasks/', include('tasks.urls')),
    path('accounting/', include('system.accounting_urls')),
    path('admin/', admin.site.urls),
]+ static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
