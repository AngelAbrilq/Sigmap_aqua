"""Rutas del modulo de alertas."""
from django.urls import path

from . import views

app_name = 'alertas'

urlpatterns = [
    path('', views.listar, name='listar'),
    path('<int:pk>/reconocer/', views.reconocer, name='reconocer'),
    path('<int:pk>/resolver/', views.resolver, name='resolver'),
    path('notificaciones/leidas/', views.marcar_notificaciones_leidas,
         name='notificaciones_leidas'),
]
