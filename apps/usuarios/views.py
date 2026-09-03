from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout
from django.contrib import messages
from django.contrib.auth.decorators import login_required


def login_view(request):
    """
    Vista de login.
    Acepta correo electrónico como credencial (USERNAME_FIELD = 'email').
    """
    # Si ya está autenticado, manda directo al admin
    if request.user.is_authenticated:
        return redirect('/admin/')

    if request.method == 'POST':
        email    = request.POST.get('username', '').strip()
        password = request.POST.get('password', '').strip()

        if not email or not password:
            messages.error(request, 'Por favor completa todos los campos.')
            return render(request, 'usuarios/login.html')

        # authenticate espera el campo USERNAME_FIELD (email) como 'username'
        usuario = authenticate(request, username=email, password=password)

        if usuario is not None:
            if usuario.estado == 'activo':
                login(request, usuario)
                # Redirige al dashboard provisional (admin)
                return redirect('/admin/')
            else:
                messages.error(request, 'Tu cuenta está inactiva. Contacta al administrador.')
        else:
            messages.error(request, 'Correo o contraseña incorrectos.')

    return render(request, 'usuarios/login.html')


def logout_view(request):
    """Cierra sesión y redirige al login."""
    logout(request)
    return redirect('usuarios:login')
