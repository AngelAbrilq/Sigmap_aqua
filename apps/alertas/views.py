"""
Vistas del modulo de alertas.

Las alertas no se crean a mano: las genera el motor (services.evaluar_lote)
cuando la API de ingesta recibe una lectura fuera de rango. Desde aqui solo se
consultan, se reconocen y se resuelven.
"""
import logging

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_http_methods

from apps.piscinas.models import Geomembrana
from apps.usuarios.permissions import puede_editar_modulo, puede_ver_modulo, resolver_dashboard

from .models import Alerta, Notificacion
from .services import AccionInvalida, reconocer_alerta, resolver_alerta

logger = logging.getLogger(__name__)

MODULO = 'alertas'
POR_PAGINA = 15


def _requiere_lectura(vista):
    """Restringe la vista a los roles con acceso al modulo de alertas."""
    @login_required
    def envoltura(request, *args, **kwargs):
        if not puede_ver_modulo(request.user, MODULO):
            messages.warning(request, 'No tienes permisos para ver las alertas.')
            return redirect(resolver_dashboard(request.user))
        return vista(request, *args, **kwargs)
    envoltura.__name__ = vista.__name__
    envoltura.__doc__ = vista.__doc__
    return envoltura


def _requiere_escritura(vista):
    """Solo los roles operativos atienden alertas; el Aprendiz las consulta."""
    @login_required
    def envoltura(request, *args, **kwargs):
        if not puede_editar_modulo(request.user, MODULO):
            messages.error(request, 'Tu rol no permite atender alertas.')
            return redirect('alertas:listar')
        return vista(request, *args, **kwargs)
    envoltura.__name__ = vista.__name__
    envoltura.__doc__ = vista.__doc__
    return envoltura


@_requiere_lectura
def listar(request):
    """Bandeja de alertas con filtros por estado, severidad y piscina."""
    filtro_estado = request.GET.get('estado', 'activa').strip()
    filtro_severidad = request.GET.get('severidad', '').strip()
    filtro_piscina = request.GET.get('piscina', '').strip()

    queryset = Alerta.objects.select_related(
        'geomembrana', 'sensor', 'tipo_parametro', 'usuario_reconocimiento'
    )

    if filtro_estado in dict(Alerta.ESTADOS):
        queryset = queryset.filter(estado=filtro_estado)
    if filtro_severidad in dict(Alerta.SEVERIDADES):
        queryset = queryset.filter(severidad=filtro_severidad)
    if filtro_piscina.isdigit():
        queryset = queryset.filter(geomembrana_id=filtro_piscina)

    # El resumen mira TODAS las alertas, no solo las filtradas: es el estado
    # del sistema, no el del filtro que el usuario tenga puesto.
    resumen = Alerta.objects.aggregate(
        activas=Count('id', filter=Q(estado='activa')),
        criticas=Count('id', filter=Q(estado='activa', severidad='critica')),
        reconocidas=Count('id', filter=Q(estado='reconocida')),
        resueltas_hoy=Count('id', filter=Q(
            estado='resuelta', fecha_resolucion__date=timezone.localdate()
        )),
    )

    paginador = Paginator(queryset, POR_PAGINA)
    pagina = paginador.get_page(request.GET.get('page'))

    return render(request, 'funcionalidades/Alertas.html', {
        'actual': MODULO,
        'pagina': pagina,
        'alertas': pagina.object_list,
        'resumen': resumen,
        'filtro_estado': filtro_estado,
        'filtro_severidad': filtro_severidad,
        'filtro_piscina': filtro_piscina,
        'estados_disponibles': Alerta.ESTADOS,
        'severidades_disponibles': Alerta.SEVERIDADES,
        'piscinas': Geomembrana.objects.all(),
        'puede_editar': puede_editar_modulo(request.user, MODULO),
    })


@_requiere_escritura
@require_http_methods(['POST'])
def reconocer(request, pk):
    """
    Marca la alerta como vista por un operario.

    Reconocer no es resolver: deja constancia de quien se hizo cargo mientras
    el problema sigue abierto.
    """
    alerta = get_object_or_404(Alerta, pk=pk)
    try:
        reconocer_alerta(alerta, request.user)
    except AccionInvalida as error:
        messages.info(request, str(error))
    else:
        messages.success(request, 'Alerta reconocida.')
    return redirect('alertas:listar')


@_requiere_escritura
@require_http_methods(['POST'])
def resolver(request, pk):
    """
    Cierra la alerta registrando la accion correctiva aplicada.

    La accion tomada es obligatoria: una alerta critica cerrada sin explicacion
    no sirve para la trazabilidad del cultivo.
    """
    alerta = get_object_or_404(Alerta, pk=pk)
    try:
        resolver_alerta(alerta, request.user, request.POST.get('accion_tomada', ''))
    except AccionInvalida as error:
        messages.error(request, str(error))
    else:
        messages.success(request, 'Alerta resuelta.')
    return redirect('alertas:listar')


@login_required
@require_http_methods(['POST'])
def marcar_notificaciones_leidas(request):
    """Marca como leidas todas las notificaciones del usuario autenticado."""
    actualizadas = Notificacion.objects.filter(
        usuario=request.user, leida=False
    ).update(leida=True, fecha_lectura=timezone.now())

    messages.success(request, f'{actualizadas} notificación(es) marcadas como leídas.')
    return redirect(request.META.get('HTTP_REFERER') or 'alertas:listar')
