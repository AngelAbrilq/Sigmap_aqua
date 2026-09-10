from django.urls import path
from . import views

app_name = 'core'

urlpatterns = [
    path('', views.instructor_lider, name='index'),
    path('instructor-lider/', views.instructor_lider, name='instructor_lider'),
    path('sensores/', views.sensores, name='sensores'),
    path('monitoreo/', views.monitoreo, name='monitoreo'),
    path('graficas-reportes/', views.graficas_reportes, name='graficas_reportes'),
    path('comparacion-periodos/', views.comparacion_periodos, name='comparacion_periodos'),
    path('alertas/', views.alertas, name='alertas'),
    path('ai/', views.ai, name='ai'),
    path('usuarios/', views.usuarios, name='usuarios'),
    path('geomembranas/', views.geomembranas, name='geomembranas'),
    path('configuraciones/', views.configuraciones, name='configuraciones'),
]