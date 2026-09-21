/**
 * @file    bioaqua_ingesta.ino
 * @brief   Nodo de ingesta real ESP32 -> API Django BioAqua System.
 * @target  ESP32-D0WD-V3 (WROOM-32), Arduino core 3.x
 *
 * QUE HACE
 *   1. Se asocia al WiFi 2.4 GHz.
 *   2. (Opcional al arrancar) hace handshake para validar token y ver que
 *      sensores espera el servidor para su piscina.
 *   3. Cada INTERVALO_S: lee cada sensor ACTIVO, lo convierte a su unidad real
 *      con su calibracion, arma un lote JSON y lo envia por HTTP POST a
 *      /api/v1/lecturas/ con la cabecera "Authorization: Device <token>".
 *
 * DISENO PARA "SOLO CONECTAR EL DIA DE LA IMPLEMENTACION"
 *   - Los sensores viven en una TABLA (SENSORES[]). Agregar uno = una linea.
 *   - `codigo_hardware` DEBE COINCIDIR EXACTO con el de la tabla `sensores` de
 *     la BD (columna codigo_hardware). Si no coincide, el servidor rechaza esa
 *     lectura con "No existe un sensor registrado con codigo ...".
 *   - No se envia timestamp: el servidor pone la hora (evita lios de zona
 *     horaria). El ESP32 solo mide.
 *
 * LIBRERIAS (Arduino IDE -> Gestor de librerias):
 *   - ArduinoJson  (v7.x)          por Benoit Blanchon
 *   - OneWire                       por Paul Stoffregen   (solo si usas DS18B20)
 *   - DallasTemperature             por Miles Burton      (solo si usas DS18B20)
 *
 * REGLA ELECTRICA CRITICA
 *   - Sensores analogicos SOLO en pines de ADC1 (GPIO32-39). ADC2 comparte
 *     hardware con el WiFi y devuelve basura con la radio encendida.
 *   - Ninguna senal analogica puede superar 3.3 V en el pin (mide con
 *     multimetro antes de conectar). GND comun obligatorio.
 */

#include <WiFi.h>
#include <HTTPClient.h>
#include <ArduinoJson.h>
#include "secrets.h"

// Descomenta estas dos lineas cuando cablees el DS18B20 de temperatura:
// #include <OneWire.h>
// #include <DallasTemperature.h>

// ---------------------------------------------------------------------------
// Configuracion general
// ---------------------------------------------------------------------------

static const char* FIRMWARE_VERSION = "1.0.0-ingesta";

/** Segundos entre lotes de lecturas. Debe ser >= al intervalo_lectura de la BD. */
static const uint32_t INTERVALO_S = 300;         // 5 min

static const uint32_t TIMEOUT_WIFI_MS = 20000;
static const uint32_t TIMEOUT_HTTP_MS = 10000;

/** Muestras por lectura analogica: se promedian para ahogar el ruido de 60 Hz. */
static const uint8_t  MUESTRAS_ADC = 64;

static const uint8_t  PIN_LED_ESTADO = 2;        // LED integrado. No conectar nada.

// ---------------------------------------------------------------------------
// Registro de sensores  <-- AQUI se agrega/activa cada sensor el dia de campo
// ---------------------------------------------------------------------------

/** Como se convierte el voltaje leido a la unidad real del parametro. */
enum TipoSensor {
  ANALOGICO_LINEAL,   // unidad = M * voltaje + B  (pH, oxigeno con placa)
  TEMP_DS18B20,       // sonda digital OneWire
};

struct SensorCfg {
  const char* codigo_hardware;  // EXACTO como en la BD (tabla sensores)
  TipoSensor  tipo;
  uint8_t     gpio;             // analogico: pin ADC1 (34/35/32/33/36/39)
  float       m;                // pendiente (solo ANALOGICO_LINEAL)
  float       b;                // intercepto (solo ANALOGICO_LINEAL)
  bool        activo;           // false = cableado aun no hecho, no se envia
};

