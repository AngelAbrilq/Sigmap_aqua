"""Rutas del modulo de analisis predictivo con IA."""
from django.urls import path

from . import views, views_asistente

app_name = 'ia'

urlpatterns = [
    path('', views.panel, name='panel'),
    path('generar/', views.generar, name='generar'),
    path('evaluar/', views.evaluar, name='evaluar'),
    path('<int:pk>/estado/', views.cambiar_estado, name='cambiar_estado'),

    # Asistente flotante: preguntas libres y su informe en Excel
    path('asistente/preguntar/', views_asistente.preguntar_view, name='asistente_preguntar'),
    path('asistente/<int:pk>/excel/', views_asistente.excel_view, name='asistente_excel'),
]
