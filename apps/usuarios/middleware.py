from django.contrib import messages
from django.shortcuts import redirect

from .permissions import puede_entrar_al_admin, resolver_dashboard


class BloqueoAdminNativoMiddleware:
    """
    Impide que los roles operativos lleguen al admin nativo de Django.

    - Anonimo            -> login propio del proyecto (con ?next=)
    - Rol operativo      -> su dashboard correspondiente
    - Superusuario tecnico -> pasa
    """

    PREFIJO_ADMIN = '/admin/'

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.path.startswith(self.PREFIJO_ADMIN):
            if not request.user.is_authenticated:
                return redirect(f'/auth/login/?next={request.path}')
            if not puede_entrar_al_admin(request.user):
                messages.warning(request, 'No tienes acceso al panel de administracion.')
                return redirect(resolver_dashboard(request.user))

        return self.get_response(request)
