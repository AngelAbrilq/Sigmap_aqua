"""
Rangos efectivos de cada parametro segun la etapa de produccion de la piscina.

Regla de negocio (RF010 / RF012):
    1. Si la geomembrana tiene etapa (Alevin, Levante, Engorde, Cosecha) y esa
       etapa define el rango del parametro, ese es el rango OPTIMO. Asi un
       estanque de alevinos se evalua con limites mas estrictos que uno de
       engorde, aunque midan el mismo parametro.
    2. Si no, se usa el rango normal global de TipoParametro.
    3. El margen de RIESGO es el del TipoParametro: la distancia entre su rango
       normal y su rango de riesgo (que debe contener al normal). Ese margen se
       aplica alrededor del rango optimo vigente.
    4. Fuera del margen de riesgo el valor es CRITICO.
"""
import unicodedata
from dataclasses import dataclass
from decimal import Decimal

CAMPOS_ETAPA = {
    'ph': ('rango_ph_min', 'rango_ph_max'),
    'temperatura': ('rango_temperatura_min', 'rango_temperatura_max'),
    'oxigeno': ('rango_oxigeno_min', 'rango_oxigeno_max'),
    'turbidez': ('rango_turbidez_min', 'rango_turbidez_max'),
}


@dataclass(frozen=True)
class Rangos:
    """Limites con los que se clasifica una lectura."""
    normal_min: Decimal | None
    normal_max: Decimal | None
    riesgo_min: Decimal | None
    riesgo_max: Decimal | None
    fuente: str  # 'Alevin', 'Engorde'... o 'general'


def _clave_parametro(nombre):
    """
    Normaliza el nombre del parametro a una clave de CAMPOS_ETAPA.

    :param nombre: TipoParametro.nombre_parametro (ej. 'Oxígeno disuelto')
    :return: 'ph' | 'temperatura' | 'oxigeno' | 'turbidez' | None
    """
    texto = unicodedata.normalize('NFKD', nombre or '').encode('ascii', 'ignore').decode().lower().strip()
    if 'turb' in texto:
        return 'turbidez'
    if 'oxi' in texto:
        return 'oxigeno'
    if 'temp' in texto:
        return 'temperatura'
    if texto == 'ph' or texto.startswith('ph '):
        return 'ph'
    return None


def _envolvente_riesgo(tipo):
    """
    Rango de riesgo global tratado como envolvente del normal.

    Tolera datos viejos donde el riesgo se cargo como una franja de un solo
    lado (ej. oxigeno 2.5-4.0): se une con el normal para que nunca quede un
    valor que salte de normal a critico.
    """
    candidatos_min = [v for v in (tipo.rango_riesgo_min, tipo.rango_normal_min) if v is not None]
    candidatos_max = [v for v in (tipo.rango_riesgo_max, tipo.rango_normal_max) if v is not None]
    return (min(candidatos_min) if candidatos_min else None,
            max(candidatos_max) if candidatos_max else None)


def rangos_efectivos(tipo, etapa=None):
    """
    Calcula los rangos con los que se evalua un parametro en una piscina.

    :param tipo: monitoreo.TipoParametro
    :param etapa: piscinas.EtapaProduccion o None
    :return: Rangos
    """
    env_min, env_max = _envolvente_riesgo(tipo)
    clave = _clave_parametro(tipo.nombre_parametro)

    if etapa is not None and clave in CAMPOS_ETAPA:
        campo_min, campo_max = CAMPOS_ETAPA[clave]
        etapa_min, etapa_max = getattr(etapa, campo_min), getattr(etapa, campo_max)
        if etapa_min is not None and etapa_max is not None:
            margen_bajo = (tipo.rango_normal_min - env_min
                           if None not in (tipo.rango_normal_min, env_min) else Decimal('0'))
            margen_alto = (env_max - tipo.rango_normal_max
                           if None not in (tipo.rango_normal_max, env_max) else Decimal('0'))
            riesgo_min = etapa_min - margen_bajo
            if clave in ('turbidez', 'oxigeno') and riesgo_min < 0:
                riesgo_min = Decimal('0')
            return Rangos(etapa_min, etapa_max, riesgo_min, etapa_max + margen_alto,
                          etapa.nombre_etapa)

    return Rangos(tipo.rango_normal_min, tipo.rango_normal_max, env_min, env_max, 'general')


def clasificar_valor(valor, rangos):
    """
    Clasifica un valor medido.

    :param valor: Decimal medido
    :param rangos: Rangos
    :return: 'normal' | 'riesgo' | 'critico'
    """
    if rangos.normal_min is None or rangos.normal_max is None:
        return 'critico'
    if rangos.normal_min <= valor <= rangos.normal_max:
        return 'normal'
    dentro_min = rangos.riesgo_min is None or valor >= rangos.riesgo_min
    dentro_max = rangos.riesgo_max is None or valor <= rangos.riesgo_max
    return 'riesgo' if (dentro_min and dentro_max) else 'critico'


def clasificar_lectura(sensor, valor):
    """
    Atajo para la ingesta: clasifica con la etapa actual de la piscina del sensor.

    :param sensor: monitoreo.Sensor (con geomembrana y tipo_parametro)
    :param valor: Decimal medido
    :return: tuple (estado, Rangos)
    """
    rangos = rangos_efectivos(sensor.tipo_parametro, sensor.geomembrana.etapa_actual)
    return clasificar_valor(valor, rangos), rangos