/**
 * Calibracion de dos puntos por sensor (se obtiene con buffers patron):
 *   pH:  sumerge en pH 7 y pH 4, anota el voltaje, calcula M y B de la recta.
 *   O2:  aire saturado (~7-8 mg/L) y solucion cero.
 * Los valores de abajo son PLACEHOLDERS: reemplazalos con tu calibracion real.
 */
static const float PH_M = -5.70f,  PH_B = 18.62f;   // pH  = M*V + B
static const float OX_M =  3.00f,  OX_B =  0.00f;   // mg/L = M*V + B

static SensorCfg SENSORES[] = {
  //  codigo_hardware   tipo               gpio   M      B     activo
  { "SEN-PH",   ANALOGICO_LINEAL,  34,   PH_M,  PH_B,  true  },
  { "SEN-OX",   ANALOGICO_LINEAL,  35,   OX_M,  OX_B,  true  },
  { "SEN-TEMP", TEMP_DS18B20,       4,   0.0f,  0.0f,  false },  // activar al cablear
};
static const size_t N_SENSORES = sizeof(SENSORES) / sizeof(SENSORES[0]);

// DS18B20 (se inicializa solo si hay alguno TEMP_DS18B20 activo)
// OneWire oneWire(4);
// DallasTemperature ds18(&oneWire);

static uint32_t contadorSecuencia = 0;

// ---------------------------------------------------------------------------
// WiFi
// ---------------------------------------------------------------------------

static bool conectarWiFi() {
  if (WiFi.status() == WL_CONNECTED) return true;

  Serial.printf("[WIFI] Asociando a \"%s\" ...\n", WIFI_SSID);
  WiFi.mode(WIFI_STA);
  WiFi.setSleep(false);
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);

  const uint32_t inicio = millis();
  while (WiFi.status() != WL_CONNECTED) {
    if (millis() - inicio > TIMEOUT_WIFI_MS) {
      Serial.printf("[WIFI] ERROR: timeout. status=%d (revisa: red 2.4 GHz, clave, alcance)\n",
                    WiFi.status());
      WiFi.disconnect(true);
      return false;
    }
    delay(250);
    Serial.print('.');
  }
  Serial.printf("\n[WIFI] OK. IP=%s  MAC=%s  RSSI=%d dBm\n",
                WiFi.localIP().toString().c_str(),
                WiFi.macAddress().c_str(), WiFi.RSSI());
  return true;
}

// ---------------------------------------------------------------------------
// Lectura de sensores
// ---------------------------------------------------------------------------

/**
 * @brief Lee un pin analogico (ADC1) y devuelve el voltaje en VOLTIOS.
 * Usa analogReadMilliVolts(), que en el core 3.x aplica la calibracion de
 * fabrica del ADC (corrige no linealidad y Vref) -> mucho mas exacto que la
 * regla de tres cruda 0..4095.
 */
static float leerVoltaje(uint8_t gpio) {
  uint32_t suma_mV = 0;
  for (uint8_t i = 0; i < MUESTRAS_ADC; i++) {
    suma_mV += analogReadMilliVolts(gpio);
    delay(2);
  }
  return (suma_mV / (float)MUESTRAS_ADC) / 1000.0f;   // mV -> V
}

/**
 * @brief Obtiene el valor en unidad real de un sensor, o NAN si no se pudo leer.
 */
static float leerSensor(const SensorCfg& s) {
  switch (s.tipo) {
    case ANALOGICO_LINEAL: {
      float v = leerVoltaje(s.gpio);
      return s.m * v + s.b;
    }
    case TEMP_DS18B20: {
      // ds18.requestTemperatures();
      // float t = ds18.getTempCByIndex(0);
      // return (t == DEVICE_DISCONNECTED_C) ? NAN : t;
      return NAN;   // recuerda descomentar las librerias y el sensor arriba
    }
  }
  return NAN;
}

// ---------------------------------------------------------------------------
// Envio del lote a la API
// ---------------------------------------------------------------------------

/**
 * @brief Lee todos los sensores activos, arma el lote JSON y lo hace POST.
 * @return true si el servidor respondio 2xx.
 */
