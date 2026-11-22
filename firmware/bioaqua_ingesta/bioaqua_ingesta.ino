/**
 * @file    bioaqua_ingesta.ino
 * @brief   Nodo de ingesta ESP32 -> API Django BioAqua, con MODO OFFLINE (RF019).
 * @target  ESP32-D0WD-V3 (WROOM-32), Arduino core 3.x
 *
 * QUE HACE
 *   1. Se asocia al WiFi 2.4 GHz y sincroniza la hora por NTP.
 *   2. Cada intervaloS (30 s, ajustable desde el software): lee cada sensor ACTIVO, lo convierte a su unidad real,
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
 * SENSORES CABLEADOS (ver docs/HARDWARE_SENSORES.md para el cableado):
 *   GPIO32 DS18B20 temperatura   pull-up 4,7 kOhm a 3V3, sin divisor
 *   GPIO34 pH PH-4502C           divisor 10k/20k obligatorio (sale hasta 5 V)
 *   GPIO35 turbidez TS-300B      divisor 10k/10k obligatorio (sale hasta 4,5 V)
 *
 * CALIBRACION DESDE EL MONITOR SERIE (115200, "Both NL & CR"), sin reprogramar:
 *   AYUDA            lista de comandos
 *   VER              voltajes crudos y calibracion vigente
 *   CAL TUR          sonda de turbidez en agua LIMPIA: fija el punto 0 NTU
 *   CAL PH 6.86      sonda de pH en buffer 6.86 (luego CAL PH 4.01)
 *   RESET CAL        vuelve a la calibracion de fabrica
 *   PANTALLA         reinicia la pantalla TFT y redibuja el tablero
 *   La calibracion queda en la memoria NVS del ESP32 y sobrevive a reinicios.
 *
 * CAMARA OV7670 (camara.h, RF027): foto QQVGA en JPEG a POST /api/v1/capturas/
 *   cada 5 min y, ademas, cuando el software marca una lectura critica.
 *   Pines y cableado en camara.h. Si la camara falla, el nodo sigue midiendo.
 *   Comando FOTO en el monitor serie: envia una foto en el momento.
 *
 * PANTALLA TFT 3.5" (pantalla_tft.h): animacion de encendido y tablero en
 *   vivo con las mismas lecturas que se envian. Corre en el hilo principal:
 *   pantallaEsperar() reemplaza a los delay(), asi la pantalla anima mientras
 *   el nodo espera, sin retrasar el envio al software.
 *
 * LIBRERIAS: ArduinoJson 7.x, OneWire, DallasTemperature, TFT_eSPI (con el
 *   User_Setup.h de firmware/pantalla_imagen copiado en la libreria).
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
#include <Preferences.h>
#include "secrets.h"  

#include <OneWire.h>
#include <DallasTemperature.h>
#include "pantalla_tft.h"
#include "camara.h"

// ---------------------------------------------------------------------------
static const char* FIRMWARE_VERSION = "1.6.0-camara";     // max 20 caracteres (columna firmware_version)
// Intervalo entre lotes. Arranca en 30 s y lo ajusta el SOFTWARE en cada
// respuesta (campo data.intervalo_segundos, RF011): sin reprogramar el ESP32.
static const uint32_t INTERVALO_INICIAL_S = 7;   // el software lo ajusta en la 1.a respuesta
static const uint32_t INTERVALO_MIN_S     = 2;   // modo pruebas
static const uint32_t INTERVALO_MAX_S     = 3600;
static uint32_t intervaloS = INTERVALO_INICIAL_S;
static const uint32_t TIMEOUT_WIFI_MS = 20000;
static const uint32_t TIMEOUT_HTTP_MS = 10000;
static const uint8_t  MUESTRAS_ADC  = 31;      // impar: la mediana cae en una muestra real
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
enum TipoSensor {
  PH_LINEAL,        // recta pH = m*V + b, calibrada con buffers 4,01 y 6,86
  TURBIDEZ_NTU,     // TS-300B: curva del fabricante, voltaje alto = agua limpia
  TEMP_DS18B20      // sonda digital OneWire
};

/**
 * Configuracion de un sensor cableado al nodo.
 *
 * factor_divisor: cuanto hay que multiplicar el voltaje leido en el pin para
 * recuperar el voltaje real del sensor: (R1 + R2) / R2.
 *   10k/20k -> 1.5   |   10k/10k -> 2.0   |   sin divisor -> 1.0
 */
