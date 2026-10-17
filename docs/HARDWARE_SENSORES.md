# Módulo de hardware: nodo de sensores ESP32 — SIGMAP-AQUA

> Documento técnico único del hardware y el firmware. Reúne el diseño eléctrico, el cableado, el firmware, la puesta en marcha, la calibración y el diagnóstico del nodo que mide la calidad del agua y la envía al software SIGMAP-AQUA (Django).
> Versión 2.0 · 15 de octubre de 2026 · Rama `main`
> Unifica los antiguos `firmware/bioaqua_calibracion/CALIBRACION.md` y `firmware/bioaqua_ingesta/README_DESPLIEGUE.md`.

---

## 1. Descripción

El nodo de sensores es el extremo físico del sistema: un microcontrolador ESP32 montado en una placa de expansión, conectado a las sondas sumergidas en la geomembrana. Mide los parámetros del agua y los envía por WiFi al software SIGMAP-AQUA.

Principio de diseño: **el ESP32 es un mensajero**. Mide, convierte a la unidad de ingeniería y envía. No decide si un valor es peligroso, no guarda histórico permanente y no conoce la base de datos. La clasificación (normal, riesgo o crítico), las alertas y el guardado en MySQL son responsabilidad de Django.

Esa separación tiene tres consecuencias prácticas:

- Un umbral del agua se cambia desde la web, sin reprogramar la placa que está en el estanque.
- Un nodo robado no expone credenciales de base de datos, solo un token revocable.
- La validación de plausibilidad física ocurre en el servidor, donde se puede versionar y probar.

### 1.1 Parámetros medidos

| Parámetro | Sensor | Unidad | Rango del sensor | Rango óptimo tilapia | Estado |
|---|---|---|---|---|---|
| Temperatura | DS18B20 (sonda inox) | °C | −10 a 85 | 24 – 30 | ✅ Activo |
| pH | PH-4502C + sonda BNC | pH | 0 a 14 | 6,5 – 8,5 | ✅ Activo |
| Turbidez | TS-300B | NTU | 0 a 3000 | 0 – 25 | ✅ Activo |
| Oxígeno disuelto | DFRobot SEN0237-A | mg/L | 0 a 20 | 5,0 – 9,0 | ⏳ Pendiente (sonda sin cablear) |

Los rangos óptimos no están en el firmware: viven en la tabla `tipos_parametros` y se editan desde el módulo de configuraciones.

---

## 2. Estado actual (15-oct-2026)

| Sensor | `codigo_hardware` | Pin | Acondicionamiento | `factor_divisor` | Alimentación | Estado |
|---|---|---|---|---|---|---|
| Temperatura DS18B20 | `SEN-001-TEM` | GPIO32 | Pull-up 4,7 kΩ DATA → 3V3 | — | 3V3 | ✅ Lee bien (≈ 24 °C) |
| pH PH-4502C | `SEN-001-PH` | GPIO34 | Divisor ⚠ por confirmar | 1,5 en ingesta / 1,667 en calibración | 5 V (VIN) | ⚠ Marca pH ≈ 3 (sonda 3,23 V) |
| Turbidez TS-300B | `SEN-001-TUR` | GPIO35 | Divisor 10 kΩ / 10 kΩ | 2,0 | 5 V (VIN) | ⚠ Se queda en 3000 NTU (sonda 1,03 V) |
| Oxígeno SEN0237-A | `SEN-001-OXI` | GPIO33 | Directo | 1,0 | 5 V | ⏳ `activo = false` |

Problemas abiertos, en orden:

