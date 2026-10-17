"""
Escribe cada 10 s en logs/estado_ingesta.txt las ultimas lecturas del nodo,
para verificar la ingesta sin abrir la BD. Uso: python firmware/tools/monitor_lecturas.py
"""
import os
import sys
import time
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

import django  # noqa: E402

django.setup()

from django.db import close_old_connections  # noqa: E402
from django.utils import timezone  # noqa: E402

from apps.alertas.models import Alerta  # noqa: E402
from apps.monitoreo.models import Dispositivo, Lectura  # noqa: E402

SALIDA = RAIZ / 'logs' / 'estado_ingesta.txt'


def volcar():
    close_old_connections()
    lineas = [f'Actualizado: {timezone.localtime():%Y-%m-%d %H:%M:%S}', '']
    for d in Dispositivo.objects.select_related('geomembrana'):
        if d.ultima_conexion:
            lineas.append(f'Dispositivo {d.codigo} ({d.geomembrana.codigo_identificacion}) '
                          f'estado={d.estado} ultima_conexion={timezone.localtime(d.ultima_conexion):%H:%M:%S}')
    lineas += ['', 'Ultimas 12 lecturas:']
    for l in Lectura.objects.select_related('sensor', 'tipo_parametro').order_by('-id')[:12]:
        lineas.append(f'  #{l.id:<6} {l.sensor.codigo_hardware:12} {l.valor_medida:>10} '
                      f'{l.estado_lectura:8} {timezone.localtime(l.timestamp_lectura):%H:%M:%S} '
                      f'recibida {timezone.localtime(l.fecha_recepcion):%H:%M:%S}')
    activas = Alerta.objects.filter(estado='activa').count()
    lineas += ['', f'Alertas activas: {activas}']
    SALIDA.write_text('\n'.join(lineas) + '\n', encoding='utf-8')


while True:
    try:
        volcar()
    except Exception as error:  # noqa: BLE001 - el monitor no debe caerse
        SALIDA.write_text(f'Error: {error}\n', encoding='utf-8')
    time.sleep(10)
