"""
Rutas de la API móvil, bajo /api/v1/movil/.

Versionada desde el principio: cuando la app instalada en los celulares del
SENA quede atrás, /v2/ puede cambiar el contrato sin romperles la app a los
que no actualicen.
"""
from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import alertas, auth, geomembranas, ia, lecturas, predicciones, reportes

app_name = 'api_movil'

router = DefaultRouter()
router.register('geomembranas', geomembranas.GeomembranaViewSet, basename='geomembranas')
router.register('alertas', alertas.AlertaViewSet, basename='alertas')

urlpatterns = [
    # Autenticación
    path('auth/token/', auth.LoginView.as_view(), name='token'),
    path('auth/refresh/', auth.RefreshView.as_view(), name='refresh'),
    path('auth/logout/', auth.LogoutView.as_view(), name='logout'),
    path('auth/me/', auth.PerfilView.as_view(), name='perfil'),

    # Datos
    path('lecturas/', lecturas.HistorialLecturasView.as_view(), name='lecturas'),
    path('predicciones/', predicciones.PrediccionesView.as_view(), name='predicciones'),
    path('notificaciones/', alertas.NotificacionesView.as_view(), name='notificaciones'),
    path('notificaciones/leidas/', alertas.NotificacionesView.as_view(),
         name='notificaciones_leidas'),

    # Inteligencia artificial
    path('ia/analisis/', ia.AnalisisIAView.as_view(), name='ia_analisis'),
    path('ia/asistente/', ia.AsistenteIAView.as_view(), name='ia_asistente'),
    path('ia/asistente/<int:pk>/excel/', ia.AsistenteExcelView.as_view(),
         name='ia_asistente_excel'),

    # Reportes PDF / Excel (mismo contenido que la exportación web)
    path('parametros/', reportes.ParametrosView.as_view(), name='parametros'),
    path('reportes/historial/resumen/', reportes.ResumenReporteView.as_view(),
         name='reporte_resumen'),
    path('reportes/historial/', reportes.DescargaReporteView.as_view(),
         name='reporte_descarga'),

    path('', include(router.urls)),
]
