"""
RF013: evaluacion de la condicion de produccion de una piscina + recomendaciones.

Toma la ultima lectura de cada parametro que mide la geomembrana, la clasifica
contra los rangos de TipoParametro y, por cada parametro fuera de rango, entrega
una recomendacion concreta y ejecutable en campo. La aptitud NO usa IA: es una
regla deterministica y auditable (apta = ningun parametro en estado critico).
"""
from .models import Lectura, TipoParametro

# Recomendaciones por parametro y direccion del desvio (alto/bajo respecto al
# rango optimo). La clave se busca por coincidencia en el nombre del parametro.
RECOMENDACIONES = {
    'ph': {
        'alto': 'pH alto: revisa exceso de fitoplancton/algas, airea en la tarde y '
                'aplica correctivo acidificante de forma gradual.',
        'bajo': 'pH bajo: encala con cal agricola de forma gradual y verifica la '
                'dureza y alcalinidad del agua.',
    },
    'oxigeno': {
        'bajo': 'Oxigeno bajo: enciende los aireadores, reduce alimentacion y '
                'densidad, y retira materia organica acumulada.',
        'alto': 'Oxigeno sobresaturado: reduce la aireacion en horas de sol para '
                'evitar embolias gaseosas en los peces.',
    },
    'temperatura': {
        'alto': 'Temperatura alta: aumenta recambio o sombra y airea de noche; el '
                'oxigeno disuelto cae cuando sube la temperatura.',
        'bajo': 'Temperatura baja: reduce la alimentacion (metabolismo lento) y '
                'protege el estanque del viento.',
    },
    'turbidez': {
        'alto': 'Turbidez alta: revisa solidos en suspension y aumenta el recambio; '
                'puede indicar exceso de fitoplancton o sedimento removido.',
        'bajo': 'Turbidez muy baja: agua demasiado clara y poco fitoplancton; '
                'revisa el plan de fertilizacion.',
    },
}


def _direccion(valor, tipo):
    """Indica si el valor quedo por 'alto' o 'bajo' del rango optimo."""
    if tipo.rango_normal_max is not None and valor > tipo.rango_normal_max:
        return 'alto'
    if tipo.rango_normal_min is not None and valor < tipo.rango_normal_min:
        return 'bajo'
    return None


def _recomendacion(tipo, direccion):
    """Devuelve la recomendacion de campo para un parametro fuera de rango."""
    nombre = tipo.nombre_parametro.strip().lower()
    for clave, mapa in RECOMENDACIONES.items():
        if clave in nombre:
            return mapa.get(direccion) or 'Revisa este parametro y ajusta segun el protocolo del cultivo.'
    return 'Revisa este parametro y ajusta segun el protocolo del cultivo.'


def evaluar_aptitud(geomembrana):
    """
    Evalua si una piscina esta apta para produccion (RF013).

    :param geomembrana: piscinas.Geomembrana
    :return: dict {apta, estado_general, motivos, sin_datos, evaluados}
             - apta: bool (False si algun parametro esta critico)
             - estado_general: 'optimo' | 'riesgo' | 'critico'
             - motivos: lista de parametros fuera de rango con su recomendacion
             - sin_datos: parametros que la piscina mide pero aun no reportan
    """
    tipos = list(
        TipoParametro.objects
        .filter(sensores__geomembrana=geomembrana, sensores__estado='activo')
        .distinct()
    )

    motivos, sin_datos = [], []
    hay_critico = hay_riesgo = False

    for tipo in tipos:
        ultima = (
            Lectura.objects
            .filter(geomembrana=geomembrana, tipo_parametro=tipo)
            .order_by('-timestamp_lectura')
            .first()
        )
        if ultima is None:
            sin_datos.append(tipo.nombre_parametro)
            continue

        estado = tipo.clasificar(ultima.valor_medida)
        if estado == 'normal':
            continue

        if estado == 'critico':
            hay_critico = True
        else:
            hay_riesgo = True

        direccion = _direccion(ultima.valor_medida, tipo)
        motivos.append({
            'parametro': tipo.nombre_parametro,
            'valor': ultima.valor_medida,
            'unidad': tipo.unidad_medida,
            'estado': estado,
            'direccion': direccion,
            'recomendacion': _recomendacion(tipo, direccion),
        })

    estado_general = 'critico' if hay_critico else ('riesgo' if hay_riesgo else 'optimo')
    return {
        'apta': not hay_critico,
        'estado_general': estado_general,
        'motivos': motivos,
        'sin_datos': sin_datos,
        'evaluados': len(tipos),
    }