struct SensorCfg {
  const char* codigo_hardware;  // EXACTO como en la tabla `sensores` de la BD
  TipoSensor  tipo;
  uint8_t     gpio;             // analogicos: solo ADC1 (32-39)
  float       factor_divisor;
  bool        activo;
};

// --- Calibracion del pH -----------------------------------------------------
// Se obtiene con dos buffers. Ver docs/HARDWARE_SENSORES.md, seccion 8.
//   pendiente  = (pH1 - pH2) / (V1 - V2)
//   intercepto = pH1 - pendiente * V1
static const float PH_M_FABRICA = -5.70f;   // valores por defecto (sketch de prueba)
static const float PH_B_FABRICA = 21.34f;
static float phM = PH_M_FABRICA;             // vigentes: se cargan de NVS en setup()
static float phB = PH_B_FABRICA;

// --- Curva de turbidez TS-300B ---------------------------------------------
// Relacion inversa: agua limpia ~4,2 V, agua turbia < 2,5 V (curva DFRobot,
// valida de 2,5 a 4,2 V). Cada modulo y cada divisor dan un voltaje distinto
// en agua limpia, asi que la lectura se ESCALA con el voltaje medido en agua
// limpia (CAL TUR): V_corregido = V * 4,2 / turbVLimpia. Al ser un cociente,
// tambien cancela el error del factor del divisor.
static const float TURB_V_CURVA_LIMPIA = 4.20f;
static const float TURB_V_CURVA_SUCIA  = 2.50f;
static const float TURB_NTU_MAX        = 3000.0f;
static float turbVLimpia = TURB_V_CURVA_LIMPIA;  // se carga de NVS en setup()

// Voltaje maximo util del ADC del ESP32 con atenuacion 11 dB. Por encima, la
// lectura satura: agua limpia y agua sucia darian lo mismo.
static const uint16_t ADC_SATURACION_MV = 3050;
static uint16_t ultimoMvPin = 0;                 // diagnostico del monitor serie

static Preferences prefs;                        // NVS "sigmap"

static SensorCfg SENSORES[] = {
  //  codigo         tipo           gpio  divisor  activo
  { "SEN-001-TEM", TEMP_DS18B20,    32,   1.0f,   true  },
  { "SEN-001-PH",  PH_LINEAL,       34,   1.5f,   true },
  { "SEN-001-TUR", TURBIDEZ_NTU,    35,   2.0f,   true  },  // divisor 10k/10k
};
static const size_t N_SENSORES = sizeof(SENSORES) / sizeof(SENSORES[0]);

static const uint8_t PIN_ONEWIRE = 32;   // DS18B20 (debe coincidir con SEN-001-TEM)
static OneWire oneWire(PIN_ONEWIRE);
static DallasTemperature ds18(&oneWire);

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
    pantallaEsperar(250); Serial.print('.');   // la pantalla sigue animando
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
    pantallaEsperar(250);
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
/**
 * @brief Voltaje real del sensor, con mediana de MUESTRAS_ADC muestras.
 *
 * Se usa mediana y no promedio: un pico de ruido de la bomba desplaza el
 * promedio, pero no la mediana. analogReadMilliVolts aplica la curva de
 * calibracion de fabrica del ADC, que es bastante mas exacta que analogRead.
 *
 * @param gpio           Pin del ADC1.
 * @param factorDivisor  1.5 con el divisor 10k/20k; 1.0 sin divisor.
 * @return Voltaje del sensor en voltios.
 */
