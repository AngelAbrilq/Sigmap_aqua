# Módulo de hardware: nodo de sensores ESP32 — BioAqua System

> Documento técnico del proyecto SIGMAP-AQUA. Cubre el diseño eléctrico, el cableado, la calibración y la puesta en marcha del nodo que mide la calidad del agua y la envía a la API de Django.
> Versión 1.0 · 20 de septiembre de 2026 · Rama `feature/modulos-funcionales`

---

## 1. Descripción

El nodo de sensores es el extremo físico del sistema: un microcontrolador ESP32 conectado a cuatro sensores sumergidos en la geomembrana, que mide los parámetros del agua y los transmite por WiFi a la API REST del servidor.

Principio de diseño: **el ESP32 es un mensajero**. Mide, convierte a la unidad de ingeniería y envía. No decide si un valor es peligroso, no guarda histórico permanente y no conoce la base de datos. La clasificación en normal, riesgo o crítico, la apertura de alertas y la persistencia son responsabilidad de Django.

Esa separación tiene tres consecuencias prácticas:

- Cambiar un umbral del agua se hace desde la web, sin reprogramar la placa que está en el estanque.
- Un nodo comprometido físicamente no expone credenciales de base de datos, solo un token revocable.
- La validación de plausibilidad física ocurre en el servidor, donde se puede versionar y probar.

### 1.1 Parámetros medidos

| Parámetro | Sensor | Unidad | Rango de trabajo | Rango óptimo para tilapia |
|---|---|---|---|---|
| Temperatura | DS18B20 (sonda inox) | °C | −10 a 85 | 24 – 30 |
| pH | PH-4502C + sonda BNC | pH | 0 a 14 | 6,5 – 8,5 |
| Oxígeno disuelto | DFRobot SEN0237-A | mg/L | 0 a 20 | 5,0 – 9,0 |
| Turbidez | TS-300B | NTU | 0 a 3000 | 0 – 25 |

Los rangos óptimos no están en el firmware: viven en la tabla `tipos_parametros` y se editan desde el módulo de configuraciones.

---

## 2. Requerimientos

### 2.1 Funcionales

| ID | Requerimiento |
|---|---|
| RFH-01 | El nodo mide los cuatro parámetros del agua con las sondas sumergidas en la geomembrana. |
| RFH-02 | Convierte cada señal a su unidad de ingeniería aplicando la calibración de esa sonda. |
| RFH-03 | Compensa la lectura de oxígeno disuelto con la temperatura medida en el mismo instante. |
| RFH-04 | Agrupa las mediciones en un lote y lo envía por HTTP POST a `/api/v1/lecturas/` cada 5 minutos. |
| RFH-05 | Se autentica con un token de dispositivo revocable, entregado por el servidor. |
| RFH-06 | Si no hay red, guarda el lote en memoria flash y lo reenvía cuando la conexión vuelve. |
| RFH-07 | Omite del lote el sensor que no responde, sin interrumpir el envío de los demás. |
| RFH-08 | Señala su estado con el LED de la placa: destello corto es enlace sano; parpadeo lento es sin WiFi. |

### 2.2 No funcionales

- **Eléctricos:** lógica de 3,3 V no tolerante a 5 V; máximo 12 mA por pin; tierra común obligatoria entre fuente, sensores y placa.
- **Muestreo:** una medición cada 30 segundos, envío por lote cada 5 minutos. Los parámetros del agua cambian lentamente; muestrear más rápido satura MySQL sin aportar información.
- **Precisión:** mediana de 31 muestras del ADC por lectura, para que un pico de ruido de la bomba no desplace el valor.
- **Ambientales:** electrónica en caja IP65 con prensaestopas; solo las sondas quedan sumergidas.
- **Red:** WiFi 2,4 GHz. El ESP32 no opera en 5 GHz.
- **Seguridad:** el token se guarda en `secrets.h`, excluido de Git. Ninguna credencial de base de datos viaja al firmware.

