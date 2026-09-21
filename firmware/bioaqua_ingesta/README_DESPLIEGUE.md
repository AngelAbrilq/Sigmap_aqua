# BioAqua — Runbook de despliegue del nodo ESP32 (ingesta real)

Objetivo: que el día de la implementación sea **solo cablear y grabar**. Todo lo
de software queda listo con antelación siguiendo esta guía.

## 0. Librerías del Arduino IDE (instalar una vez)
- **ArduinoJson** 7.x (Benoit Blanchon)
- **OneWire** y **DallasTemperature** (solo si usarás el DS18B20 de temperatura)
- Placa: "ESP32 Dev Module" (paquete *esp32 by Espressif*, core **3.x**)

## 1. Pinout (ADC1 obligatorio para analógicos)
| Señal | Pin ESP32 | Nota |
|---|---|---|
| pH (Po de la placa PH4502C) | **GPIO34** | ADC1, input-only |
| Oxígeno disuelto (salida analógica) | **GPIO35** | ADC1, input-only |
| DS18B20 DATA | **GPIO4** | + resistencia **4.7 kΩ** a 3V3 |
| VCC pH / O2 | **5V (VIN)** | módulos de 5 V |
| VCC DS18B20 | **3V3** | |
| GND (todos) | **GND común** | obligatorio |
| LED estado | GPIO2 | interno, **no conectar nada** |

> Antes de conectar un analógico al pin, **mide con multímetro** que la salida
> no supere 3.3 V. Si supera, usa divisor de voltaje o dañarás el ADC.

## 2. Preparar la BD (una vez, en el PC con Django + Laragon encendido)
```powershell
# a) Crear la geomembrana real (o hazlo desde la web como Instructor Líder).
#    Anota su codigo_identificacion, ej. GEO-01

# b) Crear los sensores de esa piscina (desde la web /geomembranas y /sensores,
#    o admin). DECIDE sus codigo_hardware, ej: GEO01-PH, GEO01-OX, GEO01-TEMP.
#    Pon rango_medicion_min/max reales (fuera de ese rango la lectura se rechaza).

# c) Registrar el nodo y obtener su token:
python manage.py crear_dispositivo ESP32-P1 --piscina GEO-01
#    -> imprime el TOKEN una sola vez. Cópialo.
```

## 3. Configurar el firmware
1. Copia `secrets.h.example` a **`secrets.h`** y completa: WiFi (2.4 GHz),
   `DEVICE_TOKEN` (el del paso 2c), `SERVER_HOST` (IP del PC en la LAN) y puerto.
2. En `bioaqua_ingesta.ino`, en la tabla **`SENSORES[]`**, pon los
   `codigo_hardware` **EXACTOS** que creaste en la BD (paso 2b) y `activo=true`
   solo en los que ya estén cableados.
3. Ajusta la calibración (`PH_M/PH_B`, `OX_M/OX_B`) con buffers patrón (ver §5).

## 4. Grabar y verificar
- Sube el sketch, abre el **Monitor Serial a 115200 baudios**.
- Deberías ver: conexión WiFi OK → `POST .../lecturas/` → `201 -> {..."registradas":N...}`.
- Entra a la web `/monitoreo/` y `/alertas/`: la lectura ya está ahí.

## 5. Calibración de dos puntos (rápida)
- **pH**: mide el voltaje en buffer pH 7 y pH 4. Con dos puntos (V, pH) calcula
  la recta `pH = M·V + B` y pon M y B en el `.ino`.
- **O2**: punto alto = aire saturado (~7–8 mg/L), punto bajo = solución cero.

## 6. Diagnóstico (mapa error → causa)
El servidor responde SIEMPRE `{success, data, message}`. Si algo falla:
| Respuesta del servidor | Causa | Arreglo |
|---|---|---|
| `401 Cabecera Authorization ... mal formada` | token ausente/formato | revisa `DEVICE_TOKEN` y el header `Device <token>` |
| `401 Token de dispositivo invalido` | token no existe/rotado | vuelve a correr `crear_dispositivo --rotar-token` y actualiza `secrets.h` |
| `No existe un sensor registrado con codigo "X"` | `codigo_hardware` no coincide | iguala la tabla del `.ino` con la BD |
| `... pertenece a otra piscina` | el sensor no es de la piscina del nodo | corrige la piscina del sensor o del dispositivo |
| `... supera/por debajo del rango medible` | valor fuera de `rango_medicion` | calibración o cableado; el resto del lote sí entra |
| Error de transporte / timeout | red/IP/puerto | confirma IP del PC, `DEBUG`/firewall, misma LAN, 2.4 GHz |

## 7. Checklist del día
- [ ] MySQL (Laragon) y `runserver 0.0.0.0:8000` encendidos.
- [ ] Geomembrana + sensores creados, con `rango_medicion` y `codigo_hardware`.
- [ ] Dispositivo creado y token en `secrets.h`.
- [ ] `SENSORES[]` del `.ino` con los códigos reales y `activo` correcto.
- [ ] Multímetro: ninguna salida analógica > 3.3 V.
- [ ] GND común entre fuente, sensores y ESP32.
- [ ] Grabar → Monitor Serial → ver `201` → confirmar en la web.

## Nota sobre modo offline (RF019)
Este firmware, si el POST falla, reintenta en el próximo ciclo (no guarda en
disco todavía). El buffer local en LittleFS + reenvío es el trabajo de RF019,
marcado con un `TODO` en `enviarLote()`.