static float leerVoltaje(uint8_t gpio, float factorDivisor) {
  uint16_t muestras[MUESTRAS_ADC];
  for (uint8_t i = 0; i < MUESTRAS_ADC; i++) {
    muestras[i] = (uint16_t)analogReadMilliVolts(gpio);
    delay(2);
  }
  // Insercion: con 31 elementos es mas rapido que cualquier algoritmo elegante.
  for (uint8_t i = 1; i < MUESTRAS_ADC; i++) {
    const uint16_t v = muestras[i];
    int8_t j = i - 1;
    while (j >= 0 && muestras[j] > v) { muestras[j + 1] = muestras[j]; j--; }
    muestras[j + 1] = v;
  }
  const float mV_pin = muestras[MUESTRAS_ADC / 2];
  ultimoMvPin = (uint16_t)mV_pin;
  return (mV_pin * factorDivisor) / 1000.0f;
}

/**
 * @brief Convierte el voltaje del TS-300B a NTU con la curva del fabricante.
 *
 * El voltaje se normaliza con el de agua limpia calibrado (CAL TUR), de modo
 * que ese punto vale 0 NTU. Por encima se reporta 0 NTU; por debajo de 2,5 V
 * normalizados, 3000 NTU (limite de la curva).
 *
 * @param voltios Voltaje real del sensor (ya sin el divisor).
 * @return Turbidez en NTU.
 */
static float turbidezNTU(float voltios) {
  if (turbVLimpia <= 0.1f) return NAN;
  const float v = voltios * (TURB_V_CURVA_LIMPIA / turbVLimpia);   // normalizado a la curva
  if (v >= TURB_V_CURVA_LIMPIA) return 0.0f;
  if (v <= TURB_V_CURVA_SUCIA)  return TURB_NTU_MAX;
  const float ntu = -1120.4f * v * v + 5742.3f * v - 4353.8f;
  return constrain(ntu, 0.0f, TURB_NTU_MAX);
}

/**
 * @brief Lee un sensor y devuelve su magnitud en la unidad de la base de datos.
 * @param s Configuracion del sensor.
 * @return Valor medido, o NAN si el sensor no respondio.
 */
static float leerSensor(const SensorCfg& s) {
  switch (s.tipo) {
    case TEMP_DS18B20: {
      // Sin bloqueo: lee la conversion pedida en el ciclo anterior y pide la
      // siguiente. Antes se esperaban ~375 ms y la pantalla se congelaba.
      const float t = ds18.getTempCByIndex(0);
      ds18.requestTemperatures();
      if (t == DEVICE_DISCONNECTED_C || t < -50.0f || t > 80.0f) return NAN;
      return t;
    }
    case PH_LINEAL:
      return constrain(phM * leerVoltaje(s.gpio, s.factor_divisor) + phB, 0.0f, 14.0f);
    case TURBIDEZ_NTU:
      return turbidezNTU(leerVoltaje(s.gpio, s.factor_divisor));
  }
  return NAN;
}

/** Nombre y unidad legibles de cada tipo de sensor, para el monitor serie. */
static void etiquetaSensor(TipoSensor tipo, const char*& nombre, const char*& unidad) {
  switch (tipo) {
    case TEMP_DS18B20: nombre = "Temperatura"; unidad = "°C";   break;
    case PH_LINEAL:    nombre = "pH";          unidad = "pH";   break;
    case TURBIDEZ_NTU: nombre = "Turbidez";    unidad = "NTU";  break;
    default:           nombre = "Sensor";      unidad = "";     break;
  }
}

/** Valor tal como se envia al software: redondeado a 2 decimales. */
static float valorEnviado(float valor) { return roundf(valor * 100.0f) / 100.0f; }

/** Tarjeta de la pantalla que corresponde a cada tipo de sensor. */
static bool canalPantalla(TipoSensor tipo, CanalPantalla& canal) {
  switch (tipo) {
    case TEMP_DS18B20: canal = PANT_TEMP; return true;
    case PH_LINEAL:    canal = PANT_PH;   return true;
    case TURBIDEZ_NTU: canal = PANT_TURB; return true;
    default:           return false;
  }
}

