/**
 * pantalla_imagen.ino — SIGMAP AQUA · Pantalla de telemetria
 * Pantalla 3.5" RPi Display (ILI9486, 480x320) + ESP32, libreria TFT_eSPI.
 *
 * QUE HACE
 *   1. Animacion de encendido: ondas de agua, gota, titulo, burbujas y barra
 *      de carga que de verdad revisa los sensores (pH, turbidez y DS18B20).
 *   2. Tablero en vivo: 3 tarjetas (temperatura, pH, turbidez) con valor
 *      grande, estado y barra animada; grafica de tendencia que se desplaza
 *      con cada lectura; indicador de radar en la cabecera al capturar datos.
 *
 * SIN PARPADEO: fillScreen() solo se usa una vez al armar cada pantalla. En
 * el loop() se redibujan unicamente las zonas que cambian, y siempre a traves
 * de sprites (buffers en RAM) que se envian completos a la pantalla.
 *
 * HARDWARE (igual que la version anterior, no cambiar):
 *   Pantalla: ver User_Setup.h de esta carpeta (MOSI 23, SCK 18, CS 5, DC 16,
 *   RST 17). Sensores: mismos pines y divisores que bioaqua_ingesta.ino:
 *   pH GPIO34 (divisor 1.5), turbidez GPIO35 (divisor 2.0), DS18B20 GPIO32.
 *   La calibracion (CAL PH / CAL TUR) se lee de la memoria NVS "sigmap", la
 *   misma que guarda bioaqua_ingesta, asi que no hay que calibrar de nuevo.
 *
 * NOTA: este sketch solo MUESTRA las lecturas; no las envia al servidor.
 *   Para el envio por WiFi sigue estando bioaqua_ingesta.ino.
 *
 * Librerias: TFT_eSPI (Bodmer), OneWire, DallasTemperature.
 * El User_Setup.h de esta carpeta va en Documentos\Arduino\libraries\TFT_eSPI\
 */
#include <SPI.h>
#include <TFT_eSPI.h>
#include <Preferences.h>
#include <OneWire.h>
#include <DallasTemperature.h>

// ============================================================================
// Configuracion
// ============================================================================
#define MODO_DEMO 0   // 1 = valores simulados (para mostrar sin sensores)

static const uint8_t  SCREEN_ROTATION      = 1;      // horizontal 480x320
static const uint32_t INTERVALO_LECTURA_MS = 2000;   // cada cuanto se mide
static const uint32_t FRAME_MS             = 33;     // ~30 fps de animacion
static const uint32_t PULSO_MS             = 900;    // duracion del radar
static const uint32_t SCROLL_MS            = 420;    // desplazamiento grafica
static const float    SUAVIZADO            = 0.20f;  // 0..1, interpolacion

// Sensores: mismos pines y divisores que bioaqua_ingesta.ino
static const uint8_t PIN_PH       = 34;
static const float   DIV_PH       = 1.5f;
static const uint8_t PIN_TURBIDEZ = 35;
static const float   DIV_TURBIDEZ = 2.0f;
static const uint8_t PIN_ONEWIRE  = 32;
static const uint8_t MUESTRAS_ADC = 15;              // impar: mediana real

// Calibracion de fabrica (se reemplaza con la guardada en NVS)
static const float PH_M_FABRICA        = -5.70f;
static const float PH_B_FABRICA        = 21.34f;
static const float TURB_V_CURVA_LIMPIA = 4.20f;
static const float TURB_V_CURVA_SUCIA  = 2.50f;
static const float TURB_NTU_MAX        = 3000.0f;

// ============================================================================
// Tipos (van antes de cualquier funcion: el IDE de Arduino inserta los
// prototipos automaticos antes de la primera funcion del sketch)
// ============================================================================
static const uint8_t PUNTOS = 60;                     // historial de la grafica

enum Estado : uint8_t { SIN_DATO, OPTIMO, RIESGO, CRITICO };

struct Canal {
  const char* nombre;
  const char* unidad;          // "C" se dibuja con simbolo de grados
  uint16_t    color;
  float       escalaMin, escalaMax;   // rango de la barra y de la grafica
  float       optMin, optMax;         // rango optimo (Engorde, como en la web)
  float       margen;                 // fuera del optimo hasta aqui = riesgo
  uint8_t     decimales;
  int16_t     x;                      // posicion de la tarjeta
  float       objetivo;               // ultima lectura (NAN = sin dato)
  float       mostrado;               // valor animado en pantalla
  Estado      estado;
  Estado      estadoDibujado;
  float       historial[PUNTOS];
};

struct Burbuja { int16_t x, y; uint8_t r; uint8_t vel; };

