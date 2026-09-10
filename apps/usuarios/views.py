from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.shortcuts import redirect, render
from django.utils.http import url_has_allowed_host_and_scheme

from .permissions import resolver_dashboard


def _destino_post_login(request, usuario):
    """
    Calcula a donde enviar al usuario recien autenticado.
    Prioriza ?next= (validado contra el host) y cae en la matriz de roles.

    :param request: HttpRequest
    :param usuario: instancia de usuarios.Usuario ya autenticada
    :return: str con la ruta destino
    """
    next_url = request.POST.get('next') or request.GET.get('next')
    if next_url and url_has_allowed_host_and_scheme(
        next_url,
        allowed_hosts={request.get_host()},
        require_secure=request.is_secure(),
    ):
        return next_url
    return resolver_dashboard(usuario)


def login_view(request):
    """
    Vista de login por email. Redirige al dashboard segun el rol.
    Nunca envia al admin nativo de Django.
    """
    if request.user.is_authenticated:
        return redirect(resolver_dashboard(request.user))

    if request.method == 'POST':
        email = request.POST.get('username', '').strip()
        password = request.POST.get('password', '').strip()

        if not email or not password:
            messages.error(request, 'Por favor completa todos los campos.')
            return render(request, 'usuarios/login.html')

        usuario = authenticate(request, username=email, password=password)

        if usuario is None:
            messages.error(request, 'Correo o contrasena incorrectos.')
        elif usuario.estado != 'activo':
            messages.error(request, 'Tu cuenta esta inactiva. Contacta al administrador.')
        elif not usuario.rol_id:
            messages.error(request, 'Tu cuenta no tiene un rol asignado. Contacta al administrador.')
        else:
            login(request, usuario)
            return redirect(_destino_post_login(request, usuario))

    return render(request, 'usuarios/login.html')


def logout_view(request):
    """Cierra sesion y vuelve al login."""
    logout(request)
    return redirect('usuarios:login')