/** Pasa a la pantalla el MISMO valor que viaja en el JSON (2 decimales). */
static void mostrarEnPantalla(TipoSensor tipo, float valor) {
  CanalPantalla canal;
  if (canalPantalla(tipo, canal)) pantallaValor(canal, valorEnviado(valor));
}

static bool reenviandoCola = false;   // true mientras se reenvian lotes viejos

/** Pasa a la pantalla el estado que el software le dio a cada lectura. */
static void estadosDelServidor(JsonArray lecturas) {
  if (reenviandoCola) return;          // un lote viejo no debe pisar el estado actual
  for (JsonObject l : lecturas) {
    const char* codigo = l["sensor"] | "";
    for (size_t i = 0; i < N_SENSORES; i++) {
      CanalPantalla canal;
      if (strcmp(SENSORES[i].codigo_hardware, codigo) == 0 && canalPantalla(SENSORES[i].tipo, canal)) {
        pantallaEstadoServidor(canal, l["estado_lectura"] | "");
      }
    }
  }
}

/** Arma el cuerpo JSON del lote actual. Devuelve "" si no hubo lecturas. */
static String construirCuerpo() {
  JsonDocument doc;
  doc["firmware"] = FIRMWARE_VERSION;
  doc["mac"] = WiFi.macAddress();
  JsonArray arr = doc["lecturas"].to<JsonArray>();
  const String ts = timestampISO();

  uint8_t incluidas = 0;
  pantallaInicioLote();
  Serial.println("\n------------------------------------------------------------");
  Serial.printf(" Lote %s\n", ts.length() ? ts.c_str() : "(sin hora NTP)");
  Serial.println(" SENSOR       |     VALOR      | mV pin | CODIGO");
  Serial.println("--------------+----------------+--------+-----------------");
  for (size_t i = 0; i < N_SENSORES; i++) {
    const SensorCfg& s = SENSORES[i];
    if (!s.activo) continue;
    float valor = leerSensor(s);
    if (isnan(valor)) { Serial.printf("[ADC] %s sin lectura, se omite.\n", s.codigo_hardware); continue; }
    const char* nombre; const char* unidad;
    etiquetaSensor(s.tipo, nombre, unidad);
    if (s.tipo == TEMP_DS18B20) {
      Serial.printf(" %-12s | %8.2f %-5s |    --  | %s\n", nombre, valor, unidad, s.codigo_hardware);
    } else {
      Serial.printf(" %-12s | %8.2f %-5s | %6u | %s%s\n", nombre, valor, unidad, ultimoMvPin,
                    s.codigo_hardware, ultimoMvPin >= ADC_SATURACION_MV ? "  [!] ADC SATURADO: revisa el divisor" : "");
    }
    mostrarEnPantalla(s.tipo, valor);
    JsonObject l = arr.add<JsonObject>();
    l["codigo_hardware"] = s.codigo_hardware;
    l["valor"] = valorEnviado(valor);
    l["secuencia"] = ++contadorSecuencia;
    if (ts.length()) l["timestamp"] = ts;   // clave para el dedup offline
    incluidas++;
  }
  Serial.println("------------------------------------------------------------");
  pantallaPublicar();
  if (incluidas == 0) return String("");
  // Paquete JSON que viaja al software (se muestra para la sustentacion).
  Serial.println("[JSON] Paquete armado:");
  serializeJsonPretty(doc, Serial);
  Serial.println();
  String out; serializeJson(doc, out); return out;
}

// ---------------------------------------------------------------------------
// Envio + cola offline (RF019)
// ---------------------------------------------------------------------------
/**
 * @brief Procesa la respuesta del software: aplica el intervalo configurado
 *        (RF011) y muestra el resumen o el motivo del rechazo.
 * @param codigo Codigo HTTP recibido.
 * @param cuerpo Cuerpo JSON {success, data, message}.
 */