// ============================================================================
// Paleta (RGB565). Fondo muy oscuro para que los colores vivos resalten.
// ============================================================================
constexpr uint16_t rgb(uint8_t r, uint8_t g, uint8_t b) {
  return ((r & 0xF8) << 8) | ((g & 0xFC) << 3) | (b >> 3);
}
static const uint16_t C_FONDO    = rgb(3, 8, 20);
static const uint16_t C_PANEL    = rgb(9, 20, 40);
static const uint16_t C_BORDE    = rgb(26, 58, 98);
static const uint16_t C_PISTA    = rgb(20, 36, 62);
static const uint16_t C_REJILLA  = rgb(28, 48, 78);
static const uint16_t C_TENUE    = rgb(120, 150, 185);
static const uint16_t C_BLANCO   = rgb(235, 245, 255);
static const uint16_t C_CIAN     = rgb(0, 229, 255);
static const uint16_t C_TURQUESA = rgb(0, 200, 175);
static const uint16_t C_ESMERALDA= rgb(0, 220, 120);
static const uint16_t C_NEON     = rgb(60, 255, 40);
static const uint16_t C_AMBAR    = rgb(255, 190, 0);
static const uint16_t C_CORAL    = rgb(255, 70, 110);
static const uint16_t C_AZUL     = rgb(0, 70, 160);
static const uint16_t C_GRIS     = rgb(90, 100, 115);

// ============================================================================
// Geometria del tablero
// ============================================================================
static const int16_t HEADER_H = 40;
static const int16_t CARD_Y = 46, CARD_W = 152, CARD_H = 106;
static const int16_t VAL_W = 134, VAL_H = 34;        // sprite del valor
static const int16_t BAR_W = 132, BAR_H = 12;        // sprite de la barra
static const int16_t GRAF_PANEL_Y = 158;
static const int16_t G_X = 14, G_Y = 182, G_W = 452, G_H = 130;
static const int16_t RADAR_D = 34, RADAR_X = 440, RADAR_Y = 3;

// ============================================================================
// Modelo de cada parametro mostrado
// ============================================================================
static Canal canales[] = {
  // nombre        unidad color    escala      optimo     margen dec  x
  { "TEMPERATURA", "C",   C_AMBAR, 15, 35,     24, 30,    2.0f,  1,   8 },
  { "pH",          "pH",  C_CIAN,  4,  10,     6.5f, 7.8f, 0.5f, 2, 164 },
  { "TURBIDEZ",    "NTU", C_NEON,  0,  100,    0, 50,     50.0f, 0, 320 },
};
static const uint8_t N_CANALES = sizeof(canales) / sizeof(canales[0]);
enum { CH_TEMP = 0, CH_PH = 1, CH_TURB = 2 };

// ============================================================================
// Estado global
// ============================================================================
TFT_eSPI    tft;
TFT_eSprite sprValor(&tft);
TFT_eSprite sprBarra(&tft);
TFT_eSprite sprGrafica(&tft);
TFT_eSprite sprRadar(&tft);

static OneWire           oneWire(PIN_ONEWIRE);
static DallasTemperature ds18(&oneWire);
static bool              hayDs18 = false;

static float phM = PH_M_FABRICA, phB = PH_B_FABRICA;
static float turbVLimpia = TURB_V_CURVA_LIMPIA;

static uint8_t  nPuntos = 0;
static uint32_t nLecturas = 0;
static uint32_t ultimaLecturaMs = 0, ultimoFrameMs = 0;
static uint32_t inicioPulsoMs = 0, inicioScrollMs = 0;
static bool     graficaPendiente = true;
static bool     graficaOk = false;
static int8_t   cabeceraDibujada = -1;    // 0 = en vivo, 1 = capturando

// ============================================================================
// Utilidades
// ============================================================================
/** Mezcla dos colores: t = 0 devuelve a, t = 1 devuelve b. */
static uint16_t mezclar(uint16_t a, uint16_t b, float t) {
  return tft.alphaBlend((uint8_t)(constrain(t, 0.0f, 1.0f) * 255), b, a);
}

/** Valor normalizado 0..1 dentro de la escala del canal. */
static float normalizar(const Canal& c, float v) {
  return constrain((v - c.escalaMin) / (c.escalaMax - c.escalaMin), 0.0f, 1.0f);
}

static Estado calcularEstado(const Canal& c, float v) {
  if (isnan(v)) return SIN_DATO;
  if (v >= c.optMin && v <= c.optMax) return OPTIMO;
  if (v >= c.optMin - c.margen && v <= c.optMax + c.margen) return RIESGO;
  return CRITICO;
}

