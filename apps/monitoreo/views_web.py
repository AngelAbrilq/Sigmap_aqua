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

from . import exportacion
from .forms import SensorForm
from .rangos import rangos_efectivos
from .simulacion import es_parametro, tarjeta_oxigeno_simulada
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
# Lecturas por sensor que se envian al grafico en vivo (2 min a 2 s por lote).
PUNTOS_SERIE_VIVO = 60
REFRESCO_MIN_S = 2
REFRESCO_MAX_S = 15


def _intervalo_refresco(geomembrana):
    """
    Cada cuanto refresca el tablero: el intervalo de lectura mas corto de los
    sensores activos, acotado a [2, 15] s. Si el nodo envia cada 2 s, el
    tablero tambien; si envia cada 5 min, no tiene sentido consultar cada 2 s.
    """
    if geomembrana is None:
        return REFRESCO_MAX_S
    from django.db.models import Min
    minimo = geomembrana.sensores.filter(estado='activo').aggregate(
        m=Min('intervalo_lectura_segundos'))['m'] or REFRESCO_MAX_S
    return max(REFRESCO_MIN_S, min(REFRESCO_MAX_S, int(minimo)))


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
        'intervalo_refresco': _intervalo_refresco(seleccionada),
        'puntos_serie': PUNTOS_SERIE_VIVO,
    })


def _estado_sensores(geomembrana, puntos_serie=0):
    """
    Ultima lectura (y opcionalmente la serie reciente) de cada sensor activo.

    Antes se traian TODAS las lecturas de los ultimos 2 dias y se reducian en
    memoria: con el nodo enviando cada 2 s eso son cientos de miles de filas por
    refresco. Ahora se hace una consulta acotada por sensor que usa el indice
    (sensor, -timestamp_lectura): con 3-4 sensores son 3-4 lecturas de indice,
    mucho mas barato que el escaneo anterior.

    :param geomembrana: piscinas.Geomembrana
    :param puntos_serie: cuantas lecturas recientes incluir por sensor (0 = ninguna)
    :return: list de dicts listos para el template / JSON
    """
    sensores_activos = list(
        geomembrana.sensores.filter(estado='activo').select_related('tipo_parametro')
    )
    tarjetas = []
    for sensor in sensores_activos:
        limite = max(1, puntos_serie)
        recientes = list(
            Lectura.objects
            .filter(sensor=sensor)
            .order_by('-timestamp_lectura')
            .values('valor_medida', 'estado_lectura', 'timestamp_lectura')[:limite]
        )
        lectura = recientes[0] if recientes else None
        tipo = sensor.tipo_parametro
        rangos = rangos_efectivos(tipo, geomembrana.etapa_actual)
        tarjetas.append({
            'sensor': sensor,
            'parametro': tipo.nombre_parametro,
            'unidad': tipo.unidad_medida,
            'valor': lectura['valor_medida'] if lectura else None,
            'estado': lectura['estado_lectura'] if lectura else 'sin_datos',
            'momento': lectura['timestamp_lectura'] if lectura else None,
            'rango_min': rangos.normal_min,
            'rango_max': rangos.normal_max,
            'rango_fuente': rangos.fuente,
            'serie': [
                {'t': r['timestamp_lectura'].isoformat(), 'v': float(r['valor_medida'])}
                for r in reversed(recientes)
            ] if puntos_serie else [],
        })

    # Oxigeno de prueba mientras se instala el sensor real (ver simulacion.py).
    tipo_oxigeno = next(
        (t for t in TipoParametro.objects.all() if es_parametro(t.nombre_parametro, 'oxi')),
        None,
    )
    simulada = tarjeta_oxigeno_simulada(geomembrana, tarjetas, tipo_oxigeno)
    if simulada:
        tarjetas.append(simulada)
    return tarjetas


@requiere_lectura('monitoreo')
def api_estado(request, pk):
    """
    Estado actual de una piscina en JSON, para el refresco del tablero.

    Formato estandar {success, data, message}, igual que la API de hardware.

    :param pk: id de la geomembrana
    """
    geomembrana = get_object_or_404(Geomembrana, pk=pk)
    tarjetas = _estado_sensores(geomembrana, puntos_serie=PUNTOS_SERIE_VIVO)

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
                'rango_min': float(t['rango_min']) if t['rango_min'] is not None else None,
                'rango_max': float(t['rango_max']) if t['rango_max'] is not None else None,
                'rango_fuente': t['rango_fuente'],
                'serie': t['serie'],
                'simulado': t.get('simulado', False),
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


def _descarga(contenido, tipo, extension):
    """Respuesta de descarga con nombre fechado: historial_AAAAMMDD_HHMM.ext"""
    respuesta = HttpResponse(contenido, content_type=tipo)
    marca = timezone.localtime().strftime('%Y%m%d_%H%M')
    respuesta['Content-Disposition'] = f'attachment; filename="historial_{marca}.{extension}"'
    return respuesta


@requiere_lectura('historial')
def historial_excel(request):
    """Exporta el historial filtrado a Excel: hojas Resumen y Lecturas."""
    filtros, queryset = _filtrar_lecturas(request)
    ctx = exportacion.construir_contexto(filtros, queryset, request.user, MAX_FILAS_EXPORT)
    logger.info('Export Excel de historial por %s (%s filas)', request.user.email, len(ctx.lecturas))
    return _descarga(
        exportacion.generar_excel(ctx),
        'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet', 'xlsx')


@requiere_lectura('historial')
def historial_pdf(request):
    """Exporta el historial filtrado a un informe PDF."""
    filtros, queryset = _filtrar_lecturas(request)
    ctx = exportacion.construir_contexto(filtros, queryset, request.user, exportacion.MAX_FILAS_PDF)
    logger.info('Export PDF de historial por %s (%s filas)', request.user.email, len(ctx.lecturas))
    return _descarga(exportacion.generar_pdf(ctx), 'application/pdf', 'pdf')


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
        from apps.auditoria.services import ip_de, registrar_evento
        registrar_evento(
            'config_umbral',
            f'Parametro creado: {parametro.nombre_parametro}',
            usuario=request.user,
            datos={'campos': list(form.changed_data)}, ip=ip_de(request),
        )
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
        from apps.auditoria.services import ip_de, registrar_evento
        registrar_evento(
            'config_umbral',
            f'Umbrales de {parametro.nombre_parametro} modificados',
            usuario=request.user, nivel='advertencia',
            datos={'campos': list(form.changed_data)}, ip=ip_de(request),
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