static void aplicarRespuesta(int codigo, const String& cuerpo) {
  JsonDocument resp;
  if (deserializeJson(resp, cuerpo)) {
    Serial.println("[HTTP] Respuesta no es JSON.");
    return;
  }
  const char* mensaje = resp["message"] | "";
  if (codigo == 401 || codigo == 403) {
    Serial.printf("[AUTH] %s  -> revisa DEVICE_TOKEN y el estado del dispositivo.\n", mensaje);
    return;
  }
  if (codigo >= 400) {
    Serial.printf("[HTTP] Rechazado: %s\n", mensaje);
    serializeJsonPretty(resp["data"], Serial); Serial.println();
    return;
  }
  JsonObject data = resp["data"];
  // Lectura critica en el lote actual -> foto de evidencia (no en reenvios viejos).
  if (!reenviandoCola && (data["criticas"] | 0) > 0) camaraSolicitarAlerta();
  Serial.printf("[SIGMAP-AQUA] %s registradas=%d criticas=%d alertas=%d\n", mensaje,
                data["registradas"] | 0, data["criticas"] | 0, data["alertas_generadas"] | 0);
  estadosDelServidor(data["lecturas"]);   // la pantalla usa el mismo estado que el software
  JsonArray rechazadas = data["rechazadas"];
  if (!rechazadas.isNull() && rechazadas.size() > 0) {
    Serial.print("[HTTP] Lecturas rechazadas: ");
    serializeJson(rechazadas, Serial); Serial.println();
  }
  const uint32_t nuevo = data["intervalo_segundos"] | 0;
  if (nuevo >= INTERVALO_MIN_S && nuevo <= INTERVALO_MAX_S && nuevo != intervaloS) {
    Serial.printf("[CONFIG] Intervalo actualizado por el software: %lu s -> %lu s\n",
                  (unsigned long)intervaloS, (unsigned long)nuevo);
    intervaloS = nuevo;
  }
}

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
  if (codigo > 0) aplicarRespuesta(codigo, http.getString());
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
  reenviandoCola = true;
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
  reenviandoCola = false;
  if (pendientes.length() == 0) LittleFS.remove(COLA_PATH);
  else { File w = LittleFS.open(COLA_PATH, "w"); if (w) { w.print(pendientes); w.close(); } }
  if (enviados) Serial.printf("[COLA] Reenviados %d lote(s).\n", enviados);
}

// ---------------------------------------------------------------------------
// Calibracion por monitor serie (persistida en NVS)
// ---------------------------------------------------------------------------
/** Busca el primer sensor activo de un tipo; nullptr si no hay. */
static const SensorCfg* sensorDeTipo(TipoSensor tipo) {
  for (size_t i = 0; i < N_SENSORES; i++) {
    if (SENSORES[i].tipo == tipo && SENSORES[i].activo) return &SENSORES[i];
  }
  return nullptr;
}

/** Promedio de varias lecturas de voltaje (ya con divisor) para calibrar. */
static float voltajeEstable(const SensorCfg& s) {
  float suma = 0.0f;
  for (uint8_t i = 0; i < 10; i++) { suma += leerVoltaje(s.gpio, s.factor_divisor); delay(50); }
  return suma / 10.0f;
}

static bool calTurbGuardada = false;   // true si turb_v0 esta en la NVS
static bool calPhGuardada   = false;   // true si ph_m y ph_b estan en la NVS

/** Carga la calibracion guardada; si no hay, deja los valores de fabrica. */
static void cargarCalibracion() {
  if (prefs.begin("sigmap", true)) {       // falla si nunca se ha calibrado nada
    calTurbGuardada = prefs.isKey("turb_v0");
    calPhGuardada   = prefs.isKey("ph_m") && prefs.isKey("ph_b");
    turbVLimpia = prefs.getFloat("turb_v0", TURB_V_CURVA_LIMPIA);
    phM = prefs.getFloat("ph_m", PH_M_FABRICA);
    phB = prefs.getFloat("ph_b", PH_B_FABRICA);
    prefs.end();
  }
  pantallaCalibracion(calPhGuardada, calTurbGuardada);
}

