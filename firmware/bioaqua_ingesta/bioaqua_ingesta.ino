/**
 * @file    bioaqua_ingesta.ino
 * @brief   Nodo de ingesta ESP32 -> API Django BioAqua, con MODO OFFLINE (RF019).
 * @target  ESP32-D0WD-V3 (WROOM-32), Arduino core 3.x
 *
 * QUE HACE
 *   1. Se asocia al WiFi 2.4 GHz y sincroniza la hora por NTP.
 *   2. Cada INTERVALO_S: lee cada sensor ACTIVO, lo convierte a su unidad real,
 *      marca cada lectura con su timestamp y arma un lote JSON.
 *   3. Intenta enviarlo por POST a /api/v1/lecturas/ con "Authorization: Device".
 *   4. MODO OFFLINE (RF019): si el envio falla (sin red / servidor caido), el
 *      lote se GUARDA en LittleFS (/cola.jsonl) y se REENVIA cuando vuelve la
 *      conexion. El backend deduplica por (sensor, timestamp), asi que un
 *      reenvio nunca crea lecturas repetidas.
 *
 * "SOLO CONECTAR EL DIA DE CAMPO"
 *   - Sensores en la TABLA SENSORES[]: agregar/activar uno es una linea.
 *   - `codigo_hardware` DEBE coincidir EXACTO con la tabla `sensores` de la BD.
 *
 * LIBRERIAS: ArduinoJson 7.x. (OneWire + DallasTemperature solo si usas DS18B20).
 * PARTICION: elige en Arduino IDE una particion con SPIFFS/LittleFS
 *   (Tools -> Partition Scheme -> "Default 4MB with spiffs").
 *
 * REGLA ELECTRICA: analogicos SOLO en ADC1 (GPIO32-39); nada > 3.3 V al pin;
 * GND comun. (ADC2 no funciona con WiFi encendido.)
 */

#include <WiFi.h>
#include <HTTPClient.h>
#include <ArduinoJson.h>
#include <LittleFS.h>
#include <time.h>
#include "secrets.h"

// Descomenta si cableas el DS18B20:
// #include <OneWire.h>
// #include <DallasTemperature.h>

// ---------------------------------------------------------------------------
static const char* FIRMWARE_VERSION = "1.1.0-offline";
static const uint32_t INTERVALO_S   = 300;      // 5 min entre lotes
static const uint32_t TIMEOUT_WIFI_MS = 20000;
static const uint32_t TIMEOUT_HTTP_MS = 10000;
static const uint8_t  MUESTRAS_ADC  = 64;
static const uint8_t  PIN_LED_ESTADO = 2;
static const char*    COLA_PATH = "/cola.jsonl";
static const size_t   COLA_MAX_LINEAS = 500;    // tope de lotes encolados

// NTP (America/Bogota, sin horario de verano)
static const char* NTP1 = "pool.ntp.org";
static const char* NTP2 = "time.google.com";
static const char* TZ_CO = "<-05>5";

// ---------------------------------------------------------------------------
// Registro de sensores  <-- aqui se agrega/activa cada sensor
// ---------------------------------------------------------------------------
enum TipoSensor { ANALOGICO_LINEAL, TEMP_DS18B20 };

struct SensorCfg {
  const char* codigo_hardware;  // EXACTO como en la BD
  TipoSensor  tipo;
  uint8_t     gpio;             // analogico: pin ADC1
  float       m;                // unidad = m*voltaje + b
  float       b;
  bool        activo;
};

static const float PH_M = -5.70f, PH_B = 18.62f;   // reemplaza con tu calibracion
static const float OX_M =  3.00f, OX_B =  0.00f;

static SensorCfg SENSORES[] = {
  { "SEN-PH",   ANALOGICO_LINEAL, 34, PH_M, PH_B, true  },
  { "SEN-OX",   ANALOGICO_LINEAL, 35, OX_M, OX_B, true  },
  { "SEN-TEMP", TEMP_DS18B20,      4, 0.0f, 0.0f, false },
};
static const size_t N_SENSORES = sizeof(SENSORES) / sizeof(SENSORES[0]);
// OneWire oneWire(4); DallasTemperature ds18(&oneWire);