1. **Factor del pH inconsistente.** `bioaqua_ingesta.ino` asume 10k/20k (1,5) y `bioaqua_calibracion.ino` asume 10k/15k (1,667). Leer el código de colores de las resistencias reales del pH en la protoboard y dejar el mismo factor en ambos sketches.
2. **pH ≈ 3.** Con la sonda en buffer 6,86 girar el potenciómetro de cero (junto al BNC) hasta ≈ 2,50 V en `Po`; luego calibrar con 6,86 y 4,01 (sección 8.1). `PH_M = -5.59` y `PH_B = 21.06` son valores de ejemplo.
3. **Turbidez en 3000 NTU.** En agua limpia la sonda debe dar ≈ 4,2 V y da 1,03 V. Medir con multímetro la pata `A` del módulo contra GND:
   - ≈ 2 V → el módulo está a 3,3 V: pasarlo a VIN (5 V).
   - ≈ 4 V pero el pin ve ≈ 0,5 V → divisor mal armado (R2 o columna equivocada).
   - ≈ 1 V → cable sonda–módulo flojo, o el cable de señal está en `D` y no en `A`.

---

## 3. Requerimientos

### 3.1 Funcionales

| ID | Requerimiento |
|---|---|
| RFH-01 | El nodo mide los parámetros del agua con las sondas sumergidas en la geomembrana. |
| RFH-02 | Convierte cada señal a su unidad de ingeniería aplicando la calibración de esa sonda. |
| RFH-03 | Compensa la lectura de oxígeno disuelto con la temperatura medida en el mismo ciclo. |
| RFH-04 | Agrupa las mediciones en un lote JSON y lo envía por HTTP POST a `/api/v1/lecturas/`. |
| RFH-05 | Se autentica con un token de dispositivo revocable, generado por el servidor. |
| RFH-06 | Si no hay red, guarda el lote en la flash (LittleFS) y lo reenvía al reconectar (RF019). |
| RFH-07 | Omite del lote el sensor que no responde, sin interrumpir el envío de los demás. |
| RFH-08 | Enciende el LED de la placa (GPIO2) mientras mide y envía cada lote. |

### 3.2 No funcionales

- **Eléctricos:** lógica de 3,3 V no tolerante a 5 V; máximo 12 mA por pin; tierra común obligatoria.
- **Muestreo:** un lote cada `INTERVALO_S` segundos. Hoy está en **150 s** para pruebas; en campo se deja en **300 s (5 min)**. El agua cambia lento: muestrear más rápido llena MySQL sin aportar información.
- **Precisión:** cada lectura analógica es la **mediana de 31 muestras** del ADC, para que un pico de ruido de la bomba no desplace el valor.
- **Ambientales:** electrónica en caja IP65 con prensaestopas; solo las sondas quedan sumergidas.
- **Red:** WiFi 2,4 GHz (el ESP32 no opera en 5 GHz).
- **Seguridad:** el token vive en `secrets.h`, excluido de Git. Ninguna credencial de base de datos llega al firmware.

### 3.3 Materiales

| Cant. | Componente | Función | Precio aprox. (COP) |
|---|---|---|---|
| 1 | ESP32 DevKit V1 (WROOM-32) + placa de expansión | Microcontrolador | 35.000 |
| 1 | Sonda DS18B20 en acero inoxidable | Temperatura | 18.000 |
| 1 | Módulo PH-4502C + sonda BNC | pH | 95.000 |
| 1 | Sensor TS-300B + módulo | Turbidez | 48.000 |
| 1 | Kit SEN0237-A (DFRobot) | Oxígeno disuelto (pendiente) | 480.000 |
| 1 | Fuente 5 V · 2 A | Alimentación | 22.000 |
| 4 | Resistencias 10 kΩ y 20 kΩ (1 %) | Divisores de voltaje | 2.000 |
| 1 | Resistencia 4,7 kΩ | Pull-up del bus OneWire | 500 |
| 1 | Caja IP65 con prensaestopas | Protección a la intemperie | 40.000 |
| 1 | Protoboard o placa perforada y bornera | Armado | 15.000 |
| 2 | Soluciones buffer pH 4,01 y 6,86 | Calibración | 35.000 |
| 1 | ADS1115 (opcional) | ADC externo de 16 bits | 28.000 |

Precios de referencia en Colombia, septiembre de 2026.

---

## 4. Diseño eléctrico

