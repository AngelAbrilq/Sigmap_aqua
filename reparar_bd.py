"""
Reparador de la base de datos sigmap_agua.

Causa raiz confirmada: se ejecuto `sigmap_agua.sql`, un dump del esquema
LEGACY (pre-Django, junio 2026). Ese archivo hace DROP TABLE IF EXISTS de
cada tabla y las recrea con la estructura antigua (`id_usuario` en vez de
`id`, `contrasena_hash`, `geomenbranas` mal escrito, etc.), ademas de crear
8 tablas y 4 vistas que Django no usa.

Estrategia:
  1. Respalda TODO el contenido actual a un .json (nada se pierde).
  2. Compara el esquema vivo contra el esperado (parseado del dump Django).
  3. DROP + CREATE de las tablas faltantes o divergentes.
  4. Elimina las vistas y tablas legacy sobrantes.
  5. Deja la BD lista para `migrate --fake-initial` + `cargar_datos_iniciales`.

Uso:  venv\\Scripts\\python.exe reparar_bd.py
"""

import json
import re
import sys
from datetime import datetime, date
from decimal import Decimal
from pathlib import Path

try:
    import pymysql
except ImportError:
    sys.exit('Falta pymysql. Ejecuta: venv\\Scripts\\pip.exe install pymysql')

BASE_DIR = Path(__file__).resolve().parent
DUMP_PATH = Path(r'C:\Laragon\www\_sql\Sigmap_aqua.sql')
BACKUP_DIR = BASE_DIR / 'backups_bd'

# Tablas y vistas del esquema legacy que Django no usa.
LEGACY_TABLES = [
    'analisis_ia', 'auditoria', 'comparaciones_datos', 'eventos_sistema',
    'geomenbranas', 'notificaciones_push', 'panel_control', 'reportes',
    'sesiones_usuario',
]
LEGACY_VIEWS = [
    'v_alertas_activas', 'v_estado_piscinas',
    'v_resumen_parametros_24h', 'v_ultimas_lecturas',
]


def leer_env():
    """Lee las credenciales desde el archivo .env del proyecto."""
    valores = {}
    env_path = BASE_DIR / '.env'
    if env_path.exists():
        for linea in env_path.read_text(encoding='utf-8-sig').splitlines():
            linea = linea.strip()
            if linea and not linea.startswith('#') and '=' in linea:
                clave, _, valor = linea.partition('=')
                valores[clave.strip()] = valor.strip()
    return {
        'database': valores.get('DB_NAME', 'sigmap_agua'),
        'user': valores.get('DB_USER', 'root'),
        'password': valores.get('DB_PASSWORD', ''),
        'host': valores.get('DB_HOST', '127.0.0.1'),
        'port': int(valores.get('DB_PORT', 3306)),
        'charset': 'utf8mb4',
    }


def parsear_dump(texto):
    """Extrae {tabla: [columnas]} y {tabla: sentencia CREATE} del dump Django."""
    patron = re.compile(
        r'CREATE TABLE IF NOT EXISTS `(?P<tabla>[^`]+)` \((?P<cuerpo>.*?)\n\) ENGINE=.*?;',
        re.DOTALL,
    )
    columnas, sentencias = {}, {}
    for m in patron.finditer(texto):
        tabla = m.group('tabla')
        columnas[tabla] = re.findall(
            r'^\s+`([^`]+)`\s+\w', m.group('cuerpo'), re.MULTILINE
        )
        sentencias[tabla] = m.group(0).replace(
            'CREATE TABLE IF NOT EXISTS', 'CREATE TABLE'
        )
    return columnas, sentencias


def serializable(valor):
    """Convierte tipos de MySQL a algo que json.dumps acepte."""
    if isinstance(valor, (datetime, date)):
        return valor.isoformat()
    if isinstance(valor, Decimal):
        return str(valor)
    if isinstance(valor, (bytes, bytearray)):
        return valor.decode('utf-8', errors='replace')
    return valor


def respaldar(cursor, tablas, destino):
    """Vuelca el contenido de cada tabla a un JSON antes de tocar nada."""
    volcado = {}
    for tabla in tablas:
        try:
            cursor.execute(f'SELECT * FROM `{tabla}`')
            volcado[tabla] = [
                {k: serializable(v) for k, v in fila.items()}
                for fila in cursor.fetchall()
            ]
        except Exception as exc:
            volcado[tabla] = {'_error': str(exc)}
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_text(
        json.dumps(volcado, indent=2, ensure_ascii=False), encoding='utf-8'
    )
    return volcado