static void mostrarCalibracion() {
  Serial.println("\n[CAL] ---- Calibracion vigente ----");
  Serial.printf("[CAL] Turbidez: agua limpia = %.3f V (0 NTU)  [%s]\n", turbVLimpia,
                calTurbGuardada ? "GUARDADA" : "DE FABRICA: falta CAL TUR");
  Serial.printf("[CAL] pH: pH = %.4f * V + %.4f  [%s]\n", phM, phB,
                calPhGuardada ? "GUARDADA" : "DE FABRICA: falta CAL PH 6.86 y CAL PH 4.01");
  for (size_t i = 0; i < N_SENSORES; i++) {
    const SensorCfg& s = SENSORES[i];
    if (!s.activo || s.tipo == TEMP_DS18B20) continue;
    const float v = leerVoltaje(s.gpio, s.factor_divisor);
    Serial.printf("[CAL] %-12s pin %u mV -> sensor %.3f V%s\n", s.codigo_hardware, ultimoMvPin, v,
                  ultimoMvPin >= ADC_SATURACION_MV ? "  [!] SATURADO" : "");
  }
}

/** CAL TUR: fija el voltaje de agua limpia como 0 NTU. */
static void calibrarTurbidez() {
  const SensorCfg* s = sensorDeTipo(TURBIDEZ_NTU);
  if (!s) { Serial.println("[CAL] No hay sensor de turbidez activo."); return; }
  const float v = voltajeEstable(*s);
  if (ultimoMvPin >= ADC_SATURACION_MV) {
    Serial.println("[CAL] ERROR: el ADC esta saturado en agua limpia. Cambia el divisor (10k/20k) y repite.");
    return;
  }
  if (v < 1.0f) { Serial.println("[CAL] ERROR: voltaje muy bajo; la sonda esta en el agua y alimentada a 5 V?"); return; }
  turbVLimpia = v;
  prefs.begin("sigmap", false); prefs.putFloat("turb_v0", v); prefs.end();
  calTurbGuardada = true;
  pantallaCalibracion(calPhGuardada, calTurbGuardada);
  Serial.printf("[CAL] OK turbidez: agua limpia = %.3f V queda como 0 NTU.\n", v);
}

/** CAL PH <referencia>: guarda un punto; con dos puntos recalcula la recta. */
static void calibrarPh(float referencia) {
  const SensorCfg* s = sensorDeTipo(PH_LINEAL);
  if (!s) { Serial.println("[CAL] No hay sensor de pH activo."); return; }
  if (referencia < 1.0f || referencia > 13.0f) { Serial.println("[CAL] Uso: CAL PH 6.86  o  CAL PH 4.01"); return; }
  const float v = voltajeEstable(*s);
  prefs.begin("sigmap", false);
  const float refAnterior = prefs.getFloat("ph_r1", NAN);
  const float vAnterior   = prefs.getFloat("ph_v1", NAN);
  prefs.putFloat("ph_r1", referencia);
  prefs.putFloat("ph_v1", v);
  Serial.printf("[CAL] Punto pH %.2f = %.4f V guardado.\n", referencia, v);
  if (!isnan(refAnterior) && fabsf(refAnterior - referencia) > 1.0f && fabsf(vAnterior - v) > 0.05f) {
    phM = (refAnterior - referencia) / (vAnterior - v);
    phB = referencia - phM * v;
    prefs.putFloat("ph_m", phM);
    prefs.putFloat("ph_b", phB);
    calPhGuardada = true;
    pantallaCalibracion(calPhGuardada, calTurbGuardada);
    Serial.printf("[CAL] OK pH: pH = %.4f * V + %.4f (puntos %.2f y %.2f)\n", phM, phB, refAnterior, referencia);
  } else {
    Serial.println("[CAL] Lava la sonda, ponla en el otro buffer y repite con su valor.");
  }
  prefs.end();
}

static void resetCalibracion() {
  prefs.begin("sigmap", false); prefs.clear(); prefs.end();
  turbVLimpia = TURB_V_CURVA_LIMPIA; phM = PH_M_FABRICA; phB = PH_B_FABRICA;
  calTurbGuardada = calPhGuardada = false;
  pantallaCalibracion(false, false);
  Serial.println("[CAL] Calibracion de fabrica restaurada.");
}