### 4.1 Restricciones del ESP32

1. **Lógica de 3,3 V, no tolerante a 5 V.** Un sensor alimentado a 5 V puede entregar 5 V en su salida; ese pin se daña para siempre.
2. **GPIO12 no se usa nunca.** En alto durante el arranque configura la flash a 1,8 V y la placa no enciende.
3. **GPIO6 a GPIO11 están reservados** para la flash interna.
4. **El ADC2 no funciona con WiFi activo.** Los analógicos solo van en ADC1: GPIO 32, 33, 34, 35, 36 y 39.
5. **GPIO34, 35, 36 y 39 son solo de entrada** y no tienen pull-up interno.
6. **Máximo 12 mA por pin.** Relés y bombas van con transistor, MOSFET u optoacoplador.
7. **Tierra común obligatoria** entre fuente, sensores y placa.

### 4.2 Asignación de pines

| Sensor | `codigo_hardware` | Pin | Tipo de señal | Acondicionamiento |
|---|---|---|---|---|
| Temperatura DS18B20 | `SEN-001-TEM` | GPIO32 | Digital OneWire, 3,3 V | Pull-up 4,7 kΩ entre DATA y 3V3 |
| pH PH-4502C (salida `Po`) | `SEN-001-PH` | GPIO34 (ADC1_CH6) | Analógica 0 – 5 V | Divisor de voltaje |
| Turbidez TS-300B (salida `A`) | `SEN-001-TUR` | GPIO35 (ADC1_CH7) | Analógica 0 – 4,5 V | Divisor 10 kΩ / 10 kΩ |
| Oxígeno SEN0237-A | `SEN-001-OXI` | GPIO33 (ADC1_CH5) | Analógica 0 – 3,0 V | Directa |
| LED de estado | — | GPIO2 | Salida | No conectar nada externo |

Libres para ampliar: GPIO36 y GPIO39 (analógicos), GPIO4. GPIO21 y GPIO22 quedan reservados para el bus I²C del ADS1115.

`codigo_hardware` debe coincidir carácter por carácter con la tabla `sensores`. El servidor rechaza con HTTP 400 cualquier lectura cuyo código no exista, esté inactivo o pertenezca a otra geomembrana.

### 4.3 Divisor de voltaje

```
V_pin = V_sensor × R2 / (R1 + R2)

pH       10k / 20k:  5,0 V × 20k / 30k = 3,33 V   → factor (R1+R2)/R2 = 1,5
pH       10k / 15k:  5,0 V × 15k / 25k = 3,00 V   → factor 1,667
Turbidez 10k / 10k:  4,5 V × 10k / 20k = 2,25 V   → factor 2,0
```

R1 va entre la salida del sensor y el pin; R2 entre ese mismo punto y GND. El firmware recupera el voltaje original multiplicando por `(R1 + R2) / R2` (`factor_divisor` en la tabla `SENSORES[]`). Si se cambian las resistencias, se cambia también ese factor. Cada sensor lleva su propio divisor.

Código de colores (sin contar la banda de tolerancia):

| Valor | 4 bandas (5 %) | 5 bandas (1 %) |
|---|---|---|
| 4,7 kΩ | amarillo-violeta-rojo | amarillo-violeta-negro-café |
| 10 kΩ | café-negro-naranja | café-negro-negro-rojo |
| 15 kΩ | café-verde-naranja | café-verde-negro-rojo |
| 20 kΩ | rojo-negro-naranja | rojo-negro-negro-rojo |

### 4.4 Alimentación

- Una fuente de 5 V y 2 A alimenta `VIN` y la línea de 5 V de los módulos de pH, turbidez y oxígeno.
- El DS18B20 va a 3V3: así su línea de datos nunca supera 3,3 V.
- Los módulos de 5 V **no** se alimentan del pin 3V3: ese regulador entrega poca corriente y provoca reinicios.
- Todos los GND se unen en un mismo riel o bornera.
- El cable a las sondas es apantallado o UTP, con la malla a GND solo en el extremo de la caja.
- Bombas y aireadores van en otra fuente: el arranque de un motor tumba la tensión y reinicia la placa.

