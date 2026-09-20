"""
Rutas de la API móvil, bajo /api/v1/movil/.

Versionada desde el principio: cuando la app instalada en los celulares del
SENA quede atrás, /v2/ puede cambiar el contrato sin romperles la app a los
que no actualicen.
"""
from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import alertas, auth, geomembranas, lecturas, predicciones

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

    path('', include(router.urls)),
]
