# SIGMAP-AQUA (BioAqua System) — Contexto completo del proyecto

> Resumen para retomar el proyecto en un chat nuevo. Corte: **15 de octubre de 2026**.
> Pega este archivo al inicio del nuevo chat con: *"Este es el contexto de mi proyecto, continuemos desde aquí."*

---

## 1. Qué es el proyecto

Sistema automatizado de monitoreo de la calidad del agua en geomembranas (estanques) piscícolas. Nodos **ESP32** leen sensores (temperatura, pH, turbidez y, a futuro, oxígeno disuelto), envían los datos por WiFi a una **API Django**, se guardan en **MySQL**, se clasifica el estado del agua (óptimo / riesgo / crítico), se generan alertas, historial, gráficas, reportes y análisis con IA (DeepSeek, con Gemini de respaldo).

- **Programa:** SENA – Tecnólogo en Análisis y Desarrollo de Software · Ficha **3230026**
- **Centro:** Centro de Formación Agroindustrial – Regional Huila
- **Instructor:** Felipe Martínez
- **Fechas:** 28/07/2026 → 19/12/2026 (sustentación)

### Equipo

| Persona | Rol | Se encarga de |
|---|---|---|
| Ángel Nicolás Abril Quimbaya | Líder / Backend API | Django, DRF, arquitectura, autenticación, despliegue |
| Juan José Gracia Cocoma | Backend / Datos y alertas | Base de datos, motor de alertas, notificaciones, reportes |
| Jhonny Stiven Yunda Guzmán | Backend / Frontend | Dashboard web y app móvil |
| Yesman Ronaldo Ortega Ávila | Backend / Hardware | ESP32, sensores, maqueta y simulador |

Roles del sistema: **Instructor Líder (admin)**, **Operario piscícola**, **Aprendiz** (solo consulta).

---

## 2. Repositorio y entorno

| Dato | Valor |
|---|---|
| Ruta local | `C:\Laragon\www\Proyecto Formativo\Sigmap_aqua` |
| GitHub | https://github.com/AngelAbrilq/Sigmap_aqua.git |
| Rama principal | `main` (ramas: `Angel_Abril`, `JGraciamDev`, `Yesman`, `feature/modulos-funcionales`, `pirulo`) |
| Base de datos | MySQL `sigmap_agua` (Laragon, PyMySQL) |
| SO | Windows + PowerShell (ojo: archivos han quedado con BOM/UTF-16) |
| Commits | Conventional Commits, **sin** línea `Co-Authored-By: Claude` |

**Stack real:** Python 3 · Django 5.2 · Django REST Framework · MySQL · Chart.js · ESP32 (Arduino core 3.x) · DeepSeek (IA principal) · Google Gemini (respaldo).

`requirements.txt`: Django 5.2.16, djangorestframework 3.17.1, django-cors-headers, PyMySQL, python-decouple, pillow.

`.env` (ver `.env.example`): `SECRET_KEY, DEBUG, ALLOWED_HOSTS, DB_NAME, DB_USER, DB_PASSWORD, DB_HOST, DB_PORT, SECURE_SSL, CSRF_TRUSTED_ORIGINS, IA_PROVEEDOR, DEEPSEEK_API_KEY, DEEPSEEK_MODEL, GEMINI_API_KEY, GEMINI_MODEL, EMAIL_HOST, EMAIL_PORT, EMAIL_USE_TLS, EMAIL_HOST_USER, EMAIL_HOST_PASSWORD, DEFAULT_FROM_EMAIL`.

### Comandos útiles

```bash
python manage.py runserver 0.0.0.0:8000          # para que el ESP32 lo vea en la LAN
python manage.py test                             # 194 pruebas
python manage.py test --settings=config.settings_dev   # con SQLite
python manage.py cargar_datos_iniciales
python manage.py crear_usuarios_prueba
python manage.py preparar_demo
python manage.py crear_dispositivo ESP32-P1 --piscina GEO-01 [--rotar-token]
python manage.py detectar_sensores_caidos         # falta programarlo (cron)
python manage.py evaluar_predicciones             # falta programarlo (cron)
python manage.py verificar_ia
python firmware/tools/simular_nodo.py             # simula un ESP32 contra la API
```

---

## 3. Arquitectura del backend (apps Django)

| App | Responsabilidad | Rutas |
|---|---|---|
| `usuarios` | Login, recuperación de contraseña, roles, matriz de permisos, CRUD usuarios | `/auth/login`, `/auth/logout`, `/auth/recuperar/`, `/usuarios/` |
| `core` | Bienvenida y paneles por rol | `/`, `/dashboard/`, `/instructor-lider/`, `/operario/`, `/aprendiz/` |
| `piscinas` | Geomembranas y etapas de producción | `/geomembranas/` |
| `monitoreo` | Sensores, dispositivos, ingesta, monitoreo en vivo, historial, rangos, aptitud | `/sensores/`, `/monitoreo/`, `/historial/` (+CSV), `/configuraciones/` |
| `alertas` | Motor de alertas, estado del agua, notificaciones internas | `/alertas/` |
| `reportes` | Gráficas, reportes por periodo (CSV), comparación de 2 periodos | `/graficas-reportes/`, `/comparacion-periodos/` |
| `auditoria` | Registro de eventos | `/eventos/` |
| `ia` | Diagnóstico y predicciones con DeepSeek (Gemini de respaldo), precisión histórica | `/ai/` |

