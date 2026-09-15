"""Rutas del modulo de analisis predictivo con IA."""
from django.urls import path

from . import views

app_name = 'ia'

urlpatterns = [
    path('', views.panel, name='panel'),
    path('generar/', views.generar, name='generar'),
    path('<int:pk>/estado/', views.cambiar_estado, name='cambiar_estado'),
]
