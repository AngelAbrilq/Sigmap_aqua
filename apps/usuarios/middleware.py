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


class SinCacheSesionMiddleware:
    """
    Evita que el navegador almacene en caché las respuestas de páginas
    autenticadas o de cierre de sesión. De este modo, si el usuario cierra
    sesión e intenta pulsar el botón 'Atrás' en el navegador, no podrá ver
    pantallas protegidas ni restaurar la sesión.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        if (hasattr(request, 'user') and request.user.is_authenticated) or request.path.startswith('/auth/logout'):
            response['Cache-Control'] = 'no-cache, no-store, must-revalidate, max-age=0'
            response['Pragma'] = 'no-cache'
            response['Expires'] = '0'
        return response
