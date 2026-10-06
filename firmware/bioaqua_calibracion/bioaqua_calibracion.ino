/**
 * @file    bioaqua_calibracion.ino
 * @brief   Banco de calibracion de los sensores del nodo BioAqua.
 * @target  ESP32-D0WD-V3 (WROOM-32), Arduino core 3.x
 *
 * QUE HACE
 * Imprime por el monitor serie, cada segundo, el voltaje REAL de cada sensor
 * analogico y la temperatura del DS18B20. No usa WiFi y no envia nada: sirve
 * para anotar los numeros con los que se calculan las constantes que van en
 * bioaqua_ingesta.ino.
 *
 * COMO SE USA
 *   1. Carga este sketch y abre el monitor serie a 115200 baudios.
 *   2. pH: mete la sonda en el buffer 6,86, espera a que el voltaje se
 *      estabilice (~1 min) y anota. Lava con agua destilada y repite con el
 *      buffer 4,01. Con esos dos pares (pH, voltaje) calcula:
 *          PH_M = (pH1 - pH2) / (V1 - V2)
 *          PH_B = pH1 - PH_M * V1
 *   3. Oxigeno: con la membrana humeda al aire, espera 2 minutos y anota el
 *      voltaje en mV y la temperatura. Esos valores son OXI_CAL_MV y
 *      OXI_CAL_TEMP_C.
 *   4. Turbidez: sonda en agua destilada. El voltaje que marque es tu punto de
 *      0 NTU; si difiere mucho de 4,2 V, ajusta TURB_V_AGUA_LIMPIA.
 *   5. Copia las constantes a bioaqua_ingesta.ino y anotalas en el cuaderno
 *      del proyecto con la fecha.
 *
 * REGLA ELECTRICA: el pH y la turbidez DEBEN entrar por su divisor 10k/20k.
 * Mide con el multimetro antes de conectar: nada por encima de 3,3 V al pin.
 */

#include <OneWire.h>
#include <DallasTemperature.h>

static const uint8_t PIN_PH        = 34;
static const uint8_t PIN_OXIGENO   = 35;
static const uint8_t PIN_TURBIDEZ  = 32;
static const uint8_t PIN_ONEWIRE   = 4;

/** 1.5 con el divisor 10k/20k de la guia; 1.0 si el sensor entra directo. */
static const float DIV_PH       = 1.5f;
static const float DIV_OXIGENO  = 1.0f;
static const float DIV_TURBIDEZ = 1.5f;

static const uint8_t MUESTRAS = 31;   // impar: la mediana cae en una muestra real

static OneWire oneWire(PIN_ONEWIRE);
static DallasTemperature ds18(&oneWire);

/**
 * @brief Mediana de MUESTRAS lecturas del ADC, en milivoltios del pin.
 * @param gpio Pin del ADC1 (32-39).
 * @return Milivoltios medidos en el pin, sin corregir el divisor.
 */
static float medianaMilivoltios(uint8_t gpio) {
  uint16_t m[MUESTRAS];
  for (uint8_t i = 0; i < MUESTRAS; i++) {
    m[i] = (uint16_t)analogReadMilliVolts(gpio);
    delay(2);
  }
  for (uint8_t i = 1; i < MUESTRAS; i++) {
    const uint16_t v = m[i];
    int8_t j = i - 1;
    while (j >= 0 && m[j] > v) { m[j + 1] = m[j]; j--; }
    m[j + 1] = v;
  }
  return m[MUESTRAS / 2];
}

/**
 * @brief Imprime una fila con el voltaje del pin y el voltaje real del sensor.
 * @param nombre  Etiqueta del sensor.
 * @param gpio    Pin del ADC1.
 * @param divisor Factor del divisor resistivo.
 */
static void reportarAnalogico(const char* nombre, uint8_t gpio, float divisor) {
  const float mV_pin = medianaMilivoltios(gpio);
  const float V_real = (mV_pin * divisor) / 1000.0f;

  Serial.printf("  %-10s GPIO%-2u  pin: %7.1f mV   sensor: %5.3f V",
                nombre, gpio, mV_pin, V_real);

  if (mV_pin > 3200.0f) {
    Serial.print("   <-- PELIGRO: cerca del limite de 3,3 V, revisa el divisor");
  }
  Serial.println();
}

void setup() {
  Serial.begin(115200);
  delay(1000);

  ds18.begin();
  ds18.setResolution(12);

  Serial.println();
  Serial.println("=========================================");
  Serial.println(" BioAqua - Banco de calibracion");
  Serial.println("=========================================");
  Serial.printf("Sensores DS18B20 en el bus: %d\n", ds18.getDeviceCount());
  Serial.println("Anota los valores cuando dejen de moverse.");
  Serial.println();
}

void loop() {
  ds18.requestTemperatures();
  const float tempC = ds18.getTempCByIndex(0);

  Serial.println("-----------------------------------------");
  if (tempC == DEVICE_DISCONNECTED_C) {
    Serial.println("  Temperatura  GPIO4   SIN LECTURA: revisa el pull-up de 4,7 kOhm");
  } else {
    Serial.printf("  Temperatura  GPIO4   %.2f C\n", tempC);
  }

  reportarAnalogico("pH",        PIN_PH,       DIV_PH);
  reportarAnalogico("Oxigeno",   PIN_OXIGENO,  DIV_OXIGENO);
  reportarAnalogico("Turbidez",  PIN_TURBIDEZ, DIV_TURBIDEZ);
  delay(1000);
}
