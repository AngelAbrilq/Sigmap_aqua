"""
Context processor del asistente IA flotante.

El asistente vive en base.html y aparece en todas las páginas del sistema, no
solo en /ai/. Fuera del módulo de IA no hay atributos data-ia-* que leer, así
que aquí se arma un resumen compacto del último análisis para que el agente
tenga de qué hablar en cualquier pantalla.

Costo por página: 4 consultas pequeñas (último análisis, predicciones
pendientes, conteo de predicciones y conteo de alertas activas), todas
acotadas y apoyadas en índices existentes.
"""

import logging

from django.db.models import Count, Q
from django.urls import reverse
from django.utils import timezone

logger = logging.getLogger(__name__)

MODULO_IA = 'ai'
MAX_ANOMALIAS = 8
MAX_RECOMENDACIONES = 6
MAX_PENDIENTES = 8
MAX_DIAGNOSTICO = 700


def _resumen_analisis(analisis):
    """
    Datos del análisis que el agente necesita para conversar.

    :param analisis: ia.AnalisisIA o None
    :return: dict serializable o None
    """
    if analisis is None:
        return None

    salida = analisis.resultados_salida or {}
    anomalias = analisis.anomalias_detectadas or []
    return {
        'id': analisis.pk,
        'piscina': analisis.geomembrana.nombre_piscina,
        'tipo': analisis.get_tipo_analisis_display(),
        'confianza': int(analisis.confianza) if analisis.confianza is not None else None,
        'riesgo': salida.get('riesgo_proyectado') or '',
        'diagnostico': (analisis.descripcion_analisis or '')[:MAX_DIAGNOSTICO],
        'anomalias': [
            {
                'parametro': str(item.get('parametro', '')),
                'descripcion': str(item.get('descripcion', '')),
                'gravedad': str(item.get('gravedad', '')),
            }
            for item in anomalias[:MAX_ANOMALIAS]
            if isinstance(item, dict)
        ],
        'recomendaciones': [str(r) for r in (salida.get('recomendaciones') or [])[:MAX_RECOMENDACIONES]],
        'fecha': timezone.localtime(analisis.fecha_generacion).strftime('%d/%m/%Y %H:%M'),
    }


def _resumen_predicciones(prediccion_model):
    """
    Pendientes y precisión del modelo en una sola pasada.

    :param prediccion_model: modelo ia.Prediccion
    :return: tuple (lista de pendientes, dict de precisión)
    """
    hoy = timezone.localdate()
    pendientes = [
        {
            'parametro': p.tipo_parametro.nombre_parametro,
            'fecha': p.fecha_objetivo.strftime('%d/%m/%Y'),
            'intervalo': p.rango_previsto,
            'esperado': str(p.valor_esperado),
            'probabilidad': float(p.probabilidad_fuera_rango or 0),
            'vencida': p.fecha_objetivo < hoy,
            'justificacion': (p.justificacion or '')[:160],
        }
        for p in prediccion_model.objects.pendientes()
        .select_related('tipo_parametro').order_by('fecha_objetivo')[:MAX_PENDIENTES]
    ]

    totales = prediccion_model.objects.aggregate(
        pendientes=Count('id', filter=Q(estado='pendiente')),
        acertadas=Count('id', filter=Q(estado='acertada')),
        fallidas=Count('id', filter=Q(estado='fallida')),
    )
    evaluadas = totales['acertadas'] + totales['fallidas']
    precision = {
        'tasa_acierto': round(totales['acertadas'] * 100 / evaluadas, 1) if evaluadas else None,
        'evaluadas': evaluadas,
        'acertadas': totales['acertadas'],
        'fallidas': totales['fallidas'],
        'pendientes': totales['pendientes'],
    }
    return pendientes, precision


def _resumen_alertas():
    """Alertas activas y cuántas son críticas o altas."""
    from apps.alertas.models import Alerta

    return Alerta.objects.filter(estado='activa').aggregate(
        activas=Count('id'),
        graves=Count('id', filter=Q(severidad__in=['critica', 'alta'])),
    )


def _resumen_piscinas():
    """Piscinas registradas con su estado (respaldo local si la IA no responde)."""
    from apps.piscinas.models import Geomembrana

    return [
        {
            'nombre': g.nombre_piscina,
            'codigo': g.codigo_identificacion,
            'activa': g.estado == 'activo',
            'apta': g.apta_para_produccion,
        }
        for g in Geomembrana.objects.order_by('nombre_piscina')[:30]
    ]


def agente_ia(request):
    """
    Contexto global del asistente IA.

    Solo se entrega a usuarios autenticados con acceso al módulo de IA; para el
    resto `agente_ia` es None y base.html no pinta el asistente.

    :param request: HttpRequest
    :return: dict con la clave `agente_ia`
    """
    usuario = getattr(request, 'user', None)
    if usuario is None or not usuario.is_authenticated:
        return {'agente_ia': None}

    from apps.usuarios.permissions import puede_ver_modulo

    if not puede_ver_modulo(usuario, MODULO_IA):
        return {'agente_ia': None}

    match = getattr(request, 'resolver_match', None)
    en_modulo = bool(match and match.namespace == 'ia')

    datos = {
        'en_modulo_ia': en_modulo,
        'url_modulo': reverse('ia:panel'),
        'url_alertas': reverse('alertas:listar'),
        'url_preguntar': reverse('ia:asistente_preguntar'),
        'ia_disponible': False,
        'analisis': None,
        'pendientes': [],
        'precision': {},
        'alertas': {'activas': 0, 'graves': 0},
        'piscinas': [],
    }

    try:
        from .models import AnalisisIA, Prediccion

        ultimo = AnalisisIA.objects.select_related('geomembrana').first()
        datos['analisis'] = _resumen_analisis(ultimo)
        if ultimo is not None:
            datos['url_analisis'] = f"{datos['url_modulo']}?seleccion={ultimo.pk}"
        datos['pendientes'], datos['precision'] = _resumen_predicciones(Prediccion)
        datos['alertas'] = _resumen_alertas()
        datos['piscinas'] = _resumen_piscinas()

        from .services import ia_configurada
        datos['ia_disponible'] = ia_configurada()
    except Exception:  # noqa: BLE001 - el asistente nunca debe tumbar una página
        logger.exception('No se pudo armar el contexto del asistente IA')

    return {'agente_ia': datos}