static uint16_t colorEstado(Estado e, uint16_t colorCanal) {
  switch (e) {
    case OPTIMO:  return colorCanal;
    case RIESGO:  return C_AMBAR;
    case CRITICO: return C_CORAL;
    default:      return C_GRIS;
  }
}

/** Dibuja una gota de agua (circulo + punta) centrada en (cx, cy). */
static void dibujarGota(TFT_eSPI& d, int16_t cx, int16_t cy, int16_t r, uint16_t color) {
  d.fillCircle(cx, cy, r, color);
  d.fillTriangle(cx - r + 1, cy - r / 3, cx + r - 1, cy - r / 3, cx, cy - r * 2, color);
}

// ============================================================================
// Lectura de sensores (misma logica que bioaqua_ingesta.ino)
// ============================================================================
/** Voltaje real del sensor: mediana de MUESTRAS_ADC lecturas, con divisor. */
static float leerVoltaje(uint8_t gpio, float divisor) {
  uint16_t m[MUESTRAS_ADC];
  for (uint8_t i = 0; i < MUESTRAS_ADC; i++) { m[i] = analogReadMilliVolts(gpio); delay(1); }
  for (uint8_t i = 1; i < MUESTRAS_ADC; i++) {          // insercion
    const uint16_t v = m[i]; int8_t j = i - 1;
    while (j >= 0 && m[j] > v) { m[j + 1] = m[j]; j--; }
    m[j + 1] = v;
  }
  return (m[MUESTRAS_ADC / 2] * divisor) / 1000.0f;
}

static float leerPh() {
  return constrain(phM * leerVoltaje(PIN_PH, DIV_PH) + phB, 0.0f, 14.0f);
}

static float leerTurbidez() {
  if (turbVLimpia <= 0.1f) return NAN;
  const float v = leerVoltaje(PIN_TURBIDEZ, DIV_TURBIDEZ) * (TURB_V_CURVA_LIMPIA / turbVLimpia);
  if (v >= TURB_V_CURVA_LIMPIA) return 0.0f;
  if (v <= TURB_V_CURVA_SUCIA)  return TURB_NTU_MAX;
  return constrain(-1120.4f * v * v + 5742.3f * v - 4353.8f, 0.0f, TURB_NTU_MAX);
}

/**
 * Temperatura sin bloquear: lee la conversion pedida en el ciclo anterior y
 * pide la siguiente (el DS18B20 tarda ~375 ms; asi no congela la animacion).
 */
static float leerTemperatura() {
  if (!hayDs18) return NAN;
  const float t = ds18.getTempCByIndex(0);
  ds18.requestTemperatures();
  if (t == DEVICE_DISCONNECTED_C || t < -50.0f || t > 80.0f) return NAN;
  return t;
}

static void detectarDs18() {
  ds18.begin();
  hayDs18 = ds18.getDeviceCount() > 0;
  if (hayDs18) {
    ds18.setResolution(11);
    ds18.setWaitForConversion(false);
    ds18.requestTemperatures();
  }
}

static void cargarCalibracion() {
  Preferences prefs;
  prefs.begin("sigmap", true);                 // solo lectura
  turbVLimpia = prefs.getFloat("turb_v0", TURB_V_CURVA_LIMPIA);
  phM = prefs.getFloat("ph_m", PH_M_FABRICA);
  phB = prefs.getFloat("ph_b", PH_B_FABRICA);
  prefs.end();
}

#if MODO_DEMO
/** Valores simulados realistas, con excursiones para ver los colores de alerta. */
static void lecturaDemo(float& temp, float& ph, float& turb) {
  const float t = millis() / 1000.0f;
  temp = 27.0f + 2.2f * sinf(t / 9.0f) + random(-10, 10) / 40.0f;
  ph   = 7.15f + 0.85f * sinf(t / 13.0f) + random(-10, 10) / 60.0f;
  turb = 28.0f + 30.0f * (0.5f + 0.5f * sinf(t / 7.0f)) + random(0, 10);
}
#endif

// ============================================================================
// Fase 1: animacion de encendido
// ============================================================================
static Burbuja burbujas[12];

static void iniciarBurbujas() {
  for (uint8_t i = 0; i < 12; i++) {
    const bool izquierda = i % 2 == 0;
    burbujas[i] = { (int16_t)(izquierda ? random(14, 72) : random(408, 466)),
                    (int16_t)random(330, 520), (uint8_t)random(3, 8), (uint8_t)random(2, 5) };
  }
}

