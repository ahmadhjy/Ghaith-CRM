from django.contrib import admin
from django.urls import path, include
from django.conf.urls.static import static
from django.conf import settings

from notifications.views import service_worker

urlpatterns = [
    path('sw.js', service_worker, name='service_worker'),
    path('', include('display.urls')),
    path('tasks/', include('tasks.urls')),
    path('admin/', admin.site.urls),
]+ static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
