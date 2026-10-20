# SIGMAP-AQUA · BioAqua System

Sistema de monitoreo en tiempo real de la calidad del agua en geomembranas piscícolas (tilapia). Un nodo **ESP32** lee temperatura, pH y turbidez (oxígeno disuelto pendiente), envía las lecturas por WiFi al software **Django**, que las valida, clasifica (normal / riesgo / crítico), guarda en **MySQL**, genera alertas y las muestra en el panel web.

SENA · Tecnólogo en Análisis y Desarrollo de Software · Ficha 3230026 · Centro de Formación Agroindustrial, Regional Huila.

## Recorrido del dato

```
Sondas → ESP32 (firmware/bioaqua_ingesta) → POST /api/v1/lecturas/
      → apps/monitoreo (valida, clasifica, guarda en lecturas_sensores)
      → apps/alertas (abre / cierra alertas)
      → /monitoreo/ (panel web, refresco cada 15 s)
```

## Estructura

| Carpeta | Contenido |
|---|---|
| `config/` | Settings, URLs raíz, WSGI/ASGI |
| `apps/` | Apps Django: `usuarios`, `core`, `piscinas`, `monitoreo`, `alertas`, `reportes`, `auditoria`, `ia` |
| `templates/` y `static/` | Interfaz web (Bootstrap + Chart.js) |
| `firmware/` | Sketches del ESP32 y herramientas del nodo (`firmware/tools/`) |
| `docs/` | Documentación del proyecto |
| `tests/` | Pruebas |

## Arranque rápido

```powershell
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env          # completar credenciales de MySQL
python manage.py migrate
python manage.py cargar_datos_iniciales
python manage.py crear_usuarios_prueba
python manage.py runserver 0.0.0.0:8000   # 0.0.0.0 para que el ESP32 lo vea en la red
```

Pruebas: `python manage.py test`. Simular un nodo sin hardware: `python firmware/tools/simular_nodo.py`.

Antes de conectar el ESP32 real (deja intervalo de 30 s, límites físicos y vínculo del nodo con la piscina):

```powershell
python firmware/tools/preparar_sustentacion.py --intervalo 30
python firmware/tools/monitor_lecturas.py      # en otra terminal: muestra las lecturas que llegan
```

## Documentación

| Documento | Para qué |
|---|---|
| [`docs/HARDWARE_SENSORES.md`](docs/HARDWARE_SENSORES.md) | Cableado, pines, firmware, puesta en marcha, calibración y diagnóstico del ESP32 |
| [`docs/CONTEXTO_SIGMAP_AQUA.md`](docs/CONTEXTO_SIGMAP_AQUA.md) | Estado general del proyecto: equipo, arquitectura, requerimientos y pendientes |
| [`docs/PENDIENTES_TECNICOS.md`](docs/PENDIENTES_TECNICOS.md) | Bugs, inconsistencias y trampas detectadas en el recorrido del dato, con su corrección |
| [`docs/gestion/`](docs/gestion/) | Acta de constitución, plan Agile y lineamientos |
| [`docs/diagramas/`](docs/diagramas/) | Arquitectura y modelo entidad-relación |
| [`docs/postman/`](docs/postman/) | Colección Postman de la API del ESP32 |
| [`docs/video/`](docs/video/) | Video de instalación del nodo |

## Equipo

| Integrante | Rol |
|---|---|
| Ángel Nicolás Abril Quimbaya | Líder / Backend |
| Juan José Gracia Cocomá | Backend / Datos y alertas |
| Jhonny Stiven Yunda Guzmán | Frontend web |
| Yesman Ronaldo Ortega Ávila | Hardware / IoT |