static bool enviarLote() {
  if (!conectarWiFi()) return false;

  JsonDocument doc;
  doc["firmware"] = FIRMWARE_VERSION;
  doc["mac"]      = WiFi.macAddress();
  JsonArray lecturas = doc["lecturas"].to<JsonArray>();

  uint8_t incluidas = 0;
  for (size_t i = 0; i < N_SENSORES; i++) {
    const SensorCfg& s = SENSORES[i];
    if (!s.activo) continue;

    float valor = leerSensor(s);
    if (isnan(valor)) {
      Serial.printf("[ADC] %s sin lectura valida, se omite este ciclo.\n", s.codigo_hardware);
      continue;   // un sensor mudo no rompe el lote; el servidor abrira la alerta RF001
    }

    JsonObject l = lecturas.add<JsonObject>();
    l["codigo_hardware"] = s.codigo_hardware;
    l["valor"]           = roundf(valor * 100.0f) / 100.0f;  // 2 decimales
    l["secuencia"]       = ++contadorSecuencia;
    incluidas++;
  }

  if (incluidas == 0) {
    Serial.println("[ENVIO] Ningun sensor produjo lectura; nada que enviar.");
    return false;
  }

  char url[96];
  snprintf(url, sizeof(url), "http://%s:%d/api/v1/lecturas/", SERVER_HOST, SERVER_PORT);
  char auth[80];
  snprintf(auth, sizeof(auth), "Device %s", DEVICE_TOKEN);

  String cuerpo;
  serializeJson(doc, cuerpo);

  HTTPClient http;
  http.setConnectTimeout(TIMEOUT_HTTP_MS);
  http.setTimeout(TIMEOUT_HTTP_MS);
  if (!http.begin(url)) {
    Serial.println("[HTTP] No se pudo iniciar la conexion.");
    return false;
  }
  http.addHeader("Content-Type", "application/json");
  http.addHeader("Authorization", auth);

  Serial.printf("[HTTP] POST %s  cuerpo=%s\n", url, cuerpo.c_str());
  int codigo = http.POST(cuerpo);

  bool ok = (codigo >= 200 && codigo < 300);
  if (codigo > 0) {
    Serial.printf("[HTTP] %d -> %s\n", codigo, http.getString().c_str());
  } else {
    Serial.printf("[HTTP] Error de transporte: %s\n", http.errorToString(codigo).c_str());
  }
  http.end();

  // --- RF019 (futuro): si !ok, guardar 'cuerpo' en LittleFS y reintentar luego ---
  return ok;
}

// ---------------------------------------------------------------------------
// setup / loop
// ---------------------------------------------------------------------------

void setup() {
  Serial.begin(115200);
  delay(300);
  pinMode(PIN_LED_ESTADO, OUTPUT);

  // ADC: 12 bits (0..4095) y atenuacion para medir hasta ~3.3 V.
  analogReadResolution(12);
  analogSetAttenuation(ADC_11db);

  // Si activas DS18B20: descomenta el include, el objeto ds18 y esto:
  // ds18.begin();

  Serial.printf("\n=== BioAqua nodo de ingesta v%s ===\n", FIRMWARE_VERSION);
  conectarWiFi();
  Serial.printf("Enviando lotes cada %lu s a %s:%d\n",
                (unsigned long)INTERVALO_S, SERVER_HOST, SERVER_PORT);
}

void loop() {
  static uint32_t ultimoEnvio = 0;
  const uint32_t ahora = millis();

  // Primer envio inmediato, luego cada INTERVALO_S.
  if (ultimoEnvio == 0 || (ahora - ultimoEnvio) >= INTERVALO_S * 1000UL) {
    digitalWrite(PIN_LED_ESTADO, HIGH);
    bool ok = enviarLote();
    digitalWrite(PIN_LED_ESTADO, LOW);
    ultimoEnvio = ahora;
    Serial.println(ok ? "[CICLO] OK\n" : "[CICLO] Falló, se reintenta al próximo intervalo\n");
  }

  delay(200);   // el ESP32 respira; el temporizador real es INTERVALO_S
}