---

## 5. Flujo de funcionamiento

```
Sondas → acondicionamiento (divisor / pull-up) → ADC1 y bus OneWire del ESP32
      → conversión a unidad de ingeniería (calibración y compensación por temperatura)
      → lote JSON cada INTERVALO_S
      → HTTP POST /api/v1/lecturas/   con   Authorization: Device <token>
           │
           ├─ éxito → Django valida el rango físico del sensor (serializers.py)
           │            → clasifica normal / riesgo / crítico contra tipos_parametros
           │            → guarda en lecturas_sensores
           │            → motor de alertas: abre o cierra alertas
           │            → web (/monitoreo/) y app móvil
           │
           └─ fallo (sin red o servidor caído)
                      → el lote se guarda en LittleFS (/cola.jsonl; COLA_MAX_LINEAS = 500 está declarado pero aún no se aplica)
                      → se reenvía al reconectar; el servidor deduplica por (sensor, timestamp)
```

Orden de cada ciclo (`construirCuerpo()`): la temperatura va primero porque la compensación del oxígeno la necesita.

1. DS18B20: `requestTemperatures()` (≈ 750 ms a 12 bits).
2. pH: mediana de 31 muestras → × factor del divisor → recta `PH_M × V + PH_B`.
3. Oxígeno (cuando esté activo): mediana → mg/L con la temperatura del paso 1.
4. Turbidez: mediana → × factor del divisor → curva del fabricante.
5. Lote JSON con `codigo_hardware`, `valor`, `secuencia` y `timestamp`.
6. Envío o encolado.

---

## 6. Firmware

### 6.1 Sketches

| Carpeta | Uso |
|---|---|
| `firmware/bioaqua_handshake/` | Prueba WiFi + token contra `/api/v1/dispositivos/handshake/`. No lee sensores. |
| `firmware/bioaqua_calibracion/` | Banco de calibración: imprime cada 2 s (`PERIODO_MS`) una tabla con temperatura, pH y turbidez, su voltaje y si está `ESTABLE`. No envía nada. |
| `firmware/bioaqua_ingesta/` | Producción: lee los sensores activos, imprime la tabla, arma el JSON, lo envía y maneja la cola offline. |
| `firmware/tools/simular_nodo.py` | Simula un ESP32 contra el servidor, para probar sin hardware. |

### 6.2 Arduino IDE

- Placa **ESP32 Dev Module** (paquete *esp32 by Espressif*, core 3.x), monitor serie a **115200** baudios.
- Partition Scheme: **«Default 4MB with spiffs»** (necesario para LittleFS y el modo offline).
- Librerías: **ArduinoJson 7.x**, **OneWire**, **DallasTemperature**.
- Programar por el USB del DevKit, no por el de la placa de expansión.

### 6.3 `secrets.h`

Se copia de `secrets.h.example` y no se sube a Git:

```cpp
#define WIFI_SSID     "TuRed2.4GHz"
#define WIFI_PASSWORD "clave"
#define DEVICE_TOKEN  "token_de_crear_dispositivo"
#define SERVER_HOST   "192.168.x.x"   // IP del PC con Django
#define SERVER_PORT   8000
```

### 6.4 Tabla `SENSORES[]` de `bioaqua_ingesta.ino`

```cpp
//  codigo         tipo           gpio  divisor  activo
{ "SEN-001-TEM", TEMP_DS18B20,    32,   1.0f,   true  },
{ "SEN-001-PH",  PH_LINEAL,       34,   1.5f,   true  },
{ "SEN-001-OXI", OXIGENO_MGL,     33,   1.0f,   false },  // activar al cablear la sonda
{ "SEN-001-TUR", TURBIDEZ_NTU,    35,   2.0f,   true  },
```

Agregar o activar un sensor es cambiar una línea.

