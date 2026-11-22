/**
 * @file    camara.h
 * @brief   Camara OV7670 (sin FIFO) del nodo SIGMAP-AQUA: captura una foto
 *          QQVGA, la comprime a JPEG y la envia a POST /api/v1/capturas/ (RF027).
 *
 * CABLEADO (camara -> ESP32). La camara va a 3.3 V, NUNCA a 5 V:
 *   3.3V -> 3V3        GND  -> GND
 *   RET  -> 3V3        PWDN -> GND          (no gastan GPIO)
 *   SCL  -> GPIO27  + resistencia 4,7 kOhm a 3V3
 *   SDA  -> GPIO26  + resistencia 4,7 kOhm a 3V3
 *   XLK  -> GPIO25     PLK  -> GPIO39 (VN)
 *   VS   -> GPIO19     HS   -> GPIO36 (VP)
 *   D0 -> 13   D1 -> 14   D2 -> 15   D3 -> 21
 *   D4 -> 22   D5 -> 33   D6 -> 17   D7 -> 4
 *
 * POR QUE ESTOS PINES
 *   - 19, 22 y 17 los libera la pantalla (se quita el touch y su RST va al
 *     pin EN). Los sensores (32, 34, 35) y el LED (2) no se tocan.
 *   - VS va en un pin normal y no en 36/39: el driver usa una INTERRUPCION en
 *     VSYNC, y GPIO36/39 dan interrupciones falsas cuando se usa el ADC
 *     (errata del ESP32). HS y PLK van por I2S, sin interrupcion: ahi si sirven.
 *
 * MEMORIA (ESP32 sin PSRAM)
 *   - 160x120 RGB565 = 38 KB de cuadro en DRAM. camaraIniciar() va ANTES de
 *     la pantalla para reservar ese bloque antes de que los sprites fragmenten.
 *   - frame2jpg() de la libreria pide 128 KB de golpe y en este ESP32 falla,
 *     por eso se comprime con frame2jpg_cb() a un buffer propio de 24 KB
 *     (una foto QQVGA pesa ~4-8 KB).
 *
 * Si la camara no responde, el nodo SIGUE midiendo y enviando lecturas:
 * la camara nunca debe tumbar la ingesta.
 */
#pragma once

#include <Arduino.h>
#include <WiFi.h>
#include <HTTPClient.h>
#include "esp_camera.h"
#include "img_converters.h"

// ---------------------------------------------------------------------------
// Configuracion
// ---------------------------------------------------------------------------
static const int CAM_PIN_XCLK  = 25;
static const int CAM_PIN_SIOD  = 26;   // SDA
static const int CAM_PIN_SIOC  = 27;   // SCL
static const int CAM_PIN_PCLK  = 39;   // PLK (solo entrada)
static const int CAM_PIN_VSYNC = 19;   // VS  (pin normal: lleva interrupcion)
static const int CAM_PIN_HREF  = 36;   // HS  (solo entrada)
static const int CAM_PIN_D0 = 13, CAM_PIN_D1 = 14, CAM_PIN_D2 = 15, CAM_PIN_D3 = 21;
static const int CAM_PIN_D4 = 22, CAM_PIN_D5 = 33, CAM_PIN_D6 = 17, CAM_PIN_D7 = 4;

static const uint32_t CAM_XCLK_HZ          = 10000000;  // 10 MHz: estable sin PSRAM
static const uint8_t  CAM_JPEG_CALIDAD     = 80;        // 0-100
static const size_t   CAM_JPEG_MAX_BYTES   = 24 * 1024;
static const uint32_t CAM_INTERVALO_S      = 300;       // foto periodica cada 5 min
static const uint32_t CAM_ESPERA_ALERTA_S  = 60;        // como maximo 1 foto de alerta por minuto
static const uint8_t  CAM_CUADROS_DESCARTE = 2;         // los primeros salen sin exposicion
static const uint8_t  OV7670_PID           = 0x76;

// ---------------------------------------------------------------------------
// Estado interno
// ---------------------------------------------------------------------------
namespace cam {
  static bool     lista = false;
  static uint8_t* jpeg = nullptr;           // buffer propio de salida JPEG
  static size_t   jpegLen = 0;
  static bool     desborde = false;
  static uint32_t ultimaFotoMs = 0;
  static uint32_t ultimaAlertaMs = 0;
  static bool     alertaPendiente = false;
  static bool     primeraFotoHecha = false;

