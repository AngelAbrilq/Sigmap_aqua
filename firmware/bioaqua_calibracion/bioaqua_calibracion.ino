/**
 * @file    bioaqua_calibracion.ino
 * @brief   Banco de pruebas y calibracion de sondas - BioAqua System / SIGMAP-AQUA.
 * @target  ESP32-D0WD-V3 (WROOM-32), Arduino core 3.x
 *
 * Muestra en el monitor serie, organizados en una tabla, los tres sensores:
 *   Temperatura (DS18B20), pH (PH-4502C) y Turbidez (TS-300B).
 * Por cada uno: valor, unidad, estado del agua, voltajes y estabilidad.
 *
 * pH y NTU son ESTIMADOS con constantes genericas hasta calibrar con
 * soluciones patron (ver docs/HARDWARE_SENSORES.md, seccion 8). Anota V_sonda cuando diga ESTABLE.
 *
 * MONITOR SERIE: 115200 baudios.
 * LIBRERIAS:     OneWire y DallasTemperature.
 *
 * CABLEADO
 *   Temperatura DS18B20  DATA -> GPIO32, pull-up 4,7k entre DATA y 3V3 (VCC a 3V3)
 *   pH  PH-4502C         Po -> [10k] -+- GPIO34 -+- [15k] -> GND   factor 1.667
 *   Turbidez TS-300B     A  -> [10k] -+- GPIO35 -+- [10k] -> GND   factor 2.000
 *   Modulos analogicos a 5 V (VIN), nunca al 3V3. GND comun con el ESP32.
 */

#include <OneWire.h>
#include <DallasTemperature.h>

// ---------------------------------------------------------------------------
// Configuracion (pon en false el sensor que no este conectado)
// ---------------------------------------------------------------------------
#define USAR_TEMPERATURA true
#define USAR_PH          true
#define USAR_TURBIDEZ    true

static const uint8_t PIN_TEMP     = 32;
static const uint8_t PIN_PH       = 34;
static const uint8_t PIN_TURBIDEZ = 35;

static const float FACTOR_PH       = 1.667f;  // (10k + 15k) / 15k
static const float FACTOR_TURBIDEZ = 2.000f;  // (10k + 10k) / 10k

// pH provisional (mismas constantes que bioaqua_ingesta.ino); se reemplazan al calibrar.
static const float PH_M = -5.59f;
static const float PH_B = 21.06f;

// Rangos optimos para tilapia (los mismos de la tabla tipos_parametros).
static const float TEMP_MIN = 24.0f, TEMP_MAX = 30.0f;
static const float PH_MIN   = 6.5f,  PH_MAX   = 8.5f;
static const float TURB_MAX = 25.0f;

// Medicion
static const uint8_t  N_MUESTRAS        = 31;    // mediana por lectura
static const uint8_t  N_HISTORIA        = 10;    // ventana de estabilidad
static const float    UMBRAL_ESTABLE_MV = 5.0f;  // +-5 mV
static const float    V_TOPE_ADC        = 3.1f;
static const uint16_t PERIODO_MS        = 2000;

static OneWire oneWire(PIN_TEMP);
static DallasTemperature ds18(&oneWire);
static uint32_t ciclo = 0;

// ---------------------------------------------------------------------------
// Ventana de estabilidad por canal analogico
// ---------------------------------------------------------------------------
struct Ventana {
  float   v[N_HISTORIA];
  uint8_t n;
};
static Ventana ventPh = {{0}, 0};
static Ventana ventTur = {{0}, 0};

/** @brief Agrega una muestra a la ventana. */
void registrar(Ventana& w, float valor) {
  for (uint8_t i = N_HISTORIA - 1; i > 0; i--) w.v[i] = w.v[i - 1];
  w.v[0] = valor;
  if (w.n < N_HISTORIA) w.n++;
}

/** @brief Max - min en mV; -1 si la ventana aun no esta llena. */
float dispersionMv(const Ventana& w) {
  if (w.n < N_HISTORIA) return -1.0f;
  float mn = w.v[0], mx = w.v[0];
  for (uint8_t i = 1; i < N_HISTORIA; i++) { mn = min(mn, w.v[i]); mx = max(mx, w.v[i]); }
  return (mx - mn) * 1000.0f;
}

/** @brief Texto de estabilidad para la columna LECTURA. */
const char* textoEstabilidad(const Ventana& w) {
  const float d = dispersionMv(w);
  if (d < 0) return "midiendo...";
  return d <= UMBRAL_ESTABLE_MV ? "ESTABLE" : "asentandose";
}

/**
 * @brief Mediana de N lecturas del pin, en voltios.
 * analogReadMilliVolts usa la calibracion de fabrica del ADC.
 */
float leerVoltiosPin(uint8_t pin) {
  uint32_t m[N_MUESTRAS];
  for (uint8_t i = 0; i < N_MUESTRAS; i++) { m[i] = analogReadMilliVolts(pin); delay(2); }
  for (uint8_t i = 1; i < N_MUESTRAS; i++) {
    uint32_t x = m[i]; int j = i;
    while (j > 0 && m[j - 1] > x) { m[j] = m[j - 1]; j--; }
    m[j] = x;
  }
  return m[N_MUESTRAS / 2] / 1000.0f;
}

