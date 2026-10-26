"""
Ajuste de rangos por etapa (alevinos) y correccion de rangos globales.

Ejecutar con logs/EJECUTAR_TAREA.bat; la salida queda en logs/tarea.txt.
Es idempotente: se puede correr varias veces.
"""
import os
import sys
from decimal import Decimal as D
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

import django  # noqa: E402

django.setup()

from apps.monitoreo.models import TipoParametro  # noqa: E402
from apps.monitoreo.rangos import rangos_efectivos  # noqa: E402
from apps.piscinas.models import EtapaProduccion, Geomembrana  # noqa: E402

# Turbidez maxima optima por etapa (NTU): los alevinos necesitan agua mas clara.
TURBIDEZ_POR_ETAPA = {'Alevin': ('0', '25'), 'Levante': ('0', '40'),
                      'Engorde': ('0', '50'), 'Cosecha': ('0', '50')}

# Rangos globales corregidos: el riesgo debe CONTENER al normal.
GLOBALES = {
    'Oxigeno Disuelto': {'rango_riesgo_min': D('2.5'), 'rango_riesgo_max': D('12')},
    'Turbidez': {'rango_normal_min': D('0'), 'rango_normal_max': D('50'),
                 'rango_riesgo_min': D('0'), 'rango_riesgo_max': D('100')},
}

for nombre, campos in GLOBALES.items():
    n = TipoParametro.objects.filter(nombre_parametro__iexact=nombre).update(**campos)
    print(f'[OK] TipoParametro {nombre}: {n} fila(s) -> {campos}')

for nombre, (minimo, maximo) in TURBIDEZ_POR_ETAPA.items():
    n = EtapaProduccion.objects.filter(nombre_etapa__iexact=nombre).update(
        rango_turbidez_min=D(minimo), rango_turbidez_max=D(maximo))
    print(f'[OK] Etapa {nombre}: turbidez {minimo}-{maximo} NTU ({n} fila)')

print('\nRangos efectivos que vera el sistema:')
tipos = list(TipoParametro.objects.filter(nombre_parametro__in=['pH', 'Temperatura', 'Oxigeno Disuelto', 'Turbidez']))
for etapa in [None] + list(EtapaProduccion.objects.all()):
    nombre = etapa.nombre_etapa if etapa else 'general'
    partes = []
    for t in tipos:
        r = rangos_efectivos(t, etapa)
        partes.append(f'{t.nombre_parametro}: opt {r.normal_min}-{r.normal_max} / riesgo {r.riesgo_min}-{r.riesgo_max}')
    print(f'  [{nombre}] ' + ' | '.join(partes))

g = Geomembrana.objects.filter(codigo_identificacion='GEO-001').select_related('etapa_actual').first()
print(f'\nGEO-001 (donde esta el ESP32) etapa actual: {g.etapa_actual if g else "?"}')