/** Mueve las burbujas por los costados; las borra con el color del fondo. */
static void moverBurbujas() {
  for (uint8_t i = 0; i < 12; i++) {
    Burbuja& b = burbujas[i];
    tft.fillCircle(b.x, b.y, b.r + 1, C_FONDO);
    b.y -= b.vel;
    b.x += (int16_t)(sinf((b.y + i * 40) / 18.0f) * 1.2f);
    if (b.y < -10) { b.y = random(330, 380); b.r = random(3, 8); }
    if (b.y < 330) {
      tft.drawCircle(b.x, b.y, b.r, mezclar(C_FONDO, C_CIAN, 0.85f));
      tft.drawPixel(b.x - b.r / 3, b.y - b.r / 3, C_BLANCO);
    }
  }
}

static void bootOndas() {
  const int16_t cx = 240, cy = 118;
  for (int16_t r = 0; r <= 300; r += 4) {
    for (uint8_t k = 0; k < 3; k++) {
      const int16_t rr = r - k * 44;
      if (rr <= 0) continue;
      const float intensidad = 1.0f - rr / 260.0f;
      const uint16_t color = k == 0 ? C_CIAN : (k == 1 ? C_TURQUESA : C_AZUL);
      if (intensidad > 0) {
        tft.drawCircle(cx, cy, rr, mezclar(C_FONDO, color, intensidad));
        tft.drawCircle(cx, cy, rr + 1, mezclar(C_FONDO, color, intensidad * 0.6f));
      }
      if (rr > 4) {                                   // borra el anillo anterior
        tft.drawCircle(cx, cy, rr - 4, C_FONDO);
        tft.drawCircle(cx, cy, rr - 3, C_FONDO);
      }
    }
    delay(9);
  }
  tft.fillScreen(C_FONDO);
}

static void bootLogo() {
  const int16_t cx = 240, cy = 92;
  for (uint8_t s = 1; s <= 12; s++) {                 // la gota crece
    dibujarGota(tft, cx, cy, s * 2, mezclar(C_AZUL, C_CIAN, s / 12.0f));
    delay(22);
  }
  tft.fillCircle(cx - 7, cy - 4, 4, C_BLANCO);       // brillo
  tft.drawCircle(cx, cy, 30, C_TURQUESA);
  tft.drawCircle(cx, cy, 31, mezclar(C_FONDO, C_TURQUESA, 0.5f));

  // Titulo letra por letra
  const char* titulo = "SIGMAP AQUA";
  tft.setFreeFont(&FreeSansBold24pt7b);
  tft.setTextDatum(TL_DATUM);
  const int16_t ancho = tft.textWidth(titulo);
  int16_t x = 240 - ancho / 2;
  char letra[2] = {0, 0};
  for (uint8_t i = 0; titulo[i]; i++) {
    letra[0] = titulo[i];
    tft.setTextColor(i < 6 ? C_BLANCO : C_CIAN);
    tft.drawString(letra, x, 136);
    x += tft.textWidth(letra);
    delay(55);
  }

  // Linea de brillo que se abre desde el centro
  for (int16_t w = 0; w <= ancho / 2; w += 6) {
    tft.drawFastHLine(240 - w, 184, w * 2, mezclar(C_TURQUESA, C_ESMERALDA, (float)w / (ancho / 2)));
    tft.drawFastHLine(240 - w, 185, w * 2, C_TURQUESA);
    delay(8);
  }

  // Subtitulo que aparece gradualmente
  tft.setTextFont(2);
  tft.setTextDatum(TC_DATUM);
  for (uint8_t p = 1; p <= 6; p++) {
    tft.setTextColor(mezclar(C_FONDO, C_TENUE, p / 6.0f), C_FONDO);
    tft.drawString("Smart Water & IoT Telemetry", 240, 194);
    delay(45);
  }
}

/** Avanza la barra de carga de 'desde' a 'hasta' % con burbujas animadas. */
static void avanzarCarga(uint8_t desde, uint8_t hasta, const char* texto) {
  const int16_t bx = 90, by = 258, bw = 300, bh = 14;
  tft.setTextFont(2);
  tft.setTextDatum(TC_DATUM);
  tft.setTextColor(C_TENUE, C_FONDO);
  tft.setTextPadding(360);
  tft.drawString(texto, 240, 230);
  tft.setTextPadding(0);

  for (uint8_t p = desde; p <= hasta; p++) {
    const int16_t lleno = (bw - 4) * p / 100;
    for (int16_t x = 0; x < lleno; x++) {             // degradado esmeralda -> cian
      tft.drawFastVLine(bx + 2 + x, by + 2, bh - 4, mezclar(C_ESMERALDA, C_CIAN, (float)x / (bw - 4)));
    }
    char pct[8];
    snprintf(pct, sizeof(pct), "%u%%", p);
    tft.setTextDatum(TR_DATUM);
    tft.setTextColor(C_CIAN, C_FONDO);
    tft.setTextPadding(40);
    tft.drawString(pct, bx + bw, by + 20);
    tft.setTextPadding(0);
    tft.setTextDatum(TC_DATUM);
    moverBurbujas();
    delay(14);
  }
}

