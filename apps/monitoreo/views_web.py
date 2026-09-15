"""
Vistas web del app monitoreo: sensores, tiempo real e historial.

Separadas de views.py, que sirve la API de ingesta de los nodos ESP32. Son dos
audiencias distintas: hardware autenticado por token, y personas autenticadas
por sesion.
"""
import csv
import logging
from datetime import timedelta

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Avg, Count, Max, Min, Q
from django.db.models.functions import TruncHour
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_http_methods

from apps.piscinas.models import Geomembrana
from apps.usuarios.permissions import puede_editar_modulo, puede_ver_modulo, resolver_dashboard

from .forms import SensorForm
from .models import Lectura, Sensor, TipoParametro

logger = logging.getLogger(__name__)

POR_PAGINA = 12
MAX_FILAS_EXPORT = 5000


# ----------------------------------------------------------------------
# Decoradores
# ----------------------------------------------------------------------
def requiere_lectura(modulo):
    """Restringe la vista a los roles con el modulo en su matriz de lectura."""
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


def requiere_escritura(modulo, destino):
    """Restringe la vista a los roles que pueden modificar el modulo."""
    def decorador(vista):
        @login_required
        def envoltura(request, *args, **kwargs):
            if not puede_editar_modulo(request.user, modulo):
                messages.error(request, 'Tu rol no permite modificar este módulo.')
                return redirect(destino)
            return vista(request, *args, **kwargs)
        envoltura.__name__ = vista.__name__
        envoltura.__doc__ = vista.__doc__
        return envoltura
    return decorador


# ======================================================================
# SENSORES
# ======================================================================
@requiere_lectura('sensores')
def sensores(request):
    """Listado de sensores con busqueda, filtros y panel de detalle."""
    termino = request.GET.get('q', '').strip()
    filtro_estado = request.GET.get('estado', '').strip()
    filtro_piscina = request.GET.get('piscina', '').strip()

    queryset = Sensor.objects.select_related('geomembrana', 'tipo_parametro')

    if termino:
        queryset = queryset.filter(
            Q(nombre_sensor__icontains=termino)
            | Q(codigo_hardware__icontains=termino)
            | Q(modelo_sensor__icontains=termino)
            | Q(marca_sensor__icontains=termino)
        )
    if filtro_estado in dict(Sensor.ESTADOS):
        queryset = queryset.filter(estado=filtro_estado)
    if filtro_piscina.isdigit():
        queryset = queryset.filter(geomembrana_id=filtro_piscina)

    resumen = queryset.aggregate(
        total=Count('id'),
        activos=Count('id', filter=Q(estado='activo')),
        averiados=Count('id', filter=Q(estado='averiado')),
        mantenimiento=Count('id', filter=Q(estado='mantenimiento')),
    )
    resumen['calibracion_vencida'] = queryset.filter(
        proxima_calibracion__lt=timezone.localdate()
    ).count()
    resumen['bateria_baja'] = queryset.filter(bateria_nivel_actual__lt=20).count()

    paginador = Paginator(queryset, POR_PAGINA)
    pagina = paginador.get_page(request.GET.get('page'))

    seleccion_id = request.GET.get('seleccion')
    seleccionado = queryset.filter(pk=seleccion_id).first() if seleccion_id else None
    if seleccionado is None and pagina.object_list:
        seleccionado = pagina.object_list[0]

    ultimas = []
    if seleccionado:
        ultimas = (
            Lectura.objects
            .filter(sensor=seleccionado)
            .select_related('tipo_parametro')[:10]
        )

    return render(request, 'funcionalidades/sensores.html', {
        'actual': 'sensores',
        'pagina': pagina,
        'sensores': pagina.object_list,
        'seleccionado': seleccionado,
        'ultimas_lecturas': ultimas,
        'resumen': resumen,
        'termino': termino,
        'filtro_estado': filtro_estado,
        'filtro_piscina': filtro_piscina,
        'estados_disponibles': Sensor.ESTADOS,
        'piscinas': Geomembrana.objects.operativas(),
        'puede_editar': puede_editar_modulo(request.user, 'sensores'),
        'form': SensorForm(),
        'form_editar': SensorForm(instance=seleccionado) if seleccionado else None,
    })


