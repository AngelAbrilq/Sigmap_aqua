"""
Acceso de demostración por QR.

Flujo:
    1. El instructor proyecta /demo/presentacion/ con un QR por rol.
    2. Alguien escanea: GET /demo/q/<token>/ muestra la animación de acceso
       (el GET no inicia sesión, así los visores de enlaces de WhatsApp o la
       vista previa de la cámara no "gastan" el acceso).
    3. La animación envía POST al mismo enlace: se valida la firma, se inicia
       sesión con el usuario del rol y se redirige a su panel.
    4. La pantalla de presentación consulta /demo/actividad/ y celebra cada
       ingreso en vivo.

Todo queda apagado salvo que DEMO_QR_ACTIVO=True en el .env.
"""

import logging
from datetime import timedelta

from django.conf import settings
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.http import Http404, JsonResponse
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_http_methods

from apps.auditoria.models import EventoSistema
from apps.auditoria.services import ip_de, registrar_evento
from apps.usuarios.permissions import ROL_INSTRUCTOR, obtener_nombre_rol, resolver_dashboard

from .qr import qr_svg
from .roles import ORDEN_ROLES, ROLES_DEMO, usuario_demo
from .tokens import TokenDemoInvalido, crear_token, leer_token, vigencia_segundos

logger = logging.getLogger(__name__)

VIA_QR = 'qr_demo'
BACKEND_SESION = 'django.contrib.auth.backends.ModelBackend'
MAX_EVENTOS_FEED = 20


def _exigir_demo_activo():
    """La demostración no existe (404) si no está activada en el .env."""
    if not getattr(settings, 'DEMO_QR_ACTIVO', False):
        raise Http404('Acceso de demostración desactivado')


def url_base(request):
    """
    URL pública del sistema para armar los enlaces de los QR.

    Prioridad: DEMO_QR_URL_BASE del .env; si no, la que llega por el túnel
    (cabeceras X-Forwarded-* de devtunnels) o la del propio request.

    :param request: HttpRequest
    :return: str sin barra final, ej. 'https://g8lnb4b3-8000.use.devtunnels.ms'
    """
    configurada = getattr(settings, 'DEMO_QR_URL_BASE', '').strip()
    if configurada:
        return configurada.rstrip('/')
    proto = request.META.get('HTTP_X_FORWARDED_PROTO', request.scheme).split(',')[0].strip()
    host = request.META.get('HTTP_X_FORWARDED_HOST', '').split(',')[0].strip() or request.get_host()
    return f'{proto}://{host}'


def enlace_acceso(base, usuario):
    """Enlace firmado que va dentro del QR de un usuario."""
    return f'{base}/demo/q/{crear_token(usuario)}/'


@csrf_exempt  # el token firmado ES la credencial; devtunnels rompe el chequeo de origen
@require_http_methods(['GET', 'POST'])
def acceso(request, token):
    """
    Pantalla de acceso del QR (GET) e inicio de sesión (POST).

    :param token: token firmado del QR
    """
    _exigir_demo_activo()

    try:
        usuario = leer_token(token)
    except TokenDemoInvalido as error:
        logger.info('QR de demostración rechazado: %s', error.motivo)
        return render(request, 'demo/acceso_invalido.html',
                      {'motivo': error.motivo, 'mensaje': str(error)}, status=403)

    nombre_rol = usuario.rol.nombre_rol
    rol = ROLES_DEMO[nombre_rol]

    if request.method == 'GET':
        return render(request, 'demo/acceso.html', {
            'usuario': usuario,
            'rol': rol,
            'minutos_sesion': settings.DEMO_QR_SESION_MINUTOS,
        })

    login(request, usuario, backend=BACKEND_SESION)
    request.session.set_expiry(int(settings.DEMO_QR_SESION_MINUTOS) * 60)
    request.session['acceso_demo'] = rol['slug']

    registrar_evento(
        EventoSistema.Tipo.SESION_INICIO,
        f'Ingreso por QR de demostración como {rol["titulo"]}',
        usuario=usuario,
        ip=ip_de(request),
        datos={
            'via': VIA_QR,
            'rol': rol['slug'],
            'dispositivo': request.META.get('HTTP_USER_AGENT', '')[:160],
        },
    )
    return redirect(resolver_dashboard(usuario))


def _solo_instructor(request):
    """El panel de presentación es del Instructor Líder."""
    return obtener_nombre_rol(request.user) == ROL_INSTRUCTOR


@login_required
@require_GET
def presentacion(request):
    """
    Pantalla para proyectar en la sustentación: un QR por rol y los ingresos
    en vivo. Cada carga firma tokens nuevos con DEMO_QR_HORAS de vigencia.
    """
    _exigir_demo_activo()
    if not _solo_instructor(request):
        return redirect(resolver_dashboard(request.user))

    base = url_base(request)
    tarjetas = []
    for nombre_rol in ORDEN_ROLES:
        usuario = usuario_demo(nombre_rol)
        rol = ROLES_DEMO[nombre_rol]
        if usuario is None:
            tarjetas.append({'rol': rol, 'usuario': None})
            continue
        enlace = enlace_acceso(base, usuario)
        tarjetas.append({
            'rol': rol,
            'usuario': usuario,
            'enlace': enlace,
            'qr': qr_svg(enlace, rol['color'], rol['color2'], uid=f'qr-{rol["slug"]}',
                         titulo=f'Código QR de acceso como {rol["titulo"]}'),
        })

    ultimo = EventoSistema.objects.order_by('-pk').values_list('pk', flat=True).first() or 0
    expira = timezone.localtime() + timedelta(seconds=vigencia_segundos())
    return render(request, 'demo/presentacion.html', {
        'tarjetas': tarjetas,
        'base': base,
        'expira': expira,
        'datos_js': {
            'expira': expira.isoformat(),
            'ultimo': ultimo,
            'url_actividad': reverse('demo:actividad'),
            'roles': {
                rol['slug']: {k: rol[k] for k in ('titulo', 'icono', 'color', 'color2')}
                for rol in ROLES_DEMO.values()
            },
        },
    })


@login_required
@require_GET
def actividad(request):
    """
    Ingresos por QR posteriores a un evento dado (feed en vivo).

    GET ?despues=<id_evento>
    Respuesta: {success, data: [{id, rol, nombre, hora}], message}
    """
    _exigir_demo_activo()
    if not _solo_instructor(request):
        return JsonResponse({'success': False, 'data': [], 'message': 'Sin permiso'}, status=403)

    try:
        despues = max(0, int(request.GET.get('despues', 0)))
    except (TypeError, ValueError):
        return JsonResponse({'success': False, 'data': [], 'message': 'Parámetro "despues" inválido'},
                            status=400)

    eventos = (
        EventoSistema.objects
        .filter(pk__gt=despues, tipo_evento=EventoSistema.Tipo.SESION_INICIO, datos__via=VIA_QR)
        .select_related('usuario')
        .order_by('pk')[:MAX_EVENTOS_FEED]
    )
    data = [
        {
            'id': evento.pk,
            'rol': evento.datos.get('rol', ''),
            'nombre': evento.usuario.nombre_completo if evento.usuario else 'Usuario',
            'hora': timezone.localtime(evento.created_at).strftime('%H:%M:%S'),
        }
        for evento in eventos
    ]
    return JsonResponse({'success': True, 'data': data, 'message': f'{len(data)} ingreso(s)'})