def main():
    if not DUMP_PATH.exists():
        sys.exit(f'No encuentro el respaldo Django: {DUMP_PATH}')

    config = leer_env()
    print(f"Conectando a {config['host']}:{config['port']}/{config['database']} ...")
    conexion = pymysql.connect(cursorclass=pymysql.cursors.DictCursor, **config)
    cursor = conexion.cursor()

    esperadas, sentencias = parsear_dump(DUMP_PATH.read_text(encoding='utf-8'))
    print(f'Tablas esperadas por Django: {len(esperadas)}\n')

    cursor.execute(
        'SELECT table_name AS t, table_type AS tipo FROM information_schema.tables '
        'WHERE table_schema = %s',
        (config['database'],),
    )
    objetos = cursor.fetchall()
    vivas = sorted(o['t'] for o in objetos if o['tipo'] == 'BASE TABLE')
    vistas = sorted(o['t'] for o in objetos if o['tipo'] == 'VIEW')

    # --- 1. Respaldo de seguridad --------------------------------------
    marca = datetime.now().strftime('%Y%m%d_%H%M%S')
    destino = BACKUP_DIR / f'respaldo_antes_de_reparar_{marca}.json'
    volcado = respaldar(cursor, vivas + vistas, destino)
    total = sum(len(v) for v in volcado.values() if isinstance(v, list))
    print(f'[1/4] Respaldo guardado: {destino.name}')
    print(f'      {len(vivas)} tablas + {len(vistas)} vistas, {total} filas.\n')

    # --- 2. Diagnostico -------------------------------------------------
    faltantes, divergentes, correctas = [], [], []
    for tabla, cols_esperadas in esperadas.items():
        if tabla not in vivas:
            faltantes.append(tabla)
            continue
        cursor.execute(
            'SELECT column_name AS c FROM information_schema.columns '
            'WHERE table_schema = %s AND table_name = %s',
            (config['database'], tabla),
        )
        cols_vivas = {f['c'] for f in cursor.fetchall()}
        faltan = sorted(set(cols_esperadas) - cols_vivas)
        (divergentes.append((tabla, faltan)) if faltan else correctas.append(tabla))

    sobrantes = [t for t in vivas if t not in esperadas]

    print('[2/4] Diagnostico:')
    print(f'      OK          ({len(correctas)}): {", ".join(correctas) or "-"}')
    print(f'      FALTAN      ({len(faltantes)}): {", ".join(faltantes) or "-"}')
    print(f'      ESQUEMA MAL ({len(divergentes)}):')
    for tabla, faltan in divergentes:
        print(f'                   - {tabla}: le faltan {", ".join(faltan)}')
    print(f'      LEGACY      ({len(sobrantes)}): {", ".join(sobrantes) or "-"}')
    print(f'      VISTAS      ({len(vistas)}): {", ".join(vistas) or "-"}\n')

    # --- 3. Reconstruccion del esquema Django ---------------------------
    a_reconstruir = faltantes + [t for t, _ in divergentes]
    cursor.execute('SET FOREIGN_KEY_CHECKS = 0')

    if a_reconstruir:
        print(f'[3/4] Reconstruyendo {len(a_reconstruir)} tabla(s)...')
        for tabla in a_reconstruir:
            cursor.execute(f'DROP TABLE IF EXISTS `{tabla}`')
            cursor.execute(sentencias[tabla])
            print(f'      recreada: {tabla}')
    else:
        print('[3/4] El esquema Django ya esta correcto.')
    print()

    # --- 4. Limpieza del esquema legacy ---------------------------------
    basura_tablas = [t for t in sobrantes if t in LEGACY_TABLES]
    basura_vistas = [v for v in vistas if v in LEGACY_VIEWS]
    ajenas = [t for t in sobrantes if t not in LEGACY_TABLES]

    if basura_tablas or basura_vistas:
        print(f'[4/4] Eliminando {len(basura_tablas)} tablas y '
              f'{len(basura_vistas)} vistas legacy...')
        for vista in basura_vistas:
            cursor.execute(f'DROP VIEW IF EXISTS `{vista}`')
            print(f'      vista eliminada: {vista}')
        for tabla in basura_tablas:
            cursor.execute(f'DROP TABLE IF EXISTS `{tabla}`')
            print(f'      tabla eliminada: {tabla}')
    else:
        print('[4/4] No hay restos legacy que limpiar.')

    if ajenas:
        print(f'\n      AVISO: estas tablas no las reconozco y NO las toque: '
              f'{", ".join(ajenas)}')

    cursor.execute('SET FOREIGN_KEY_CHECKS = 1')
    conexion.commit()
    conexion.close()

    print('\nEsquema reparado. Ahora:')
    print('   venv\\Scripts\\python.exe manage.py migrate --fake-initial')
    print('   venv\\Scripts\\python.exe manage.py cargar_datos_iniciales')


if __name__ == '__main__':
    main()
