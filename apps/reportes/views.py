"""
Vistas de graficas, reportes y comparacion de periodos.

Los datos de las graficas se serializan a JSON en el servidor y viajan en un
<script type="application/json">, no incrustados en el HTML: asi el template
no interpola datos dentro de codigo JavaScript.
"""
import csv
import json
import logging
from datetime import timedelta

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_http_methods

from apps.piscinas.models import Geomembrana
from apps.monitoreo.models import TipoParametro
from apps.usuarios.permissions import puede_editar_modulo, puede_ver_modulo, resolver_dashboard

from .models import ComparacionDatos, Reporte
from .services import comparar_periodos, redactar_diferencias, resumen_periodo, serie_temporal

logger = logging.getLogger(__name__)


def _requiere(modulo):
    """Restringe la vista a los roles con el modulo en su matriz."""
    def decorador(vista):
        @login_required
        def envoltura(request, *args, **kwargs):
            if not puede_ver_modulo(request.user, modulo):
                messages.warning(request, 'No tienes permisos para ver ese módulo.')
                return redirect(resolver_dashboard(request.user))
            return vista(request, *args, **kwargs)
        envoltura.__name__ = vista.__name__
        envoltura.__doc__ = vista.__doc__
        return envoltura
    return decorador


def _rango_desde_get(request, dias_por_defecto=7):
    """
    Extrae y valida el rango de fechas de la querystring.

    :return: tuple(date desde, date hasta)
    """
    from datetime import date

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


# ======================================================================
# GRAFICAS Y REPORTES
# ======================================================================
@_requiere('graficas_reportes')
def graficas(request):
    """Graficas de evolucion por parametro y listado de reportes guardados."""
    piscinas = Geomembrana.objects.all()
    piscina_id = request.GET.get('piscina', '').strip()

    seleccionada = piscinas.filter(pk=piscina_id).first() if piscina_id.isdigit() else None
    if seleccionada is None:
        seleccionada = piscinas.first()

    desde, hasta = _rango_desde_get(request)

    parametro_id = request.GET.get('parametro', '').strip()
    parametro = None
    if parametro_id.isdigit():
        parametro = TipoParametro.objects.filter(pk=parametro_id).first()

    series = {}
    resumen = None
    if seleccionada:
        series = serie_temporal(seleccionada, desde, hasta, parametro)
        resumen = resumen_periodo(seleccionada, desde, hasta)

    return render(request, 'funcionalidades/graficasyreportes.html', {
        'actual': 'graficas_reportes',
        'piscinas': piscinas,
        'seleccionada': seleccionada,
        'parametros': TipoParametro.objects.filter(estado='activo'),
        'filtro_parametro': parametro_id,
        'desde': desde.isoformat(),
        'hasta': hasta.isoformat(),
        'resumen': resumen,
        'series_json': json.dumps(series, ensure_ascii=False),
        'reportes': Reporte.objects.select_related('geomembrana', 'generado_por')[:10],
        'puede_generar': puede_editar_modulo(request.user, 'graficas_reportes'),
        'tipos_reporte': Reporte.TIPOS,
    })


@login_required
@require_http_methods(['POST'])
def reporte_crear(request):
    """
    Congela el periodo consultado como un Reporte persistido.

    Los datos se guardan calculados: un reporte es evidencia de un momento,
    no una consulta que cambia cada vez que se abre.
    """
    if not puede_editar_modulo(request.user, 'graficas_reportes'):
        messages.error(request, 'Tu rol no permite generar reportes.')
        return redirect('reportes:graficas')

    geomembrana = get_object_or_404(Geomembrana, pk=request.POST.get('piscina'))
    desde, hasta = _rango_desde_get(request)

    from datetime import date
    try:
        desde = date.fromisoformat(request.POST.get('desde', ''))
        hasta = date.fromisoformat(request.POST.get('hasta', ''))
    except ValueError:
        messages.error(request, 'Rango de fechas inválido.')
        return redirect('reportes:graficas')

    if desde > hasta:
        desde, hasta = hasta, desde

    datos = resumen_periodo(geomembrana, desde, hasta)
    if not datos['lecturas']:
        messages.error(
            request,
            f'No hay lecturas de {geomembrana.nombre_piscina} entre {desde} y {hasta}. '
            'No se generó el reporte.'
        )
        return redirect('reportes:graficas')

    tipo = request.POST.get('tipo', 'personalizado')
    if tipo not in dict(Reporte.TIPOS):
        tipo = 'personalizado'

    titulo = (request.POST.get('titulo', '').strip()
              or f'{geomembrana.nombre_piscina} · {desde} a {hasta}')

    reporte = Reporte.objects.create(
        geomembrana=geomembrana,
        titulo=titulo,
        tipo_reporte=tipo,
        fecha_inicio=desde,
        fecha_fin=hasta,
        datos_reporte=datos,
        resumen_ejecutivo=_redactar_resumen(geomembrana, datos),
        generado_por=request.user,
    )

    logger.info('Reporte %s generado por %s', reporte.pk, request.user.email)
    messages.success(request, f'Reporte "{titulo}" generado.')
    return redirect(f"{reverse('reportes:graficas')}?piscina={geomembrana.pk}")


