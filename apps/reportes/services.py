"""
Agregaciones para graficas, reportes y comparaciones.

Todo el calculo ocurre en la base de datos con annotate/aggregate. La tabla
`lecturas_sensores` es la que mas crece del sistema: traerla a Python para
promediar no escala mas alla de la demo.
"""
from datetime import timedelta
from decimal import Decimal

from django.db.models import Avg, Count, Max, Min, Q
from django.db.models.functions import TruncDay, TruncHour

from apps.alertas.models import Alerta
from apps.monitoreo.models import Lectura

# Por debajo de este umbral se agrupa por hora; por encima, por dia.
DIAS_PARA_AGRUPAR_POR_DIA = 3


def _num(valor):
    """Decimal -> float para poder serializar a JSON."""
    return float(valor) if isinstance(valor, Decimal) else valor


def serie_temporal(geomembrana, desde, hasta, tipo_parametro=None):
    """
    Evolucion del valor promedio por parametro a lo largo del periodo.

    Agrupa por hora en ventanas cortas y por dia en ventanas largas, para que
    la grafica nunca reciba miles de puntos que el navegador no puede dibujar.

    :param geomembrana: piscinas.Geomembrana
    :param desde: date inicial
    :param hasta: date final
    :param tipo_parametro: TipoParametro opcional para acotar
    :return: dict {parametro: {'unidad', 'puntos': [{'t', 'valor'}]}}
    """
    queryset = Lectura.objects.filter(
        geomembrana=geomembrana,
        timestamp_lectura__date__gte=desde,
        timestamp_lectura__date__lte=hasta,
    )
    if tipo_parametro:
        queryset = queryset.filter(tipo_parametro=tipo_parametro)

    truncador = TruncDay if (hasta - desde).days > DIAS_PARA_AGRUPAR_POR_DIA else TruncHour

    filas = (
        queryset
        .annotate(bloque=truncador('timestamp_lectura'))
        .values('bloque', 'tipo_parametro__nombre_parametro', 'tipo_parametro__unidad_medida')
        .annotate(promedio=Avg('valor_medida'), lecturas=Count('id'))
        .order_by('bloque')
    )

    series = {}
    for fila in filas:
        nombre = fila['tipo_parametro__nombre_parametro']
        serie = series.setdefault(nombre, {
            'unidad': fila['tipo_parametro__unidad_medida'],
            'puntos': [],
        })
        serie['puntos'].append({
            't': fila['bloque'].isoformat(),
            'valor': round(_num(fila['promedio']), 4),
            'lecturas': fila['lecturas'],
        })
    return series


def resumen_parametros(geomembrana, desde, hasta):
    """
    Estadistica descriptiva por parametro en un periodo.

    :return: list de dicts con promedio, min, max y conteos de incidencia
    """
    filas = (
        Lectura.objects
        .filter(geomembrana=geomembrana,
                timestamp_lectura__date__gte=desde,
                timestamp_lectura__date__lte=hasta)
        .values('tipo_parametro__nombre_parametro',
                'tipo_parametro__unidad_medida',
                'tipo_parametro__rango_normal_min',
                'tipo_parametro__rango_normal_max')
        .annotate(
            lecturas=Count('id'),
            promedio=Avg('valor_medida'),
            minimo=Min('valor_medida'),
            maximo=Max('valor_medida'),
            fuera_rango=Count('id', filter=Q(dentro_rango=False)),
            criticas=Count('id', filter=Q(estado_lectura='critico')),
        )
        .order_by('tipo_parametro__nombre_parametro')
    )

    resultado = []
    for fila in filas:
        lecturas = fila['lecturas'] or 0
        fuera = fila['fuera_rango'] or 0
        resultado.append({
            'parametro': fila['tipo_parametro__nombre_parametro'],
            'unidad': fila['tipo_parametro__unidad_medida'],
            'rango_min': _num(fila['tipo_parametro__rango_normal_min']),
            'rango_max': _num(fila['tipo_parametro__rango_normal_max']),
            'lecturas': lecturas,
            'promedio': round(_num(fila['promedio']), 3) if fila['promedio'] is not None else None,
            'minimo': _num(fila['minimo']),
            'maximo': _num(fila['maximo']),
            'fuera_rango': fuera,
            'criticas': fila['criticas'] or 0,
            # Cumplimiento: el indicador que realmente importa al piscicultor.
            'cumplimiento': round((lecturas - fuera) / lecturas * 100, 1) if lecturas else None,
        })
    return resultado