static uint32_t contadorSecuencia = 0;
static bool     horaLista = false;

// ---------------------------------------------------------------------------
// WiFi + NTP
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
      Serial.printf("\n[WIFI] Sin conexion (status=%d). Se trabajara offline.\n", WiFi.status());
      return false;
    }
    delay(250); Serial.print('.');
  }
  Serial.printf("\n[WIFI] OK. IP=%s RSSI=%d dBm\n",
                WiFi.localIP().toString().c_str(), WiFi.RSSI());
  return true;
}

static void sincronizarHora() {
  configTzTime(TZ_CO, NTP1, NTP2);
  const uint32_t inicio = millis();
  time_t ahora = 0;
  while ((ahora = time(nullptr)) < 1700000000 && millis() - inicio < 8000) {
    delay(250);
  }
  horaLista = (ahora >= 1700000000);
  Serial.println(horaLista ? "[NTP] Hora sincronizada." :
                             "[NTP] Sin hora fiable; las lecturas iran sin timestamp.");
}

/** ISO 8601 local con offset fijo de Colombia, o "" si no hay hora fiable. */
static String timestampISO() {
  if (!horaLista) return String("");
  time_t ahora = time(nullptr);
  if (ahora < 1700000000) return String("");
  struct tm tl;
  localtime_r(&ahora, &tl);
  char buf[32];
  strftime(buf, sizeof(buf), "%Y-%m-%dT%H:%M:%S-05:00", &tl);
  return String(buf);
}

// ---------------------------------------------------------------------------
// Lectura de sensores
// ---------------------------------------------------------------------------
static float leerVoltaje(uint8_t gpio) {
  uint32_t suma_mV = 0;
  for (uint8_t i = 0; i < MUESTRAS_ADC; i++) { suma_mV += analogReadMilliVolts(gpio); delay(2); }
  return (suma_mV / (float)MUESTRAS_ADC) / 1000.0f;
}

static float leerSensor(const SensorCfg& s) {
  switch (s.tipo) {
    case ANALOGICO_LINEAL: return s.m * leerVoltaje(s.gpio) + s.b;
    case TEMP_DS18B20:
      // ds18.requestTemperatures(); float t = ds18.getTempCByIndex(0);
      // return (t == DEVICE_DISCONNECTED_C) ? NAN : t;
      return NAN;
  }
  return NAN;
}

/** Arma el cuerpo JSON del lote actual. Devuelve "" si no hubo lecturas. */
static String construirCuerpo() {
  JsonDocument doc;
  doc["firmware"] = FIRMWARE_VERSION;
  doc["mac"] = WiFi.macAddress();
  JsonArray arr = doc["lecturas"].to<JsonArray>();
  const String ts = timestampISO();

  uint8_t incluidas = 0;
  for (size_t i = 0; i < N_SENSORES; i++) {
    const SensorCfg& s = SENSORES[i];
    if (!s.activo) continue;
    float valor = leerSensor(s);
    if (isnan(valor)) { Serial.printf("[ADC] %s sin lectura, se omite.\n", s.codigo_hardware); continue; }
    JsonObject l = arr.add<JsonObject>();
    l["codigo_hardware"] = s.codigo_hardware;
    l["valor"] = roundf(valor * 100.0f) / 100.0f;
    l["secuencia"] = ++contadorSecuencia;
    if (ts.length()) l["timestamp"] = ts;   // clave para el dedup offline
    incluidas++;
  }
  if (incluidas == 0) return String("");
  String out; serializeJson(doc, out); return out;
}