def _redactar_resumen(geomembrana, datos):
    """
    Redacta el resumen ejecutivo a partir de los agregados del periodo.

    :return: str con el resumen
    """
    lineas = [
        f'Periodo de {datos["dias"]} día(s) con {datos["lecturas"]} lecturas '
        f'en {geomembrana.nombre_piscina}.'
    ]
    if datos['cumplimiento'] is not None:
        lineas.append(f'Cumplimiento de rangos: {datos["cumplimiento"]}%.')
    if datos['fuera_rango']:
        lineas.append(
            f'{datos["fuera_rango"]} lectura(s) fuera de rango, '
            f'{datos["criticas"]} de ellas críticas.'
        )
    else:
        lineas.append('Todas las lecturas se mantuvieron dentro de rango.')
    if datos['alertas']:
        lineas.append(
            f'{datos["alertas"]} alerta(s) generadas, '
            f'{datos["alertas_resueltas"]} resueltas.'
        )

    criticos = [p['parametro'] for p in datos['parametros']
                if p['cumplimiento'] is not None and p['cumplimiento'] < 90]
    if criticos:
        lineas.append(f'Parámetros con menor cumplimiento: {", ".join(criticos)}.')

    return ' '.join(lineas)


@_requiere('graficas_reportes')
def reporte_csv(request, pk):
    """Exporta a CSV los agregados congelados de un reporte."""
    reporte = get_object_or_404(Reporte.objects.select_related('geomembrana'), pk=pk)

    respuesta = HttpResponse(content_type='text/csv; charset=utf-8-sig')
    respuesta['Content-Disposition'] = f'attachment; filename="reporte_{reporte.pk}.csv"'

    escritor = csv.writer(respuesta, delimiter=';')
    escritor.writerow([reporte.titulo])
    escritor.writerow(['Piscina', reporte.geomembrana.nombre_piscina])
    escritor.writerow(['Periodo', f'{reporte.fecha_inicio} a {reporte.fecha_fin}'])
    escritor.writerow([])
    escritor.writerow(['Parámetro', 'Unidad', 'Lecturas', 'Promedio', 'Mínimo',
                       'Máximo', 'Fuera de rango', 'Cumplimiento %'])

    for fila in reporte.datos_reporte.get('parametros', []):
        escritor.writerow([
            fila['parametro'], fila['unidad'], fila['lecturas'], fila['promedio'],
            fila['minimo'], fila['maximo'], fila['fuera_rango'], fila['cumplimiento'],
        ])

    escritor.writerow([])
    escritor.writerow(['Resumen', reporte.resumen_ejecutivo])
    return respuesta


# ======================================================================
# COMPARACION DE PERIODOS
# ======================================================================
@_requiere('comparacion_periodos')
def comparacion(request):
    """Compara dos rangos de fechas de la misma piscina."""
    from datetime import date

    piscinas = Geomembrana.objects.all()
    piscina_id = request.GET.get('piscina', '').strip()
    seleccionada = piscinas.filter(pk=piscina_id).first() if piscina_id.isdigit() else None
    if seleccionada is None:
        seleccionada = piscinas.first()

    hoy = timezone.localdate()
    defectos = {
        'p1_inicio': hoy - timedelta(days=14),
        'p1_fin': hoy - timedelta(days=8),
        'p2_inicio': hoy - timedelta(days=7),
        'p2_fin': hoy,
    }
    periodos = {}
    for clave, valor in defectos.items():
        try:
            periodos[clave] = date.fromisoformat(request.GET.get(clave, ''))
        except ValueError:
            periodos[clave] = valor

    resultado = None
    if seleccionada:
        resultado = comparar_periodos(
            seleccionada, periodos['p1_inicio'], periodos['p1_fin'],
            periodos['p2_inicio'], periodos['p2_fin'],
        )

    return render(request, 'funcionalidades/comparacion.html', {
        'actual': 'comparacion_periodos',
        'piscinas': piscinas,
        'seleccionada': seleccionada,
        'periodos': {k: v.isoformat() for k, v in periodos.items()},
        'resultado': resultado,
        'comparacion_json': json.dumps(resultado, ensure_ascii=False) if resultado else '{}',
        'diferencias': redactar_diferencias(resultado) if resultado else '',
        'guardadas': ComparacionDatos.objects.select_related('geomembrana')[:5],
        'puede_guardar': puede_editar_modulo(request.user, 'comparacion_periodos'),
    })


@login_required
@require_http_methods(['POST'])
def comparacion_guardar(request):
    """Persiste la comparacion en curso para poder consultarla luego."""
    if not puede_editar_modulo(request.user, 'comparacion_periodos'):
        messages.error(request, 'Tu rol no permite guardar comparaciones.')
        return redirect('reportes:comparacion')

    from datetime import date

    geomembrana = get_object_or_404(Geomembrana, pk=request.POST.get('piscina'))
    try:
        fechas = {c: date.fromisoformat(request.POST.get(c, ''))
                  for c in ('p1_inicio', 'p1_fin', 'p2_inicio', 'p2_fin')}
    except ValueError:
        messages.error(request, 'Fechas inválidas.')
        return redirect('reportes:comparacion')

    resultado = comparar_periodos(geomembrana, fechas['p1_inicio'], fechas['p1_fin'],
                                  fechas['p2_inicio'], fechas['p2_fin'])

    ComparacionDatos.objects.create(
        geomembrana=geomembrana,
        usuario=request.user,
        periodo_1_inicio=fechas['p1_inicio'], periodo_1_fin=fechas['p1_fin'],
        periodo_2_inicio=fechas['p2_inicio'], periodo_2_fin=fechas['p2_fin'],
        resultados_comparacion=resultado,
        diferencias_principales=redactar_diferencias(resultado),
    )

    messages.success(request, 'Comparación guardada.')
    return redirect(f"{reverse('reportes:comparacion')}?piscina={geomembrana.pk}")
