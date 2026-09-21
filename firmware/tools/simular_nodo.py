#!/usr/bin/env python3
"""
Simulador de nodo ESP32 para BioAqua — valida el camino de ingesta SIN hardware.

Hace EXACTAMENTE lo que hara el ESP32:
  1) POST /api/v1/dispositivos/handshake/  -> descubre que sensores espera el server
  2) POST /api/v1/lecturas/                -> envia un lote con valores plausibles

El paso 1 es la clave: el handshake devuelve los `codigo_hardware` exactos que el
servidor espera para la piscina de ese dispositivo, asi que el lote se arma solo
y nunca hay desajuste de codigos.

Uso (con Django corriendo y el token de un dispositivo real):
  python firmware/tools/simular_nodo.py --host 127.0.0.1:8000 --token <TOKEN>
  python firmware/tools/simular_nodo.py --host 127.0.0.1:8000 --token <TOKEN> --critico

Solo usa la libreria estandar (urllib): no instala nada.
"""
import argparse
import json
import urllib.error
import urllib.request

VALORES_OK = {'ph': 7.2, 'oxigeno': 6.5, 'oxígeno': 6.5, 'temperatura': 26.0, 'turbidez': 15.0}
VALORES_CRIT = {'ph': 9.6, 'oxigeno': 2.0, 'oxígeno': 2.0, 'temperatura': 38.0, 'turbidez': 900.0}


def _post(url, token, payload):
    data = json.dumps(payload).encode('utf-8')
    req = urllib.request.Request(url, data=data, method='POST')
    req.add_header('Content-Type', 'application/json')
    req.add_header('Authorization', f'Device {token}')
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            return r.status, json.loads(r.read().decode('utf-8'))
    except urllib.error.HTTPError as e:
        cuerpo = e.read().decode('utf-8') or '{}'
        return e.code, json.loads(cuerpo)
    except urllib.error.URLError as e:
        return -1, {'message': f'No se pudo conectar: {e.reason}'}


def valor_para(parametro, critico):
    tabla = VALORES_CRIT if critico else VALORES_OK
    clave = (parametro or '').strip().lower()
    for k, v in tabla.items():
        if k in clave:
            return v
    return 1.0


def main():
    ap = argparse.ArgumentParser(description='Simula un nodo ESP32 contra la API BioAqua.')
    ap.add_argument('--host', default='127.0.0.1:8000', help='host:puerto de Django')
    ap.add_argument('--token', required=True, help='token del dispositivo (crear_dispositivo)')
    ap.add_argument('--critico', action='store_true',
                    help='envia valores fuera de rango para probar el motor de alertas')
    a = ap.parse_args()
    base = f'http://{a.host}/api/v1'

    print('1) Handshake...')
    st, hs = _post(f'{base}/dispositivos/handshake/', a.token,
                   {'firmware': 'sim-1.0', 'mac': 'AA:BB:CC:DD:EE:FF', 'rssi': -55})
    print(f'   HTTP {st}: {json.dumps(hs, ensure_ascii=False, indent=2)}')
    if st != 200 or not hs.get('success'):
        print('   X Handshake fallo. Revisa el token, la IP/puerto y que Django este corriendo.')
        return
    esperados = hs['data']['sensores_esperados']
    if not esperados:
        print('   ! El dispositivo no tiene sensores activos en su piscina. Crea sensores primero.')
        return

    lecturas = [
        {'codigo_hardware': s['codigo_hardware'], 'valor': valor_para(s['parametro'], a.critico)}
        for s in esperados
    ]
    etiqueta = ' (CRITICAS)' if a.critico else ''
    print(f'\n2) Enviando lote de {len(lecturas)} lectura(s){etiqueta}...')
    st, res = _post(f'{base}/lecturas/', a.token,
                    {'firmware': 'sim-1.0', 'mac': 'AA:BB:CC:DD:EE:FF', 'lecturas': lecturas})
    print(f'   HTTP {st}: {json.dumps(res, ensure_ascii=False, indent=2)}')
    if st == 201 and res.get('success'):
        d = res['data']
        print(f'\nOK: {d["registradas"]} registrada(s), {d["alertas_generadas"]} alerta(s) nueva(s). '
              f'Revisa /monitoreo/ y /alertas/ en la web.')
    else:
        print('\nX Ingesta rechazada; revisa el detalle de arriba.')


if __name__ == '__main__':
    main()
