"""Rutas del acceso de demostración por QR (apagadas si DEMO_QR_ACTIVO=False)."""
from django.urls import path

from . import views

app_name = 'demo'

urlpatterns = [
    path('q/<str:token>/', views.acceso, name='acceso'),
    path('presentacion/', views.presentacion, name='presentacion'),
    path('actividad/', views.actividad, name='actividad'),
]
