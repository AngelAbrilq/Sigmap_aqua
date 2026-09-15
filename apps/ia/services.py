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
from datetime import timedelta
from decimal import Decimal

from django.conf import settings
from django.db.models import Avg, Count, Max, Min, Q
from django.utils import timezone

from apps.alertas.models import Alerta
from apps.monitoreo.models import Lectura

from .models import AnalisisIA

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

INSTRUCCION_SISTEMA = (
    'Eres un ingeniero acuícola que asesora a un equipo de piscicultura en Huila, '
    'Colombia. Analizas datos de calidad de agua de estanques con geomembrana. '
    'Respondes SIEMPRE en español, con lenguaje técnico pero comprensible para un '
    'operario de campo. Basas cada afirmación únicamente en los datos que recibes; '
    'si los datos son insuficientes para concluir algo, lo dices explícitamente en '
    'lugar de inventar. Tus recomendaciones son acciones concretas y ejecutables '
    'en campo, no generalidades. El campo confianza es un número de 0 a 100 que '
    'refleja qué tan sólida es tu conclusión dada la cantidad y calidad de los datos.'
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


def _construir_prompt(contexto, tipo):
    """
    Redacta la peticion concreta segun el tipo de analisis solicitado.

    :param contexto: dict de construir_contexto
    :param tipo: 'diagnostico' | 'prediccion' | 'recomendacion'
    :return: str con el prompt
    """
    encargos = {
        'diagnostico': (
            'Diagnostica el estado actual del agua de esta piscina. Identifica qué '
            'parámetros están fuera de rango y qué implica para los peces.'
        ),
        'prediccion': (
            'Proyecta cómo evolucionará la calidad del agua en los próximos 3 a 7 días '
            'según la tendencia de estos datos, e indica qué problema es más probable '
            'que aparezca primero.'
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
def _llamar_gemini(prompt):
    """
    Envia el prompt a Gemini y devuelve la respuesta ya parseada.

    :param prompt: texto de la peticion
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
            'responseSchema': ESQUEMA_RESPUESTA,
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


def generar_analisis(geomembrana, tipo='diagnostico', dias=7):
    """
    Genera y persiste un analisis de IA para una piscina.

    :param geomembrana: piscinas.Geomembrana
    :param tipo: 'diagnostico' | 'prediccion' | 'recomendacion'
    :param dias: ventana de datos a considerar
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

    salida = _llamar_gemini(_construir_prompt(contexto, tipo))
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

    logger.info(
        'Análisis IA %s generado para %s (confianza %s)',
        analisis.pk, geomembrana.codigo_identificacion, confianza,
    )
    return analisis
