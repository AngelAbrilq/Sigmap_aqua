"""
Rutas de autenticacion y gestion de usuarios.

Un unico namespace 'usuarios' con los prefijos escritos aqui, en vez de dos
modulos montados en puntos distintos: dos include() con el mismo app_name
colisionan en el espacio de nombres.
"""
from django.urls import path

from . import views

app_name = 'usuarios'

urlpatterns = [
    # Autenticacion
    path('auth/login/',  views.login_view,  name='login'),
    path('auth/logout/', views.logout_view, name='logout'),

    # Gestion de cuentas (solo Instructor Lider escribe)
    path('usuarios/', views.listar, name='listar'),
    path('usuarios/crear/', views.crear, name='crear'),
    path('usuarios/<int:pk>/editar/', views.editar, name='editar'),
    path('usuarios/<int:pk>/estado/', views.desactivar, name='desactivar'),
]
