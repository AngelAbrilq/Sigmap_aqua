# Pendientes técnicos y trampas de sustentación — SIGMAP-AQUA

> Registro de problemas encontrados al revisar el recorrido del dato (sensor → ESP32 → software → MySQL → dashboard).
> Cada ítem dice dónde está, qué pasa, cómo responderlo si el instructor lo nota y cómo corregirlo.
> Corte: 16 de octubre de 2026. Se actualiza en cada estación.

**Severidad:** 🔴 bug real · 🟠 riesgo o inconsistencia · 🟡 detalle o limpieza

---

## Estación 1 · Sensores y pines

| ID | Sev. | Dónde | Problema | Corrección |
|---|---|---|---|---|
| T01 | 🟠 | `bioaqua_ingesta.ino:115` vs `bioaqua_calibracion.ino:37` | Factor del divisor de pH distinto: 1,5 (10k/20k) en ingesta y 1,667 (10k/15k) en calibración | Leer las bandas de las resistencias reales y dejar el mismo factor en ambos sketches |
| T02 | 🟠 | `bioaqua_ingesta.ino:88-89` | `PH_M = -5.59` y `PH_B = 21.06` son de ejemplo; con 3,23 V el sistema marca pH ≈ 3 | Ajustar el cero con el potenciómetro (Po ≈ 2,5 V en pH 7) y calibrar con buffers 6,86 y 4,01 |
| T03 | 🟠 | Hardware turbidez | Se queda en 3000 NTU; la sonda da 1,03 V en vez de ≈ 4,2 V | Medir la pata A del módulo: módulo a 5 V, divisor bien armado, cable en A y no en D |
| T04 | 🟡 | `bioaqua_ingesta.ino:45` | `FIRMWARE_VERSION = "1.2.0-4sensores"`, pero solo hay 3 activos (oxígeno `activo=false`) | Respuesta: "soporta 4; el oxígeno se activa al cablear la sonda" |

## Estación 2 · Firmware y lectura

| ID | Sev. | Dónde | Problema | Corrección |
|---|---|---|---|---|
| T05 | 🟡 | `bioaqua_ingesta.ino:46` | El comentario dice "100 s", pero `INTERVALO_S = 150`; en campo debe ser 300 | Corregir el comentario y dejar 300 en campo |
| T06 | 🔴 | `leerVoltaje()` · `bioaqua_ingesta.ino:191-206` | Una sonda analógica desconectada (pin en 0 V) no da `NAN`: el pH sale 21,06 → `constrain` → **14,0**, el servidor lo acepta (está en 0–14) y abre una alerta crítica falsa | En `leerVoltaje()`, devolver `NAN` si `mV_pin < 50` (ninguna sonda sana da 0 V) |
| T07 | 🟡 | `bioaqua_ingesta.ino:373` | Residuo `// ds18.begin();` duplicado y comentado | Borrar la línea |

## Estación 3 · Envío

| ID | Sev. | Dónde | Problema | Corrección |
|---|---|---|---|---|
| T08 | 🟠 | `guardarEnCola()` · `bioaqua_ingesta.ino:335` | `COLA_MAX_LINEAS = 500` está declarado pero nunca se usa: la cola crece hasta llenar la flash | Contar las líneas antes de agregar y descartar la más antigua al llegar a 500 |
| T09 | 🟠 | `enviarCuerpo()` · `http://` | HTTP sin cifrar: con Wireshark en la misma red se ven el JSON y el header `Authorization: Device <token>` | Respuesta: red WPA2, token revocable; HTTPS está en pendientes. Migrar a `WiFiClientSecure` + HTTPS |
| T10 | 🟠 | `timestampISO()` | Sin NTP las lecturas van sin `timestamp`; si esos lotes se reenvían desde la cola, el servidor no puede deduplicarlos | Encolar solo lotes con hora, o guardar `millis()` y corregir la hora al sincronizar |
| T11 | 🟡 | `firmware/bioaqua_ingesta/` | Solo existe `secrets.h.example`; no compila hasta crear `secrets.h` | Es a propósito (`.gitignore`); documentado en `HARDWARE_SENSORES.md` §6.3 |

## Estación 4 · Software y base de datos

| ID | Sev. | Dónde | Problema | Corrección |
|---|---|---|---|---|
| T12 | 🔴 | `loop()` + `vaciarCola()` · `bioaqua_ingesta.ino:354, 389-393` | **Lote envenenado:** el ESP32 encola cualquier fallo, incluidos 400 y 401. Ese lote nunca será aceptado, y `vaciarCola()` se detiene en el primer fallo, así que **la cola queda bloqueada para siempre** y solo crece | `enviarCuerpo()` debe devolver el código: encolar solo con `-1` (red) o `5xx`; con `4xx` descartar el lote e imprimir el error |
| T13 | 🟠 | `Lectura.Meta` · `apps/monitoreo/models.py:176` | La deduplicación (sensor, timestamp) se hace con una consulta previa, sin restricción `UNIQUE` en MySQL; dos peticiones simultáneas pueden duplicar | `UniqueConstraint(fields=['sensor', 'timestamp_lectura'])` + migración |
| T14 | 🟠 | `TipoParametro.clasificar()` · `apps/monitoreo/models.py:32-41` | Si un parámetro no tiene rangos configurados (null), **toda lectura sale `critico`** | Devolver `normal` o `sin_rango` cuando no hay rangos, o volver obligatorios los rangos en el formulario |
| T15 | 🟡 | `LecturaEntradaSerializer.validate_codigo_hardware()` · `apps/monitoreo/serializers.py` | Una consulta a `sensores` por cada lectura del lote (N+1; máximo 100) | Precargar los sensores del lote en una consulta (`codigo_hardware__in`) en `LoteLecturasSerializer` |
| T16 | 🟡 | `resolver_alertas_normalizadas()` · `apps/alertas/services.py:186` | Un `UPDATE` por cada lectura normal | Agrupar por (geomembrana, tipo_parametro) y hacer un solo `UPDATE` |

---

## Orden sugerido para corregir

1. **T12** (cola bloqueada) y **T06** (pH 14 falso): son bugs que pueden aparecer en la demo.
2. **T01, T02, T03**: calibración del hardware.
3. **T08, T13, T14**: robustez.
4. El resto: limpieza.
