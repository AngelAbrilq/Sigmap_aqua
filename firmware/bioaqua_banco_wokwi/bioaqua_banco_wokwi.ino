/**
 * @file    bioaqua_banco_wokwi.ino
 * @brief   Banco de cableado y logica del nodo BioAqua - SOLO SIMULACION.
 *
 * ================== AVISO IMPORTANTE ==================
 * Este sketch NO mide agua. Wokwi no dispone de sondas de pH, oxigeno
 * disuelto ni turbidez: los potenciometros del esquema sustituyen la
 * SALIDA ELECTRICA de esos modulos para validar dos cosas y nada mas:
 *   1. Que el mapa de pines es correcto (ADC1, OneWire, strapping pins).
 *   2. Que la logica de lectura y conversion compila y opera.
 *
 * Los valores que imprime NO son parametros del agua y NO deben enviarse
 * jamas a la API ni a la base de datos sigmap_agua.
 * ======================================================
 */

#include <OneWire.h>
#include <DallasTemperature.h>

static const uint8_t PIN_TEMP_ONEWIRE = 4;   // DS18B20   SEN-001-TEM
static const uint8_t PIN_PH_ADC       = 34;  // PH-4502C  SEN-001-PH   ADC1_CH6
static const uint8_t PIN_OXI_ADC      = 35;  // SEN0237-A SEN-001-OXI  ADC1_CH7
static const uint8_t PIN_TUR_ADC      = 32;  // TS-300B   SEN-001-TUR  ADC1_CH4
static const uint8_t PIN_LED_ESTADO   = 2;

// factor_divisor = (R1 + R2) / R2
static const float FACTOR_PH  = 1.667f;  // 10k / 15k  -> 5.0 V llega como 3.00 V
static const float FACTOR_OXI = 1.000f;  // directo    -> 3.0 V
static const float FACTOR_TUR = 1.500f;  // 10k / 20k  -> 4.5 V llega como 3.00 V

static const float   V_REF      = 3.3f;
static const float   V_TOPE_ADC = 3.1f;  // por encima el ADC satura
static const int     ADC_MAX    = 4095;
static const uint8_t N_MUESTRAS = 31;

OneWire oneWire(PIN_TEMP_ONEWIRE);
DallasTemperature sensorTemp(&oneWire);

/**
 * @brief Mediana de N lecturas del ADC; evita que un pico de ruido
 *        (arranque de bomba) desplace el valor.
 * @param pin Pin analogico del ADC1.
 * @return Cuenta cruda del ADC, 0 a 4095.
 */
int leerAdcMediana(uint8_t pin) {
  int m[N_MUESTRAS];
  for (uint8_t i = 0; i < N_MUESTRAS; i++) { m[i] = analogRead(pin); delay(2); }
  for (uint8_t i = 1; i < N_MUESTRAS; i++) {
    int v = m[i]; int j = i;
    while (j > 0 && m[j - 1] > v) { m[j] = m[j - 1]; j--; }
    m[j] = v;
  }
  return m[N_MUESTRAS / 2];
}

/** @brief Convierte cuenta del ADC a voltios en el pin. */
float cuentaAVoltios(int cuenta) { return (cuenta * V_REF) / ADC_MAX; }

/**
 * @brief Imprime una linea de canal analogico y avisa si el pin satura.
 * @param codigo codigo_hardware del sensor, como esta en la tabla `sensores`.
 * @param pin    Pin del ADC1.
 * @param factor factor_divisor que reconstruye el voltaje de la sonda.
 */
void reportarCanal(const char* codigo, uint8_t pin, float factor) {
  int   cuenta = leerAdcMediana(pin);
  float vPin   = cuentaAVoltios(cuenta);
  float vSonda = vPin * factor;
  Serial.printf("%-12s ADC=%4d  V_pin=%.3f  V_sonda=%.3f", codigo, cuenta, vPin, vSonda);
  if (vPin > V_TOPE_ADC) Serial.print("   << SATURA: revisar divisor");
  Serial.println();
}

void setup() {
  Serial.begin(115200);
  delay(500);
  pinMode(PIN_LED_ESTADO, OUTPUT);
  analogSetAttenuation(ADC_11db);
  sensorTemp.begin();
  sensorTemp.setResolution(12);

  Serial.println();
  Serial.println("================================================");
  Serial.println(" BioAqua - BANCO DE CABLEADO (SIMULACION)");
  Serial.println(" NO son datos de agua. No enviar a la API.");
  Serial.println("================================================");
  Serial.printf("Sensores OneWire detectados: %d\n\n", sensorTemp.getDeviceCount());
}

void loop() {
  digitalWrite(PIN_LED_ESTADO, HIGH);

  sensorTemp.requestTemperatures();
  float tempC = sensorTemp.getTempCByIndex(0);

  Serial.println("--- ciclo ---");
  if (tempC == DEVICE_DISCONNECTED_C) {
    Serial.println("SEN-001-TEM  sin respuesta (falta pull-up 4.7k en GPIO4)");
  } else {
    Serial.printf("SEN-001-TEM  %.2f C\n", tempC);
  }
  reportarCanal("SEN-001-PH",  PIN_PH_ADC,  FACTOR_PH);
  reportarCanal("SEN-001-OXI", PIN_OXI_ADC, FACTOR_OXI);
  reportarCanal("SEN-001-TUR", PIN_TUR_ADC, FACTOR_TUR);
  Serial.println();

  digitalWrite(PIN_LED_ESTADO, LOW);
  delay(3000);
}
