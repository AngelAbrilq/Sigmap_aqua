"""
Autenticación JWT de la app móvil.

Los nodos ESP32 usan un token de dispositivo permanente porque no hacen login
ni pueden refrescar nada. Las personas sí: aquí va el flujo completo
login → access → refresh rotativo → logout con blacklist.
"""
import logging

from rest_framework.exceptions import AuthenticationFailed
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenObtainPairView

from apps.usuarios.permissions import MODULOS_ESCRITURA_POR_ROL, MODULOS_POR_ROL, obtener_nombre_rol

from ..respuestas import respuesta
from ..serializers import UsuarioMovilSerializer

logger = logging.getLogger(__name__)


class LoginSerializer(TokenObtainPairSerializer):
    """
    Login por correo, con el rol embebido en el token.

    El rol viaja dentro del JWT para que la app arme su menú sin una segunda
    petición. Aun así el backend revalida cada acción: el token es una pista
    para la interfaz, nunca la autoridad.
    """

    default_error_messages = {
        'no_active_account': 'Correo o contraseña incorrectos.',
    }

    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)
        token['rol'] = obtener_nombre_rol(user)
        token['nombre'] = user.nombre_completo
        return token

    def validate(self, attrs):
        datos = super().validate(attrs)

        if self.user.estado != 'activo':
            raise AuthenticationFailed('La cuenta está inactiva. Contacta al administrador.')
        if not self.user.rol_id:
            raise AuthenticationFailed('Tu cuenta no tiene un rol asignado.')

        datos['usuario'] = UsuarioMovilSerializer(
            self.user, context=self.context).data
        return datos


class LoginView(TokenObtainPairView):
    """
    POST auth/token/ → {access, refresh, usuario}

    Con throttling: sin él, el login es un oráculo de fuerza bruta contra
    las contraseñas de todo el equipo.
    """

    serializer_class = LoginSerializer
    permission_classes = [AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'login'

    def post(self, request, *args, **kwargs):
        original = super().post(request, *args, **kwargs)
        correo = request.data.get('email', '')
        logger.info('Login móvil correcto: %s', correo)
        return respuesta(True, original.data, 'Inicio de sesión exitoso.')


class RefreshView(APIView):
    """
    POST auth/refresh/ → {access, refresh}

    Se implementa a mano en vez de usar TokenRefreshView tal cual para que la
    respuesta salga envuelta como todas las demás: un cliente que tiene que
    tratar una ruta distinto es un cliente con un bug esperando.
    """

    permission_classes = [AllowAny]

    def post(self, request):
        crudo = request.data.get('refresh')
        if not crudo:
            return respuesta(False, None, 'Falta el token de refresco.', 400)

        try:
            refresh = RefreshToken(crudo)
            datos = {'access': str(refresh.access_token)}

            # ROTATE_REFRESH_TOKENS: el refresh usado se invalida y se emite
            # uno nuevo, para que un token robado sirva una sola vez.
            from django.conf import settings
            if settings.SIMPLE_JWT.get('ROTATE_REFRESH_TOKENS'):
                if settings.SIMPLE_JWT.get('BLACKLIST_AFTER_ROTATION'):
                    try:
                        refresh.blacklist()
                    except AttributeError:
                        # La app token_blacklist no está instalada: se rota
                        # igual, sin invalidar el anterior.
                        pass
                refresh.set_jti()
                refresh.set_exp()
                refresh.set_iat()
                datos['refresh'] = str(refresh)

            return respuesta(True, datos, 'Sesión renovada.')

        except TokenError as exc:
            logger.info('Refresh rechazado: %s', exc)
            return respuesta(False, None, 'La sesión expiró. Inicia sesión de nuevo.', 401)


class LogoutView(APIView):
    """
    POST auth/logout/ → invalida el refresh.

    Sin blacklist, "cerrar sesión" solo borraría el token del teléfono: quien
    lo hubiera copiado seguiría entrando hasta que expirara.
    """

    permission_classes = [IsAuthenticated]

    def post(self, request):
        crudo = request.data.get('refresh')
        if not crudo:
            return respuesta(False, None, 'Falta el token de refresco.', 400)

        try:
            RefreshToken(crudo).blacklist()
        except AttributeError:
            return respuesta(False, None,
                             'El servidor no tiene habilitada la lista negra de tokens.', 501)
        except TokenError:
            # Ya estaba invalidado o expirado: el resultado para el usuario
            # es el mismo, así que no se trata como error.
            pass

        logger.info('Logout móvil: %s', request.user.email)
        return respuesta(True, None, 'Sesión cerrada.')


class PerfilView(APIView):
    """
    GET auth/me/ → perfil + módulos que su rol puede ver y editar.

    La app usa esto para armar el menú y decidir qué botones renderiza. Es una
    conveniencia de interfaz: `PermisoModulo` vuelve a validar en cada
    petición, así que ocultar un botón nunca es el control de acceso.
    """

    permission_classes = [IsAuthenticated]

    def get(self, request):
        rol = obtener_nombre_rol(request.user)
        lectura = MODULOS_POR_ROL.get(rol)
        escritura = MODULOS_ESCRITURA_POR_ROL.get(rol)

        datos = UsuarioMovilSerializer(request.user, context={'request': request}).data
        datos['modulos'] = {
            # None en la matriz significa "todos": se traduce explícitamente
            # para que el cliente no tenga que interpretar un null.
            'lectura': 'todos' if lectura is None else sorted(lectura),
            'escritura': 'todos' if escritura is None else sorted(escritura or []),
        }
        return respuesta(True, datos, 'Perfil del usuario.')