@requiere_escritura('sensores', 'monitoreo:sensores')
@require_http_methods(['POST'])
def sensor_crear(request):
    """Alta de sensor. Solo POST con CSRF valido."""
    form = SensorForm(request.POST)
    if form.is_valid():
        sensor = form.save()
        logger.info('Sensor creado %s por %s', sensor.codigo_hardware, request.user.email)
        messages.success(request, f'Sensor {sensor.codigo_hardware} registrado.')
        return redirect(f"{reverse('monitoreo:sensores')}?seleccion={sensor.pk}")

    messages.error(request, 'Revisa los campos marcados: el sensor no se registró.')
    return _sensores_con_errores(request, form, 'crear')


@requiere_escritura('sensores', 'monitoreo:sensores')
@require_http_methods(['POST'])
def sensor_editar(request, pk):
    """Actualiza un sensor existente."""
    sensor = get_object_or_404(Sensor, pk=pk)
    form = SensorForm(request.POST, instance=sensor)
    if form.is_valid():
        form.save()
        logger.info('Sensor editado %s por %s', sensor.codigo_hardware, request.user.email)
        messages.success(request, f'{sensor.codigo_hardware} actualizado.')
        return redirect(f"{reverse('monitoreo:sensores')}?seleccion={sensor.pk}")

    messages.error(request, 'Revisa los campos marcados: los cambios no se guardaron.')
    return _sensores_con_errores(request, form, 'editar', sensor)


@requiere_escritura('sensores', 'monitoreo:sensores')
@require_http_methods(['POST'])
def sensor_eliminar(request, pk):
    """
    Da de baja un sensor.

    Las lecturas lo referencian con PROTECT: un borrado fisico destruiria el
    historico de mediciones. Con lecturas asociadas se marca 'inactivo'.
    """
    sensor = get_object_or_404(Sensor, pk=pk)
    codigo = sensor.codigo_hardware
    lecturas = sensor.lecturas.count()

    if lecturas or sensor.alertas.exists():
        sensor.estado = 'inactivo'
        sensor.save(update_fields=['estado', 'fecha_edicion'])
        messages.warning(
            request,
            f'{codigo} tiene {lecturas} lectura(s) registradas. Se marcó como inactivo '
            f'en lugar de borrarse, para conservar el histórico.'
        )
    else:
        sensor.delete()
        messages.success(request, f'Sensor {codigo} eliminado.')

    logger.info('Baja de sensor %s por %s', codigo, request.user.email)
    return redirect('monitoreo:sensores')


def _sensores_con_errores(request, form, modal, seleccionado=None):
    """Re-renderiza el listado conservando el formulario con sus errores."""
    queryset = Sensor.objects.select_related('geomembrana', 'tipo_parametro')
    paginador = Paginator(queryset, POR_PAGINA)
    pagina = paginador.get_page(1)
    if seleccionado is None and pagina.object_list:
        seleccionado = pagina.object_list[0]

    return render(request, 'funcionalidades/sensores.html', {
        'actual': 'sensores',
        'pagina': pagina,
        'sensores': pagina.object_list,
        'seleccionado': seleccionado,
        'ultimas_lecturas': [],
        'resumen': queryset.aggregate(
            total=Count('id'),
            activos=Count('id', filter=Q(estado='activo')),
            averiados=Count('id', filter=Q(estado='averiado')),
            mantenimiento=Count('id', filter=Q(estado='mantenimiento')),
        ),
        'termino': '', 'filtro_estado': '', 'filtro_piscina': '',
        'estados_disponibles': Sensor.ESTADOS,
        'piscinas': Geomembrana.objects.operativas(),
        'puede_editar': True,
        'form': form if modal == 'crear' else SensorForm(),
        'form_editar': form if modal == 'editar' else (
            SensorForm(instance=seleccionado) if seleccionado else None
        ),
        'abrir_modal': modal,
    })


