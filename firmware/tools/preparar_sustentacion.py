"""
Deja la BD lista para recibir el nodo ESP32 real (SEN-001-*).

- Rangos de medicion = limites fisicos del documento de requerimientos (RF007).
- Oxigeno disuelto inactivo mientras la sonda no este cableada.
- Intervalo de lectura 30 s (lo recibe el ESP32 en cada respuesta, RF011).
- Reporta el dispositivo de esa geomembrana (sin mostrar el token).

Uso: python firmware/tools/preparar_sustentacion.py [--intervalo 30]
"""
import argparse
import os
import sys
from decimal import Decimal
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

import django  # noqa: E402

django.setup()

from apps.monitoreo.models import Dispositivo, Sensor  # noqa: E402

LIMITES_FISICOS = {
    'SEN-001-PH': (Decimal('0'), Decimal('14')),
    'SEN-001-TEM': (Decimal('0'), Decimal('50')),
    'SEN-001-TUR': (Decimal('0'), Decimal('3000')),
    'SEN-001-OXI': (Decimal('0'), Decimal('20')),
}
SENSORES_SIN_CABLEAR = {'SEN-001-OXI'}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--intervalo', type=int, default=30)
    parser.add_argument('--dispositivo', default='ESP32-P1',
                        help='Nodo que se vincula a la piscina de los sensores SEN-001-*')
    args = parser.parse_args()

    sensores = list(Sensor.objects.select_related('geomembrana', 'tipo_parametro')
                    .filter(codigo_hardware__in=LIMITES_FISICOS))
    if not sensores:
        print('[ERROR] No existen sensores SEN-001-* en la BD.')
        return 1

    for sensor in sensores:
        minimo, maximo = LIMITES_FISICOS[sensor.codigo_hardware]
        sensor.rango_medicion_min = minimo
        sensor.rango_medicion_max = maximo
        sensor.intervalo_lectura_segundos = args.intervalo
        sensor.estado = 'inactivo' if sensor.codigo_hardware in SENSORES_SIN_CABLEAR else 'activo'
        sensor.save(update_fields=['rango_medicion_min', 'rango_medicion_max',
                                   'intervalo_lectura_segundos', 'estado'])
        print(f'[OK] {sensor.codigo_hardware:12} {sensor.tipo_parametro.nombre_parametro:18} '
              f'rango {minimo}-{maximo}  intervalo {args.intervalo}s  estado {sensor.estado}  '
              f'piscina {sensor.geomembrana.codigo_identificacion}')

    piscinas = {s.geomembrana_id for s in sensores}
    if len(piscinas) > 1:
        print('[ALERTA] Los sensores SEN-001-* estan en piscinas distintas; deben ser la misma.')

    if len(piscinas) == 1:
        piscina_id = next(iter(piscinas))
        nodo = Dispositivo.objects.filter(codigo=args.dispositivo).first()
        if nodo is None:
            print(f'[ERROR] No existe el dispositivo {args.dispositivo}.')
        elif nodo.geomembrana_id != piscina_id:
            anterior = nodo.geomembrana.codigo_identificacion
            nodo.geomembrana_id = piscina_id
            nodo.estado = 'activo'
            nodo.save(update_fields=['geomembrana', 'estado'])
            print(f'[OK] {nodo.codigo} movido de {anterior} a la piscina de los sensores.')

    for disp in Dispositivo.objects.filter(geomembrana_id__in=piscinas):
        print(f'[DISPOSITIVO] {disp.codigo} estado={disp.estado} '
              f'piscina={disp.geomembrana.codigo_identificacion} '
              f'token_termina_en=...{disp.token[-6:]} ultima_conexion={disp.ultima_conexion}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
