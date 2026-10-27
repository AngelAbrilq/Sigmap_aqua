"""
Tokens firmados de los QR de demostración.

El QR NO lleva correo ni contraseña: lleva `<id_usuario>.<versión>` firmado
con la SECRET_KEY y con marca de tiempo. Nadie puede fabricar uno sin la
clave del servidor, vence solo y se revoca subiendo DEMO_QR_VERSION.
"""

from django.conf import settings
from django.core import signing

SALT = 'sigmap.demo.qr'


class TokenDemoInvalido(Exception):
    """El token no permite entrar. `motivo` explica por qué al usuario."""

    MENSAJES = {
        'expirado': 'Este código QR ya venció.',
        'revocado': 'Este código QR fue desactivado por el instructor.',
        'invalido': 'Este código QR no es válido.',
        'usuario': 'El usuario de este código QR ya no está disponible.',
    }

    def __init__(self, motivo):
        self.motivo = motivo
        super().__init__(self.MENSAJES.get(motivo, self.MENSAJES['invalido']))


def _firmador():
    return signing.TimestampSigner(salt=SALT)


def vigencia_segundos():
    """Tiempo de vida de un QR según DEMO_QR_HORAS."""
    return int(settings.DEMO_QR_HORAS) * 3600


def crear_token(usuario):
    """
    Firma el acceso de un usuario.

    :param usuario: usuarios.Usuario
    :return: str corto, apto para un QR legible
    """
    return _firmador().sign(f'{usuario.pk}.{settings.DEMO_QR_VERSION}')


def leer_token(token):
    """
    Valida un token y devuelve el usuario al que da acceso.

    :param token: str recibido en la URL
    :return: usuarios.Usuario activo con un rol de demostración
    :raises TokenDemoInvalido: si venció, fue revocado o es falso
    """
    from apps.usuarios.models import Usuario

    from .roles import ROLES_DEMO

    try:
        valor = _firmador().unsign(token, max_age=vigencia_segundos())
    except signing.SignatureExpired as exc:
        raise TokenDemoInvalido('expirado') from exc
    except signing.BadSignature as exc:
        raise TokenDemoInvalido('invalido') from exc

    try:
        pk, version = (int(parte) for parte in valor.split('.'))
    except ValueError as exc:
        raise TokenDemoInvalido('invalido') from exc

    if version != int(settings.DEMO_QR_VERSION):
        raise TokenDemoInvalido('revocado')

    usuario = Usuario.objects.select_related('rol').filter(
        pk=pk, estado='activo', is_active=True).first()
    if usuario is None or not usuario.rol_id or usuario.rol.nombre_rol not in ROLES_DEMO:
        raise TokenDemoInvalido('usuario')
    return usuario