# ======================================================================
# MONITOREO EN TIEMPO REAL
# ======================================================================
@requiere_lectura('monitoreo')
def monitoreo(request):
    """
    Tablero de estado actual del agua por piscina.

    Muestra la ultima lectura de cada sensor. El refresco lo hace el endpoint
    JSON `monitoreo:api_estado`, no una recarga completa de la pagina.
    """
    piscina_id = request.GET.get('piscina', '').strip()
    piscinas = Geomembrana.objects.operativas().con_relaciones()

    seleccionada = None
    if piscina_id.isdigit():
        seleccionada = piscinas.filter(pk=piscina_id).first()
    if seleccionada is None:
        seleccionada = piscinas.first()

    return render(request, 'funcionalidades/monitoreo.html', {
        'actual': 'monitoreo',
        'piscinas': piscinas,
        'seleccionada': seleccionada,
        'tarjetas': _estado_sensores(seleccionada) if seleccionada else [],
        'intervalo_refresco': 15,
    })


def _estado_sensores(geomembrana):
    """
    Ultima lectura de cada sensor activo de una piscina.

    Una consulta por sensor seria N+1. En su lugar se traen las lecturas
    recientes de la piscina en UNA consulta y se reduce en memoria, quedandose
    con la primera de cada sensor (el orden por defecto ya es descendente).

    :param geomembrana: piscinas.Geomembrana
    :return: list de dicts listos para el template
    """
    sensores_activos = list(
        geomembrana.sensores.filter(estado='activo').select_related('tipo_parametro')
    )
    if not sensores_activos:
        return []

    corte = timezone.now() - timedelta(days=2)
    recientes = (
        Lectura.objects
        .filter(sensor__in=sensores_activos, timestamp_lectura__gte=corte)
        .select_related('sensor', 'tipo_parametro')
    )

    ultima_por_sensor = {}
    for lectura in recientes:
        ultima_por_sensor.setdefault(lectura.sensor_id, lectura)

    tarjetas = []
    for sensor in sensores_activos:
        lectura = ultima_por_sensor.get(sensor.id)
        tipo = sensor.tipo_parametro
        tarjetas.append({
            'sensor': sensor,
            'parametro': tipo.nombre_parametro,
            'unidad': tipo.unidad_medida,
            'valor': lectura.valor_medida if lectura else None,
            'estado': lectura.estado_lectura if lectura else 'sin_datos',
            'momento': lectura.timestamp_lectura if lectura else None,
            'rango_min': tipo.rango_normal_min,
            'rango_max': tipo.rango_normal_max,
            'bateria': sensor.bateria_nivel_actual,
        })
    return tarjetas


@requiere_lectura('monitoreo')
def api_estado(request, pk):
    """
    Estado actual de una piscina en JSON, para el refresco del tablero.

    Formato estandar {success, data, message}, igual que la API de hardware.

    :param pk: id de la geomembrana
    """
    geomembrana = get_object_or_404(Geomembrana, pk=pk)
    tarjetas = _estado_sensores(geomembrana)

    return JsonResponse({
        'success': True,
        'message': f'Estado de {geomembrana.nombre_piscina}.',
        'data': {
            'piscina': geomembrana.nombre_piscina,
            'semaforo': geomembrana.estado_operativo,
            'semaforo_label': geomembrana.estado_operativo_label,
            'alertas_activas': geomembrana.alertas_activas.count(),
            'actualizado': timezone.now().isoformat(),
            'sensores': [{
                'codigo': t['sensor'].codigo_hardware,
                'nombre': t['sensor'].nombre_sensor,
                'parametro': t['parametro'],
                'unidad': t['unidad'],
                'valor': float(t['valor']) if t['valor'] is not None else None,
                'estado': t['estado'],
                'momento': t['momento'].isoformat() if t['momento'] else None,
                'bateria': t['bateria'],
            } for t in tarjetas],
        },
    })


