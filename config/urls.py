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

    # Bienvenida y paneles por rol
    path('', include('apps.core.urls')),
    path('', include('apps.usuarios.urls')),      # auth/login, auth/logout, usuarios/

    # Modulos funcionales. Cada uno lo sirve su propio app: registrar la misma
    # URL en core y aqui provoca un bucle de redirecciones.
    path('geomembranas/', include('apps.piscinas.urls')),
    path('alertas/', include('apps.alertas.urls')),
    path('ai/', include('apps.ia.urls')),
    path('', include('apps.monitoreo.urls_web')),   # sensores, monitoreo, historial, configuraciones
    path('', include('apps.reportes.urls')),        # graficas-reportes, comparacion-periodos

    # API REST de la app movil (personas, autenticadas con JWT).
    # Va ANTES de api/v1/ para que 'movil/' no lo capture la ruta del firmware.
    path('api/v1/movil/', include('apps.api_movil.urls')),

    # API consumida por los nodos ESP32 en campo (token de dispositivo)
    path('api/v1/', include('apps.monitoreo.urls')),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
