"""Rutas del modulo de infraestructura piscicola (geomembranas)."""
from django.urls import path

from . import views

app_name = 'piscinas'

urlpatterns = [
    path('', views.listar, name='listar'),                      # GET  listado + detalle
    path('crear/', views.crear, name='crear'),                  # POST alta
    path('<int:pk>/editar/', views.editar, name='editar'),      # POST actualizacion
    path('<int:pk>/eliminar/', views.eliminar, name='eliminar'),# POST baja o desactivacion
]
