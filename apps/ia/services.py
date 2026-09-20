"""
Cliente de Gemini y construccion del contexto de analisis.

Usa urllib de la biblioteca estandar en vez de `requests`: el proyecto ya
tiene 11 dependencias y este modulo solo hace un POST con JSON.

El sistema NO depende de que la IA este disponible. Si falta la API key o
Google responde con error, se lanza ErrorIA y la vista lo informa; el resto
del monitoreo sigue funcionando igual.
"""
import json
import logging
import urllib.error
import urllib.request
from datetime import date, timedelta
from decimal import Decimal

from django.conf import settings
from django.db.models import Avg, Count, Max, Min, Q
from django.utils import timezone

from apps.alertas.models import Alerta
from apps.monitoreo.models import Lectura

from .models import AnalisisIA, Prediccion

logger = logging.getLogger(__name__)

URL_BASE = 'https://generativelanguage.googleapis.com/v1beta/models'
TIEMPO_ESPERA = 30  # segundos

# Esquema que se le exige al modelo. Forzar JSON estructurado evita tener que
# parsear prosa libre y hace el resultado utilizable por el template.
ESQUEMA_RESPUESTA = {
    'type': 'OBJECT',
    'properties': {
        'diagnostico': {'type': 'STRING'},
        'anomalias': {
            'type': 'ARRAY',
            'items': {
                'type': 'OBJECT',
                'properties': {
                    'parametro': {'type': 'STRING'},
                    'descripcion': {'type': 'STRING'},
                    'gravedad': {'type': 'STRING', 'enum': ['baja', 'media', 'alta']},
                },
                'required': ['parametro', 'descripcion', 'gravedad'],
            },
        },
        'recomendaciones': {'type': 'ARRAY', 'items': {'type': 'STRING'}},
        'riesgo_proyectado': {'type': 'STRING', 'enum': ['bajo', 'medio', 'alto']},
        'confianza': {'type': 'NUMBER'},
    },
    'required': ['diagnostico', 'anomalias', 'recomendaciones',
                 'riesgo_proyectado', 'confianza'],
}

# Esquema para el analisis de tipo 'prediccion'.
#
# Exige proyecciones FALSABLES: un intervalo numerico y una fecha concreta. Una
# frase como "el pH podria subir" no se puede contrastar contra nada; "el pH
# estara entre 7.8 y 8.3 el jueves" si. Sin esto no hay forma de medir si el
# modelo acierta.
ESQUEMA_PREDICCION = {
    'type': 'OBJECT',
    'properties': {
        'diagnostico': {'type': 'STRING'},
        'anomalias': {
            'type': 'ARRAY',
            'items': {
                'type': 'OBJECT',
                'properties': {
                    'parametro': {'type': 'STRING'},
                    'descripcion': {'type': 'STRING'},
                    'gravedad': {'type': 'STRING', 'enum': ['baja', 'media', 'alta']},
                },
                'required': ['parametro', 'descripcion', 'gravedad'],
            },
        },
        'recomendaciones': {'type': 'ARRAY', 'items': {'type': 'STRING'}},
        'riesgo_proyectado': {'type': 'STRING', 'enum': ['bajo', 'medio', 'alto']},
        'confianza': {'type': 'NUMBER'},
        'predicciones': {
            'type': 'ARRAY',
            'items': {
                'type': 'OBJECT',
                'properties': {
                    'parametro': {'type': 'STRING'},
                    'valor_esperado': {'type': 'NUMBER'},
                    'valor_min': {'type': 'NUMBER'},
                    'valor_max': {'type': 'NUMBER'},
                    'probabilidad_fuera_de_rango': {'type': 'NUMBER'},
                    'justificacion': {'type': 'STRING'},
                },
                'required': ['parametro', 'valor_esperado', 'valor_min',
                             'valor_max', 'justificacion'],
            },
        },
    },
    'required': ['diagnostico', 'anomalias', 'recomendaciones',
                 'riesgo_proyectado', 'confianza', 'predicciones'],
}