# ======================================================================
# HISTORIAL
# ======================================================================
@requiere_lectura('historial')
def historial(request):
    """
    Historico de lecturas con filtros por piscina, parametro, estado y fechas.

    Los filtros se aplican en la base de datos, nunca en Python: la tabla
    `lecturas_sensores` crece sin limite y traerla completa no es viable.
    """
    filtros, queryset = _filtrar_lecturas(request)

    resumen = queryset.aggregate(
        total=Count('id'),
        fuera_rango=Count('id', filter=Q(dentro_rango=False)),
        criticas=Count('id', filter=Q(estado_lectura='critico')),
        promedio=Avg('valor_medida'),
        minimo=Min('valor_medida'),
        maximo=Max('valor_medida'),
    )

    paginador = Paginator(queryset, 25)
    pagina = paginador.get_page(request.GET.get('page'))

    return render(request, 'funcionalidades/Historial.html', {
        'actual': 'historial',
        'pagina': pagina,
        'lecturas': pagina.object_list,
        'resumen': resumen,
        'piscinas': Geomembrana.objects.all(),
        'parametros': TipoParametro.objects.filter(estado='activo'),
        'estados_lectura': Lectura.ESTADOS_LECTURA,
        **filtros,
    })


@requiere_lectura('historial')
def historial_csv(request):
    """
    Exporta el historial filtrado a CSV.

    Se acota a MAX_FILAS_EXPORT y se recorre con iterator() para no cargar
    en memoria un rango de fechas amplio.
    """
    _, queryset = _filtrar_lecturas(request)

    respuesta = HttpResponse(content_type='text/csv; charset=utf-8-sig')
    marca = timezone.now().strftime('%Y%m%d_%H%M')
    respuesta['Content-Disposition'] = f'attachment; filename="historial_{marca}.csv"'

    escritor = csv.writer(respuesta, delimiter=';')
    escritor.writerow(['Fecha', 'Piscina', 'Sensor', 'Parámetro', 'Valor',
                       'Unidad', 'Estado', 'Dentro de rango'])

    for lectura in queryset[:MAX_FILAS_EXPORT].iterator(chunk_size=500):
        escritor.writerow([
            timezone.localtime(lectura.timestamp_lectura).strftime('%Y-%m-%d %H:%M:%S'),
            lectura.geomembrana.nombre_piscina,
            lectura.sensor.codigo_hardware,
            lectura.tipo_parametro.nombre_parametro,
            lectura.valor_medida,
            lectura.tipo_parametro.unidad_medida,
            lectura.get_estado_lectura_display(),
            'Sí' if lectura.dentro_rango else 'No',
        ])

    logger.info('Export CSV de historial por %s', request.user.email)
    return respuesta


def _filtrar_lecturas(request):
    """
    Traduce los parametros GET a un queryset filtrado de lecturas.

    Centraliza el filtrado para que la vista HTML y la exportacion CSV
    apliquen exactamente los mismos criterios.

    :return: tuple(dict con los filtros aplicados, QuerySet)
    """
    hoy = timezone.localdate()
    desde = request.GET.get('desde', '').strip() or (hoy - timedelta(days=7)).isoformat()
    hasta = request.GET.get('hasta', '').strip() or hoy.isoformat()
    piscina = request.GET.get('piscina', '').strip()
    parametro = request.GET.get('parametro', '').strip()
    estado = request.GET.get('estado', '').strip()

    queryset = Lectura.objects.select_related('sensor', 'geomembrana', 'tipo_parametro')

    try:
        queryset = queryset.filter(timestamp_lectura__date__gte=desde,
                                   timestamp_lectura__date__lte=hasta)
    except (ValueError, TypeError):
        # Fecha malformada en la URL: se ignora el rango en vez de reventar.
        desde = (hoy - timedelta(days=7)).isoformat()
        hasta = hoy.isoformat()
        queryset = queryset.filter(timestamp_lectura__date__gte=desde,
                                   timestamp_lectura__date__lte=hasta)

    if piscina.isdigit():
        queryset = queryset.filter(geomembrana_id=piscina)
    if parametro.isdigit():
        queryset = queryset.filter(tipo_parametro_id=parametro)
    if estado in dict(Lectura.ESTADOS_LECTURA):
        queryset = queryset.filter(estado_lectura=estado)

    filtros = {
        'desde': desde, 'hasta': hasta,
        'filtro_piscina': piscina, 'filtro_parametro': parametro, 'filtro_estado': estado,
    }
    return filtros, queryset