static void bootCarga() {
  const int16_t bx = 90, by = 258, bw = 300, bh = 14;
  tft.drawRoundRect(bx, by, bw, bh, 7, C_BORDE);
  iniciarBurbujas();

  char linea[48];
  avanzarCarga(0, 20, "Inicializando pantalla... OK");

#if MODO_DEMO
  avanzarCarga(21, 45, "Modo demostracion: sensores simulados");
  avanzarCarga(46, 90, "Generando datos de prueba... OK");
#else
  snprintf(linea, sizeof(linea), "Sonda de pH (GPIO%u)... %.2f OK", PIN_PH, leerPh());
  avanzarCarga(21, 45, linea);

  const float ntu = leerTurbidez();
  snprintf(linea, sizeof(linea), "Turbidez TS-300B... %.0f NTU OK", ntu);
  avanzarCarga(46, 70, linea);

  detectarDs18();
  avanzarCarga(71, 90, hayDs18 ? "Temperatura DS18B20... OK"
                               : "Temperatura DS18B20... SIN SONDA");
#endif
  avanzarCarga(91, 100, "Sistema listo. Iniciando monitoreo...");
  delay(350);
}

/** Barrido de transicion hacia el tablero. */
static void bootTransicion() {
  for (int16_t x = 0; x <= 480 + 24; x += 12) {
    if (x < 480) tft.fillRect(x, 0, 12, 320, C_CIAN);
    if (x >= 24) tft.fillRect(x - 24, 0, 12, 320, C_FONDO);
    delay(6);
  }
}

static void animacionEncendido() {
  tft.fillScreen(C_FONDO);
  bootOndas();
  bootLogo();
  bootCarga();
  bootTransicion();
}

// ============================================================================
// Fase 2: tablero en tiempo real
// ============================================================================
static void dibujarCabeceraFija() {
  dibujarGota(tft, 20, 26, 8, C_CIAN);
  tft.fillCircle(17, 24, 2, C_BLANCO);
  tft.setTextDatum(TL_DATUM);
  tft.setTextFont(4);
  tft.setTextColor(C_BLANCO, C_FONDO);
  tft.drawString("SIGMAP", 36, 8);
  tft.setTextColor(C_CIAN, C_FONDO);
  tft.drawString("AQUA", 36 + tft.textWidth("SIGMAP "), 8);
  for (int16_t x = 0; x < 480; x++) {                 // linea degradada
    tft.drawPixel(x, HEADER_H, mezclar(C_CIAN, C_ESMERALDA, x / 480.0f));
  }
}

/** Texto de estado de la cabecera; solo se redibuja cuando cambia. */
static void dibujarCabeceraEstado(bool capturando) {
  const int8_t modo = capturando ? 1 : 0;
  static uint32_t lecturasDibujadas = UINT32_MAX;
  if (modo == cabeceraDibujada && lecturasDibujadas == nLecturas) return;
  cabeceraDibujada = modo;
  lecturasDibujadas = nLecturas;

  char texto[40];
  if (capturando) snprintf(texto, sizeof(texto), "Capturando datos...");
  else snprintf(texto, sizeof(texto), "EN VIVO  #%lu", (unsigned long)nLecturas);
  tft.setTextFont(2);
  tft.setTextDatum(MR_DATUM);
  tft.setTextColor(capturando ? C_CIAN : C_NEON, C_FONDO);
  tft.setTextPadding(170);
  tft.drawString(texto, RADAR_X - 6, 20);
  tft.setTextPadding(0);
}

static void dibujarRadar(uint32_t ahora) {
  const int16_t c = RADAR_D / 2;
  sprRadar.fillSprite(C_FONDO);
  const uint32_t t = ahora - inicioPulsoMs;
  if (nLecturas > 0 && t < PULSO_MS) {
    const float p = (float)t / PULSO_MS;
    // Onda que se expande y se apaga
    sprRadar.drawCircle(c, c, 4 + p * 12, mezclar(C_FONDO, C_CIAN, 1.0f - p));
    sprRadar.drawCircle(c, c, 15, C_CIAN);
    // Haz giratorio con estela
    const float ang = p * 3.0f * PI;
    for (uint8_t k = 0; k < 4; k++) {
      const float a = ang - k * 0.28f;
      sprRadar.drawLine(c, c, c + cosf(a) * 14, c + sinf(a) * 14,
                        mezclar(C_FONDO, C_CIAN, 1.0f - k * 0.25f));
    }
    sprRadar.fillCircle(c, c, 3, C_BLANCO);
  } else {
    // Reposo: latido suave en verde
    const float b = (sinf(ahora / 380.0f) + 1.0f) * 0.5f;
    sprRadar.drawCircle(c, c, 15, C_BORDE);
    sprRadar.drawCircle(c, c, 9, mezclar(C_FONDO, C_NEON, b * 0.4f));
    sprRadar.fillCircle(c, c, 3 + b * 2, mezclar(C_PANEL, C_NEON, 0.5f + b * 0.5f));
  }
  sprRadar.pushSprite(RADAR_X, RADAR_Y);
}

