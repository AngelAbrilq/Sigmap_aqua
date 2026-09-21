"""
Consulta del historial de eventos del sistema (RF018).

Acceso exclusivo del Instructor Líder: la matriz de roles no concede el módulo
'eventos' a Operario ni Aprendiz, así que puede_ver_modulo() los bloquea.
"""
import logging
from datetime import date, timedelta

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Count, Q
from django.shortcuts import redirect, render
from django.utils import timezone

from apps.piscinas.models import Geomembrana
from apps.usuarios.permissions import puede_ver_modulo, resolver_dashboard

from .models import EventoSistema

logger = logging.getLogger('apps.auditoria')

MODULO = 'eventos'
POR_PAGINA = 25


def _requiere_lectura(vista):
    """Restringe la vista a los roles con el módulo 'eventos' en su matriz."""
    @login_required
    def envoltura(request, *args, **kwargs):
        if not puede_ver_modulo(request.user, MODULO):
            messages.warning(request, 'No tienes permisos para ver el registro de eventos.')
            return redirect(resolver_dashboard(request.user))
        return vista(request, *args, **kwargs)
    envoltura.__name__ = vista.__name__
    envoltura.__doc__ = vista.__doc__
    return envoltura


def _rango_desde_get(request, dias_por_defecto=30):
    """Extrae y valida el rango de fechas de la querystring."""
    hoy = timezone.localdate()
    try:
        desde = date.fromisoformat(request.GET.get('desde', ''))
    except ValueError:
        desde = hoy - timedelta(days=dias_por_defecto)
    try:
        hasta = date.fromisoformat(request.GET.get('hasta', ''))
    except ValueError:
        hasta = hoy
    if desde > hasta:
        desde, hasta = hasta, desde
    return desde, hasta


@_requiere_lectura
def lista(request):
    """Historial de eventos filtrable por tipo, nivel, piscina y rango de fechas."""
    queryset = EventoSistema.objects.select_related('usuario', 'geomembrana')

    tipo = request.GET.get('tipo', '').strip()
    nivel = request.GET.get('nivel', '').strip()
    piscina = request.GET.get('piscina', '').strip()
    desde, hasta = _rango_desde_get(request)

    queryset = queryset.filter(created_at__date__gte=desde, created_at__date__lte=hasta)
    if tipo in EventoSistema.Tipo.values:
        queryset = queryset.filter(tipo_evento=tipo)
    if nivel in EventoSistema.Nivel.values:
        queryset = queryset.filter(nivel=nivel)
    if piscina.isdigit():
        queryset = queryset.filter(geomembrana_id=piscina)

    resumen = queryset.aggregate(
        total=Count('id'),
        criticos=Count('id', filter=Q(nivel='critico')),
        advertencias=Count('id', filter=Q(nivel='advertencia')),
    )

    paginador = Paginator(queryset, POR_PAGINA)
    pagina = paginador.get_page(request.GET.get('page'))

    return render(request, 'funcionalidades/eventos.html', {
        'actual': MODULO,
        'pagina': pagina,
        'eventos': pagina.object_list,
        'resumen': resumen,
        'piscinas': Geomembrana.objects.all(),
        'tipos': EventoSistema.Tipo.choices,
        'niveles': EventoSistema.Nivel.choices,
        'filtros': {
            'tipo': tipo, 'nivel': nivel, 'piscina': piscina,
            'desde': desde.isoformat(), 'hasta': hasta.isoformat(),
        },
    })