/** Lee comandos del monitor serie sin bloquear el ciclo de envio. */
static void atenderSerie() {
  static String linea;
  while (Serial.available()) {
    const char c = (char)Serial.read();
    if (c != '\n' && c != '\r') { if (linea.length() < 40) linea += c; continue; }
    linea.trim(); linea.toUpperCase();
    if (linea.length() == 0) continue;
    if (linea == "VER") mostrarCalibracion();
    else if (linea == "CAL TUR") calibrarTurbidez();
    else if (linea.startsWith("CAL PH")) calibrarPh(linea.substring(6).toFloat());
    else if (linea == "RESET CAL") resetCalibracion();
    else if (linea == "PANTALLA") pantallaReiniciar();
    else if (linea == "FOTO") camaraFotoManual(timestampISO(), SERVER_HOST, SERVER_PORT, DEVICE_TOKEN);
    else Serial.println("[CAL] Comandos: VER | CAL TUR | CAL PH 6.86 | CAL PH 4.01 | RESET CAL | PANTALLA | FOTO");
    linea = "";
  }
}

// ---------------------------------------------------------------------------
void setup() {
  Serial.begin(115200); delay(300);
  pinMode(PIN_LED_ESTADO, OUTPUT);
  ds18.begin();
  ds18.setResolution(11);            // 0,125 C; ~375 ms (cabe en ciclos de 2 s)
  ds18.setWaitForConversion(false);  // conversion en segundo plano (ver leerSensor)
  ds18.requestTemperatures();        // primera conversion, lista para el primer lote
  analogReadResolution(12);
  analogSetAttenuation(ADC_11db);
  if (!LittleFS.begin(true)) Serial.println("[FS] LittleFS no monto; el modo offline no guardara.");
  cargarCalibracion();
  // La camara va ANTES de la pantalla: reserva su bloque de 38 KB antes de que
  // los sprites fragmenten la memoria. Si falla, el nodo sigue sin camara.
  camaraIniciar();
  // La pantalla arranca DESPUES de configurar los demas pines y ANTES del
  // WiFi, en el hilo principal: el mismo orden que pantalla_imagen.ino.
  pantallaIniciar();
  Serial.printf("\n=== SIGMAP-AQUA nodo v%s | intervalo %lu s | modo offline ===\n", FIRMWARE_VERSION, (unsigned long)intervaloS);
  mostrarCalibracion();
  Serial.println("[CAL] Escribe AYUDA en el monitor serie para calibrar.");
  const bool wifiOk = conectarWiFi();
  pantallaWifi(wifiOk);
  if (wifiOk) sincronizarHora();
  pantallaTerminarArranque(wifiOk);  // fin de la animacion y tablero en vivo
}

void loop() {
  atenderSerie();
  pantallaDiagnostico();
  static uint32_t ultimo = 0;
  const uint32_t ahora = millis();
  if (ultimo == 0 || (ahora - ultimo) >= intervaloS * 1000UL) {
    digitalWrite(PIN_LED_ESTADO, HIGH);

    if (!horaLista && conectarWiFi()) sincronizarHora();  // reintenta NTP si hizo falta

    String cuerpo = construirCuerpo();
    if (cuerpo.length() == 0) {
      Serial.println("[CICLO] Sin lecturas este ciclo.");
    } else {
      const bool wifiOk = conectarWiFi();
      pantallaWifi(wifiOk);
      if (wifiOk && enviarCuerpo(cuerpo)) {
        vaciarCola();               // en linea: manda lo de ahora y vacia lo pendiente
        pantallaEnvio(PANT_ENVIADO);
        camaraCiclo(timestampISO(), SERVER_HOST, SERVER_PORT, DEVICE_TOKEN);  // RF027
      } else {
        guardarEnCola(cuerpo);      // offline: a la cola
        pantallaEnvio(wifiOk ? PANT_SIN_SERVIDOR : PANT_SIN_WIFI);
      }
    }

    digitalWrite(PIN_LED_ESTADO, LOW);
    ultimo = ahora;
  }
  pantallaEsperar(20);               // en vez de delay(): la pantalla anima mientras tanto
}