### 2.3 Materiales

| Cant. | Componente | Función | Precio aprox. (COP) |
|---|---|---|---|
| 1 | ESP32 DevKit V1 (WROOM-32) | Microcontrolador | 35.000 |
| 1 | Sonda DS18B20 en acero inoxidable | Temperatura | 18.000 |
| 1 | Módulo PH-4502C + sonda BNC | pH | 95.000 |
| 1 | Kit SEN0237-A (DFRobot) | Oxígeno disuelto | 480.000 |
| 1 | Sensor TS-300B | Turbidez | 48.000 |
| 1 | Fuente 5 V · 2 A | Alimentación | 22.000 |
| 2 | Resistencias 10 kΩ y 20 kΩ (1 %) | Divisores de voltaje | 2.000 |
| 1 | Resistencia 4,7 kΩ | Pull-up del bus OneWire | 500 |
| 1 | Caja IP65 con prensaestopas | Protección a la intemperie | 40.000 |
| 1 | Protoboard o placa perforada y bornera | Armado | 15.000 |
| 2 | Soluciones buffer pH 4,01 y 6,86 | Calibración | 35.000 |
| 1 | ADS1115 (opcional) | ADC externo de 16 bits | 28.000 |

Precios de referencia en Colombia, septiembre de 2026. Verificar antes de comprar.

---

## 3. Diseño eléctrico

### 3.1 Restricciones del ESP32

Estas reglas condicionan todo el cableado y no son negociables:

1. **Lógica de 3,3 V, no tolerante a 5 V.** Un sensor alimentado a 5 V puede entregar 5 V en su salida; ese pin se daña de forma permanente.
2. **GPIO12 no se usa nunca.** En alto durante el arranque configura la flash a 1,8 V y la placa no vuelve a encender.
3. **GPIO6 a GPIO11 están reservados** para la memoria flash interna del módulo.
4. **El ADC2 no funciona con WiFi activo.** Los únicos canales analógicos utilizables son GPIO 32, 33, 34, 35, 36 y 39.
5. **GPIO34, 35, 36 y 39 son solo de entrada** y no tienen resistencia interna configurable.
6. **Máximo 12 mA por pin.** Relés y bombas se manejan con transistor, MOSFET u optoacoplador.
7. **Tierra común obligatoria** entre fuente, sensores y placa.

### 3.2 Asignación de pines

| Sensor | `codigo_hardware` | Pin | Tipo de señal | Acondicionamiento |
|---|---|---|---|---|
| Temperatura DS18B20 | `SEN-001-TEM` | GPIO4 | Digital OneWire, 3,3 V | Pull-up de 4,7 kΩ entre datos y 3,3 V |
| pH PH-4502C | `SEN-001-PH` | GPIO34 (ADC1_CH6) | Analógica 0 – 5 V | Divisor 10 kΩ / 20 kΩ |
| Oxígeno disuelto SEN0237-A | `SEN-001-OXI` | GPIO35 (ADC1_CH7) | Analógica 0 – 3,0 V | Directa |
| Turbidez TS-300B | `SEN-001-TUR` | GPIO32 (ADC1_CH4) | Analógica 0 – 4,5 V | Divisor 10 kΩ / 20 kΩ |
| LED de estado | — | GPIO2 | Salida | No conectar nada externo |

Pines analógicos libres para ampliación: GPIO33, GPIO36 y GPIO39. GPIO21 y GPIO22 quedan reservados para el bus I²C del ADS1115, si más adelante se requieren más canales.

El valor de `codigo_hardware` debe coincidir carácter por carácter con el registro en la tabla `sensores`. La API rechaza con HTTP 400 cualquier lectura cuyo código no exista, esté inactivo o pertenezca a otra geomembrana.

### 3.3 Divisor de voltaje

Para los sensores de 5 V:

```
V_pin = V_sensor × R2 / (R1 + R2)
      = 5 V × 20 kΩ / 30 kΩ
      = 3,33 V
```

