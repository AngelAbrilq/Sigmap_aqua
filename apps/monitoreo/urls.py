"""Rutas de la API de ingesta consumida por los nodos ESP32."""
from django.urls import path

from .views import HandshakeView, IngestaLecturasView

app_name = 'monitoreo_api'

urlpatterns = [
    path('dispositivos/handshake/', HandshakeView.as_view(), name='handshake'),
    path('lecturas/', IngestaLecturasView.as_view(), name='ingesta-lecturas'),
]
