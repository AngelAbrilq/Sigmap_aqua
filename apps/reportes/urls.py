"""Rutas de graficas, reportes y comparacion de periodos."""
from django.urls import path

from . import views

app_name = 'reportes'

urlpatterns = [
    path('graficas-reportes/', views.graficas, name='graficas'),
    path('graficas-reportes/crear/', views.reporte_crear, name='reporte_crear'),
    path('graficas-reportes/<int:pk>/csv/', views.reporte_csv, name='reporte_csv'),

    path('comparacion-periodos/', views.comparacion, name='comparacion'),
    path('comparacion-periodos/guardar/', views.comparacion_guardar, name='comparacion_guardar'),
]