def resumen_periodo(geomembrana, desde, hasta):
    """
    Cifras globales del periodo, usadas por reportes y comparaciones.

    :return: dict serializable
    """
    lecturas = Lectura.objects.filter(
        geomembrana=geomembrana,
        timestamp_lectura__date__gte=desde,
        timestamp_lectura__date__lte=hasta,
    ).aggregate(
        total=Count('id'),
        fuera_rango=Count('id', filter=Q(dentro_rango=False)),
        criticas=Count('id', filter=Q(estado_lectura='critico')),
    )

    alertas = Alerta.objects.filter(
        geomembrana=geomembrana,
        fecha_generacion__date__gte=desde,
        fecha_generacion__date__lte=hasta,
    ).aggregate(
        total=Count('id'),
        criticas=Count('id', filter=Q(severidad='critica')),
        resueltas=Count('id', filter=Q(estado='resuelta')),
    )

    total = lecturas['total'] or 0
    fuera = lecturas['fuera_rango'] or 0

    return {
        'desde': desde.isoformat(),
        'hasta': hasta.isoformat(),
        'dias': (hasta - desde).days + 1,
        'lecturas': total,
        'fuera_rango': fuera,
        'criticas': lecturas['criticas'] or 0,
        'cumplimiento': round((total - fuera) / total * 100, 1) if total else None,
        'alertas': alertas['total'] or 0,
        'alertas_criticas': alertas['criticas'] or 0,
        'alertas_resueltas': alertas['resueltas'] or 0,
        'parametros': resumen_parametros(geomembrana, desde, hasta),
    }


def comparar_periodos(geomembrana, p1_inicio, p1_fin, p2_inicio, p2_fin):
    """
    Compara dos periodos y calcula la variacion de cada indicador.

    :return: dict con ambos resumenes y las diferencias calculadas
    """
    uno = resumen_periodo(geomembrana, p1_inicio, p1_fin)
    dos = resumen_periodo(geomembrana, p2_inicio, p2_fin)

    def delta(a, b):
        """Variacion absoluta y relativa de b respecto de a."""
        if a is None or b is None:
            return {'absoluto': None, 'porcentaje': None, 'direccion': 'sin_datos'}
        diferencia = round(b - a, 2)
        porcentaje = round((b - a) / a * 100, 1) if a else None
        if diferencia > 0:
            direccion = 'sube'
        elif diferencia < 0:
            direccion = 'baja'
        else:
            direccion = 'igual'
        return {'absoluto': diferencia, 'porcentaje': porcentaje, 'direccion': direccion}

    # Por parametro, emparejando por nombre.
    params_uno = {p['parametro']: p for p in uno['parametros']}
    params_dos = {p['parametro']: p for p in dos['parametros']}

    por_parametro = []
    for nombre in sorted(set(params_uno) | set(params_dos)):
        a = params_uno.get(nombre)
        b = params_dos.get(nombre)
        por_parametro.append({
            'parametro': nombre,
            'unidad': (a or b).get('unidad'),
            'periodo_1': a['promedio'] if a else None,
            'periodo_2': b['promedio'] if b else None,
            'variacion': delta(a['promedio'] if a else None, b['promedio'] if b else None),
            'cumplimiento_1': a['cumplimiento'] if a else None,
            'cumplimiento_2': b['cumplimiento'] if b else None,
        })

    return {
        'periodo_1': uno,
        'periodo_2': dos,
        'variaciones': {
            'lecturas': delta(uno['lecturas'], dos['lecturas']),
            'fuera_rango': delta(uno['fuera_rango'], dos['fuera_rango']),
            'cumplimiento': delta(uno['cumplimiento'], dos['cumplimiento']),
            'alertas': delta(uno['alertas'], dos['alertas']),
        },
        'por_parametro': por_parametro,
    }


def redactar_diferencias(comparacion):
    """
    Traduce las variaciones numericas a frases legibles.

    :param comparacion: dict de comparar_periodos
    :return: str con una linea por hallazgo relevante
    """
    lineas = []
    cumplimiento = comparacion['variaciones']['cumplimiento']

    if cumplimiento['direccion'] == 'sube':
        lineas.append(
            f'El cumplimiento de rangos mejoró {abs(cumplimiento["absoluto"])} puntos.'
        )
    elif cumplimiento['direccion'] == 'baja':
        lineas.append(
            f'El cumplimiento de rangos cayó {abs(cumplimiento["absoluto"])} puntos.'
        )

    alertas = comparacion['variaciones']['alertas']
    if alertas['direccion'] == 'sube':
        lineas.append(f'Se generaron {abs(alertas["absoluto"])} alerta(s) más que en el periodo 1.')
    elif alertas['direccion'] == 'baja':
        lineas.append(f'Se generaron {abs(alertas["absoluto"])} alerta(s) menos.')

    for fila in comparacion['por_parametro']:
        variacion = fila['variacion']
        if variacion['porcentaje'] is not None and abs(variacion['porcentaje']) >= 10:
            verbo = 'subió' if variacion['direccion'] == 'sube' else 'bajó'
            lineas.append(
                f'{fila["parametro"]} {verbo} {abs(variacion["porcentaje"])}% '
                f'({fila["periodo_1"]} → {fila["periodo_2"]} {fila["unidad"]}).'
            )

    return '\n'.join(lineas) or 'Sin diferencias relevantes entre los dos periodos.'