### 6.5 JSON que envía el nodo

```json
{
  "firmware": "1.2.0-4sensores",
  "mac": "24:6F:28:AA:BB:CC",
  "lecturas": [
    {"codigo_hardware": "SEN-001-TEM", "valor": 24.06, "secuencia": 1, "timestamp": "2026-10-15T15:30:00-05:00"},
    {"codigo_hardware": "SEN-001-PH",  "valor": 7.12,  "secuencia": 2, "timestamp": "2026-10-15T15:30:00-05:00"},
    {"codigo_hardware": "SEN-001-TUR", "valor": 12.4,  "secuencia": 3, "timestamp": "2026-10-15T15:30:00-05:00"}
  ]
}
```

---

## 7. Puesta en marcha

### 7.1 Preparar el servidor (una vez)

1. Encender MySQL en Laragon.
2. En la web, crear la geomembrana (ej. `GEO-01`) y los sensores `SEN-001-TEM`, `SEN-001-PH` y `SEN-001-TUR` con su rango de medición (0–50, 0–14, 0–3000). Fuera de ese rango, el servidor rechaza la lectura.
3. Registrar el nodo y copiar el token, que se muestra una sola vez:
   ```powershell
   python manage.py crear_dispositivo ESP32-P1 --piscina GEO-01
   ```
4. Arrancar Django visible en la red local, buscar la IP con `ipconfig` y permitir Python en el firewall (red privada):
   ```powershell
   python manage.py runserver 0.0.0.0:8000
   ```

### 7.2 Armado paso a paso

Cada paso tiene una verificación. No se avanza sin superarla: si algo falla, la causa está en el último paso.

| # | Paso | Verificación |
|---|---|---|
| 1 | Cargar `bioaqua_handshake` con la placa sin sensores | El serial imprime la IP y el servidor responde 200 |
| 2 | Conectar la fuente de 5 V y armar el riel de GND | 5,0 ± 0,2 V y 3,3 ± 0,1 V con el multímetro |
| 3 | Cablear el DS18B20 con su pull-up de 4,7 kΩ | Marca la temperatura ambiente, no −127 °C |
| 4 | Armar los divisores y alimentar pH y turbidez | Ninguna salida de divisor supera 3,3 V |
| 5 | Conectar las señales analógicas a GPIO34 y GPIO35 | Los voltajes cambian al mover las sondas |
| 6 | Calibrar con `bioaqua_calibracion` (sección 8) | En buffer 6,86 el pH queda entre 6,75 y 6,95 |
| 7 | Llenar `secrets.h` y cargar `bioaqua_ingesta` | `[HTTP] 201 OK` y los datos en `/monitoreo/` y `/historial/` |
| 8 | Montar en caja IP65 e instalar en el estanque | 24 horas seguidas sin huecos en el historial |

En el paso 8 los cables entran a la caja formando un lazo hacia abajo antes del prensaestopas, para que el agua de lluvia escurra en vez de seguir el cable.

### 7.3 Checklist del día de campo

- [ ] MySQL (Laragon) y `runserver 0.0.0.0:8000` encendidos.
- [ ] Geomembrana y sensores creados, con `rango_medicion` y `codigo_hardware`.
- [ ] Dispositivo creado y su token en `secrets.h`.
- [ ] `SENSORES[]` con los códigos reales y `activo` correcto.
- [ ] Multímetro: ninguna salida analógica supera 3,3 V.
- [ ] GND común entre fuente, sensores y ESP32.
- [ ] `INTERVALO_S` en 300 para campo.
- [ ] Grabar → monitor serie → ver `201` → confirmar en la web.

---

## 8. Calibración

`bioaqua_calibracion.ino` **mide voltaje, no unidades**. Las constantes salen de este procedimiento y no de valores genéricos de internet: cada electrodo tiene su propia pendiente y se degrada con el uso. Si el sketch imprime `*** ALERTA: V_pin supera el tope del ADC`, desconectar y revisar las resistencias.