  /** Callback del codificador: copia cada bloque JPEG al buffer propio. */
  static size_t escribirJpeg(void* /*arg*/, size_t index, const void* data, size_t len) {
    if (index + len > CAM_JPEG_MAX_BYTES) { desborde = true; return 0; }
    memcpy(jpeg + index, data, len);
    jpegLen = index + len;
    return len;
  }
}

/** true si la camara arranco bien y puede tomar fotos. */
static bool camaraLista() { return cam::lista; }

/**
 * @brief Configura la OV7670 con el cuadro en DRAM (sin PSRAM).
 * Llamar en setup() ANTES de pantallaIniciar().
 * @return true si la camara respondio por SCCB y es una OV7670.
 */
static bool camaraIniciar() {
  cam::jpeg = (uint8_t*)malloc(CAM_JPEG_MAX_BYTES);
  if (!cam::jpeg) {
    Serial.println("[CAM] Sin memoria para el buffer JPEG. Camara desactivada.");
    return false;
  }

  camera_config_t c = {};
  c.pin_pwdn = -1;              // PWDN cableado a GND
  c.pin_reset = -1;             // RET cableado a 3V3
  c.pin_xclk = CAM_PIN_XCLK;
  c.pin_sccb_sda = CAM_PIN_SIOD;
  c.pin_sccb_scl = CAM_PIN_SIOC;
  c.pin_d7 = CAM_PIN_D7; c.pin_d6 = CAM_PIN_D6; c.pin_d5 = CAM_PIN_D5; c.pin_d4 = CAM_PIN_D4;
  c.pin_d3 = CAM_PIN_D3; c.pin_d2 = CAM_PIN_D2; c.pin_d1 = CAM_PIN_D1; c.pin_d0 = CAM_PIN_D0;
  c.pin_vsync = CAM_PIN_VSYNC;
  c.pin_href = CAM_PIN_HREF;
  c.pin_pclk = CAM_PIN_PCLK;
  c.xclk_freq_hz = CAM_XCLK_HZ;
  c.ledc_timer = LEDC_TIMER_0;
  c.ledc_channel = LEDC_CHANNEL_0;
  c.pixel_format = PIXFORMAT_RGB565;   // la OV7670 no comprime: JPEG lo hace el ESP32
  c.frame_size = FRAMESIZE_QQVGA;      // 160x120
  c.fb_count = 1;
  c.fb_location = CAMERA_FB_IN_DRAM;
  c.grab_mode = CAMERA_GRAB_WHEN_EMPTY;

  const esp_err_t err = esp_camera_init(&c);
  if (err != ESP_OK) {
    Serial.printf("[CAM] Error 0x%x al iniciar. Revisa 3.3V, SDA/SCL (+4,7k), XLK y GND. "
                  "El nodo sigue sin camara.\n", err);
    free(cam::jpeg); cam::jpeg = nullptr;
    return false;
  }

  sensor_t* s = esp_camera_sensor_get();
  if (s) {
    Serial.printf("[CAM] Sensor PID 0x%02x %s\n", s->id.PID,
                  s->id.PID == OV7670_PID ? "(OV7670 OK)" : "(no es OV7670)");
  }
  cam::lista = true;
  Serial.printf("[CAM] Lista: QQVGA 160x120, foto cada %lu s. Heap libre %u B\n",
                (unsigned long)CAM_INTERVALO_S, ESP.getFreeHeap());
  return true;
}

/**
 * @brief Toma una foto y la deja comprimida en cam::jpeg / cam::jpegLen.
 * @return true si hay un JPEG valido.
 */
