"""
Rutas del app core: bienvenida y paneles por rol.

Los modulos funcionales NO se registran aqui. Cada uno lo sirve su propio app
(piscinas, monitoreo, alertas, reportes, usuarios). Registrarlos en dos sitios
provoca un bucle de redirecciones: core captura la URL primero, redirige al
modulo real, y el reverse devuelve la misma URL.
"""
from django.urls import path

from . import views

app_name = 'core'

urlpatterns = [
    path('', views.index, name='index'),                                    # Bienvenida publica
    path('dashboard/', views.dashboard, name='dashboard'),                  # Router por rol

    # Paneles por rol
    path('instructor-lider/', views.instructor_lider, name='instructor_lider'),
    path('aprendiz/', views.aprendiz, name='aprendiz'),
    path('operario/', views.operario, name='operario'),
]
