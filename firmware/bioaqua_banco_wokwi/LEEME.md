# Banco de cableado en Wokwi — nodo ESP32 de BioAqua

**Verificado el 5 de octubre de 2026**: compila y corre en Wokwi. El LED de GPIO2
conmuta, confirmando que `loop()` se ejecuta.

## Qué es

Un gemelo **eléctrico y lógico** del nodo de sensores, para validar el mapa de
pines, los divisores y el firmware antes de cablear hardware real.

## Qué NO es

Wokwi **no tiene** sondas de pH, oxígeno disuelto ni turbidez. Los tres
potenciómetros del esquema reemplazan la *salida eléctrica* de esos módulos.

- ✅ Sirve para: verificar pines, divisores, bus OneWire, y que la lógica compile y corra.
- ❌ No sirve para: medir, calibrar, ni estimar el comportamiento de una sonda en agua.

**Los valores que produce no son parámetros del agua y no deben enviarse a
`/api/v1/lecturas/` ni a la base de datos `sigmap_agua`.** El sketch es solo
serial: no tiene WiFi ni HTTP, así que no puede enviarlos aunque se quisiera.

## Cómo abrirlo

1. <https://wokwi.com/projects/new/esp32>
2. Pestaña **Code** → `diagram.json` → selecciona todo y pega este `diagram.json`
3. `sketch.ino` → pega `bioaqua_banco_wokwi.ino`
4. **Library Manager** → `+` → agrega `DallasTemperature` y `OneWire`
5. ▶ Gira los potenciómetros y mira el monitor serie

## ⚠️ Corrección respecto a la versión 1.0 del documento de hardware

El divisor de pH documentado como **10 kΩ / 20 kΩ entrega 3,333 V**, por encima
del tope útil del ADC (~3,1 V con atenuación de 11 dB). La parte alta de la
escala de pH se recorta: valores distintos devuelven la misma cuenta.

**Valor corregido: 10 kΩ / 15 kΩ → 3,000 V, `factor_divisor` = 1,667.**

No daña el pin (el máximo absoluto es 3,6 V), pero falsea la medición en silencio.

## Resistencias

| Sensor | Salida | R1 | R2 | V en el pin | `factor_divisor` |
|---|---|---|---|---|---|
| pH PH-4502C | 0–5 V | 10 kΩ | **15 kΩ** | 3,000 V | **1,667** |
| Turbidez TS-300B | 0–4,5 V | 10 kΩ | 20 kΩ | 3,000 V | 1,500 |
| Oxígeno SEN0237-A | 0–3,0 V | — | — | 3,000 V | 1,000 |
| Temperatura DS18B20 | Digital | 4,7 kΩ pull-up entre DQ y 3V3 | — | — | — |

```
Salida del sensor ──[ R1 ]──┬──> GPIO del ESP32
                             ├──[ C 100 nF ]── GND
                            [ R2 ]
                             │
                            GND
```

`V_pin = V_sonda × R2 / (R1 + R2)` · `factor_divisor = (R1 + R2) / R2`

**Resistencias de 1 % (película metálica).** Con 5 % el error llega a ±4 %, que en
pH son ≈0,5 unidades — la diferencia entre "normal" y "alerta" para tilapia.

Los condensadores de 100 nF a GND forman un filtro pasa-bajos (~240–265 Hz) que
elimina el ruido de 60 Hz de la bomba y los transitorios de la radio WiFi.

## Mapa de pines

| Sensor | `codigo_hardware` | Pin | Acondicionamiento |
|---|---|---|---|
| DS18B20 | `SEN-001-TEM` | GPIO4 | Pull-up 4,7 kΩ a 3V3 |
| PH-4502C | `SEN-001-PH` | GPIO34 | Divisor 10k/15k + 100 nF |
| SEN0237-A | `SEN-001-OXI` | GPIO35 | Directo |
| TS-300B | `SEN-001-TUR` | GPIO32 | Divisor 10k/20k + 100 nF |
| LED estado | — | GPIO2 | No conectar nada externo |

Prohibidos: **GPIO12** (strapping: deja la placa sin arrancar) y **GPIO6–11** (flash SPI).
Con WiFi activo el ADC2 no funciona: solo GPIO 32, 33, 34, 35, 36 y 39 sirven como analógicos.

## Qué comprobar al correrlo

| Comprobación | Resultado esperado |
|---|---|
| DS18B20 responde | Temperatura ≈ 24 °C, no `sin respuesta` |
| Divisor de pH al máximo | `V_pin` ≈ 3,00 V y **sin** el aviso `<< SATURA` |
| Oxígeno directo | `V_pin` = `V_sonda` |
| Divisor de turbidez al máximo | `V_sonda` ≈ 4,5 V |

Si aparece `<< SATURA`, el cálculo de resistencias está mal. En hardware real ese
mismo error daña el pin de forma permanente y silenciosa.