static bool camaraCapturarJpeg() {
  if (!cam::lista) return false;

  // Descarta cuadros viejos: con GRAB_WHEN_EMPTY el primero puede ser antiguo.
  for (uint8_t i = 0; i < CAM_CUADROS_DESCARTE; i++) {
    camera_fb_t* viejo = esp_camera_fb_get();
    if (viejo) esp_camera_fb_return(viejo);
  }

  camera_fb_t* fb = esp_camera_fb_get();
  if (!fb) {
    Serial.println("[CAM] No llego el cuadro. Revisa D0-D7, PLK, VS y HS.");
    return false;
  }

  cam::jpegLen = 0;
  cam::desborde = false;
  const bool ok = frame2jpg_cb(fb, CAM_JPEG_CALIDAD, cam::escribirJpeg, nullptr);
  esp_camera_fb_return(fb);   // devolver SIEMPRE el cuadro al driver

  if (!ok || cam::desborde || cam::jpegLen == 0) {
    Serial.printf("[CAM] Fallo la compresion JPEG%s.\n",
                  cam::desborde ? " (supera el buffer: baja CAM_JPEG_CALIDAD)" : "");
    return false;
  }
  return true;
}

/**
 * @brief Envia el JPEG al software. Sin cola offline: una foto vieja no
 *        sirve para decidir y la flash del ESP32 es pequena.
 * @param motivo        "periodica" o "alerta" (cabecera X-Motivo).
 * @param timestamp     hora NTP ISO 8601, o "" si no hay.
 * @param host, puerto, token  los mismos de secrets.h
 * @return true si el servidor respondio 201.
 */
static bool camaraEnviar(const char* motivo, const String& timestamp,
                         const char* host, uint16_t puerto, const char* token) {
  if (!cam::lista || WiFi.status() != WL_CONNECTED) return false;
  if (!camaraCapturarJpeg()) return false;

  char url[96];
  snprintf(url, sizeof(url), "http://%s:%u/api/v1/capturas/", host, puerto);
  char auth[80];
  snprintf(auth, sizeof(auth), "Device %s", token);

  HTTPClient http;
  http.setConnectTimeout(10000);
  http.setTimeout(10000);
  if (!http.begin(url)) return false;
  http.addHeader("Content-Type", "image/jpeg");
  http.addHeader("Authorization", auth);
  http.addHeader("X-Motivo", motivo);
  if (timestamp.length()) http.addHeader("X-Timestamp", timestamp);

  const int codigo = http.POST(cam::jpeg, cam::jpegLen);
  const bool ok = (codigo == 201);
  Serial.printf("[CAM] Foto %s %u B -> HTTP %d %s\n", motivo, (unsigned)cam::jpegLen, codigo,
                ok ? "OK" : (codigo > 0 ? http.getString().c_str() : http.errorToString(codigo).c_str()));
  http.end();
  return ok;
}

/** Pide una foto de evidencia porque el software marco lecturas criticas. */
static void camaraSolicitarAlerta() { cam::alertaPendiente = true; }

/**
 * @brief Llamar en cada ciclo del loop(), despues de enviar el lote.
 *        Decide si toca foto de alerta o periodica y la envia.
 */
static void camaraCiclo(const String& timestamp, const char* host, uint16_t puerto, const char* token) {
  if (!cam::lista || WiFi.status() != WL_CONNECTED) return;
  const uint32_t ahora = millis();

  if (cam::alertaPendiente &&
      (cam::ultimaAlertaMs == 0 || ahora - cam::ultimaAlertaMs >= CAM_ESPERA_ALERTA_S * 1000UL)) {
    cam::alertaPendiente = false;
    cam::ultimaAlertaMs = ahora;
    if (camaraEnviar("alerta", timestamp, host, puerto, token)) cam::ultimaFotoMs = ahora;
    return;   // una foto por ciclo: no retrasar el siguiente lote
  }

  if (!cam::primeraFotoHecha || ahora - cam::ultimaFotoMs >= CAM_INTERVALO_S * 1000UL) {
    cam::primeraFotoHecha = true;
    cam::ultimaFotoMs = ahora;   // aunque falle, no reintentar en cada ciclo
    camaraEnviar("periodica", timestamp, host, puerto, token);
  }
}

/** Comando FOTO del monitor serie: envia una foto ya (para la sustentacion). */
static void camaraFotoManual(const String& timestamp, const char* host, uint16_t puerto, const char* token) {
  if (!cam::lista) { Serial.println("[CAM] La camara no esta iniciada."); return; }
  if (WiFi.status() != WL_CONNECTED) { Serial.println("[CAM] Sin WiFi: no se puede enviar."); return; }
  camaraEnviar("periodica", timestamp, host, puerto, token);
}