// ---------------------------------------------------------------------------
// Envio + cola offline (RF019)
// ---------------------------------------------------------------------------
static bool enviarCuerpo(const String& cuerpo) {
  if (WiFi.status() != WL_CONNECTED) return false;
  char url[96];
  snprintf(url, sizeof(url), "http://%s:%d/api/v1/lecturas/", SERVER_HOST, SERVER_PORT);
  char auth[80];
  snprintf(auth, sizeof(auth), "Device %s", DEVICE_TOKEN);

  HTTPClient http;
  http.setConnectTimeout(TIMEOUT_HTTP_MS);
  http.setTimeout(TIMEOUT_HTTP_MS);
  if (!http.begin(url)) return false;
  http.addHeader("Content-Type", "application/json");
  http.addHeader("Authorization", auth);
  int codigo = http.POST((uint8_t*)cuerpo.c_str(), cuerpo.length());
  bool ok = (codigo >= 200 && codigo < 300);
  Serial.printf("[HTTP] %d %s\n", codigo, ok ? "OK" : http.errorToString(codigo).c_str());
  http.end();
  return ok;
}

static void guardarEnCola(const String& cuerpo) {
  File f = LittleFS.open(COLA_PATH, "a");
  if (!f) { Serial.println("[COLA] No se pudo abrir la cola."); return; }
  f.print(cuerpo); f.print("\n"); f.close();
  Serial.println("[COLA] Lote guardado offline; se reenviara al reconectar.");
}

/** Reenvia lo encolado; conserva solo lo que aun falle. */
static void vaciarCola() {
  if (!LittleFS.exists(COLA_PATH) || WiFi.status() != WL_CONNECTED) return;
  File f = LittleFS.open(COLA_PATH, "r");
  if (!f) return;
  String pendientes = "";
  int enviados = 0, fallidos = 0;
  while (f.available()) {
    String linea = f.readStringUntil('\n');
    linea.trim();
    if (linea.length() == 0) continue;
    if (enviarCuerpo(linea)) enviados++;
    else { pendientes += linea + "\n"; fallidos++; if (fallidos == 1) break; }  // corta si vuelve a caer
  }
  // arrastra lo no leido aun si cortamos
  while (f.available()) { String l = f.readStringUntil('\n'); l.trim(); if (l.length()) pendientes += l + "\n"; }
  f.close();
  if (pendientes.length() == 0) LittleFS.remove(COLA_PATH);
  else { File w = LittleFS.open(COLA_PATH, "w"); if (w) { w.print(pendientes); w.close(); } }
  if (enviados) Serial.printf("[COLA] Reenviados %d lote(s).\n", enviados);
}

// ---------------------------------------------------------------------------
void setup() {
  Serial.begin(115200); delay(300);
  pinMode(PIN_LED_ESTADO, OUTPUT);
  analogReadResolution(12);
  analogSetAttenuation(ADC_11db);
  if (!LittleFS.begin(true)) Serial.println("[FS] LittleFS no monto; el modo offline no guardara.");
  // ds18.begin();
  Serial.printf("\n=== BioAqua nodo v%s (con modo offline) ===\n", FIRMWARE_VERSION);
  if (conectarWiFi()) sincronizarHora();
}

void loop() {
  static uint32_t ultimo = 0;
  const uint32_t ahora = millis();
  if (ultimo == 0 || (ahora - ultimo) >= INTERVALO_S * 1000UL) {
    digitalWrite(PIN_LED_ESTADO, HIGH);

    if (!horaLista && conectarWiFi()) sincronizarHora();  // reintenta NTP si hizo falta

    String cuerpo = construirCuerpo();
    if (cuerpo.length() == 0) {
      Serial.println("[CICLO] Sin lecturas este ciclo.");
    } else if (conectarWiFi() && enviarCuerpo(cuerpo)) {
      vaciarCola();                 // en linea: manda lo de ahora y vacia lo pendiente
    } else {
      guardarEnCola(cuerpo);        // offline: a la cola
    }

    digitalWrite(PIN_LED_ESTADO, LOW);
    ultimo = ahora;
  }
  delay(200);
}
