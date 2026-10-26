"""
Oxigeno disuelto SIMULADO para el tablero de monitoreo en tiempo real.

El sensor de oxigeno (SEN0237-A) aun no esta instalado. Para que el tablero
muestre los cuatro parametros durante las pruebas, se genera un valor
ficticio que acompana a los sensores reales:

- Usa los mismos instantes de la lectura de referencia (temperatura, si
  existe), asi la grafica avanza al mismo ritmo que las demas.
- Parte de la saturacion de oxigeno a la temperatura medida (el agua mas
  caliente retiene menos oxigeno) y le suma una oscilacion que se repite
  cada 10 minutos.
- Es determinista: el mismo instante da siempre el mismo valor, asi que no
  "salta" entre refrescos.

Estos valores NO se guardan en la base de datos ni generan alertas: solo
viven en la respuesta del tablero y van marcados como simulados. Se apaga
con MONITOREO_OXIGENO_SIMULADO=False en el .env.
"""
import math
import unicodedata
from datetime import datetime
from decimal import ROUND_HALF_UP, Decimal
from types import SimpleNamespace

from django.conf import settings

from .rangos import clasificar_valor, rangos_efectivos

FRACCION_SATURACION = 0.85    # estanque sano: 80-90 % de saturacion
AMPLITUD_MG_L = 0.35          # variacion de la oscilacion
PERIODO_S = 600               # la oscilacion se repite cada 10 minutos
TEMPERATURA_POR_DEFECTO = 26.0


def es_parametro(nombre, fragmento):
    """True si el nombre del parametro contiene el fragmento (sin tildes)."""
    texto = unicodedata.normalize('NFKD', nombre or '').encode('ascii', 'ignore').decode().lower()
    return fragmento in texto


def saturacion_oxigeno(temperatura_c):
    """
    Oxigeno disuelto en saturacion (mg/L) en agua dulce a nivel del mar.

    Ajuste polinomico clasico (APHA) valido entre 0 y 40 °C.

    :param temperatura_c: temperatura del agua en °C
    :return: float mg/L
    """
    t = max(0.0, min(40.0, float(temperatura_c)))
    return 14.652 - 0.41022 * t + 0.007991 * t ** 2 - 0.000077774 * t ** 3


def valor_simulado(momento, temperatura_c):
    """
    Valor ficticio de oxigeno para un instante.

    :param momento: datetime de la lectura de referencia
    :param temperatura_c: temperatura medida en ese instante
    :return: Decimal con 2 decimales
    """
    fase = 2 * math.pi * (momento.timestamp() % PERIODO_S) / PERIODO_S
    valor = saturacion_oxigeno(temperatura_c) * FRACCION_SATURACION + AMPLITUD_MG_L * math.sin(fase)
    return Decimal(str(valor)).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)


def _referencia(tarjetas):
    """Tarjeta real que marca el ritmo: temperatura primero, si no cualquiera con datos."""
    con_datos = [t for t in tarjetas if t['momento'] is not None]
    for tarjeta in con_datos:
        if es_parametro(tarjeta['parametro'], 'temp'):
            return tarjeta
    return con_datos[0] if con_datos else None


def tarjeta_oxigeno_simulada(geomembrana, tarjetas, tipo_oxigeno):
    """
    Construye la tarjeta de oxigeno simulado con el mismo formato que las reales.

    :param geomembrana: piscinas.Geomembrana
    :param tarjetas: tarjetas reales ya calculadas por _estado_sensores
    :param tipo_oxigeno: monitoreo.TipoParametro de oxigeno disuelto
    :return: dict de tarjeta, o None si no aplica
    """
    if not getattr(settings, 'MONITOREO_OXIGENO_SIMULADO', True) or tipo_oxigeno is None:
        return None
    # Solo se simula si NO hay un sensor de oxigeno activo. Uno activo sin
    # lecturas debe verse "Sin datos": inventarle valores ocultaria una falla.
    if any(es_parametro(t['parametro'], 'oxi') for t in tarjetas):
        return None

    referencia = _referencia(tarjetas)
    if referencia is None:
        return None

    es_temperatura = es_parametro(referencia['parametro'], 'temp')

    def temperatura(valor):
        return float(valor) if es_temperatura and valor is not None else TEMPERATURA_POR_DEFECTO

    serie = []
    for punto in referencia['serie']:
        momento = datetime.fromisoformat(punto['t'])
        serie.append({'t': punto['t'], 'v': float(valor_simulado(momento, temperatura(punto['v'])))})

    valor = valor_simulado(referencia['momento'], temperatura(referencia['valor']))
    rangos = rangos_efectivos(tipo_oxigeno, geomembrana.etapa_actual)

    # Se reutiliza el sensor de oxigeno registrado (aunque este inactivo) para
    # mostrar su codigo real; si no existe, un identificador de prueba.
    sensor = (
        geomembrana.sensores.filter(tipo_parametro=tipo_oxigeno).first()
        or SimpleNamespace(codigo_hardware='SIM-OXI', nombre_sensor='Oxígeno disuelto (simulado)')
    )

    return {
        'sensor': sensor,
        'parametro': tipo_oxigeno.nombre_parametro,
        'unidad': tipo_oxigeno.unidad_medida,
        'valor': valor,
        'estado': clasificar_valor(valor, rangos),
        'momento': referencia['momento'],
        'rango_min': rangos.normal_min,
        'rango_max': rangos.normal_max,
        'rango_fuente': rangos.fuente,
        'serie': serie,
        'simulado': True,
    }
