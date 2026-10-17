# SIGMAP-AQUA · BioAqua System

Sistema de monitoreo en tiempo real de la calidad del agua en geomembranas piscícolas (tilapia). Un nodo **ESP32** lee temperatura, pH y turbidez (oxígeno disuelto pendiente), envía las lecturas por WiFi al software **Django**, que las valida, clasifica (normal / riesgo / crítico), guarda en **MySQL**, genera alertas y las muestra en el panel web y en la app móvil **Flutter**.

SENA · Tecnólogo en Análisis y Desarrollo de Software · Ficha 3230026 · Centro de Formación Agroindustrial, Regional Huila.

## Recorrido del dato

```
Sondas → ESP32 (firmware/bioaqua_ingesta) → POST /api/v1/lecturas/
      → apps/monitoreo (valida, clasifica, guarda en lecturas_sensores)
      → apps/alertas (abre / cierra alertas)
      → /monitoreo/ (panel web, refresco cada 15 s) y app móvil
```

## Estructura

| Carpeta | Contenido |
|---|---|
| `config/` | Settings, URLs raíz, WSGI/ASGI |
| `apps/` | Apps Django: `usuarios`, `core`, `piscinas`, `monitoreo`, `alertas`, `reportes`, `auditoria`, `ia`, `api_movil` |
| `templates/` y `static/` | Interfaz web (Bootstrap + Chart.js) |
| `firmware/` | Sketches del ESP32 y simulador de nodo |
| `mobile/` | App Flutter (ver `mobile/README.md`) |
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

## Documentación

| Documento | Para qué |
|---|---|
| [`docs/HARDWARE_SENSORES.md`](docs/HARDWARE_SENSORES.md) | Cableado, pines, firmware, puesta en marcha, calibración y diagnóstico del ESP32 |
| [`docs/CONTEXTO_SIGMAP_AQUA.md`](docs/CONTEXTO_SIGMAP_AQUA.md) | Estado general del proyecto: equipo, arquitectura, requerimientos y pendientes |
| [`docs/PENDIENTES_TECNICOS.md`](docs/PENDIENTES_TECNICOS.md) | Bugs, inconsistencias y trampas detectadas en el recorrido del dato, con su corrección |
| [`docs/GUIA_MODULO_MOVIL.md`](docs/GUIA_MODULO_MOVIL.md) | API móvil (JWT) y app Flutter |
| [`docs/gestion/`](docs/gestion/) | Acta de constitución, plan Agile y lineamientos |
| [`docs/diagramas/`](docs/diagramas/) | Arquitectura y modelo entidad-relación |
| [`docs/video/`](docs/video/) | Video de instalación del nodo |

## Equipo

| Integrante | Rol |
|---|---|
| Ángel Nicolás Abril Quimbaya | Líder / Backend |
| Juan José Gracia Cocomá | Backend / Datos y alertas |
| Jhonny Stiven Yunda Guzmán | Frontend web y app móvil |
| Yesman Ronaldo Ortega Ávila | Hardware / IoT |