R1 va entre la salida del sensor y el pin; R2 entre ese mismo punto y GND. El firmware recupera el voltaje original multiplicando por 1,5 (`factor_divisor` en la tabla `SENSORES[]`). Si se cambian las resistencias, se cambia también ese factor.

Cada sensor lleva su propio divisor. No se comparten resistencias.

### 3.4 Alimentación

- Una fuente única de 5 V y 2 A alimenta el pin `VIN` de la placa y la línea de 5 V de los sensores.
- Los sensores **no** se alimentan desde el pin de 3,3 V del ESP32: ese regulador entrega poca corriente y, al quedarse corto, provoca reinicios.
- Todos los GND se unen en una bornera.
- El cable hacia las sondas es apantallado o UTP, con la malla a GND en un solo extremo, el de la caja.
- Bombas y aireadores se alimentan desde otra fuente: el arranque de un motor produce una caída de tensión que reinicia la placa.

---

## 4. Flujo de funcionamiento

```
Sondas → acondicionamiento (divisor / pull-up) → ADC1 y bus OneWire del ESP32
      → conversión a unidad de ingeniería (calibración y compensación por temperatura)
      → lote JSON cada 5 min
      → HTTP POST /api/v1/lecturas/  con  Authorization: Device <token>
           │
           ├─ éxito → Django valida el rango físico del sensor
           │            → clasifica normal / riesgo / crítico contra tipos_parametros
           │            → persiste en lecturas_sensores
           │            → motor de alertas: abre o cierra alertas y notifica por rol
           │            → web y app móvil
           │
           └─ fallo (sin red o servidor caído)
                      → el lote se guarda en LittleFS (/cola.jsonl)
                      → se reenvía al reconectar; el backend deduplica por (sensor, timestamp)
```

**Secuencia interna de cada ciclo de medición**, en este orden por una razón concreta: la temperatura se lee primero porque la compensación del oxígeno disuelto la necesita.

1. Lectura del DS18B20 (750 ms a 12 bits de resolución).
2. Lectura de pH: mediana de 31 muestras del ADC, corrección del divisor, recta de calibración.
3. Lectura de oxígeno disuelto: mediana, y conversión a mg/L usando la temperatura del paso 1.
4. Lectura de turbidez: mediana, corrección del divisor, curva del fabricante.
5. Armado del lote JSON con `codigo_hardware`, `valor`, `secuencia` y `timestamp`.
6. Envío o encolado.

---

## 5. Casos de uso

### CU-H01 · Puesta en marcha de un nodo nuevo

**Actor:** Instructor Líder u Operario con acceso al servidor.
**Precondición:** la geomembrana existe en el sistema y la red WiFi de 2,4 GHz está disponible en el sitio.

**Flujo principal**

1. El operario registra el dispositivo: `python manage.py crear_dispositivo ESP32-P1 --piscina GEO-001`.
2. El sistema genera un token de 64 caracteres y lo muestra una sola vez.
3. El operario copia el token y las credenciales de WiFi a `firmware/bioaqua_ingesta/secrets.h`.
4. Registra los cuatro sensores desde la web, con su código de hardware y la geomembrana asignada.
5. Carga el sketch `bioaqua_handshake` y confirma en el monitor serie que el servidor responde 200.
6. Cablea los sensores siguiendo la sección 3 y calibra según la sección 6.
7. Carga `bioaqua_ingesta`. El primer lote llega en segundos.

**Postcondición:** las lecturas aparecen en el módulo de monitoreo y en la app móvil.

**Flujos alternos**

- *Token rechazado (401):* el token está mal copiado o el dispositivo fue desactivado. Se verifica en el admin de Django.
- *Sensor no reconocido (400):* el `codigo_hardware` no coincide con el registro, o el sensor pertenece a otra geomembrana. El mensaje de error nombra el código rechazado.

### CU-H02 · Ingesta periódica de mediciones

