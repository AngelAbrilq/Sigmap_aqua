/**
 * @file    bioaqua_handshake.ino
 * @brief   Validacion de enlace ESP32 -> API Django de BioAqua System.
 * @target  ESP32-D0WD-V3 (WROOM-32), Arduino core 3.x
 *
 * PROPOSITO
 * Este firmware NO lee sensores y NO genera ningun dato de agua. Su unica
 * funcion es demostrar, con la placa desnuda, que:
 *   1. El nodo se asocia a la red WiFi de 2.4 GHz.
 *   2. Alcanza por TCP el servidor Django en la LAN.
 *   3. Su token de dispositivo es aceptado.
 *   4. El servidor le responde con la piscina asignada y su hora real.
 *
 * Todo lo que este firmware transmite son magnitudes medidas por el propio
 * hardware: direccion MAC, IP asignada por DHCP, RSSI de la radio y uptime.
 * Ningun valor es inventado ni simulado.
 *
 * Los sensores se cablean SOLO despues de que este sketch reporte OK.
 */

#include <WiFi.h>
#include <HTTPClient.h>
#include <time.h>
#include "secrets.h"

// ---------------------------------------------------------------------------
// Configuracion
// ---------------------------------------------------------------------------

/** Version de firmware reportada al servidor. Subela en cada cambio real. */
static const char* FIRMWARE_VERSION = "0.1.0-handshake";

/** Segundos entre handshakes. En produccion la ingesta usara otro intervalo. */
static const uint32_t INTERVALO_HANDSHAKE_S = 30;

/** Tiempo maximo esperando asociacion WiFi antes de reintentar. */
static const uint32_t TIMEOUT_WIFI_MS = 20000;

/** Tiempo maximo esperando respuesta HTTP del servidor. */
static const uint32_t TIMEOUT_HTTP_MS = 10000;

/**
 * LED de estado. GPIO2 es el LED integrado de la placa DevKit.
 * Es un strapping pin, pero usarlo como SALIDA despues del arranque es seguro:
 * el riesgo son las senales EXTERNAS que fuerzan su nivel durante el reset.
 * No conectes nada a este pin.
 */
static const uint8_t PIN_LED_ESTADO = 2;

/** Servidores NTP. El ESP32 no tiene reloj con bateria: al reiniciar cree estar en 1970. */
static const char* NTP_PRIMARIO   = "pool.ntp.org";
static const char* NTP_SECUNDARIO = "time.google.com";
static const char* TZ_COLOMBIA    = "<-05>5";  // America/Bogota, sin horario de verano

// ---------------------------------------------------------------------------
// Estado interno
// ---------------------------------------------------------------------------

static uint32_t contadorHandshakes = 0;
static uint32_t contadorFallos     = 0;

// ---------------------------------------------------------------------------
// Utilidades
// ---------------------------------------------------------------------------

/**
 * @brief Parpadea el LED de estado un numero de veces.
 * @param veces      Cantidad de parpadeos.
 * @param duracionMs Duracion de encendido y apagado.
 */
static void parpadear(uint8_t veces, uint16_t duracionMs) {
  for (uint8_t i = 0; i < veces; i++) {
    digitalWrite(PIN_LED_ESTADO, HIGH);
    delay(duracionMs);
    digitalWrite(PIN_LED_ESTADO, LOW);
    delay(duracionMs);
  }
}

/**
 * @brief Asocia el nodo a la red WiFi con timeout acotado.
 * @return true si quedo asociado; false si expiro el timeout.
 */
static bool conectarWiFi() {
  if (WiFi.status() == WL_CONNECTED) {
    return true;
  }

  Serial.printf("[WIFI] Asociando a \"%s\" ...\n", WIFI_SSID);

  WiFi.mode(WIFI_STA);
  WiFi.setSleep(false);            // evita latencia de power save en la ingesta
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);

  const uint32_t inicio = millis();
  while (WiFi.status() != WL_CONNECTED) {
    if (millis() - inicio > TIMEOUT_WIFI_MS) {
      Serial.printf("[WIFI] ERROR: timeout tras %lu ms. status=%d\n",
                    (unsigned long)(millis() - inicio), WiFi.status());
      Serial.println("[WIFI] Causas frecuentes: SSID de 5 GHz (no soportada), "
                     "clave incorrecta, o fuera de alcance.");
      WiFi.disconnect(true);
      return false;
    }
    delay(250);
    Serial.print('.');
  }

  Serial.println();
  Serial.printf("[WIFI] Asociado. IP=%s  MAC=%s  RSSI=%d dBm\n",
                WiFi.localIP().toString().c_str(),
                WiFi.macAddress().c_str(),
                WiFi.RSSI());

  if (WiFi.RSSI() < -80) {
    Serial.println("[WIFI] AVISO: senal debil (< -80 dBm). En campo abierto esto "
                   "produce cortes intermitentes. Considera antena externa.");
  }
  return true;
}

/**
 * @brief Sincroniza el reloj interno por NTP.
 * @return true si obtuvo una fecha valida (posterior a 2020).
 */
static bool sincronizarHora() {
  configTzTime(TZ_COLOMBIA, NTP_PRIMARIO, NTP_SECUNDARIO);

  struct tm tiempo;
  if (!getLocalTime(&tiempo, 10000)) {
    Serial.println("[NTP] ERROR: no se pudo sincronizar la hora.");
    return false;
  }

  char buffer[32];
  strftime(buffer, sizeof(buffer), "%Y-%m-%d %H:%M:%S", &tiempo);
  Serial.printf("[NTP] Hora local sincronizada: %s\n", buffer);
  return true;
}

