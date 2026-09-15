"""
Autenticacion de dispositivos fisicos (ESP32) para la API de ingesta.

No usa JWT: un nodo ESP32 no hace login ni refresca tokens, se reinicia y debe
autenticarse de inmediato. Cada Dispositivo tiene un token propio y revocable.

Cabecera esperada:
    Authorization: Device <token>
"""
from functools import wraps

from django.utils import timezone
from rest_framework import status
from rest_framework.response import Response

from .models import Dispositivo

PREFIJO_AUTH = 'Device'


def _extraer_token(request):
    """Devuelve el token de la cabecera Authorization, o None si no es valida."""
    cabecera = request.META.get('HTTP_AUTHORIZATION', '')
    partes = cabecera.split()
    if len(partes) != 2 or partes[0] != PREFIJO_AUTH:
        return None
    return partes[1]


def _ip_cliente(request):
    """IP real del dispositivo, respetando proxy inverso si existe."""
    reenviada = request.META.get('HTTP_X_FORWARDED_FOR')
    if reenviada:
        return reenviada.split(',')[0].strip()
    return request.META.get('REMOTE_ADDR')


def dispositivo_requerido(vista):
    """
    Decorador para vistas DRF: valida el token del dispositivo y lo inyecta
    en request.dispositivo. Rechaza dispositivos inactivos.
    """
    @wraps(vista)
    def _envoltorio(self, request, *args, **kwargs):
        token = _extraer_token(request)
        if not token:
            return Response(
                {'success': False, 'data': None,
                 'message': 'Cabecera Authorization ausente o mal formada. '
                            'Formato esperado: "Authorization: Device <token>".'},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        try:
            dispositivo = Dispositivo.objects.select_related('geomembrana').get(token=token)
        except Dispositivo.DoesNotExist:
            return Response(
                {'success': False, 'data': None, 'message': 'Token de dispositivo invalido.'},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        if dispositivo.estado == 'inactivo':
            return Response(
                {'success': False, 'data': None,
                 'message': f'El dispositivo {dispositivo.codigo} esta inactivo.'},
                status=status.HTTP_403_FORBIDDEN,
            )

        request.dispositivo = dispositivo
        request.ip_dispositivo = _ip_cliente(request)
        return vista(self, request, *args, **kwargs)

    return _envoltorio


def marcar_conexion(dispositivo, ip=None, mac=None, firmware=None):
    """Actualiza la telemetria de enlace del dispositivo sin tocar sus lecturas."""
    campos = ['ultima_conexion', 'estado']
    dispositivo.ultima_conexion = timezone.now()
    dispositivo.estado = 'activo'

    if mac and dispositivo.mac_address != mac:
        dispositivo.mac_address = mac
        campos.append('mac_address')
    if firmware and dispositivo.firmware_version != firmware:
        dispositivo.firmware_version = firmware
        campos.append('firmware_version')

    dispositivo.save(update_fields=campos)
    return ip