**Actor:** nodo ESP32 (actor del sistema).
**Precondición:** nodo activo con token válido.

1. El nodo despierta cada 5 minutos y lee los cuatro sensores.
2. Arma el lote y lo envía a `/api/v1/lecturas/`.
3. El servidor valida que cada valor esté dentro del rango físico del sensor.
4. Clasifica cada lectura y la persiste.
5. El motor de alertas abre alerta por los parámetros fuera de rango y cierra las que volvieron a la normalidad.
6. El servidor responde con el resumen del lote: registradas, críticas, alertas generadas y rechazadas.

**Flujos alternos**

- *Valor fuera del rango medible del sensor:* el servidor descarta esa lectura y la reporta en `rechazadas`, con la razón. Indica sonda descalibrada o cableado defectuoso.
- *Sin red:* el lote se guarda en LittleFS y se reenvía al reconectar (RF019).

### CU-H03 · Calibración periódica de una sonda

**Actor:** Operario.
**Precondición:** soluciones buffer vigentes.

1. Retira la sonda, la lava con agua destilada y carga el sketch `bioaqua_calibracion`.
2. Mide el voltaje en cada solución patrón y lo anota.
3. Calcula las constantes y las escribe en `bioaqua_ingesta.ino`.
4. Recarga el firmware y verifica que la lectura en el buffer de pH 7 quede entre 6,9 y 7,1.
5. Registra fecha, voltajes y constantes en la bitácora del proyecto.

**Frecuencia:** pH cada mes; oxígeno disuelto cada tres meses, con cambio de electrolito cada seis; turbidez cuando el agua destilada deje de dar el voltaje de referencia.

---

## 6. Calibración

### 6.1 pH — dos puntos

Con los buffers de 4,01 y 6,86 se obtiene la recta que convierte voltios a pH:

```
PH_M = (pH1 − pH2) / (V1 − V2)
PH_B = pH1 − PH_M × V1
```

Ejemplo con una sonda nueva:

| Solución | Voltaje medido |
|---|---|
| Buffer 6,86 | 2,54 V |
| Buffer 4,01 | 3,05 V |

```
PH_M = (6,86 − 4,01) / (2,54 − 3,05) = −5,59
PH_B = 6,86 − (−5,59 × 2,54)         = 21,06
```

El módulo PH-4502C tiene además un potenciómetro de ajuste de cero junto al conector BNC: con la sonda en buffer de pH 7 se gira hasta que la salida `Po` marque 2,50 V. El segundo potenciómetro corresponde a la alarma digital y no se usa.

### 6.2 Oxígeno disuelto — saturación en aire

Con la membrana húmeda y expuesta al aire, la sonda ve oxígeno al 100 % de saturación. Se anotan el voltaje en milivoltios y la temperatura de ese momento: son `OXI_CAL_MV` y `OXI_CAL_TEMP_C`.

La conversión a mg/L aplica la tabla de saturación del agua dulce entre 0 y 40 °C, corrigiendo la deriva de la sonda con 35 mV por grado. Sin esta compensación, un día soleado aparenta una caída de oxígeno que no existe.

### 6.3 Turbidez — agua destilada como cero

La sonda en agua destilada marca el punto de 0 NTU; en el TS-300B ronda los 4,2 V. La relación es inversa: entre más sólidos en suspensión, menor el voltaje. El firmware aplica la curva de segundo grado del fabricante y satura el resultado entre 0 y 3000 NTU.

---

## 7. Procedimiento de armado

Cada paso tiene una verificación. No se avanza al siguiente sin superarla: así, cuando algo falla, la causa está acotada al último paso.