**API del ESP32** (autenticación `Authorization: Device <token>`):
- `POST /api/v1/dispositivos/handshake/` → devuelve hora del servidor y sensores esperados.
- `POST /api/v1/lecturas/` → recibe el lote, valida, guarda, clasifica y abre/cierra alertas. Deduplica por (sensor, timestamp).

**Tablas principales:** `roles, usuarios, etapas_produccion, geomembranas, tipos_parametros (rangos normal/riesgo/crítico), sensores, dispositivos, lecturas_sensores, alertas, historial_estado_agua, notificaciones_push, eventos_sistema, reportes, comparaciones_datos, analisis_ia, predicciones_ia`.


---

## 4. Hardware y firmware (estado al 15-oct-2026)

> Detalle completo (cableado, firmware, puesta en marcha, calibración y diagnóstico): **`docs/HARDWARE_SENSORES.md`**.

| Sensor | Código BD | Pin | Acondicionamiento | Estado |
|---|---|---|---|---|
| Temperatura DS18B20 | `SEN-001-TEM` | GPIO32 | Pull-up 4,7 kΩ a 3V3 | ✅ Funciona (≈ 24 °C) |
| pH PH-4502C | `SEN-001-PH` | GPIO34 | Divisor ⚠ factor 1,5 (ingesta) vs 1,667 (calibración) | ⚠ Marca pH ≈ 3, falta calibrar |
| Turbidez TS-300B | `SEN-001-TUR` | GPIO35 | Divisor 10k/10k (factor 2,0) | ⚠ Se queda en 3000 NTU |
| Oxígeno SEN0237-A | `SEN-001-OXI` | GPIO33 | Directo | ⏳ Pendiente, `activo=false` |

Firmware en `firmware/`: `bioaqua_handshake` (prueba de enlace), `bioaqua_calibracion` (banco de voltajes cada 2 s), `bioaqua_ingesta` (producción, v1.2.0, `INTERVALO_S = 150` en pruebas / 300 en campo, cola offline en LittleFS) y `tools/simular_nodo.py`.

Arduino IDE: **ESP32 Dev Module**, puerto **COM5**, **115200** baudios, partición **«Default 4MB with spiffs»**. Librerías: ArduinoJson 7.x, OneWire, DallasTemperature.

---

## 5. Estado de los requerimientos

### Historias de usuario v8 (26 HU = 26 RF del documento de Requerimientos del 15-oct-2026)

| Estado | HU |
|---|---|
| **Terminadas (18)** | 002, 004, 008, 009, 010, 012, 013, 014, 015, 016, 017, 018, 019, 020, 022, 023, 024, 026 |
| **En desarrollo (6)** | 001 (prueba de campo), 003 (devolver intervalo en respuesta de ingesta), 005 (módulo web de dispositivos + regenerar token), 007 (eventos falla/restablecimiento de sensor, hora estimada, paquetes descartados), 011 (intervalo configurable con límites), 021 (exportar PDF y Excel) |
| **Por hacer (2)** | 006 (calibraciones de sensores — no existe el módulo), 025 (recuperar contraseña por correo/SMTP) |

Etapas de las HU: 1 Captura ESP32 (001–004) · 2 Recepción y almacenamiento (005–009) · 3 Procesamiento y alertas (010–013) · 4 Consulta y visualización (014–021) · 5 Gestión y acceso (022–026).

### Requerimientos no funcionales

Completos: escalabilidad, fiabilidad, usabilidad, mantenibilidad, interoperabilidad, robustez.
Parciales: rendimiento (sin medir < 1 s / < 2 s), seguridad (HTTPS apagado `SECURE_SSL=False`; web con sesión, no JWT; hash PBKDF2, no bcrypt/Argon2).
Pendientes: disponibilidad y portabilidad (no hay Docker ni despliegue en Ubuntu Server).

Avance estimado: **RF ≈ 88 %**, **RNF ≈ 70 %**, plan Agile **53 %** (100 de 187 puntos).

---

## 6. Plan / cronograma y pendientes