static void dibujarTarjetaFija(const Canal& c) {
  tft.fillRoundRect(c.x, CARD_Y, CARD_W, CARD_H, 10, C_PANEL);
  tft.drawRoundRect(c.x, CARD_Y, CARD_W, CARD_H, 10, C_BORDE);
  tft.fillRect(c.x + 10, CARD_Y + 1, 30, 2, c.color);          // acento
  tft.setTextFont(2);
  tft.setTextDatum(TL_DATUM);
  tft.setTextColor(c.color, C_PANEL);
  tft.drawString(c.nombre, c.x + 10, CARD_Y + 6);

  char rango[24];
  snprintf(rango, sizeof(rango), "opt %g-%g", c.optMin, c.optMax);
  tft.setTextFont(1);
  tft.setTextColor(C_TENUE, C_PANEL);
  tft.drawString(rango, c.x + 10, CARD_Y + 90);
}

static void dibujarEstado(Canal& c) {
  if (c.estado == c.estadoDibujado) return;
  c.estadoDibujado = c.estado;
  static const char* textos[] = { "SIN SONDA", "OPTIMO", "RIESGO", "CRITICO" };
  const uint16_t color = colorEstado(c.estado, c.color);
  const int16_t w = 60, h = 14, x = c.x + CARD_W - w - 8, y = CARD_Y + CARD_H - h - 6;
  tft.fillRoundRect(x, y, w, h, 7, mezclar(C_PANEL, color, 0.25f));
  tft.drawRoundRect(x, y, w, h, 7, color);
  tft.setTextFont(1);
  tft.setTextDatum(MC_DATUM);
  tft.setTextColor(color);
  tft.drawString(textos[c.estado], x + w / 2, y + h / 2 + 1);
}

static void dibujarValor(const Canal& c) {
  sprValor.fillSprite(C_PANEL);
  char txt[16];
  if (isnan(c.objetivo)) snprintf(txt, sizeof(txt), "--");
  else snprintf(txt, sizeof(txt), "%.*f", c.decimales, c.mostrado);

  sprValor.setFreeFont(&FreeSansBold18pt7b);
  sprValor.setTextDatum(BL_DATUM);
  sprValor.setTextColor(isnan(c.objetivo) ? C_GRIS : c.color);
  sprValor.drawString(txt, 0, VAL_H - 3);
  int16_t x = sprValor.textWidth(txt) + 5;

  sprValor.setTextFont(2);
  sprValor.setTextColor(C_TENUE);
  if (c.unidad[0] == 'C' && c.unidad[1] == '\0') {              // grados
    sprValor.drawCircle(x + 2, VAL_H - 17, 2, C_TENUE);
    x += 6;
  }
  sprValor.drawString(c.unidad, x, VAL_H - 4);
  sprValor.pushSprite(c.x + 10, CARD_Y + 26);
}

static void dibujarBarra(const Canal& c) {
  sprBarra.fillSprite(C_PANEL);
  sprBarra.fillRoundRect(0, 0, BAR_W, BAR_H, BAR_H / 2, C_PISTA);
  if (!isnan(c.objetivo)) {
    const int16_t w = max<int16_t>(BAR_H, normalizar(c, c.mostrado) * BAR_W);
    const uint16_t color = colorEstado(calcularEstado(c, c.mostrado), c.color);
    sprBarra.fillRoundRect(0, 0, w, BAR_H, BAR_H / 2, mezclar(C_PISTA, color, 0.55f));
    sprBarra.fillRoundRect(0, 3, w, BAR_H - 6, (BAR_H - 6) / 2, color);
    sprBarra.fillCircle(w - BAR_H / 2, BAR_H / 2, BAR_H / 2 - 1, C_BLANCO);  // punta brillante
  }
  // Marcas del rango optimo
  const int16_t x1 = normalizar(c, c.optMin) * (BAR_W - 1);
  const int16_t x2 = normalizar(c, c.optMax) * (BAR_W - 1);
  sprBarra.drawFastVLine(x1, 0, BAR_H, C_BLANCO);
  sprBarra.drawFastVLine(x2, 0, BAR_H, C_BLANCO);
  sprBarra.pushSprite(c.x + 10, CARD_Y + 70);
}

