"""Logica de negocio de alertas. Reemplaza el trigger tr_crear_alerta_lectura_fuera_rango."""

from django.db import transaction
from .models import Alerta, HistorialEstadoAgua

SEVERIDAD_POR_ESTADO = {
    'riesgo': 'media',
    'critico': 'critica',
}


def evaluar_lectura(lectura):
    """
    Clasifica una lectura y genera alerta si esta fuera de rango.
    Se llama desde el endpoint que recibe datos del hardware.
    Devuelve la Alerta creada o None.
    """
    tipo = lectura.tipo_parametro
    estado = tipo.clasificar(lectura.valor_medida)

    lectura.estado_lectura = estado
    lectura.dentro_rango = (estado == 'normal')
    lectura.save(update_fields=['estado_lectura', 'dentro_rango'])

    if estado == 'normal':
        return None

    if _existe_alerta_activa(lectura):
        return None

    return Alerta.objects.create(
        geomembrana=lectura.geomembrana,
        sensor=lectura.sensor,
        tipo_parametro=tipo,
        lectura=lectura,
        tipo_alerta=estado,
        severidad=SEVERIDAD_POR_ESTADO[estado],
        valor_que_disparo=lectura.valor_medida,
        mensaje_alerta=_construir_mensaje(lectura, estado),
    )


def _existe_alerta_activa(lectura):
    """Evita generar una alerta por cada lectura consecutiva del mismo problema."""
    return Alerta.objects.filter(
        geomembrana=lectura.geomembrana,
        tipo_parametro=lectura.tipo_parametro,
        estado='activa',
    ).exists()


def _construir_mensaje(lectura, estado):
    tipo = lectura.tipo_parametro
    etiqueta = 'crítico' if estado == 'critico' else 'en riesgo'
    return (
        f'{tipo.nombre_parametro} {etiqueta} en '
        f'{lectura.geomembrana.nombre_piscina}: '
        f'{lectura.valor_medida} {tipo.unidad_medida} '
        f'(rango normal: {tipo.rango_normal_min} - {tipo.rango_normal_max})'
    )


@transaction.atomic
def evaluar_estado_piscina(geomembrana):
    """Evalua el estado general de una piscina segun sus alertas activas."""
    activas = Alerta.objects.filter(geomembrana=geomembrana, estado='activa')

    if activas.filter(severidad='critica').exists():
        estado, apta = 'critico', False
    elif activas.exists():
        estado, apta = 'riesgo', True
    else:
        estado, apta = 'optimo', True

    return HistorialEstadoAgua.objects.create(
        geomembrana=geomembrana,
        estado_general=estado,
        apta_produccion=apta,
    )