| Hito | Fechas | Estado |
|---|---|---|
| M0 Arranque y BD | 28 jul – 5 ago | ✅ |
| M1 Autenticación y roles | 6 – 19 ago | ✅ |
| HW Prototipo y sensores | ago – 26 oct | 🔄 sensores conectados, falta calibrar/ajustar |
| M2 Gestión (CRUD) | 20 ago – 5 sep | ✅ (falta HU 005 web) |
| M3 Ingesta + firmware + simulador | 6 – 19 sep | 🔄 |
| M4 Alertas y notificaciones | 20 sep – 5 oct | ✅ (falta envío externo) |
| M5 Dashboard web | 6 – 26 oct | 🔄 pulido (Jhonny subió mejoras de UI el 7-oct) |
| M6 App móvil | 27 oct – 16 nov | 🔄 adelantada (falta push y APK) |
| M7 Integración y pruebas | 17 – 30 nov | ⏳ |
| M8 Documentación y sustentación | 1 – 19 dic | ⏳ |

**Pendientes priorizados**

1. Arreglar turbidez y pH; calibrar pH; unificar factor del pH (Yesman).
2. Tareas programadas: sensores caídos y predicciones (Juan José).
3. HU 025 recuperar contraseña (Ángel).
4. Refresco configurable del panel web (Jhonny).
5. HU 005 módulo web de dispositivos (Ángel).
6. HU 007 eventos de sensor / hora estimada / descartados (Ángel).
7. HU 021 reportes PDF y Excel (Juan José).
8. HU 006 módulo de calibraciones (Yesman).
9. Notificaciones externas (push/correo/WhatsApp) y APK release (Jhonny / Juan José).
10. Docker + Ubuntu Server + HTTPS (Ángel).
11. Pruebas de rendimiento, integración en campo y con usuarios (equipo).
12. Manuales, ERD, diccionario y corregir documento de lineamientos (equipo).

**Correcciones pendientes en el documento de lineamientos:** dice PHP (es Django); habla de nivel del agua (se mide turbidez); pide JWT en todas las rutas (web usa sesión); pide Bcrypt/Argon2 (Django usa PBKDF2).

---

## 7. Herramientas de gestión

| Herramienta | Estado |
|---|---|
| **Trello** "BioAqua System Analisis" — https://trello.com/b/hZGRkEMS | Listas **Por hacer / En desarrollo / Terminado**; 26 tarjetas HU con criterios de aceptación, responsables, etiquetas (Backend, Frontend web, App móvil, Hardware/IoT, Documentación, Infra/Seguridad) y fechas. Hay una lista "Backlog" duplicada sin limpiar. |
| **Atlassian Home** proyecto "Sigmap_aqua" (AEBVZZNG-1) | Update publicado el 15-oct: "Según lo previsto", fecha objetivo 19 dic. Límite de 280 caracteres por update. |
| **Jira** (`angelnicolasabrilq.atlassian.net`) | **Desactivado por inactividad.** Reactivar o crear sitio nuevo e importar `jira_import_sigmap_aqua.csv` (5 épicas + 26 historias). |

---

## 8. Documentos del repositorio

- `README.md` — portada del repo, estructura y arranque rápido.
- `docs/HARDWARE_SENSORES.md` — guía única de hardware y firmware (unifica la antigua `CALIBRACION.md` y `README_DESPLIEGUE.md`).
- `docs/gestion/plan_proyecto_agile.md` — plan Agile (48 tareas, sprints 0–8 + HW) con resumen de pendientes (22 tareas, 87 puntos).
- `docs/gestion/Acta_Constitucion_SIGMAP-AQUA.md` / `.docx` — acta de constitución.
- `docs/gestion/lineamientos_sigmap-aqua_estado_oct2026.docx` — lineamientos con estado del software.
- `docs/diagramas/` — arquitectura y ERD. `docs/video/` — video de instalación del nodo.
- Fuentes del equipo (proyecto de Claude): `Requerimientos_Sigmap_Aqua.docx` (26 RF), `Historias_de_Usuario_Sigmap_Aqua_v8.xlsx`, `IC-Agile-Project-Plan-28087_ES.xlsx`.

---

## 9. Cambios sin commit (al 15-oct)

Firmware (pines, tabla en monitor serie, limpieza de sketches) y reorganización de la documentación. Mensajes sugeridos (dos commits):

```
feat(firmware): DS18B20 en GPIO32, turbidez en GPIO35 (10k/10k), tabla de sensores en monitor serie y limpieza de sketches
docs: README raiz, guia unica de hardware y docs de gestion en docs/gestion
```

La copia local de `main` estaba 1 commit atrás de GitHub (mejoras de UI de Jhonny, 7-oct): hacer `git pull`.

---

## 10. Preferencias de trabajo

- Responder en español, términos técnicos en inglés; directo, sin relleno.
- Código con estándares SOLID/DRY/KISS, comentarios y manejo de errores.
- Commits Conventional Commits y **sin** `Co-Authored-By: Claude`.
- Docs SENA en Markdown académico-técnico (descripción, requisitos, flujo, casos de uso).