/** @brief Curva del fabricante TS-300B: voltaje de sonda -> NTU. */
float turbidezNTU(float v) {
  if (v >= 4.2f) return 0.0f;
  if (v < 2.5f)  return 3000.0f;
  return constrain(-1120.4f * v * v + 5742.3f * v - 4353.8f, 0.0f, 3000.0f);
}

/** @brief Estado del agua frente al rango optimo. */
const char* estadoRango(float valor, float minimo, float maximo) {
  if (valor < minimo) return "BAJO";
  if (valor > maximo) return "ALTO";
  return "OPTIMO";
}

// ---------------------------------------------------------------------------
// Impresion de filas
// ---------------------------------------------------------------------------
void filaTemperatura() {
  ds18.requestTemperatures();                 // ~750 ms a 12 bits
  const float t = ds18.getTempCByIndex(0);
  if (t == DEVICE_DISCONNECTED_C) {
    Serial.println(" Temperatura |     ---       | SIN SENSOR | DS18B20 no responde (GPIO32 / pull-up 4,7k)");
    return;
  }
  Serial.printf(" Temperatura | %8.2f °C   | %-10s | DS18B20 GPIO%-2u              | %s\n",
                t, estadoRango(t, TEMP_MIN, TEMP_MAX), PIN_TEMP,
                t == 85.0f ? "revisar (85 C = arranque)" : "OK");
}

void filaPh() {
  const float vPin   = leerVoltiosPin(PIN_PH);
  const float vSonda = vPin * FACTOR_PH;
  registrar(ventPh, vSonda);
  const float ph = constrain(PH_M * vSonda + PH_B, 0.0f, 14.0f);
  Serial.printf(" pH          | %8.2f pH   | %-10s | pin %.3f V  sonda %.3f V | %s\n",
                ph, estadoRango(ph, PH_MIN, PH_MAX), vPin, vSonda, textoEstabilidad(ventPh));
  if (vPin > V_TOPE_ADC) Serial.println("             *** ALERTA: el pin del pH supera 3,1 V. Revisa el divisor.");
  if (vPin < 0.05f)      Serial.println("             *** pH en ~0 V: modulo sin 5 V o cable Po suelto.");
}

void filaTurbidez() {
  const float vPin   = leerVoltiosPin(PIN_TURBIDEZ);
  const float vSonda = vPin * FACTOR_TURBIDEZ;
  registrar(ventTur, vSonda);
  const float ntu = turbidezNTU(vSonda);
  Serial.printf(" Turbidez    | %8.2f NTU  | %-10s | pin %.3f V  sonda %.3f V | %s\n",
                ntu, ntu <= TURB_MAX ? "OPTIMO" : "ALTO", vPin, vSonda, textoEstabilidad(ventTur));
  if (vPin > V_TOPE_ADC) Serial.println("             *** ALERTA: el pin de turbidez supera 3,1 V. Revisa el divisor.");
  if (vPin < 0.05f)      Serial.println("             *** Turbidez en ~0 V: sensor sin 5 V o cable A suelto.");
}

void separador() {
  Serial.println("-------------+---------------+------------+----------------------------+--------------");
}

// ---------------------------------------------------------------------------
void setup() {
  Serial.begin(115200);
  delay(500);
  analogSetAttenuation(ADC_11db);   // rango util ~0.15 a 3.1 V
  if (USAR_TEMPERATURA) { ds18.begin(); ds18.setResolution(12); }

  Serial.println();
  Serial.println("=====================================================================================");
  Serial.println("  BioAqua System - MONITOR DE SENSORES (temperatura, pH y turbidez)");
  Serial.println("=====================================================================================");
  if (USAR_TEMPERATURA) Serial.printf("  Temperatura : DS18B20 en GPIO%u  (detectados: %d)\n", PIN_TEMP, ds18.getDeviceCount());
  if (USAR_PH)          Serial.printf("  pH          : PH-4502C en GPIO%u  (factor divisor %.3f)\n", PIN_PH, FACTOR_PH);
  if (USAR_TURBIDEZ)    Serial.printf("  Turbidez    : TS-300B en GPIO%u  (factor divisor %.3f)\n", PIN_TURBIDEZ, FACTOR_TURBIDEZ);
  Serial.printf("  Rangos optimos: %.0f-%.0f °C | pH %.1f-%.1f | turbidez <= %.0f NTU\n",
                TEMP_MIN, TEMP_MAX, PH_MIN, PH_MAX, TURB_MAX);
  Serial.println("  pH y NTU son ESTIMADOS hasta calibrar. Cuando diga ESTABLE, anota 'sonda' en voltios.");
  Serial.println("=====================================================================================");
}

void loop() {
  Serial.printf("\n Lectura #%lu   (t = %lu s)\n", (unsigned long)(++ciclo), (unsigned long)(millis() / 1000));
  separador();
  Serial.println(" SENSOR      |     VALOR     | ESTADO     | SENAL                      | LECTURA");
  separador();
  if (USAR_TEMPERATURA) filaTemperatura();
  if (USAR_PH)          filaPh();
  if (USAR_TURBIDEZ)    filaTurbidez();
  separador();
  delay(PERIODO_MS);
}
