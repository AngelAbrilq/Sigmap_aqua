"""Rutas del registro de eventos del sistema (auditoría) — RF018."""
from django.urls import path

from . import views

app_name = 'auditoria'

urlpatterns = [
    path('', views.lista, name='lista'),
]
