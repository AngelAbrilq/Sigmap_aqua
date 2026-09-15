"""
Rutas web del app monitoreo.

Separadas de urls.py, que expone la API de ingesta de los nodos ESP32 bajo
/api/v1/. Aqui viven los modulos que consumen las personas.
"""
from django.urls import path

from . import views_web as views

app_name = 'monitoreo'

urlpatterns = [
    # Sensores
    path('sensores/', views.sensores, name='sensores'),
    path('sensores/crear/', views.sensor_crear, name='sensor_crear'),
    path('sensores/<int:pk>/editar/', views.sensor_editar, name='sensor_editar'),
    path('sensores/<int:pk>/eliminar/', views.sensor_eliminar, name='sensor_eliminar'),

    # Monitoreo en tiempo real
    path('monitoreo/', views.monitoreo, name='monitoreo'),
    path('monitoreo/api/<int:pk>/estado/', views.api_estado, name='api_estado'),

    # Historial
    path('historial/', views.historial, name='historial'),
    path('historial/csv/', views.historial_csv, name='historial_csv'),

    # Configuraciones: umbrales de los parametros medibles
    path('configuraciones/', views.configuraciones, name='configuraciones'),
    path('configuraciones/crear/', views.parametro_crear, name='parametro_crear'),
    path('configuraciones/<int:pk>/editar/', views.parametro_editar, name='parametro_editar'),
]
