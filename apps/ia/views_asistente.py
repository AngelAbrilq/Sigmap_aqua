"""
Endpoints del asistente IA flotante (circulo de la esquina).

- POST asistente/preguntar/: pregunta libre -> respuesta estructurada (JSON).
- GET  asistente/<pk>/excel/: descarga el informe de una respuesta.

Respuestas JSON con el formato estandar {success, data, message}.
"""
import json
import logging

from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_GET, require_POST

from apps.usuarios.permissions import ROL_INSTRUCTOR, obtener_nombre_rol, puede_ver_modulo

from .asistente import LimiteConsultas, MAX_PREGUNTA, generar_excel, preguntar
from .models import ConsultaIA
from .services import ErrorIA

logger = logging.getLogger(__name__)

MODULO = 'ai'


def _json(success, data=None, message='', status=200):
    return JsonResponse({'success': success, 'data': data, 'message': message}, status=status)


def _autorizado(request):
    """Sesion iniciada y rol con acceso al modulo de IA."""
    usuario = request.user
    return usuario.is_authenticated and puede_ver_modulo(usuario, MODULO)


@require_POST
def preguntar_view(request):
    """
    Recibe {"pregunta": "..."} y devuelve la respuesta de la IA.

    Errores: 400 pregunta invalida, 401/403 sin permiso, 429 limite de
    preguntas, 503 IA no disponible.
    """
    if not request.user.is_authenticated:
        return _json(False, message='Tu sesión expiró. Vuelve a iniciar sesión.', status=401)
    if not _autorizado(request):
        return _json(False, message='Tu rol no tiene acceso al asistente IA.', status=403)

    try:
        cuerpo = json.loads(request.body or b'{}')
    except (ValueError, UnicodeDecodeError):
        return _json(False, message='Solicitud inválida.', status=400)

    pregunta = cuerpo.get('pregunta') if isinstance(cuerpo, dict) else None
    if not isinstance(pregunta, str) or not pregunta.strip():
        return _json(False, data={'campo': 'pregunta'}, message='Escribe una pregunta.', status=400)
    if len(pregunta) > MAX_PREGUNTA:
        return _json(False, data={'campo': 'pregunta'},
                     message=f'La pregunta supera {MAX_PREGUNTA} caracteres.', status=400)

    try:
        consulta = preguntar(request.user, pregunta)
    except LimiteConsultas as error:
        return _json(False, message=str(error), status=429)
    except ErrorIA as error:
        logger.warning('Asistente IA sin respuesta para %s: %s', request.user.email, error)
        return _json(False, message=str(error), status=503)
    except Exception:  # noqa: BLE001 - el chat siempre recibe JSON, nunca una pagina 500
        logger.exception('Asistente IA: error inesperado respondiendo a %s', request.user.email)
        return _json(False, message='Ocurrió un error interno en el asistente. '
                                    'El detalle quedó en logs/ia.log.', status=500)

    datos = dict(consulta.respuesta)
    datos.update({'id': consulta.pk, 'modelo': consulta.modelo_usado, 'url_excel': None})
    if consulta.pk:
        datos['url_excel'] = reverse('ia:asistente_excel', args=[consulta.pk])
        mensaje = 'Respuesta generada.'
    else:
        mensaje = ('Respuesta generada, pero no se pudo guardar para descargarla en Excel. '
                   'Ejecuta: python manage.py migrate')
    datos['aviso'] = '' if consulta.pk else mensaje
    return _json(True, data=datos, message=mensaje)


@require_GET
def excel_view(request, pk):
    """
    Descarga el informe Excel de una consulta.

    Solo su autor o el Instructor Lider pueden descargarla; para el resto la
    consulta "no existe" (404), asi no se revela que ids hay.
    """
    if not _autorizado(request):
        return _json(False, message='No autorizado.', status=403)

    consulta = get_object_or_404(ConsultaIA.objects.select_related('usuario'), pk=pk)
    if consulta.usuario_id != request.user.pk and obtener_nombre_rol(request.user) != ROL_INSTRUCTOR:
        return _json(False, message='Consulta no encontrada.', status=404)

    respuesta = HttpResponse(
        generar_excel(consulta),
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    )
    marca = timezone.localtime(consulta.fecha_creacion).strftime('%Y%m%d_%H%M')
    respuesta['Content-Disposition'] = f'attachment; filename="asistente_ia_{marca}_{consulta.pk}.xlsx"'
    return respuesta