### 8.1 pH — dos puntos (mensual)

Ajuste previo de cero: con la sonda en buffer de pH 7, girar el potenciómetro junto al BNC del PH-4502C hasta que `Po` marque ≈ 2,50 V. El otro potenciómetro es de la alarma digital (`Do`) y no se usa.

| Paso | Acción | Anotar |
|---|---|---|
| 1 | Sonda en buffer **6,86**, esperar `ESTABLE` | V₁ = ____ V |
| 2 | Lavar con agua destilada y secar sin frotar | |
| 3 | Sonda en buffer **4,01**, esperar `ESTABLE` | V₂ = ____ V |

```
PH_M = (6,86 − 4,01) / (V1 − V2)
PH_B = 6,86 − PH_M × V1
```

`PH_M` sale **negativa**: más voltaje, menos pH. Ejemplo con una sonda nueva: 2,54 V en 6,86 y 3,05 V en 4,01 dan `PH_M = −5,59` y `PH_B = 21,06`.

Verificación: de nuevo en buffer 6,86, `PH_M × V + PH_B` debe caer entre 6,75 y 6,95.

### 8.2 Oxígeno disuelto — saturación en aire (trimestral; electrolito cada 6 meses)

Con la membrana húmeda y al aire, la sonda ve 100 % de saturación. Se anotan en el mismo instante el voltaje en mV (`OXI_CAL_MV`) y la temperatura del DS18B20 (`OXI_CAL_TEMP_C`). La conversión a mg/L usa la tabla de saturación del agua dulce (0–40 °C) y corrige la deriva de la sonda con 35 mV por grado. Sin esa compensación, un día soleado aparenta una caída de oxígeno que no existe.

### 8.3 Turbidez — agua destilada como cero

En agua destilada el TS-300B da ≈ 4,2 V (`TURB_V_AGUA_LIMPIA`) = 0 NTU. La relación es **inversa**: más sólidos en suspensión, menos voltaje. El firmware aplica la curva de segundo grado del fabricante y limita el resultado entre 0 y 3000 NTU. Se recalibra cuando el agua destilada deja de dar el voltaje de referencia.

### 8.4 Bitácora

Cada calibración se registra: fecha, sensor, voltajes, constantes y responsable. Cuando una lectura se vea rara, la bitácora dice si derivó la sonda o cambió el agua.

| Fecha | Sensor | V₁ | V₂ | Constantes | Responsable |
|---|---|---|---|---|---|
|  |  |  |  |  |  |

---

## 9. Diagnóstico de fallas

### 9.1 Eléctricas

| Síntoma | Causa más probable | Acción |
|---|---|---|
| Temperatura en −127 °C | Falta el pull-up de 4,7 kΩ o DATA está en otro pin | Revisar la resistencia entre DATA y 3V3 |
| Un analógico fijo en el máximo | Llegan más de 3,3 V al pin | Desconectar y medir el divisor; el pin puede estar dañado |
| Lecturas erráticas con el agua quieta | GND sin unir o cable largo sin apantallar | Unir los GND; usar cable apantallado |
| Reinicios de la placa | Fuente corta en los picos de transmisión WiFi | Fuente de 2 A y condensador de 1000 µF |
| La placa no enciende tras cablear | Algo quedó en GPIO12 | Retirarlo |
| Analógico siempre en 0 con WiFi | El pin es del ADC2 | Mover a GPIO 32–39 |
| No asocia al WiFi | Red de 5 GHz, o SSID con tildes/emojis | Red de 2,4 GHz con nombre simple |

### 9.2 Respuestas del servidor

El servidor siempre responde `{success, data, message}`.