INSTRUCCION_SISTEMA = (
    'Eres un ingeniero acuícola que asesora a un equipo de piscicultura en Huila, '
    'Colombia. Analizas datos de calidad de agua de estanques con geomembrana. '
    'Respondes SIEMPRE en español, con lenguaje técnico pero comprensible para un '
    'operario de campo. Basas cada afirmación únicamente en los datos que recibes; '
    'si los datos son insuficientes para concluir algo, lo dices explícitamente en '
    'lugar de inventar. Tus recomendaciones son acciones concretas y ejecutables '
    'en campo, no generalidades. El campo confianza es un número de 0 a 100 que '
    'refleja qué tan sólida es tu conclusión dada la cantidad y calidad de los datos.\n\n'
    'Cuando se te pidan predicciones, el sistema guardará cada intervalo que des '
    'y lo comparará contra lo que midan los sensores ese día, para llevar tu '
    'porcentaje real de aciertos. Da intervalos honestos: uno demasiado ancho '
    'acierta siempre pero no sirve para decidir nada, y uno demasiado estrecho '
    'falla. Ajusta la amplitud a la variabilidad que veas en los datos.'
)


class ErrorIA(Exception):
    """Fallo al obtener un analisis del modelo."""


# ----------------------------------------------------------------------
# Contexto
# ----------------------------------------------------------------------
def construir_contexto(geomembrana, dias=7):
    """
    Reune la evidencia numerica que se le entrega al modelo.

    Se envian agregados (promedio, minimo, maximo, conteos), no las lecturas
    crudas: un periodo de 7 dias con 4 sensores a 5 minutos son ~8000 filas,
    que ni caben en el prompt ni aportan mas que su estadistica.

    :param geomembrana: piscinas.Geomembrana a analizar
    :param dias: ventana de analisis
    :return: dict serializable con el contexto
    """
    desde = timezone.now() - timedelta(days=dias)

    por_parametro = (
        Lectura.objects
        .filter(geomembrana=geomembrana, timestamp_lectura__gte=desde)
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

    def num(valor):
        """Decimal -> float, para que el dict sea serializable a JSON."""
        return float(valor) if isinstance(valor, Decimal) else valor

    parametros = [{
        'parametro': fila['tipo_parametro__nombre_parametro'],
        'unidad': fila['tipo_parametro__unidad_medida'],
        'rango_normal': [num(fila['tipo_parametro__rango_normal_min']),
                         num(fila['tipo_parametro__rango_normal_max'])],
        'lecturas': fila['lecturas'],
        'promedio': round(num(fila['promedio']), 4) if fila['promedio'] is not None else None,
        'minimo': num(fila['minimo']),
        'maximo': num(fila['maximo']),
        'lecturas_fuera_de_rango': fila['fuera_rango'],
        'lecturas_criticas': fila['criticas'],
    } for fila in por_parametro]

    alertas = list(
        Alerta.objects
        .filter(geomembrana=geomembrana, fecha_generacion__gte=desde)
        .values('severidad', 'estado', 'mensaje_alerta')[:20]
    )

    return {
        'piscina': {
            'nombre': geomembrana.nombre_piscina,
            'codigo': geomembrana.codigo_identificacion,
            'area_m2': num(geomembrana.area_m2),
            'volumen_m3': num(geomembrana.volumen_agua_m3),
            'capacidad_peces': geomembrana.capacidad_maxima_peces,
            'etapa': geomembrana.etapa_actual.nombre_etapa if geomembrana.etapa_actual_id else None,
            'estado_operativo': geomembrana.estado_operativo_label,
            'vida_util_restante_pct': geomembrana.vida_util_restante_pct,
        },
        'ventana_dias': dias,
        'parametros': parametros,
        'alertas_periodo': alertas,
        'total_lecturas': sum(p['lecturas'] for p in parametros),
    }


def _construir_prompt(contexto, tipo, horizonte=3):
    """
    Redacta la peticion concreta segun el tipo de analisis solicitado.

    :param contexto: dict de construir_contexto
    :param tipo: 'diagnostico' | 'prediccion' | 'recomendacion'
    :param horizonte: dias hacia adelante a proyectar (solo 'prediccion')
    :return: str con el prompt
    """
    objetivo = (timezone.localdate() + timedelta(days=horizonte)).isoformat()

    encargos = {
        'diagnostico': (
            'Diagnostica el estado actual del agua de esta piscina. Identifica qué '
            'parámetros están fuera de rango y qué implica para los peces.'
        ),
        'prediccion': (
            f'Proyecta el valor PROMEDIO que tendrá cada parámetro el día {objetivo} '
            f'(dentro de {horizonte} día(s)), según la tendencia de estos datos.\n\n'
            f'Para cada parámetro que aparezca en los datos entrega, en el campo '
            f'"predicciones": el valor esperado y el intervalo [valor_min, valor_max] '
            f'dentro del cual crees que caerá ese promedio, más una justificación breve '
            f'basada en la tendencia observada.\n\n'
            f'IMPORTANTE: el sistema guardará estos intervalos y el día {objetivo} los '
            f'comparará contra lo que midan los sensores, para calcular tu porcentaje '
            f'real de aciertos. No ensanches los intervalos para asegurar el acierto: '
            f'un intervalo que abarca todo el rango físico del parámetro acierta '
            f'siempre y no sirve para tomar ninguna decisión. Ajusta la amplitud a la '
            f'dispersión real que veas entre el mínimo y el máximo históricos.'
        ),
        'recomendacion': (
            'Entrega acciones correctivas priorizadas y ejecutables en campo para '
            'llevar esta piscina a condiciones óptimas.'
        ),
    }

    return (
        f'{encargos.get(tipo, encargos["diagnostico"])}\n\n'
        f'Datos de los últimos {contexto["ventana_dias"]} días '
        f'({contexto["total_lecturas"]} lecturas):\n\n'
        f'{json.dumps(contexto, ensure_ascii=False, indent=2)}'
    )


# ----------------------------------------------------------------------
# Cliente
# ----------------------------------------------------------------------
def _llamar_gemini(prompt, esquema=None):
    """
    Envia el prompt a Gemini y devuelve la respuesta ya parseada.

    :param prompt: texto de la peticion
    :param esquema: esquema JSON a exigir (por defecto ESQUEMA_RESPUESTA)
    :return: dict con la respuesta estructurada del modelo
    :raises ErrorIA: si falta la clave, la red falla o la respuesta es invalida
    """
    api_key = getattr(settings, 'GEMINI_API_KEY', '')
    if not api_key:
        raise ErrorIA(
            'Falta GEMINI_API_KEY en el archivo .env. Consíguela gratis en '
            'https://aistudio.google.com/apikey y agrégala como GEMINI_API_KEY=tu_clave.'
        )

    modelo = getattr(settings, 'GEMINI_MODEL', 'gemini-3.5-flash-lite')
    url = f'{URL_BASE}/{modelo}:generateContent?key={api_key}'

    cuerpo = json.dumps({
        'systemInstruction': {'parts': [{'text': INSTRUCCION_SISTEMA}]},
        'contents': [{'role': 'user', 'parts': [{'text': prompt}]}],
        'generationConfig': {
            'temperature': 0.2,          # analisis tecnico: poca creatividad
            'responseMimeType': 'application/json',
            'responseSchema': esquema or ESQUEMA_RESPUESTA,
        },
    }).encode('utf-8')

    peticion = urllib.request.Request(
        url, data=cuerpo,
        headers={'Content-Type': 'application/json'},
        method='POST',
    )

    try:
        with urllib.request.urlopen(peticion, timeout=TIEMPO_ESPERA) as respuesta:
            datos = json.loads(respuesta.read().decode('utf-8'))
    except urllib.error.HTTPError as exc:
        detalle = exc.read().decode('utf-8', errors='replace')[:400]
        logger.error('Gemini respondió %s: %s', exc.code, detalle)
        if exc.code in (401, 403):
            raise ErrorIA('La API key de Gemini fue rechazada. Verifica GEMINI_API_KEY.') from exc
        if exc.code == 429:
            raise ErrorIA('Se agotó la cuota de la API de Gemini. Intenta más tarde.') from exc
        raise ErrorIA(f'Gemini devolvió un error {exc.code}.') from exc
    except urllib.error.URLError as exc:
        logger.error('Sin conexión con Gemini: %s', exc.reason)
        raise ErrorIA('No hay conexión con la API de Gemini. Revisa la red del servidor.') from exc
    except TimeoutError as exc:
        raise ErrorIA(f'Gemini no respondió en {TIEMPO_ESPERA} segundos.') from exc

    try:
        texto = datos['candidates'][0]['content']['parts'][0]['text']
        return json.loads(texto)
    except (KeyError, IndexError, ValueError) as exc:
        logger.error('Respuesta de Gemini con formato inesperado: %s', str(datos)[:400])
        raise ErrorIA('Gemini devolvió una respuesta que no se pudo interpretar.') from exc


def generar_analisis(geomembrana, tipo='diagnostico', dias=7, horizonte=3):
    """
    Genera y persiste un analisis de IA para una piscina.

    :param geomembrana: piscinas.Geomembrana
    :param tipo: 'diagnostico' | 'prediccion' | 'recomendacion'
    :param dias: ventana de datos historicos a considerar
    :param horizonte: dias hacia adelante que debe proyectar (solo 'prediccion')
    :return: AnalisisIA persistido
    :raises ErrorIA: si no hay datos suficientes o la API falla
    """
    contexto = construir_contexto(geomembrana, dias)

    if contexto['total_lecturas'] == 0:
        raise ErrorIA(
            f'No hay lecturas de {geomembrana.nombre_piscina} en los últimos {dias} días. '
            'Sin datos no se puede generar un análisis: registra sensores y espera '
            'que el nodo ESP32 envíe mediciones.'
        )

    es_prediccion = tipo == 'prediccion'
    salida = _llamar_gemini(
        _construir_prompt(contexto, tipo, horizonte),
        esquema=ESQUEMA_PREDICCION if es_prediccion else None,
    )
    modelo = getattr(settings, 'GEMINI_MODEL', 'gemini-3.5-flash-lite')

    confianza = salida.get('confianza')
    try:
        confianza = max(0, min(100, float(confianza)))
    except (TypeError, ValueError):
        confianza = None

    analisis = AnalisisIA.objects.create(
        geomembrana=geomembrana,
        tipo_analisis=tipo,
        datos_entrada=contexto,
        resultados_salida=salida,
        descripcion_analisis=salida.get('diagnostico', ''),
        recomendaciones='\n'.join(salida.get('recomendaciones', [])),
        anomalias_detectadas=salida.get('anomalias', []),
        confianza=confianza,
        modelo_usado=modelo,
    )

    if es_prediccion:
        creadas = _persistir_predicciones(analisis, salida.get('predicciones', []), horizonte)
        logger.info('Análisis IA %s: %s predicción(es) registradas', analisis.pk, creadas)

    logger.info(
        'Análisis IA %s generado para %s (confianza %s)',
        analisis.pk, geomembrana.codigo_identificacion, confianza,
    )
    return analisis


def _persistir_predicciones(analisis, predicciones, horizonte):
    """
    Convierte las proyecciones del modelo en filas contrastables.

    Se descarta en silencio lo que no se pueda auditar: un parámetro que el
    sistema no mide, o un intervalo mal formado. Guardar una predicción sobre
    algo sin sensor generaría un 'sin_datos' perpetuo que ensucia la métrica.

    :param analisis: AnalisisIA recién creado
    :param predicciones: lista de dicts devuelta por el modelo
    :param horizonte: días hacia adelante
    :return: int con las predicciones persistidas
    """
    from apps.monitoreo.models import TipoParametro

    # Solo los parámetros que esta piscina realmente mide.
    medibles = {
        tipo.nombre_parametro.lower(): tipo
        for tipo in TipoParametro.objects.filter(
            sensores__geomembrana_id=analisis.geomembrana_id,
            sensores__estado='activo',
        ).distinct()
    }
    if not medibles:
        return 0

    objetivo = timezone.localdate() + timedelta(days=horizonte)
    pendientes = []

    for item in predicciones:
        tipo = medibles.get(str(item.get('parametro', '')).strip().lower())
        if tipo is None:
            logger.info('Predicción descartada: "%s" no se mide en esta piscina',
                        item.get('parametro'))
            continue

        try:
            esperado = Decimal(str(item['valor_esperado']))
            minimo = Decimal(str(item['valor_min']))
            maximo = Decimal(str(item['valor_max']))
        except (KeyError, TypeError, ArithmeticError, ValueError):
            logger.warning('Predicción con valores ilegibles: %s', item)
            continue

        if minimo > maximo:
            minimo, maximo = maximo, minimo
        if not minimo <= esperado <= maximo:
            # El valor esperado debe caer dentro de su propio intervalo.
            esperado = (minimo + maximo) / 2

        probabilidad = item.get('probabilidad_fuera_de_rango')
        try:
            probabilidad = max(0, min(100, int(round(float(probabilidad)))))
        except (TypeError, ValueError):
            probabilidad = None

        pendientes.append(Prediccion(
            analisis=analisis,
            geomembrana_id=analisis.geomembrana_id,
            tipo_parametro=tipo,
            valor_esperado=esperado,
            valor_min=minimo,
            valor_max=maximo,
            probabilidad_fuera_rango=probabilidad,
            justificacion=str(item.get('justificacion', ''))[:2000],
            horizonte_dias=horizonte,
            fecha_objetivo=objetivo,
        ))

    if pendientes:
        Prediccion.objects.bulk_create(pendientes)
    return len(pendientes)


def evaluar_predicciones_vencidas(geomembrana=None):
    """
    Contrasta contra la realidad todas las predicciones cuya fecha ya pasó.

    Lo invoca el comando `manage.py evaluar_predicciones`, pensado para correr
    a diario. Es idempotente: una predicción ya evaluada sale del queryset.

    :param geomembrana: opcional, para acotar a una sola piscina
    :return: dict con el recuento por resultado
    """
    queryset = Prediccion.objects.vencidas().con_relaciones()
    if geomembrana is not None:
        queryset = queryset.filter(geomembrana=geomembrana)

    recuento = {'acertada': 0, 'fallida': 0, 'sin_datos': 0}
    for prediccion in queryset:
        recuento[prediccion.evaluar()] += 1

    total = sum(recuento.values())
    if total:
        logger.info('Predicciones evaluadas: %s', recuento)
    return recuento


def precision_historica(geomembrana=None, dias=90):
    """
    Qué tan bien viene acertando el modelo.

    Las predicciones 'sin_datos' quedan fuera del porcentaje: contarlas como
    fallos castigaría al modelo por un sensor caído, y contarlas como aciertos
    inflaría la métrica con días que nadie midió.

    :param geomembrana: opcional, para acotar a una sola piscina
    :param dias: ventana hacia atrás
    :return: dict con totales, tasa de acierto y detalle por parámetro
    """
    from django.db.models import Avg, Count, Q

    desde = timezone.now() - timedelta(days=dias)
    queryset = Prediccion.objects.filter(fecha_generacion__gte=desde)
    if geomembrana is not None:
        queryset = queryset.filter(geomembrana=geomembrana)

    totales = queryset.aggregate(
        total=Count('id'),
        pendientes=Count('id', filter=Q(estado='pendiente')),
        acertadas=Count('id', filter=Q(estado='acertada')),
        fallidas=Count('id', filter=Q(estado='fallida')),
        sin_datos=Count('id', filter=Q(estado='sin_datos')),
        error_medio=Avg('error_absoluto', filter=Q(estado__in=['acertada', 'fallida'])),
    )

    evaluadas = (totales['acertadas'] or 0) + (totales['fallidas'] or 0)
    totales['evaluadas'] = evaluadas
    totales['tasa_acierto'] = (
        round(totales['acertadas'] / evaluadas * 100, 1) if evaluadas else None
    )
    totales['error_medio'] = (
        round(float(totales['error_medio']), 3) if totales['error_medio'] is not None else None
    )

    por_parametro = (
        queryset
        .filter(estado__in=['acertada', 'fallida'])
        .values('tipo_parametro__nombre_parametro', 'tipo_parametro__unidad_medida')
        .annotate(
            evaluadas=Count('id'),
            acertadas=Count('id', filter=Q(estado='acertada')),
            error_medio=Avg('error_absoluto'),
        )
        .order_by('tipo_parametro__nombre_parametro')
    )

    totales['por_parametro'] = [{
        'parametro': fila['tipo_parametro__nombre_parametro'],
        'unidad': fila['tipo_parametro__unidad_medida'],
        'evaluadas': fila['evaluadas'],
        'acertadas': fila['acertadas'],
        'tasa_acierto': round(fila['acertadas'] / fila['evaluadas'] * 100, 1),
        'error_medio': round(float(fila['error_medio']), 3) if fila['error_medio'] else 0,
    } for fila in por_parametro]

    return totales
