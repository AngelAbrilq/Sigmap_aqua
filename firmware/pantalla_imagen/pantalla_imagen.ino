/**
 * pantalla_imagen.ino — Sigmap Aqua
 * Prueba SOLO DE IMAGEN de la pantalla 3.5" RPi Display (ILI9486) con ESP32.
 *
 * Usa 7 cables: 5V, GND, MOSI, SCK, LCD_CS, DC y RST. El touch NO se usa
 * (necesita 2 cables mas: MISO y TP_CS), asi que este sketch nunca lo lee.
 *
 * Que deberias ver:
 *   - Titulo "Sigmap Aqua" en cian.
 *   - 4 barras: rojo | verde | azul | blanco (si salen en otro orden o
 *     color, revisa MOSI y SCK).
 *   - Un contador que sube cada segundo: prueba que la comunicacion SPI
 *     sigue viva, no solo que arranco.
 *
 * Requiere: libreria TFT_eSPI (Bodmer) con el User_Setup.h de esta carpeta
 * copiado en Documentos\Arduino\libraries\TFT_eSPI\User_Setup.h
 */
#include <SPI.h>
#include <TFT_eSPI.h>

TFT_eSPI tft;

const uint8_t SCREEN_ROTATION = 1;          // 1 = horizontal 480x320
const uint32_t REFRESH_INTERVAL_MS = 1000;  // cada cuanto sube el contador

uint32_t lastRefreshMs = 0;
uint32_t secondsAlive = 0;

/**
 * Dibuja la pantalla fija: titulo, instrucciones y barras de color.
 */
void drawStaticScreen() {
  tft.fillScreen(TFT_BLACK);

  tft.setTextColor(TFT_CYAN, TFT_BLACK);
  tft.drawCentreString("Sigmap Aqua", tft.width() / 2, 30, 4);

  tft.setTextColor(TFT_WHITE, TFT_BLACK);
  tft.drawCentreString("Prueba de pantalla (sin touch)", tft.width() / 2, 75, 2);
  tft.drawCentreString("Rojo | Verde | Azul | Blanco", tft.width() / 2, 195, 2);

  const uint16_t barColors[4] = {TFT_RED, TFT_GREEN, TFT_BLUE, TFT_WHITE};
  const int barWidth = tft.width() / 4;
  for (uint8_t i = 0; i < 4; i++) {
    tft.fillRect(i * barWidth, 220, barWidth, 100, barColors[i]);
  }
}

/**
 * Actualiza el contador de segundos en el centro de la pantalla.
 */
void drawCounter() {
  char text[32];
  snprintf(text, sizeof(text), "Encendida: %lu s", (unsigned long)secondsAlive);
  tft.setTextColor(TFT_YELLOW, TFT_BLACK);
  tft.setTextPadding(tft.width());          // borra el numero anterior
  tft.drawCentreString(text, tft.width() / 2, 130, 4);
  tft.setTextPadding(0);
}

void setup() {
  Serial.begin(115200);
  delay(500);
  Serial.println("\n[Pantalla] Iniciando prueba de imagen...");

  tft.init();
  tft.setRotation(SCREEN_ROTATION);
  drawStaticScreen();
  drawCounter();

  Serial.printf("[Pantalla] Lista: %d x %d px\n", tft.width(), tft.height());
}

void loop() {
  if (millis() - lastRefreshMs >= REFRESH_INTERVAL_MS) {
    lastRefreshMs = millis();
    secondsAlive++;
    drawCounter();
    Serial.printf("[Pantalla] %lu s\n", (unsigned long)secondsAlive);
  }
}