| Respuesta | Causa | Arreglo |
|---|---|---|
| `201` | Lote guardado | — |
| `401` Cabecera Authorization ausente o mal formada | Falta el token o el formato `Device <token>` | Revisar `DEVICE_TOKEN` en `secrets.h` |
| `401` Token de dispositivo inválido | Token mal copiado o rotado | `crear_dispositivo ... --rotar-token` y actualizar `secrets.h` |
| `403` Dispositivo inactivo | Desactivado en el admin | Reactivarlo |
| `400` No existe un sensor con código "X" | `codigo_hardware` distinto al de la BD | Igualar `SENSORES[]` con la BD |
| `400` … pertenece a otra piscina | Sensor de otra geomembrana | Corregir la piscina del sensor o del dispositivo |
| `rechazadas` … fuera del rango medible | Valor fuera de `rango_medicion` | Calibración o cableado; el resto del lote sí entra |
| `-1` / timeout | Red, IP, puerto o firewall | Misma red 2,4 GHz, IP correcta, Python permitido en el firewall |

---

## 10. Casos de uso

### CU-H01 · Puesta en marcha de un nodo nuevo

**Actor:** Instructor Líder u Operario con acceso al servidor.
**Precondición:** la geomembrana existe y hay WiFi de 2,4 GHz en el sitio.
**Flujo principal:** sección 7.
**Postcondición:** las lecturas aparecen en el módulo de monitoreo y en la app móvil.
**Flujos alternos:** token rechazado (401) o sensor no reconocido (400); ver sección 9.2.

### CU-H02 · Ingesta periódica de mediciones

**Actor:** nodo ESP32 (actor del sistema).
**Precondición:** nodo activo con token válido.

1. Cada `INTERVALO_S` el nodo lee los sensores activos.
2. Arma el lote y lo envía a `/api/v1/lecturas/`.
3. El servidor valida que cada valor esté dentro del rango físico del sensor.
4. Clasifica cada lectura y la guarda.
5. El motor de alertas abre alertas por valores fuera de rango y cierra las que se normalizaron.
6. El servidor responde el resumen: registradas, duplicadas, críticas, alertas y rechazadas.

**Flujos alternos:** valor fuera del rango medible → se descarta y se reporta en `rechazadas`. Sin red → el lote va a LittleFS y se reenvía al reconectar.

### CU-H03 · Calibración periódica de una sonda

**Actor:** Operario.
**Precondición:** soluciones buffer vigentes.
**Flujo principal:** sección 8; al terminar se escriben las constantes en `bioaqua_ingesta.ino`, se recarga el firmware y se registra la bitácora.

---

## 11. Archivos del módulo

| Ruta | Contenido |
|---|---|
| `firmware/bioaqua_handshake/` | Validación de enlace y token |
| `firmware/bioaqua_calibracion/` | Banco de calibración |
| `firmware/bioaqua_ingesta/` | Firmware de producción con cola offline |
| `firmware/*/secrets.h` | Credenciales y token (excluido de Git) |
| `firmware/tools/simular_nodo.py` | Simulador de nodo |
| `apps/monitoreo/api_auth.py` | Autenticación `Authorization: Device <token>` |
| `apps/monitoreo/serializers.py` | Validación de plausibilidad física de cada lectura |
| `apps/monitoreo/views.py` | `HandshakeView` e `IngestaLecturasView` |
| `apps/monitoreo/urls.py` | Rutas `/api/v1/dispositivos/handshake/` y `/api/v1/lecturas/` |

---

## 12. Pendientes

- Confirmar las resistencias del pH y unificar el factor en los dos sketches.
- Calibrar pH con buffers reales y reemplazar `PH_M` / `PH_B` de ejemplo.
- Resolver la turbidez en 3000 NTU (sección 2).
- Cablear y calibrar la sonda de oxígeno; poner `SEN-001-OXI` en `activo = true`.
- Dejar `INTERVALO_S = 300` para campo.
- Medir el consumo del nodo para dimensionar batería y panel solar.
- Evaluar el ADS1115 si se agregan más analógicos (solo quedan GPIO36 y GPIO39).
- Aplicar el tope `COLA_MAX_LINEAS` en `guardarEnCola()` (hoy la cola crece sin límite).
- Migrar el envío a HTTPS antes de sacar el sistema de la red local.
