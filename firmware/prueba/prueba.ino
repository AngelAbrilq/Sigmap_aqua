/**
 * @file    prueba.ino
 * @brief   Prueba AISLADA del sensor de pH (PH-4502C) en la placa SIGMAP-AQUA.
 * @target  ESP32-D0WD-V3 (WROOM-32), Arduino core 3.x
 *
 * PROPOSITO
 *   Validar SOLO el sensor de pH sobre la placa soldada, sin WiFi, sin pantalla
 *   y sin los otros sensores. Es el primer paso antes de montar el nodo completo.
 *   Imprime en el monitor serie (115200 baud) el voltaje leido y el pH estimado.
 *
 * CABLEADO (igual que en bioaqua_ingesta.ino)
 *   PH-4502C  Po --> [10k] --+-- GPIO34 --+-- [20k] --> GND
 *   Divisor 10k/20k  =>  factor 1.5 (la sonda sale hasta ~5 V, el pin recibe <=3.3 V)
 *   Modulo alimentado a 5 V (VIN), GND comun con el ESP32. GPIO34 es solo-entrada (ADC1).
 *
 * NOTA: el pH es ESTIMADO con la recta de fabrica. Para que sea real hay que
 *   calibrar con buffers 6.86 y 4.01 (eso lo hace bioaqua_calibracion / NVS).
 */

// --- Pin y electronica del sensor de pH ---
static const uint8_t PH_PIN            = 34;     ///< GPIO34, entrada analogica (ADC1)
static const float   PH_DIVIDER_FACTOR = 1.5f;   ///< divisor 10k/20k: V_sonda = V_pin * 1.5

// --- Recta de calibracion de fabrica:  pH = m * V_sonda + b ---
static const float   PH_SLOPE     = -5.70f;      ///< pendiente por defecto (sin calibrar)
static const float   PH_INTERCEPT = 21.34f;      ///< intercepto por defecto (sin calibrar)

// --- Muestreo ---
static const uint8_t  SAMPLE_COUNT   = 20;       ///< lecturas por medicion (promedio)
static const uint32_t READ_PERIOD_MS = 1000;     ///< cada cuanto mide y muestra

/**
 * @brief  Lee el voltaje de la SONDA de pH, promediando varias muestras.
 * @return Voltaje de la sonda en voltios (ya corregido por el divisor).
 */
float readPhVoltage() {
  uint32_t totalMilliVolts = 0;
  for (uint8_t i = 0; i < SAMPLE_COUNT; i++) {
    totalMilliVolts += analogReadMilliVolts(PH_PIN);  // mV reales en el pin (curva ADC de fabrica)
    delay(5);
  }
  const float pinVolts = (totalMilliVolts / (float)SAMPLE_COUNT) / 1000.0f;
  return pinVolts * PH_DIVIDER_FACTOR;  // voltaje real de la sonda
}

/**
 * @brief  Convierte el voltaje de la sonda a pH con la recta de calibracion.
 * @param  probeVolts Voltaje de la sonda en voltios.
 * @return pH estimado (0-14 aprox.).
 */
float voltageToPh(float probeVolts) {
  return PH_SLOPE * probeVolts + PH_INTERCEPT;
}

void setup() {
  Serial.begin(115200);
  delay(300);
  analogReadResolution(12);                     // 0-4095
  analogSetPinAttenuation(PH_PIN, ADC_11db);    // rango ~0-3.1 V en el pin
  Serial.println();
  Serial.println(F("=== PRUEBA SENSOR pH (PH-4502C) - SIGMAP-AQUA ==="));
  Serial.println(F("GPIO34 | divisor 1.5 | pH estimado (sin calibrar)"));
  Serial.println(F("-------------------------------------------------"));
}

void loop() {
  const float probeVolts = readPhVoltage();
  const float phValue     = voltageToPh(probeVolts);

  Serial.printf("V_sonda: %.3f V   |   pH estimado: %.2f\n", probeVolts, phValue);

  delay(READ_PERIOD_MS);
}
