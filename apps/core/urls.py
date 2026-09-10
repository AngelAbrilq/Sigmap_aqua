from django.urls import path

from . import views

app_name = 'core'

urlpatterns = [
    path('', views.index, name='index'),                                          # Bienvenida publica
    path('dashboard/', views.dashboard, name='dashboard'),                        # Router por rol

    # Dashboards por rol
    path('instructor-lider/', views.instructor_lider, name='instructor_lider'),
    path('aprendiz/', views.aprendiz, name='aprendiz'),
    path('operario/', views.operario, name='operario'),

    # Modulos funcionales
    path('sensores/', views.sensores, name='sensores'),
    path('monitoreo/', views.monitoreo, name='monitoreo'),
    path('historial/', views.historial, name='historial'),
    path('graficas-reportes/', views.graficas_reportes, name='graficas_reportes'),
    path('comparacion-periodos/', views.comparacion_periodos, name='comparacion_periodos'),
    path('alertas/', views.alertas, name='alertas'),
    path('ai/', views.ai, name='ai'),
    path('usuarios/', views.usuarios, name='usuarios'),
    path('geomembranas/', views.geomembranas, name='geomembranas'),
    path('configuraciones/', views.configuraciones, name='configuraciones'),
]