# ======================================================================
# CONFIGURACIONES (umbrales de los parametros)
# ======================================================================
@requiere_lectura('configuraciones')
def configuraciones(request):
    """
    Umbrales que deciden cuando una lectura es normal, de riesgo o critica.

    Es la pantalla mas sensible del sistema: estos rangos alimentan
    TipoParametro.clasificar(), del que dependen todas las alertas.
    """
    from .forms import TipoParametroForm

    parametros = TipoParametro.objects.annotate(
        sensores_asociados=Count('sensores', distinct=True)
    ).order_by('nombre_parametro')

    seleccion = request.GET.get('seleccion')
    seleccionado = parametros.filter(pk=seleccion).first() if seleccion else None
    if seleccionado is None and parametros:
        seleccionado = parametros.first()

    return render(request, 'funcionalidades/configuraciones.html', {
        'actual': 'configuraciones',
        'parametros': parametros,
        'seleccionado': seleccionado,
        'puede_editar': puede_editar_modulo(request.user, 'configuraciones'),
        'form': TipoParametroForm(),
        'form_editar': TipoParametroForm(instance=seleccionado) if seleccionado else None,
        'usuario_actual': request.user,
    })


@requiere_escritura('configuraciones', 'monitoreo:configuraciones')
@require_http_methods(['POST'])
def parametro_crear(request):
    """Da de alta un parametro medible con sus tres rangos."""
    from .forms import TipoParametroForm

    form = TipoParametroForm(request.POST)
    if form.is_valid():
        parametro = form.save()
        logger.info('TipoParametro creado %s por %s',
                    parametro.nombre_parametro, request.user.email)
        messages.success(request, f'Parámetro {parametro.nombre_parametro} creado.')
        return redirect(f"{reverse('monitoreo:configuraciones')}?seleccion={parametro.pk}")

    messages.error(request, 'Revisa los rangos: el parámetro no se creó.')
    return _configuraciones_con_errores(request, form, 'crear')


@requiere_escritura('configuraciones', 'monitoreo:configuraciones')
@require_http_methods(['POST'])
def parametro_editar(request, pk):
    """
    Modifica los umbrales de un parametro.

    Cambiar un rango no reclasifica las lecturas historicas a proposito: el
    historico refleja el criterio vigente cuando se midio, no el de hoy.
    """
    from .forms import TipoParametroForm

    parametro = get_object_or_404(TipoParametro, pk=pk)
    form = TipoParametroForm(request.POST, instance=parametro)
    if form.is_valid():
        form.save()
        logger.warning(
            'Umbrales de %s modificados por %s. Afecta a las alertas futuras.',
            parametro.nombre_parametro, request.user.email,
        )
        messages.success(
            request,
            f'{parametro.nombre_parametro} actualizado. Los nuevos rangos aplican '
            f'a las lecturas que lleguen desde ahora; el histórico no se reclasifica.'
        )
        return redirect(f"{reverse('monitoreo:configuraciones')}?seleccion={parametro.pk}")

    messages.error(request, 'Revisa los rangos: los cambios no se guardaron.')
    return _configuraciones_con_errores(request, form, 'editar', parametro)


def _configuraciones_con_errores(request, form, modal, seleccionado=None):
    """Re-renderiza configuraciones conservando el formulario con sus errores."""
    from .forms import TipoParametroForm

    parametros = TipoParametro.objects.annotate(
        sensores_asociados=Count('sensores', distinct=True)
    ).order_by('nombre_parametro')
    if seleccionado is None and parametros:
        seleccionado = parametros.first()

    return render(request, 'funcionalidades/configuraciones.html', {
        'actual': 'configuraciones',
        'parametros': parametros,
        'seleccionado': seleccionado,
        'puede_editar': True,
        'form': form if modal == 'crear' else TipoParametroForm(),
        'form_editar': form if modal == 'editar' else (
            TipoParametroForm(instance=seleccionado) if seleccionado else None
        ),
        'abrir_modal': modal,
        'usuario_actual': request.user,
    })