/**
 * @brief Envia el handshake a la API y muestra la respuesta cruda del servidor.
 * @return Codigo HTTP devuelto, o un valor negativo si fallo el transporte.
 */
static int enviarHandshake() {
  if (WiFi.status() != WL_CONNECTED) {
    return -1;
  }

  char url[128];
  snprintf(url, sizeof(url), "http://%s:%d/api/v1/dispositivos/handshake/",
           SERVER_HOST, SERVER_PORT);

  char cabeceraAuth[96];
  snprintf(cabeceraAuth, sizeof(cabeceraAuth), "Device %s", DEVICE_TOKEN);

  // Solo magnitudes reales medidas por el hardware.
  char cuerpo[256];
  snprintf(cuerpo, sizeof(cuerpo),
           "{\"codigo\":\"%s\",\"mac\":\"%s\",\"firmware\":\"%s\","
           "\"rssi\":%d,\"uptime_s\":%lu,\"heap_libre\":%lu}",
           DEVICE_CODE,
           WiFi.macAddress().c_str(),
           FIRMWARE_VERSION,
           WiFi.RSSI(),
           (unsigned long)(millis() / 1000UL),
           (unsigned long)ESP.getFreeHeap());

  HTTPClient http;
  http.setTimeout(TIMEOUT_HTTP_MS);
  http.setConnectTimeout(TIMEOUT_HTTP_MS);

  if (!http.begin(url)) {
    Serial.println("[HTTP] ERROR: URL mal formada.");
    return -2;
  }

  http.addHeader("Content-Type", "application/json");
  http.addHeader("Authorization", cabeceraAuth);

  Serial.printf("[HTTP] POST %s\n", url);
  const int codigo = http.POST((uint8_t*)cuerpo, strlen(cuerpo));

  if (codigo > 0) {
    Serial.printf("[HTTP] Codigo %d\n", codigo);
    Serial.println("[HTTP] Respuesta del servidor:");
    Serial.println(http.getString());
  } else {
    Serial.printf("[HTTP] ERROR de transporte: %s\n",
                  http.errorToString(codigo).c_str());
    Serial.println("[HTTP] Revisa: runserver en 0.0.0.0, IP correcta en "
                   "SERVER_HOST, y regla de entrada en el Firewall de Windows.");
  }

  http.end();
  return codigo;
}

/**
 * @brief Imprime la identificacion real del silicio, leida del propio chip.
 */
static void reportarHardware() {
  Serial.println();
  Serial.println("==========================================");
  Serial.println(" BioAqua System - Validacion de enlace");
  Serial.println("==========================================");
  Serial.printf("Chip      : %s rev %d\n", ESP.getChipModel(), ESP.getChipRevision());
  Serial.printf("Nucleos   : %d @ %lu MHz\n",
                ESP.getChipCores(), (unsigned long)getCpuFrequencyMhz());
  Serial.printf("Flash     : %lu bytes\n", (unsigned long)ESP.getFlashChipSize());
  Serial.printf("Heap libre: %lu bytes\n", (unsigned long)ESP.getFreeHeap());
  Serial.printf("MAC       : %s\n", WiFi.macAddress().c_str());
  Serial.printf("Firmware  : %s\n", FIRMWARE_VERSION);
  Serial.printf("Nodo      : %s\n", DEVICE_CODE);
  Serial.println("------------------------------------------");
  Serial.println("Sin sensores conectados. Este sketch no mide agua.");
  Serial.println("==========================================");
  Serial.println();
}

// ---------------------------------------------------------------------------
// Ciclo principal
// ---------------------------------------------------------------------------

void setup() {
  Serial.begin(115200);
  delay(1000);

  pinMode(PIN_LED_ESTADO, OUTPUT);
  digitalWrite(PIN_LED_ESTADO, LOW);

  reportarHardware();

  if (conectarWiFi()) {
    sincronizarHora();
    parpadear(2, 120);
  }
}

void loop() {
  if (!conectarWiFi()) {
    contadorFallos++;
    parpadear(5, 400);                 // parpadeo lento y largo = sin WiFi
    delay(5000);
    return;
  }

  const int codigo = enviarHandshake();

  if (codigo == 200) {
    contadorHandshakes++;
    Serial.printf("[OK] Handshake #%lu correcto. Fallos acumulados: %lu\n\n",
                  (unsigned long)contadorHandshakes, (unsigned long)contadorFallos);
    parpadear(1, 80);                  // destello corto = enlace sano
  } else if (codigo == 401 || codigo == 403) {
    contadorFallos++;
    Serial.println("[ERROR] Token rechazado. Verifica DEVICE_TOKEN en secrets.h "
                   "y que el dispositivo este activo en el admin de Django.\n");
    parpadear(3, 200);
  } else {
    contadorFallos++;
    Serial.printf("[ERROR] Handshake fallido (codigo %d).\n\n", codigo);
    parpadear(4, 200);
  }

  // Pausa entre intentos sin bloquear la pila de red del core.
  const uint32_t espera = INTERVALO_HANDSHAKE_S * 1000UL;
  const uint32_t inicio = millis();
  while (millis() - inicio < espera) {
    delay(100);
  }
}
