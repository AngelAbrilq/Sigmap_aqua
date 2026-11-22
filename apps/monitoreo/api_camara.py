"""
Endpoint de la camara del nodo ESP32 (RF027).

    POST /api/v1/capturas/
    Authorization: Device <token>
    Content-Type: image/jpeg
    X-Motivo: periodica | alerta          (opcional, por defecto periodica)
    X-Timestamp: 2026-11-22T10:15:00-05:00 (opcional, hora NTP del nodo)
    <cuerpo: bytes JPEG crudos>

Se envia el JPEG crudo y no multipart: el ESP32 no tiene que armar un
formulario y el servidor valida que realmente sea una imagen con Pillow
antes de guardarla (un archivo con extension .jpg no basta).
"""
import io
import logging

from django.core.files.base import ContentFile
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from PIL import Image, UnidentifiedImageError
from rest_framework import status

from .api_auth import dispositivo_requerido, marcar_conexion
from .models import CapturaCamara
from .views import BaseVistaDispositivo, respuesta

logger = logging.getLogger(__name__)

TAMANO_MAX_BYTES = 200 * 1024       # una QQVGA en JPEG pesa ~3-8 KB
DIMENSION_MAX_PX = 1600
FIRMA_JPEG = b'\xff\xd8'
MOTIVOS_VALIDOS = {clave for clave, _ in CapturaCamara.MOTIVOS}


def _validar_jpeg(contenido):
    """
    Comprueba que los bytes sean un JPEG real y legible.

    :param contenido: bytes recibidos
    :return: (ancho, alto)
    :raises ValueError: con el motivo legible si la imagen no es valida
    """
    if not contenido:
        raise ValueError('El cuerpo esta vacio: se esperaba una imagen JPEG.')
    if len(contenido) > TAMANO_MAX_BYTES:
        raise ValueError(f'La imagen supera {TAMANO_MAX_BYTES // 1024} KB.')
    if not contenido.startswith(FIRMA_JPEG):
        raise ValueError('El contenido no es un JPEG (firma invalida).')
    try:
        with Image.open(io.BytesIO(contenido)) as imagen:
            imagen.verify()                       # detecta archivos truncados
        with Image.open(io.BytesIO(contenido)) as imagen:
            ancho, alto = imagen.size
            formato = imagen.format
    except (UnidentifiedImageError, OSError, SyntaxError) as error:
        raise ValueError(f'Imagen corrupta o ilegible: {error}') from error
    if formato != 'JPEG':
        raise ValueError(f'Formato {formato} no permitido: solo JPEG.')
    if ancho > DIMENSION_MAX_PX or alto > DIMENSION_MAX_PX:
        raise ValueError('Dimensiones de imagen fuera de rango.')
    return ancho, alto


def _momento_captura(valor):
    """Hora enviada por el nodo; si no hay o no es valida, la de recepcion."""
    momento = parse_datetime(valor or '')
    if momento is None:
        return timezone.now()
    if timezone.is_naive(momento):
        momento = timezone.make_aware(momento)
    # Un reloj mal sincronizado no debe dejar fotos "del futuro".
    return min(momento, timezone.now())


class CapturaCamaraView(BaseVistaDispositivo):
    """Recibe y guarda la foto del estanque tomada por el nodo."""

    @dispositivo_requerido
    def post(self, request):
        dispositivo = request.dispositivo

        tipo = request.META.get('CONTENT_TYPE', '').split(';')[0].strip().lower()
        if tipo != 'image/jpeg':
            return respuesta(False, message='Content-Type debe ser image/jpeg.',
                             codigo=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE)

        contenido = request.body
        try:
            ancho, alto = _validar_jpeg(contenido)
        except ValueError as error:
            logger.warning('Captura rechazada dispositivo=%s: %s', dispositivo.codigo, error)
            return respuesta(False, data={'campo': 'imagen', 'detalle': str(error)},
                             message='Imagen rechazada.', codigo=status.HTTP_400_BAD_REQUEST)

        motivo = request.META.get('HTTP_X_MOTIVO', 'periodica').strip().lower()
        if motivo not in MOTIVOS_VALIDOS:
            motivo = 'periodica'

        captura = CapturaCamara(
            dispositivo=dispositivo,
            geomembrana=dispositivo.geomembrana,
            motivo=motivo,
            ancho=ancho,
            alto=alto,
            tamano_bytes=len(contenido),
            timestamp_captura=_momento_captura(request.META.get('HTTP_X_TIMESTAMP')),
        )
        captura.imagen.save('captura.jpg', ContentFile(contenido), save=True)
        marcar_conexion(dispositivo, ip=request.ip_dispositivo)

        logger.info('Captura guardada dispositivo=%s id=%s %sx%s %s B motivo=%s',
                    dispositivo.codigo, captura.pk, ancho, alto, len(contenido), motivo)
        return respuesta(
            True,
            data={'id': captura.pk, 'url': captura.imagen.url,
                  'ancho': ancho, 'alto': alto, 'motivo': motivo},
            message='Captura registrada.',
            codigo=status.HTTP_201_CREATED,
        )