static void dibujarPanelGraficaFijo() {
  tft.fillRoundRect(8, GRAF_PANEL_Y, 464, 320 - GRAF_PANEL_Y - 2, 10, C_PANEL);
  tft.drawRoundRect(8, GRAF_PANEL_Y, 464, 320 - GRAF_PANEL_Y - 2, 10, C_BORDE);
  tft.setTextFont(2);
  tft.setTextDatum(TL_DATUM);
  tft.setTextColor(C_BLANCO, C_PANEL);
  tft.drawString("Tendencia en vivo", 18, GRAF_PANEL_Y + 5);

  int16_t x = 466;                                    // leyenda, de derecha a izquierda
  tft.setTextColor(C_TENUE, C_PANEL);
  tft.setTextDatum(TR_DATUM);
  for (int8_t i = N_CANALES - 1; i >= 0; i--) {
    const char* etiqueta = canales[i].nombre;
    tft.drawString(etiqueta, x, GRAF_PANEL_Y + 5);
    x -= tft.textWidth(etiqueta) + 6;
    tft.fillRoundRect(x - 12, GRAF_PANEL_Y + 11, 12, 4, 2, canales[i].color);
    x -= 22;
  }
}

static int16_t yGrafica(const Canal& c, float v) {
  return (G_H - 5) - normalizar(c, v) * (G_H - 10);
}

/**
 * Grafica normalizada (cada parametro en su propia escala) dentro de un sprite.
 * @param fase 0..1 del desplazamiento: el punto nuevo entra desde la derecha.
 */
static void dibujarGrafica(float fase) {
  if (!graficaOk) return;
  sprGrafica.fillSprite(C_PANEL);
  for (uint8_t i = 0; i <= 4; i++) {                  // rejilla punteada
    const int16_t y = 5 + i * (G_H - 10) / 4;
    for (int16_t x = 0; x < G_W; x += 6) sprGrafica.drawFastHLine(x, y, 3, C_REJILLA);
  }
  if (nPuntos < 2) { sprGrafica.pushSprite(G_X, G_Y); return; }

  const float dx = (float)(G_W - 10) / (PUNTOS - 1);
  const float desplazamiento = (1.0f - fase) * dx;

  for (uint8_t k = 0; k < N_CANALES; k++) {
    const Canal& c = canales[k];
    const uint16_t relleno = mezclar(C_PANEL, c.color, 0.16f);
    bool hayPrevio = false;
    int16_t px = 0, py = 0;
    // El historial se llena por el final: los datos validos son los ultimos nPuntos.
    for (uint8_t i = PUNTOS - nPuntos; i < PUNTOS; i++) {
      const float v = c.historial[i];
      if (isnan(v)) { hayPrevio = false; continue; }
      const int16_t x = (G_W - 6) - (PUNTOS - 1 - i) * dx + desplazamiento;
      const int16_t y = yGrafica(c, v);
      if (hayPrevio) {
        if (k == CH_PH) {                             // area bajo la curva de pH
          for (int16_t xx = max<int16_t>(px, 0); xx <= x && xx < G_W; xx++) {
            const int16_t yy = py + (int32_t)(y - py) * (xx - px) / max<int16_t>(1, x - px);
            sprGrafica.drawFastVLine(xx, yy, G_H - yy, relleno);
          }
        }
        sprGrafica.drawLine(px, py, x, y, c.color);
        sprGrafica.drawLine(px, py + 1, x, y + 1, c.color);
      }
      hayPrevio = true; px = x; py = y;
    }
    if (hayPrevio) {                                  // ultimo punto con brillo
      sprGrafica.fillCircle(px, py, 5, mezclar(C_PANEL, c.color, 0.35f));
      sprGrafica.fillCircle(px, py, 2, C_BLANCO);
    }
  }
  sprGrafica.pushSprite(G_X, G_Y);
}

static void dibujarTableroFijo() {
  tft.fillScreen(C_FONDO);
  dibujarCabeceraFija();
  for (uint8_t i = 0; i < N_CANALES; i++) {
    canales[i].estadoDibujado = (Estado)255;          // fuerza el primer dibujo
    dibujarTarjetaFija(canales[i]);
    dibujarEstado(canales[i]);
    dibujarValor(canales[i]);
    dibujarBarra(canales[i]);
  }
  dibujarPanelGraficaFijo();
  dibujarGrafica(1.0f);
}

