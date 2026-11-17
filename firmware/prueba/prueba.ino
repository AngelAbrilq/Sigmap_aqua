/**
 * @file    prueba.ino
 * @brief   Prueba de 3 sensores: pH (PH-4502C), Turbidez (TS-300B) y
 *          Temperatura (DS18B20) - SIGMAP-AQUA.
 * @target  ESP32-D0WD-V3 (WROOM-32), Arduino core 3.x
 *
 * PROPOSITO
 *   Validar pH, turbidez y temperatura sobre la placa soldada, sin WiFi ni
 *   pantalla. Imprime en el monitor serie (115200 baud) una linea por segundo.
 *
 * LIBRERIAS: OneWire y DallasTemperature (instalar desde el Library Manager).
 *
 * CABLEADO
 *   pH  PH-4502C  Po --> [10k] --+-- GPIO34 --+-- [20k] --> GND   factor 1.5
 *   Turbidez TS-300B  A  --> [10k] --+-- GPIO35 --+-- [10k] --> GND   factor 2.0
 *   Temp DS18B20  DATA --> GPIO32, pull-up 4.7k entre DATA y 3V3 (VCC a 3V3)
 *   Los analogicos (pH/turbidez) a 5 V; el DS18B20 a 3V3. GND COMUN con el ESP32.
 *   GPIO34 y GPIO35 son solo-entrada (ADC1).
 *
 * NOTA: pH y turbidez son ESTIMADOS con constantes de fabrica (falta calibrar);
 *   la temperatura del DS18B20 es directa, no necesita calibracion.
 */

#include <OneWire.h>
#include <DallasTemperature.h>

// ============================ pH (PH-4502C) =================================
static const uint8_t PH_PIN            = 34;     ///< GPIO34, entrada analogica (ADC1)
static const float   PH_DIVIDER_FACTOR = 1.5f;   ///< divisor 10k/20k: V_sonda = V_pin * 1.5
static const float   PH_SLOPE          = -5.70f; ///< recta de fabrica: pH = m*V + b
static const float   PH_INTERCEPT      = 21.34f;

// ========================== Turbidez (TS-300B) =============================
static const uint8_t TURB_PIN            = 35;     ///< GPIO35, entrada analogica (ADC1)
static const float   TURB_DIVIDER_FACTOR = 2.0f;   ///< divisor 10k/10k: V_sonda = V_pin * 2.0
static const float   TURB_VOLTS_CLEAN    = 4.20f;  ///< voltaje de agua limpia (referencia / calibracion)
static const float   TURB_VOLTS_DIRTY    = 2.50f;  ///< por debajo de esto -> NTU maximo
static const float   TURB_NTU_MAX        = 3000.0f;
static float         turbCleanRef        = TURB_VOLTS_CLEAN; ///< ref de agua limpia (ajustable al calibrar)

// ========================= Temperatura (DS18B20) ===========================
static const uint8_t TEMP_PIN = 32;   ///< GPIO32, bus OneWire (pull-up 4.7k a 3V3)
static OneWire oneWireBus(TEMP_PIN);
static DallasTemperature tempSensor(&oneWireBus);

// ============================== Muestreo ===================================
static const uint8_t  SAMPLE_COUNT   = 20;   ///< lecturas analogicas por medicion (promedio)
static const uint32_t READ_PERIOD_MS = 1000; ///< cada cuanto mide y muestra

/**
 * @brief  Lee el voltaje REAL de una sonda analogica, promediando muestras.
 * @param  gpio          Pin del ADC1 (32-39).
 * @param  dividerFactor Factor para recuperar el voltaje antes del divisor.
 * @return Voltaje de la sonda en voltios (ya corregido por el divisor).
 */
float readProbeVoltage(uint8_t gpio, float dividerFactor) {
  uint32_t totalMilliVolts = 0;
  for (uint8_t i = 0; i < SAMPLE_COUNT; i++) {
    totalMilliVolts += analogReadMilliVolts(gpio);  // mV reales en el pin (curva ADC de fabrica)
    delay(5);
  }
  const float pinVolts = (totalMilliVolts / (float)SAMPLE_COUNT) / 1000.0f;
  return pinVolts * dividerFactor;
}

/**
 * @brief  Convierte el voltaje de la sonda de pH a pH con la recta de fabrica.
 * @param  probeVolts Voltaje de la sonda en voltios.
 * @return pH estimado (0-14 aprox.).
 */
float voltageToPh(float probeVolts) {
  return PH_SLOPE * probeVolts + PH_INTERCEPT;
}

/**
 * @brief  Convierte el voltaje del TS-300B a NTU con la curva del fabricante.
 *         El voltaje se normaliza al punto de agua limpia (turbCleanRef = 0 NTU).
 * @param  probeVolts Voltaje real del sensor (ya sin el divisor).
 * @return Turbidez en NTU (0 = limpia, hasta 3000).
 */
float voltageToTurbidityNtu(float probeVolts) {
  if (turbCleanRef <= 0.1f) return NAN;
  const float v = probeVolts * (TURB_VOLTS_CLEAN / turbCleanRef);  // normalizado a la curva
  if (v >= TURB_VOLTS_CLEAN) return 0.0f;
  if (v <= TURB_VOLTS_DIRTY) return TURB_NTU_MAX;
  const float ntu = -1120.4f * v * v + 5742.3f * v - 4353.8f;
  return constrain(ntu, 0.0f, TURB_NTU_MAX);
}

/**
 * @brief  Lee la temperatura del DS18B20.
 * @return Temperatura en grados Celsius, o NAN si la sonda no responde.
 */
float readTemperatureCelsius() {
  tempSensor.requestTemperatures();
  const float celsius = tempSensor.getTempCByIndex(0);
  if (celsius == DEVICE_DISCONNECTED_C) return NAN;  // sonda ausente o mal cableada
  return celsius;
}

void setup() {
  Serial.begin(115200);
  delay(300);
  analogReadResolution(12);                      // 0-4095
  analogSetPinAttenuation(PH_PIN,   ADC_11db);   // rango ~0-3.1 V en el pin
  analogSetPinAttenuation(TURB_PIN, ADC_11db);
  tempSensor.begin();
  Serial.println();
  Serial.println(F("=== PRUEBA pH + TURBIDEZ + TEMPERATURA - SIGMAP-AQUA ==="));
  Serial.println(F("pH GPIO34 (x1.5) | Turbidez GPIO35 (x2.0) | Temp DS18B20 GPIO32"));
  Serial.println(F("--------------------------------------------------------------"));
}

void loop() {
  const float phVolts   = readProbeVoltage(PH_PIN,   PH_DIVIDER_FACTOR);
  const float phValue   = voltageToPh(phVolts);

  const float turbVolts = readProbeVoltage(TURB_PIN, TURB_DIVIDER_FACTOR);
  const float turbNtu   = voltageToTurbidityNtu(turbVolts);

  const float tempC     = readTemperatureCelsius();

  if (isnan(tempC)) {
    Serial.printf("pH: %.2f (%.3f V)   |   Turbidez: %.0f NTU (%.3f V)   |   Temp: --- (sin sonda)\n",
                  phValue, phVolts, turbNtu, turbVolts);
  } else {
    Serial.printf("pH: %.2f (%.3f V)   |   Turbidez: %.0f NTU (%.3f V)   |   Temp: %.2f C\n",
                  phValue, phVolts, turbNtu, turbVolts, tempC);
  }

  delay(READ_PERIOD_MS);
}
