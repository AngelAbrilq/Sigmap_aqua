"""
URL configuration for config project.
"""
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

admin.site.site_header = 'SIGMAP AQUA'
admin.site.site_title = 'SIGMAP AQUA'
admin.site.index_title = 'Panel de administracion'

urlpatterns = [
    # El admin queda solo para superusuarios tecnicos.
    # BloqueoAdminNativoMiddleware filtra el acceso de los roles operativos.
    path('admin/', admin.site.urls),
    path('', include('apps.core.urls')),
    path('auth/', include('apps.usuarios.urls')),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