// ============================================================================
// Ciclo de lectura y animacion
// ============================================================================
static void tomarLectura() {
  float valores[N_CANALES];
#if MODO_DEMO
  lecturaDemo(valores[CH_TEMP], valores[CH_PH], valores[CH_TURB]);
#else
  if (!hayDs18 && nLecturas % 15 == 0) detectarDs18();   // por si se reconecta
  valores[CH_TEMP] = leerTemperatura();
  valores[CH_PH]   = leerPh();
  valores[CH_TURB] = leerTurbidez();
#endif

  if (nPuntos < PUNTOS) nPuntos++;
  for (uint8_t k = 0; k < N_CANALES; k++) {
    Canal& c = canales[k];
    memmove(c.historial, c.historial + 1, sizeof(float) * (PUNTOS - 1));
    c.historial[PUNTOS - 1] = valores[k];
    c.objetivo = valores[k];
    c.estado = calcularEstado(c, c.objetivo);
    if (!isnan(c.objetivo) && isnan(c.mostrado)) c.mostrado = c.escalaMin;
  }
  nLecturas++;
  Serial.printf("[Lectura #%lu] Temp %.2f C | pH %.2f | Turbidez %.0f NTU\n",
                (unsigned long)nLecturas, valores[CH_TEMP], valores[CH_PH], valores[CH_TURB]);
}

/** Paso de interpolacion; devuelve true si el valor mostrado cambio. */
static bool interpolar(Canal& c) {
  if (isnan(c.objetivo)) return false;
  const float diff = c.objetivo - c.mostrado;
  const float minimo = powf(10.0f, -(int)c.decimales) * 0.5f;
  if (fabsf(diff) < minimo) {
    if (c.mostrado == c.objetivo) return false;
    c.mostrado = c.objetivo;
    return true;
  }
  c.mostrado += diff * SUAVIZADO;
  return true;
}

static void animarFrame(uint32_t ahora) {
  for (uint8_t k = 0; k < N_CANALES; k++) {
    Canal& c = canales[k];
    dibujarEstado(c);
    const bool sinDato = isnan(c.objetivo);
    static bool estabaSinDato[N_CANALES] = {true, true, true};
    if (interpolar(c) || sinDato != estabaSinDato[k]) {
      estabaSinDato[k] = sinDato;
      dibujarValor(c);
      dibujarBarra(c);
    }
  }

  const uint32_t tScroll = ahora - inicioScrollMs;
  if (tScroll < SCROLL_MS) {
    dibujarGrafica((float)tScroll / SCROLL_MS);
    graficaPendiente = true;
  } else if (graficaPendiente) {
    dibujarGrafica(1.0f);
    graficaPendiente = false;
  }

  dibujarRadar(ahora);
  dibujarCabeceraEstado(nLecturas > 0 && ahora - inicioPulsoMs < PULSO_MS);
}

// ============================================================================
void setup() {
  Serial.begin(115200);
  delay(300);
  Serial.println("\n[SIGMAP AQUA] Pantalla de telemetria");
  randomSeed(esp_random());

  analogReadResolution(12);
  analogSetAttenuation(ADC_11db);
  cargarCalibracion();
  for (uint8_t k = 0; k < N_CANALES; k++) {
    canales[k].objetivo = NAN;
    canales[k].mostrado = NAN;
    canales[k].estado = SIN_DATO;
    for (uint8_t i = 0; i < PUNTOS; i++) canales[k].historial[i] = NAN;
  }

  tft.init();
  tft.setRotation(SCREEN_ROTATION);

  sprValor.createSprite(VAL_W, VAL_H);
  sprBarra.createSprite(BAR_W, BAR_H);
  sprRadar.createSprite(RADAR_D, RADAR_D);
  sprGrafica.setColorDepth(8);                       // 59 KB en vez de 118 KB
  graficaOk = sprGrafica.createSprite(G_W, G_H) != nullptr;
  if (!graficaOk) Serial.println("[Pantalla] Sin RAM para la grafica; se omite.");

  animacionEncendido();
  dibujarTableroFijo();
  Serial.printf("[Pantalla] Tablero listo: %d x %d px\n", tft.width(), tft.height());
}

void loop() {
  const uint32_t ahora = millis();
  if (nLecturas == 0 || ahora - ultimaLecturaMs >= INTERVALO_LECTURA_MS) {
    ultimaLecturaMs = ahora;
    tomarLectura();
    inicioPulsoMs = inicioScrollMs = millis();
  }
  if (ahora - ultimoFrameMs >= FRAME_MS) {
    ultimoFrameMs = ahora;
    animarFrame(millis());
  }
}
