"""
Vistas del modulo de analisis predictivo.

Generar un analisis es una operacion de escritura que cuesta dinero (consume
cuota de la API), asi que exige POST con CSRF y permiso de escritura.
Validar o descartar un analisis queda reservado al Instructor Lider: es quien
responde por las decisiones tomadas sobre el cultivo.
"""
import logging

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_http_methods

from apps.piscinas.models import Geomembrana
from apps.usuarios.permissions import (
    ROL_INSTRUCTOR,
    obtener_nombre_rol,
    puede_editar_modulo,
    puede_ver_modulo,
    resolver_dashboard,
)

from .models import AnalisisIA
from .services import ErrorIA, generar_analisis

logger = logging.getLogger(__name__)

MODULO = 'ai'
VENTANAS_VALIDAS = {3, 7, 15, 30}


def _requiere_lectura(vista):
    """Restringe la vista a los roles con acceso al modulo de IA."""
    @login_required
    def envoltura(request, *args, **kwargs):
        if not puede_ver_modulo(request.user, MODULO):
            messages.warning(request, 'No tienes permisos para ver el análisis predictivo.')
            return redirect(resolver_dashboard(request.user))
        return vista(request, *args, **kwargs)
    envoltura.__name__ = vista.__name__
    envoltura.__doc__ = vista.__doc__
    return envoltura


@_requiere_lectura
def panel(request):
    """Historial de analisis generados, filtrable por piscina."""
    filtro_piscina = request.GET.get('piscina', '').strip()

    queryset = AnalisisIA.objects.select_related('geomembrana', 'validado_por')
    if filtro_piscina.isdigit():
        queryset = queryset.filter(geomembrana_id=filtro_piscina)

    paginador = Paginator(queryset, 10)
    pagina = paginador.get_page(request.GET.get('page'))

    ultimo = pagina.object_list[0] if pagina.object_list else None
    seleccion = request.GET.get('seleccion')
    if seleccion and seleccion.isdigit():
        ultimo = queryset.filter(pk=seleccion).first() or ultimo

    return render(request, 'funcionalidades/AI.html', {
        'actual': MODULO,
        'pagina': pagina,
        'analisis': pagina.object_list,
        'seleccionado': ultimo,
        'piscinas': Geomembrana.objects.operativas(),
        'filtro_piscina': filtro_piscina,
        'tipos_analisis': AnalisisIA.TIPOS,
        'ventanas': sorted(VENTANAS_VALIDAS),
        'puede_generar': puede_editar_modulo(request.user, MODULO),
        'puede_validar': obtener_nombre_rol(request.user) == ROL_INSTRUCTOR,
        'ia_configurada': bool(getattr(settings, 'GEMINI_API_KEY', '')),
    })


@login_required
@require_http_methods(['POST'])
def generar(request):
    """
    Pide un analisis nuevo a Gemini para la piscina seleccionada.

    Un fallo de la IA no es un fallo del sistema: se informa al usuario y se
    vuelve al panel, sin excepcion sin capturar.
    """
    if not puede_editar_modulo(request.user, MODULO):
        messages.error(request, 'Tu rol no permite generar análisis.')
        return redirect('ia:panel')

    piscina_id = request.POST.get('piscina', '')
    tipo = request.POST.get('tipo', 'diagnostico')
    try:
        dias = int(request.POST.get('dias', 7))
    except (TypeError, ValueError):
        dias = 7

    if tipo not in dict(AnalisisIA.TIPOS):
        tipo = 'diagnostico'
    if dias not in VENTANAS_VALIDAS:
        dias = 7

    geomembrana = get_object_or_404(Geomembrana, pk=piscina_id)

    try:
        analisis = generar_analisis(geomembrana, tipo=tipo, dias=dias)
    except ErrorIA as exc:
        logger.warning('Análisis IA fallido para %s: %s', geomembrana.codigo_identificacion, exc)
        messages.error(request, str(exc))
        return redirect('ia:panel')

    messages.success(
        request,
        f'Análisis generado para {geomembrana.nombre_piscina} '
        f'con {analisis.datos_entrada.get("total_lecturas", 0)} lecturas.'
    )
    return redirect(f"{reverse('ia:panel')}?seleccion={analisis.pk}")


@login_required
@require_http_methods(['POST'])
def cambiar_estado(request, pk):
    """
    Valida, descarta o marca como implementado un analisis.

    Exclusivo del Instructor Lider: una recomendacion de IA solo se convierte
    en instruccion operativa cuando una persona con criterio tecnico la avala.

    :param pk: id del analisis
    """
    if obtener_nombre_rol(request.user) != ROL_INSTRUCTOR:
        messages.error(request, 'Solo el Instructor Líder puede validar un análisis.')
        return redirect('ia:panel')

    analisis = get_object_or_404(AnalisisIA, pk=pk)
    nuevo = request.POST.get('estado', '')

    if nuevo not in dict(AnalisisIA.ESTADOS):
        messages.error(request, 'Estado no válido.')
        return redirect('ia:panel')

    analisis.estado = nuevo
    analisis.validado_por = request.user
    analisis.fecha_validacion = timezone.now()
    analisis.save(update_fields=['estado', 'validado_por', 'fecha_validacion'])

    logger.info('Análisis %s marcado como %s por %s', pk, nuevo, request.user.email)
    messages.success(request, f'Análisis marcado como {analisis.get_estado_display().lower()}.')
    return redirect(f"{reverse('ia:panel')}?seleccion={analisis.pk}")