| # | Paso | Verificación |
|---|---|---|
| 1 | Cargar `bioaqua_handshake` con la placa sin sensores | El serial imprime la IP y el servidor responde 200 |
| 2 | Conectar la fuente de 5 V y armar la bornera de GND | 5,0 ± 0,2 V y 3,3 ± 0,1 V con el multímetro |
| 3 | Cablear el DS18B20 con su pull-up de 4,7 kΩ | Marca la temperatura ambiente, no −127 °C |
| 4 | Armar los dos divisores y alimentar pH y turbidez | Ninguna salida de divisor supera 3,3 V |
| 5 | Conectar las tres señales analógicas a la placa | Los voltajes cambian al manipular las sondas |
| 6 | Calibrar con `bioaqua_calibracion` y las soluciones patrón | En buffer de pH 7 el firmware reporta 6,9 – 7,1 |
| 7 | Cargar `bioaqua_ingesta` con los cuatro sensores activos | Las lecturas aparecen en la web y en la app |
| 8 | Montar en caja IP65 e instalar en el estanque | 24 horas seguidas sin huecos en el historial |

En el paso 8, los cables entran a la caja formando un lazo hacia abajo antes del prensaestopas, para que el agua de lluvia escurra en vez de seguir el cable hasta la electrónica.

---

## 8. Diagnóstico de fallas

| Síntoma | Causa más probable | Acción |
|---|---|---|
| Temperatura en −127 °C | Falta el pull-up de 4,7 kΩ o el dato está en otro pin | Revisar la resistencia entre datos y 3,3 V |
| Un analógico fijo en el valor máximo | Al pin llega más de 3,3 V | Desconectar y medir el divisor; el pin puede estar dañado |
| Lecturas erráticas sin que el agua cambie | Tierras sin unir, o cable largo sin apantallar | Unir todos los GND; usar cable apantallado |
| Reinicios espontáneos de la placa | Fuente insuficiente en los picos de transmisión WiFi | Fuente de 2 A y condensador de 1000 µF |
| La placa no enciende tras cablear | Algo quedó conectado a GPIO12 | Retirarlo; si no revive, la flash quedó mal configurada |
| Analógico siempre en 0 con WiFi activo | El pin pertenece al ADC2 | Mover a GPIO 32, 33, 34, 35, 36 o 39 |
| No asocia al WiFi con la clave correcta | Red de 5 GHz, o SSID con tildes o emojis | Red de 2,4 GHz con nombre simple |
| HTTP 401 | Token mal copiado o dispositivo inactivo | Revisar `secrets.h` y el estado en el admin |
| HTTP 400 nombrando un sensor | Código de hardware inexistente, inactivo o de otra piscina | Corregir el registro del sensor |

---

## 9. Archivos del módulo

| Ruta | Contenido |
|---|---|
| `firmware/bioaqua_handshake/` | Sketch de validación de enlace. No lee sensores. |
| `firmware/bioaqua_calibracion/` | Banco de calibración: imprime voltajes reales por el monitor serie. |
| `firmware/bioaqua_ingesta/` | Firmware de producción: cuatro sensores, cola offline en LittleFS. |
| `firmware/*/secrets.h` | Credenciales y token. Excluido de Git. |
| `apps/monitoreo/api_auth.py` | Autenticación por token de dispositivo. |
| `apps/monitoreo/serializers.py` | Validación de plausibilidad física de cada lectura. |
| `apps/monitoreo/views.py` | `HandshakeView` e `IngestaLecturasView`. |
| `docs/HARDWARE_SENSORES.md` | Este documento. |

Librerías de Arduino requeridas: ArduinoJson 7.x, OneWire y DallasTemperature. Esquema de partición en el IDE: «Default 4MB with spiffs», necesario para la cola offline.

---

## 10. Pendiente

- Calibrar con las sondas reales y reemplazar las constantes de ejemplo del firmware por las medidas.
- Verificar el consumo del nodo completo para dimensionar batería y panel solar, si la instalación queda lejos de un tomacorriente.
- Evaluar el ADS1115 si se agregan más sensores analógicos: solo quedan tres canales libres en el ADC1.
- Migrar la ingesta a HTTPS antes de sacar el sistema de la red local.
