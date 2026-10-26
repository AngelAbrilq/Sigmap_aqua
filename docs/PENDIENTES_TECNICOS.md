# Pendientes técnicos y trampas de sustentación — SIGMAP-AQUA

> Registro de problemas encontrados al revisar el recorrido del dato (sensor → ESP32 → software → MySQL → dashboard).
> Cada ítem dice dónde está, qué pasa y cómo corregirlo.
> Corte: 20 de octubre de 2026 (firmware `1.4.0-sigmap`). Se actualiza en cada revisión.

**Severidad:** 🔴 bug real · 🟠 riesgo o inconsistencia · 🟡 detalle o limpieza · ✅ resuelto

---

## Estación 1 · Sensores y pines

| ID | Sev. | Dónde | Problema | Corrección |
|---|---|---|---|---|
| T01 | 🟠 | `bioaqua_ingesta.ino:120` vs `bioaqua_calibracion.ino` | El factor del divisor de pH es 1,5 (10k/20k) en ingesta; confirmar que el sketch de calibración use el mismo | Leer las bandas de las resistencias reales y dejar el mismo factor en ambos sketches |
| T02 | 🟠 | `bioaqua_ingesta.ino:93-94` | `PH_M = -5.70` y `PH_B = 21.34` vienen del "sketch de prueba", no de una calibración con buffers registrada | Calibrar con buffers 6,86 y 4,01 y anotarlo en la bitácora (`HARDWARE_SENSORES.md`) |
| T03 | 🟠 | Hardware turbidez | Se quedaba en 3000 NTU (sonda en 1,03 V en vez de ≈ 4,2 V) | Medir la pata A del módulo: módulo a 5 V, divisor bien armado, cable en A y no en D |
| T04 | ✅ | `bioaqua_ingesta.ino:45` | La versión decía "4sensores" con solo 3 activos | Resuelto: ahora es `1.4.0-sigmap` |

## Estación 2 · Firmware y lectura

| ID | Sev. | Dónde | Problema | Corrección |
|---|---|---|---|---|
| T05 | 🟡 | `bioaqua_ingesta.ino:8, 46-48` | Los comentarios dicen "30 s", pero `INTERVALO_INICIAL_S = 5`; el software lo ajusta en la primera respuesta | Corregir los comentarios: arranca en 5 s y el software manda el definitivo |
| T06 | 🔴 | `leerVoltaje()` · `bioaqua_ingesta.ino:196-211` | Una sonda analógica desconectada (pin en 0 V) no da `NAN`: el pH sale 21,34 → `constrain` → **14,0**, el servidor lo acepta y abre una alerta crítica falsa | En `leerVoltaje()`, devolver `NAN` si `mV_pin < 50` |
| T07 | 🟡 | `bioaqua_ingesta.ino:421` | Residuo `// ds18.begin();` duplicado y comentado | Borrar la línea |

## Estación 3 · Envío

| ID | Sev. | Dónde | Problema | Corrección |
|---|---|---|---|---|
| T08 | 🟠 | `guardarEnCola()` · `bioaqua_ingesta.ino:383` | `COLA_MAX_LINEAS = 500` está declarado pero nunca se usa: la cola crece hasta llenar la flash | Contar las líneas antes de agregar y descartar la más antigua al llegar a 500 |
| T09 | 🟠 | `enviarCuerpo()` · `http://` | HTTP sin cifrar: con Wireshark en la misma red se ven el JSON y el header `Authorization: Device <token>` | Red WPA2 y token revocable hoy; migrar a HTTPS (`WiFiClientSecure`) |
| T10 | 🟠 | `timestampISO()` | Sin NTP las lecturas van sin `timestamp`; si esos lotes se reenvían desde la cola, el servidor no puede deduplicarlos | Encolar solo lotes con hora, o guardar `millis()` y corregir la hora al sincronizar |
| T11 | ✅ | `firmware/bioaqua_ingesta/` | Faltaba `secrets.h` | Resuelto: ya existe (y sigue fuera de Git) |

## Estación 4 · Software y base de datos

| ID | Sev. | Dónde | Problema | Corrección |
|---|---|---|---|---|
| T12 | 🔴 | `loop()` + `vaciarCola()` · `bioaqua_ingesta.ino:402, 437-440` | **Lote envenenado:** el ESP32 encola cualquier fallo, incluidos 400/401. `aplicarRespuesta()` ya imprime el motivo, pero el lote igual va a la cola; nunca será aceptado y `vaciarCola()` se detiene en el primer fallo, así que **la cola queda bloqueada para siempre** | `enviarCuerpo()` debe devolver el código: encolar solo con `-1` (red) o `5xx`; con `4xx` descartar el lote |
| T13 | 🟠 | `Lectura.Meta` · `apps/monitoreo/models.py` | La deduplicación (sensor, timestamp) se hace con una consulta previa, sin restricción `UNIQUE` en MySQL | `UniqueConstraint(fields=['sensor', 'timestamp_lectura'])` + migración |
| T14 | 🟠 | `TipoParametro.clasificar()` · `apps/monitoreo/models.py:32-41` | Si un parámetro no tiene rangos configurados (null), **toda lectura sale `critico`** | Devolver `normal`/`sin_rango` sin rangos, o volver obligatorios los rangos |
| T15 | 🟡 | `LecturaEntradaSerializer.validate_codigo_hardware()` | Una consulta a `sensores` por cada lectura del lote (N+1; máx. 100) | Precargar los sensores del lote con `codigo_hardware__in` |
| T16 | 🟡 | `resolver_alertas_normalizadas()` · `apps/alertas/services.py:186` | Un `UPDATE` por cada lectura normal | Agrupar por (geomembrana, tipo_parametro) |

## Estación 5 · Dashboard

| ID | Sev. | Dónde | Problema | Corrección |
|---|---|---|---|---|
| T17 | 🟡 | `templates/funcionalidades/monitoreo.html:257-259` | `innerHTML` arma el valor con `sensor.unidad`, que viene de la BD: si alguien guarda HTML en la unidad de un parámetro, se ejecuta en el tablero (XSS almacenado; solo puede hacerlo un rol con permiso de configuraciones) | Crear los nodos con `textContent` en vez de `innerHTML` |
| T18 | 🟠 | `config/urls.py`, `apps/api_movil/` | La API móvil (`/api/v1/movil/`) ya no está en las rutas y su código no está en el repo, pero `README.md`, `docs/CONTEXTO_SIGMAP_AQUA.md` y `docs/GUIA_MODULO_MOVIL.md` todavía la describen | Confirmar con el equipo si se retiró a propósito; actualizar la documentación o restaurar la app |

---

## Orden sugerido para corregir

1. **T12** (cola bloqueada) y **T06** (pH 14 falso): pueden aparecer en la demo.
2. **T18**: aclarar con el equipo antes de la sustentación.
3. **T01, T02, T03**: calibración del hardware.
4. **T08, T13, T14, T17**: robustez y seguridad.
5. El resto: limpieza.
