/**
 * pantalla_tft.h — SIGMAP AQUA · Pantalla de telemetria del nodo de ingesta
 * Pantalla 3.5" RPi Display (ILI9486, 480x320) con TFT_eSPI.
 *
 * Todo corre en el hilo principal (setup/loop), igual que pantalla_imagen.ino,
 * que es la forma probada en esta pantalla. (Una version con tarea paralela de
 * FreeRTOS dejaba la pantalla en blanco.) La animacion avanza en los ratos
 * libres del ciclo: pantallaEsperar() reemplaza a los delay() del sketch, asi
 * que mientras el nodo espera al WiFi o al siguiente envio, la pantalla anima.
 *
 * Uso desde bioaqua_ingesta.ino:
 *   pantallaIniciar()                 en setup(), ANTES de encender el WiFi
 *   pantallaEsperar(ms)               en lugar de delay(ms)
 *   pantallaTerminarArranque(wifiOk)  al final del setup(): muestra el tablero
 *   pantallaWifi(true/false)          al saber si hay WiFi
 *   pantallaInicioLote()              al empezar a leer los sensores
 *   pantallaValor(PANT_PH, valor)     por cada sensor leido
 *   pantallaPublicar()                al terminar el lote
 *   pantallaEnvio(PANT_ENVIADO)       con el resultado del POST
 *   pantallaEstadoServidor(canal, "critico")  estado que calculo el software
 *
 * REGLA DE ORO: tft.init() SOLO con el WiFi APAGADO. Con el router cerca, el
 * pico de corriente del radio WiFi daña la secuencia de arranque del ILI9486 y
 * la pantalla queda en blanco (solo la luz). Dibujar con WiFi encendido si
 * funciona; inicializar no. Por eso:
 *   - pantallaIniciar() va en el setup() ANTES de conectarWiFi().
 *   - pantallaReiniciar() (comando PANTALLA) apaga el WiFi, reinicializa y
 *     deja que el loop() se reconecte solo.
 *
 * MISMOS DATOS QUE EL SOFTWARE: la pantalla muestra el valor exacto que se
 * envia (redondeado a 2 decimales, igual que el JSON) y, cuando el software
 * responde, el estado (NORMAL / RIESGO / CRITICO) que el mismo software le
 * asigno a esa lectura. Solo sin conexion usa una estimacion local.
 *
 * Pines: los del User_Setup.h de TFT_eSPI (MOSI 23, SCK 18, CS 5, DC 16).
 * RST de la pantalla va al pin EN del ESP32 y el touch no se usa: GPIO17,
 * 19 y 22 quedan para la camara (camara.h). No chocan con los sensores
 * (32, 34, 35) ni con el LED (2).
 *
 * SIN PARPADEO: fillScreen() solo al armar cada pantalla; despues se
 * redibujan unicamente las zonas que cambian, siempre por sprites.
 */
#pragma once

#include <SPI.h>
#include <WiFi.h>
#include <TFT_eSPI.h>
#include <esp_system.h>

// ============================================================================
// API publica
// ============================================================================
enum CanalPantalla : uint8_t { PANT_TEMP = 0, PANT_PH = 1, PANT_TURB = 2 };
enum ResultadoEnvio : uint8_t { PANT_SIN_ENVIO = 0, PANT_ENVIADO, PANT_SIN_WIFI, PANT_SIN_SERVIDOR };

static void pantallaIniciar();
static void pantallaEsperar(uint32_t ms);
static void pantallaTerminarArranque(bool wifiOk);
static void pantallaWifi(bool conectado);
static void pantallaCalibracion(bool phGuardada, bool turbidezGuardada);
static void pantallaInicioLote();
static void pantallaValor(CanalPantalla canal, float valor);
static void pantallaEstadoServidor(CanalPantalla canal, const char* estado);
static void pantallaPublicar();
static void pantallaEnvio(ResultadoEnvio resultado);
static void pantallaDiagnostico();
static void pantallaReiniciar();

// ============================================================================
// Implementacion (todo en el namespace para no chocar con el sketch)
// ============================================================================
namespace pant {

// ---------------------------------------------------------------- config
static const uint8_t  ROTACION   = 1;       // horizontal 480x320
static const uint32_t FRAME_MS   = 33;      // ~30 fps
static const uint32_t PULSO_MS   = 900;     // radar al capturar
static const uint32_t SCROLL_MS  = 420;     // desplazamiento de la grafica
static const float    SUAVIZADO  = 0.20f;   // interpolacion de valores
static const uint8_t  PUNTOS     = 60;      // historial de la grafica
static const uint8_t  N_BURBUJAS = 48;      // burbujas de los costados en el encendido
static const uint8_t  N_OLEADA   = 70;      // burbujas que borran el nombre al final
// Del 100 % de la carga al tablero: 400 + 1600 + 3500 + 2500 = 8 s exactos
// (cada etapa se controla por tiempo, no por cuadros).
static const uint32_t CIERRE_CARGA_MS = 400;
static const uint32_t PAUSA_NOMBRE_MS = 1600;  // tiempo para leer "SIGMAP AQUA"
static const uint32_t OLEADA_MS       = 3500;  // las burbujas borran el nombre
static const uint32_t PECES_MS        = 2500;  // alevines cruzando la pantalla
static const uint8_t  N_PECES         = 7;
// Zoom minimo de cada franja de la grafica (temp, pH, turbidez): si el valor
// casi no cambia, se ve una linea tranquila en vez de exagerar el ruido.
static const float    SPAN_MIN[] = {0.6f, 0.15f, 25.0f};
// Lecturas promediadas para dibujar la linea de cada franja. La turbidez del
// TS-300B tiene mucho ruido entre lecturas: con 3 la curva se lee bien; los
// puntos de cada lectura real se siguen marcando.
static const uint8_t  SUAVIZADO_LINEA[] = {1, 1, 3};

// ---------------------------------------------------------------- paleta
constexpr uint16_t rgb(uint8_t r, uint8_t g, uint8_t b) {
  return ((r & 0xF8) << 8) | ((g & 0xFC) << 3) | (b >> 3);
}
static const uint16_t C_FONDO     = rgb(3, 8, 20);
static const uint16_t C_PANEL     = rgb(9, 20, 40);
static const uint16_t C_BORDE     = rgb(26, 58, 98);
static const uint16_t C_PISTA     = rgb(20, 36, 62);
static const uint16_t C_REJILLA   = rgb(28, 48, 78);
static const uint16_t C_TENUE     = rgb(120, 150, 185);
static const uint16_t C_BLANCO    = rgb(235, 245, 255);
static const uint16_t C_CIAN      = rgb(0, 229, 255);
static const uint16_t C_TURQUESA  = rgb(0, 200, 175);
static const uint16_t C_ESMERALDA = rgb(0, 220, 120);
static const uint16_t C_NEON      = rgb(60, 255, 40);
static const uint16_t C_AMBAR     = rgb(255, 190, 0);
static const uint16_t C_CORAL     = rgb(255, 70, 110);
static const uint16_t C_AZUL      = rgb(0, 70, 160);
static const uint16_t C_GRIS      = rgb(90, 100, 115);

// ---------------------------------------------------------------- geometria
static const int16_t HEADER_H = 40;
static const int16_t CARD_Y = 46, CARD_W = 152, CARD_H = 106;
static const int16_t VAL_W = 134, VAL_H = 34;
static const int16_t BAR_W = 132, BAR_H = 12;
static const int16_t GRAF_PANEL_Y = 158;
static const int16_t G_X = 14, G_Y = 182, G_W = 452, G_H = 130;
static const int16_t RADAR_D = 34, RADAR_X = 440, RADAR_Y = 3;

// ---------------------------------------------------------------- modelo
enum Estado : uint8_t { SIN_DATO, NORMAL, RIESGO, CRITICO };

struct Canal {
  const char* nombre;
  const char* unidad;           // "C" se dibuja con simbolo de grados
  uint16_t    color;
  float       escalaMin, escalaMax;
  float       optMin, optMax;   // rango optimo (Engorde, como en la web)
  float       margen;           // fuera del optimo hasta aqui = riesgo
  uint8_t     decimales;
  int16_t     x;
  float       objetivo;         // ultima lectura (NAN = sin dato)
  float       mostrado;         // valor animado
  Estado      estado;
  Estado      estadoDibujado;
  bool        sinDatoDibujado;
  float       historial[PUNTOS];
};

static Canal canales[] = {
  // Los decimales son los mismos que viajan en el JSON (2), para que la
  // pantalla y el software muestren el mismo numero.
  { "TEMPERATURA", "C",   C_AMBAR, 15, 35,  24, 30,     2.0f,  2,   8 },
  { "pH",          "pH",  C_CIAN,  4,  10,  6.5f, 7.8f, 0.5f,  2, 164 },
  { "TURBIDEZ",    "NTU", C_NEON,  0,  100, 0, 50,      50.0f, 2, 320 },
};
static const uint8_t N_CANALES = sizeof(canales) / sizeof(canales[0]);

struct Burbuja { int16_t x, y; uint8_t r; uint8_t vel; bool rellena; };

// ---------------------------------------------------------------- lote de lecturas
static float    loteValores[N_CANALES] = {NAN, NAN, NAN};   // lote en armado
static float    publicados[N_CANALES]  = {NAN, NAN, NAN};   // ultimo lote completo
static int8_t   estadoServidor[N_CANALES] = {-1, -1, -1};   // estado del software (-1 = aun no)
static bool     hayEstadoServidor = false;
static uint32_t secuenciaLote = 0;
static int8_t   estadoWifi = -1;          // -1 conectando, 0 no, 1 si
static uint8_t  resultadoEnvio = PANT_SIN_ENVIO;
static uint32_t lotesEnviados = 0;
static uint32_t versionEnvio = 0;
static const char* etapa = "sin iniciar";   // diagnostico por serie
static uint32_t frames = 0;
static bool     calPh = false, calTurbidez = false;      // calibracion guardada en NVS
static bool     reinicioPedido = false;                   // comando PANTALLA
static bool     enTablero = false;                        // false = animacion de encendido
static uint8_t  progresoCarga = 0;
static uint32_t ultimoFrameMs = 0;


// ---------------------------------------------------------------- estado de la pantalla
static TFT_eSPI    tft;
static TFT_eSprite sprValor(&tft);
static TFT_eSprite sprBarra(&tft);
static TFT_eSprite sprGrafica(&tft);
static TFT_eSprite sprRadar(&tft);
static bool        graficaOk = false;
static Burbuja     burbujas[N_BURBUJAS];

static uint8_t  nPuntos = 0;
static uint32_t nLecturas = 0;
static uint32_t secuenciaVista = 0;
static uint32_t inicioPulsoMs = 0, inicioScrollMs = 0;
static bool     graficaPendiente = true;

// ============================================================================
// Utilidades
// ============================================================================
static uint16_t mezclar(uint16_t a, uint16_t b, float t) {
  return tft.alphaBlend((uint8_t)(constrain(t, 0.0f, 1.0f) * 255), b, a);
}

static float normalizar(const Canal& c, float v) {
  return constrain((v - c.escalaMin) / (c.escalaMax - c.escalaMin), 0.0f, 1.0f);
}

static Estado calcularEstado(const Canal& c, float v) {
  if (isnan(v)) return SIN_DATO;
  if (v >= c.optMin && v <= c.optMax) return NORMAL;
  if (v >= c.optMin - c.margen && v <= c.optMax + c.margen) return RIESGO;
  return CRITICO;
}

static uint16_t colorEstado(Estado e, uint16_t colorCanal) {
  switch (e) {
    case NORMAL:  return colorCanal;
    case RIESGO:  return C_AMBAR;
    case CRITICO: return C_CORAL;
    default:      return C_GRIS;
  }
}

static void dibujarGota(int16_t cx, int16_t cy, int16_t r, uint16_t color) {
  tft.fillCircle(cx, cy, r, color);
  tft.fillTriangle(cx - r + 1, cy - r / 3, cx + r - 1, cy - r / 3, cx, cy - r * 2, color);
}

// ============================================================================
// Animacion de encendido
// ============================================================================
static void nuevaBurbuja(Burbuja& b, bool alInicio) {
  const bool izquierda = random(0, 2) == 0;
  b.x = izquierda ? random(10, 82) : random(398, 470);
  b.y = alInicio ? random(40, 460) : random(328, 380);
  b.r = random(2, 10);
  b.vel = random(1, 5);
  b.rellena = random(0, 4) == 0;
}

static void iniciarBurbujas() {
  for (uint8_t i = 0; i < N_BURBUJAS; i++) nuevaBurbuja(burbujas[i], true);
}

/** Sube las burbujas por los costados; se borran con el color de fondo. */
static void moverBurbujas() {
  for (uint8_t i = 0; i < N_BURBUJAS; i++) {
    Burbuja& b = burbujas[i];
    if (b.y < 330) tft.fillCircle(b.x, b.y, b.r + 1, C_FONDO);
    b.y -= b.vel;
    b.x += (int16_t)(sinf((b.y + i * 37) / 16.0f) * 1.3f);
    b.x = constrain(b.x, 6, 474);
    if (b.y < -12) nuevaBurbuja(b, false);
    if (b.y < 330) {
      const uint16_t borde = mezclar(C_FONDO, i % 3 ? C_CIAN : C_TURQUESA, 0.9f);
      if (b.rellena) tft.fillCircle(b.x, b.y, b.r, mezclar(C_FONDO, C_CIAN, 0.35f));
      tft.drawCircle(b.x, b.y, b.r, borde);
      if (b.r > 3) tft.drawPixel(b.x - b.r / 3, b.y - b.r / 3, C_BLANCO);
    }
  }
}

static void pausaConBurbujas(uint32_t ms) {
  const uint32_t inicio = millis();
  while (millis() - inicio < ms) { moverBurbujas(); delay(16); }
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
      if (rr > 4) { tft.drawCircle(cx, cy, rr - 4, C_FONDO); tft.drawCircle(cx, cy, rr - 3, C_FONDO); }
    }
    delay(9);
  }
  tft.fillScreen(C_FONDO);
}

static void bootLogo() {
  const int16_t cx = 240, cy = 92;
  for (uint8_t s = 1; s <= 12; s++) {
    dibujarGota(cx, cy, s * 2, mezclar(C_AZUL, C_CIAN, s / 12.0f));
    moverBurbujas();
    delay(22);
  }
  tft.fillCircle(cx - 7, cy - 4, 4, C_BLANCO);
  tft.drawCircle(cx, cy, 30, C_TURQUESA);
  tft.drawCircle(cx, cy, 31, mezclar(C_FONDO, C_TURQUESA, 0.5f));

  const char* titulo = "SIGMAP AQUA";
  tft.setFreeFont(&FreeSansBold24pt7b);
  tft.setTextDatum(TL_DATUM);
  const int16_t ancho = tft.textWidth(titulo);
  int16_t x = 240 - ancho / 2;
  char letra[2] = {0, 0};
  for (uint8_t i = 0; titulo[i]; i++) {
    letra[0] = titulo[i];
    tft.setFreeFont(&FreeSansBold24pt7b);
    tft.setTextDatum(TL_DATUM);
    tft.setTextColor(i < 6 ? C_BLANCO : C_CIAN);
    tft.drawString(letra, x, 136);
    x += tft.textWidth(letra);
    pausaConBurbujas(55);
  }

  for (int16_t w = 0; w <= ancho / 2; w += 6) {
    tft.drawFastHLine(240 - w, 184, w * 2, mezclar(C_TURQUESA, C_ESMERALDA, (float)w / (ancho / 2)));
    tft.drawFastHLine(240 - w, 185, w * 2, C_TURQUESA);
    moverBurbujas();
    delay(8);
  }

  tft.setTextFont(2);
  tft.setTextDatum(TC_DATUM);
  for (uint8_t p = 1; p <= 6; p++) {
    tft.setTextColor(mezclar(C_FONDO, C_TENUE, p / 6.0f), C_FONDO);
    tft.drawString("Smart Water & IoT Telemetry", 240, 194);
    pausaConBurbujas(45);
  }
}

static void textoCarga(const char* texto) {
  tft.setTextFont(2);
  tft.setTextDatum(TC_DATUM);
  tft.setTextColor(C_TENUE, C_FONDO);
  tft.setTextPadding(300);
  tft.drawString(texto, 240, 230);
  tft.setTextPadding(0);
}

/** Avanza la barra de carga hasta 'hasta' % con burbujas animadas. */
static void avanzarCarga(uint8_t& actual, uint8_t hasta) {
  const int16_t bx = 90, by = 258, bw = 300, bh = 14;
  for (; actual <= hasta; actual++) {
    const int16_t lleno = (bw - 4) * actual / 100;
    for (int16_t x = 0; x < lleno; x++) {
      tft.drawFastVLine(bx + 2 + x, by + 2, bh - 4, mezclar(C_ESMERALDA, C_CIAN, (float)x / (bw - 4)));
    }
    char pct[8];
    snprintf(pct, sizeof(pct), "%u%%", actual);
    tft.setTextFont(2);
    tft.setTextDatum(TR_DATUM);
    tft.setTextColor(C_CIAN, C_FONDO);
    tft.setTextPadding(40);
    tft.drawString(pct, bx + bw, by + 20);
    tft.setTextPadding(0);
    moverBurbujas();
    delay(14);
  }
  if (actual > hasta) actual = hasta;
}

/** Primera parte de la barra de carga, hasta "Conectando WiFi...". */
static void bootCargaInicio() {
  tft.drawRoundRect(90, 258, 300, 14, 7, C_BORDE);
  textoCarga("Inicializando pantalla... OK");
  avanzarCarga(progresoCarga, 20);
  if (calPh && calTurbidez) textoCarga("Calibracion guardada: pH y turbidez OK");
  else if (calPh)          textoCarga("Turbidez SIN CALIBRAR (usa CAL TUR)");
  else if (calTurbidez)    textoCarga("pH SIN CALIBRAR (usa CAL PH)");
  else                     textoCarga("pH y turbidez SIN CALIBRAR (valores estimados)");
  avanzarCarga(progresoCarga, 45);
  textoCarga("Conectando WiFi...");
  avanzarCarga(progresoCarga, 70);
}

/** Cierre de la barra con el resultado real del WiFi. */
static void bootCargaFin(bool wifiOk) {
  char linea[48];
  if (wifiOk) snprintf(linea, sizeof(linea), "WiFi conectado: %s", WiFi.localIP().toString().c_str());
  else snprintf(linea, sizeof(linea), "Sin WiFi: modo offline (cola)");
  textoCarga(linea);
  avanzarCarga(progresoCarga, 88);
  textoCarga("Sistema listo. Enviando a SIGMAP AQUA...");
  avanzarCarga(progresoCarga, 100);
  pausaConBurbujas(CIERRE_CARGA_MS);
}

/**
 * Final del encendido: una oleada de burbujas sube por toda la pantalla y va
 * borrando el nombre. Dura OLEADA_MS exactos: la posicion de cada burbuja se
 * calcula con el tiempo transcurrido, no con el numero de cuadros. Las
 * burbujas de los costados siguen subiendo mientras tanto.
 */
static void bootOleadaBurbujas() {
  struct Gota { int16_t x, y0, yAnt, xAnt; uint8_t r; float vel; bool rellena; };
  Gota ola[N_OLEADA];
  for (uint8_t i = 0; i < N_OLEADA; i++) {
    Gota& g = ola[i];
    g.x = random(0, 480);
    g.y0 = 330 + random(0, 220);
    g.r = random(5, 17);
    // Velocidad para salir por arriba entre el 55 % y el 100 % de la oleada.
    g.vel = (g.y0 + 30.0f) / (OLEADA_MS * random(55, 101) / 100.0f);   // px por ms
    g.rellena = random(0, 3) == 0;
    g.yAnt = g.xAnt = -1000;
  }
  const uint32_t inicio = millis();
  for (uint32_t t = 0; t < OLEADA_MS; t = millis() - inicio) {
    for (uint8_t i = 0; i < N_OLEADA; i++) {
      Gota& g = ola[i];
      if (g.yAnt > -40) tft.fillCircle(g.xAnt, g.yAnt, g.r + 1, C_FONDO);   // borra: se lleva el nombre
      const int16_t y = g.y0 - (int16_t)(g.vel * t);
      const int16_t x = g.x + (int16_t)(sinf((y + i * 29) / 22.0f) * 4.0f);
      g.yAnt = -1000;
      if (y < 340 && y > -30) {
        if (g.rellena) tft.fillCircle(x, y, g.r, mezclar(C_FONDO, C_CIAN, 0.30f));
        tft.drawCircle(x, y, g.r, i % 3 ? C_CIAN : C_TURQUESA);
        tft.drawCircle(x - g.r / 3, y - g.r / 3, max(1, g.r / 5), C_BLANCO);
        g.yAnt = y; g.xAnt = x;
      }
    }
    moverBurbujas();                                  // las de los costados no se detienen
    delay(1);
  }
  tft.fillScreen(C_FONDO);
}

/** Alevin: cuerpo, cola, aleta y ojo. Mira hacia la derecha. */
static void dibujarPez(int16_t x, int16_t y, uint8_t t, uint16_t color) {
  tft.fillEllipse(x, y, 2 * t, t, color);
  tft.fillTriangle(x - 2 * t + 1, y, x - 3 * t - 1, y - t, x - 3 * t - 1, y + t, color);
  tft.fillTriangle(x - t / 2, y - t + 1, x + t / 2, y - t + 1, x - t, y - t - t / 2 - 1, mezclar(color, C_BLANCO, 0.3f));
  tft.fillCircle(x + t + t / 3, y - t / 4, max(1, t / 4), C_FONDO);
}

/** Alevines cruzando la pantalla de izquierda a derecha durante PECES_MS. */
static void bootPeces() {
  static const uint16_t colores[] = {rgb(255, 140, 40), C_CIAN, rgb(255, 200, 60), C_CORAL, C_ESMERALDA};
  struct Pez { int16_t y, xAnt, yAnt; uint8_t t; float vel; int16_t x0; uint16_t color; };
  Pez peces[N_PECES];
  for (uint8_t i = 0; i < N_PECES; i++) {
    Pez& p = peces[i];
    p.t = random(5, 9);                               // tamano: alevines pequenos
    p.y = 60 + i * (200 / N_PECES) + random(-6, 7);   // cada uno en su carril
    p.x0 = -40 - random(0, 120);
    p.vel = (540.0f - p.x0) / (PECES_MS * random(80, 101) / 100.0f);
    p.color = colores[i % 5];
    p.xAnt = -1000;
  }
  iniciarBurbujas();                                  // vuelven las burbujas de los costados
  const uint32_t inicio = millis();
  for (uint32_t t = 0; t < PECES_MS; t = millis() - inicio) {
    for (uint8_t i = 0; i < N_PECES; i++) {
      Pez& p = peces[i];
      if (p.xAnt > -1000) tft.fillRect(p.xAnt - 3 * p.t - 2, p.yAnt - 2 * p.t - 1, 5 * p.t + 5, 4 * p.t + 2, C_FONDO);
      const int16_t x = p.x0 + (int16_t)(p.vel * t);
      const int16_t y = p.y + (int16_t)(sinf((x + i * 50) / 28.0f) * 4.0f);   // vaiven al nadar
      p.xAnt = -1000;
      if (x > -3 * p.t && x < 480 + 3 * p.t) {
        dibujarPez(x, y, p.t, p.color);
        p.xAnt = x; p.yAnt = y;
      }
    }
    moverBurbujas();
    delay(12);
  }
}


// ============================================================================
// Tablero
// ============================================================================
static void dibujarCabeceraFija() {
  dibujarGota(20, 26, 8, C_CIAN);
  tft.fillCircle(17, 24, 2, C_BLANCO);
  tft.setTextDatum(TL_DATUM);
  tft.setTextFont(4);
  tft.setTextColor(C_BLANCO, C_FONDO);
  tft.drawString("SIGMAP", 36, 8);
  tft.setTextColor(C_CIAN, C_FONDO);
  tft.drawString("AQUA", 36 + tft.textWidth("SIGMAP "), 8);
  for (int16_t x = 0; x < 480; x++) tft.drawPixel(x, HEADER_H, mezclar(C_CIAN, C_ESMERALDA, x / 480.0f));
}

/** Estado de la cabecera: captura, envio al software y WiFi. Solo si cambia. */
static void dibujarCabeceraEstado(bool capturando) {
  static int32_t firmaDibujada = -1;
  const int32_t firma = capturando ? -2 : (int32_t)(versionEnvio * 8 + resultadoEnvio * 2 + (estadoWifi == 1));
  if (firma == firmaDibujada) return;
  firmaDibujada = firma;

  char texto[40];
  uint16_t color;
  if (capturando) {
    snprintf(texto, sizeof(texto), "Capturando datos...");
    color = C_CIAN;
  } else {
    switch (resultadoEnvio) {
      case PANT_ENVIADO:
        snprintf(texto, sizeof(texto), "ENVIADO A SIGMAP  #%lu", (unsigned long)lotesEnviados);
        color = C_NEON; break;
      case PANT_SIN_WIFI:
        snprintf(texto, sizeof(texto), "SIN WIFI - EN COLA");
        color = C_AMBAR; break;
      case PANT_SIN_SERVIDOR:
        snprintf(texto, sizeof(texto), "SERVIDOR NO RESPONDE - EN COLA");
        color = C_CORAL; break;
      default:
        snprintf(texto, sizeof(texto), estadoWifi == 1 ? "EN VIVO - WiFi OK" : "EN VIVO");
        color = C_NEON; break;
    }
  }
  tft.setTextFont(2);
  tft.setTextDatum(MR_DATUM);
  tft.setTextColor(color, C_FONDO);
  tft.setTextPadding(230);
  tft.drawString(texto, RADAR_X - 6, 20);
  tft.setTextPadding(0);
}

static void dibujarRadar(uint32_t ahora) {
  const int16_t c = RADAR_D / 2;
  sprRadar.fillSprite(C_FONDO);
  const uint32_t t = ahora - inicioPulsoMs;
  if (nLecturas > 0 && t < PULSO_MS) {
    const float p = (float)t / PULSO_MS;
    sprRadar.drawCircle(c, c, 4 + p * 12, mezclar(C_FONDO, C_CIAN, 1.0f - p));
    sprRadar.drawCircle(c, c, 15, C_CIAN);
    const float ang = p * 3.0f * PI;
    for (uint8_t k = 0; k < 4; k++) {
      const float a = ang - k * 0.28f;
      sprRadar.drawLine(c, c, c + cosf(a) * 14, c + sinf(a) * 14, mezclar(C_FONDO, C_CIAN, 1.0f - k * 0.25f));
    }
    sprRadar.fillCircle(c, c, 3, C_BLANCO);
  } else {
    const float b = (sinf(ahora / 380.0f) + 1.0f) * 0.5f;
    const uint16_t latido = resultadoEnvio == PANT_ENVIADO || resultadoEnvio == PANT_SIN_ENVIO ? C_NEON
                          : (resultadoEnvio == PANT_SIN_WIFI ? C_AMBAR : C_CORAL);
    sprRadar.drawCircle(c, c, 15, C_BORDE);
    sprRadar.drawCircle(c, c, 9, mezclar(C_FONDO, latido, b * 0.4f));
    sprRadar.fillCircle(c, c, 3 + b * 2, mezclar(C_PANEL, latido, 0.5f + b * 0.5f));
  }
  sprRadar.pushSprite(RADAR_X, RADAR_Y);
}

static void dibujarTarjetaFija(const Canal& c) {
  tft.fillRoundRect(c.x, CARD_Y, CARD_W, CARD_H, 10, C_PANEL);
  tft.drawRoundRect(c.x, CARD_Y, CARD_W, CARD_H, 10, C_BORDE);
  tft.fillRect(c.x + 10, CARD_Y + 1, 30, 2, c.color);
  tft.setTextFont(2);
  tft.setTextDatum(TL_DATUM);
  tft.setTextColor(c.color, C_PANEL);
  tft.drawString(c.nombre, c.x + 10, CARD_Y + 6);
  char rango[24];
  snprintf(rango, sizeof(rango), "opt %g-%g", c.optMin, c.optMax);
  tft.setTextFont(1);
  tft.setTextColor(C_TENUE, C_PANEL);
  tft.drawString(rango, c.x + 10, CARD_Y + 90);

  // pH y turbidez sin calibracion guardada: el valor es solo un estimado.
  const bool sinCalibrar = (&c == &canales[PANT_PH] && !calPh) || (&c == &canales[PANT_TURB] && !calTurbidez);
  if (sinCalibrar) {
    tft.setTextDatum(TR_DATUM);
    tft.setTextColor(C_AMBAR, C_PANEL);
    tft.drawString("SIN CAL", c.x + CARD_W - 8, CARD_Y + 9);
  }
}

static void dibujarEstado(Canal& c) {
  if (c.estado == c.estadoDibujado) return;
  c.estadoDibujado = c.estado;
  static const char* textos[] = { "SIN SONDA", "NORMAL", "RIESGO", "CRITICO" };
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
  // Fuente grande; si el numero no cabe junto a la unidad (p. ej. 1639.79 NTU)
  // se usa una mas pequena en vez de cortar decimales.
  sprValor.setTextFont(2);
  const int16_t anchoUnidad = sprValor.textWidth(c.unidad) + 12;
  sprValor.setFreeFont(&FreeSansBold18pt7b);
  if (sprValor.textWidth(txt) > VAL_W - anchoUnidad) sprValor.setFreeFont(&FreeSansBold12pt7b);
  sprValor.setTextDatum(BL_DATUM);
  sprValor.setTextColor(isnan(c.objetivo) ? C_GRIS : c.color);
  sprValor.drawString(txt, 0, VAL_H - 3);
  int16_t x = sprValor.textWidth(txt) + 5;
  sprValor.setTextFont(2);
  sprValor.setTextColor(C_TENUE);
  if (c.unidad[0] == 'C' && c.unidad[1] == '\0') { sprValor.drawCircle(x + 2, VAL_H - 17, 2, C_TENUE); x += 6; }
  sprValor.drawString(c.unidad, x, VAL_H - 4);
  sprValor.pushSprite(c.x + 10, CARD_Y + 26);
}

static void dibujarBarra(const Canal& c) {
  sprBarra.fillSprite(C_PANEL);
  sprBarra.fillRoundRect(0, 0, BAR_W, BAR_H, BAR_H / 2, C_PISTA);
  if (!isnan(c.objetivo)) {
    const int16_t w = max<int16_t>(BAR_H, normalizar(c, c.mostrado) * BAR_W);
    const uint16_t color = colorEstado(c.estado == SIN_DATO ? calcularEstado(c, c.mostrado) : c.estado, c.color);
    sprBarra.fillRoundRect(0, 0, w, BAR_H, BAR_H / 2, mezclar(C_PISTA, color, 0.55f));
    sprBarra.fillRoundRect(0, 3, w, BAR_H - 6, (BAR_H - 6) / 2, color);
    sprBarra.fillCircle(w - BAR_H / 2, BAR_H / 2, BAR_H / 2 - 1, C_BLANCO);
  }
  sprBarra.drawFastVLine(normalizar(c, c.optMin) * (BAR_W - 1), 0, BAR_H, C_BLANCO);
  sprBarra.drawFastVLine(normalizar(c, c.optMax) * (BAR_W - 1), 0, BAR_H, C_BLANCO);
  sprBarra.pushSprite(c.x + 10, CARD_Y + 70);
}

static void dibujarPanelGraficaFijo() {
  tft.fillRoundRect(8, GRAF_PANEL_Y, 464, 320 - GRAF_PANEL_Y - 2, 10, C_PANEL);
  tft.drawRoundRect(8, GRAF_PANEL_Y, 464, 320 - GRAF_PANEL_Y - 2, 10, C_BORDE);
  tft.setTextFont(2);
  tft.setTextDatum(TL_DATUM);
  tft.setTextColor(C_BLANCO, C_PANEL);
  tft.drawString("Tendencia en vivo", 18, GRAF_PANEL_Y + 5);
  int16_t x = 466;
  tft.setTextColor(C_TENUE, C_PANEL);
  tft.setTextDatum(TR_DATUM);
  for (int8_t i = N_CANALES - 1; i >= 0; i--) {
    tft.drawString(canales[i].nombre, x, GRAF_PANEL_Y + 5);
    x -= tft.textWidth(canales[i].nombre) + 6;
    tft.fillRoundRect(x - 12, GRAF_PANEL_Y + 11, 12, 4, 2, canales[i].color);
    x -= 22;
  }
}

/** Grafica normalizada; fase 0..1 hace entrar el punto nuevo por la derecha. */
static void dibujarGrafica(float fase) {
  if (!graficaOk) return;
  sprGrafica.fillSprite(C_PANEL);
  const int16_t carrilH = G_H / N_CANALES;           // una franja por sensor
  const float dx = (float)(G_W - 10) / (PUNTOS - 1);
  const float desplazamiento = (1.0f - fase) * dx;

  for (uint8_t k = 0; k < N_CANALES; k++) {
    const Canal& c = canales[k];
    const int16_t y0 = k * carrilH;
    const int16_t arriba = y0 + 12, abajo = y0 + carrilH - 4;   // zona de la linea
    if (k > 0) {                                       // separador punteado
      for (int16_t x = 0; x < G_W; x += 6) sprGrafica.drawFastHLine(x, y0, 3, C_REJILLA);
    }

    // Zoom automatico robusto: se usa el rango donde caen casi todas las
    // lecturas (percentiles 5 y 95), asi un pico aislado no aplasta la curva;
    // los valores fuera de ese rango se dibujan pegados al borde de la franja.
    float ordenados[PUNTOS];
    uint8_t n = 0;
    for (uint8_t i = PUNTOS - nPuntos; i < PUNTOS; i++) {
      if (!isnan(c.historial[i])) ordenados[n++] = c.historial[i];
    }
    for (uint8_t a = 1; a < n; a++) {                 // insercion: n <= 60
      const float v = ordenados[a]; int8_t b = a - 1;
      while (b >= 0 && ordenados[b] > v) { ordenados[b + 1] = ordenados[b]; b--; }
      ordenados[b + 1] = v;
    }
    float mn = n ? ordenados[(n - 1) * 5 / 100] : INFINITY;
    float mx = n ? ordenados[(n - 1) * 95 / 100] : -INFINITY;
    sprGrafica.setTextFont(1);
    sprGrafica.setTextDatum(TL_DATUM);
    sprGrafica.setTextColor(c.color);
    sprGrafica.drawString(c.nombre, 4, y0 + 3);
    if (isinf(mn)) {
      sprGrafica.setTextColor(C_GRIS);
      sprGrafica.drawString("sin datos", 90, y0 + 3);
      continue;
    }
    if (mx - mn < SPAN_MIN[k]) {
      const float centro = (mn + mx) / 2;
      mn = centro - SPAN_MIN[k] / 2;
      mx = centro + SPAN_MIN[k] / 2;
    }
    const float margen = (mx - mn) * 0.12f;
    mn -= margen; mx += margen;

    char rango[32];
    snprintf(rango, sizeof(rango), "%.*f - %.*f", c.decimales, mn + margen, c.decimales, mx - margen);
    sprGrafica.setTextDatum(TR_DATUM);
    sprGrafica.setTextColor(C_TENUE);
    sprGrafica.drawString(rango, G_W - 4, y0 + 3);

    const uint16_t relleno = mezclar(C_PANEL, c.color, 0.22f);
    bool hayPrevio = false;
    int16_t px = 0, py = 0;
    const uint8_t ventana = SUAVIZADO_LINEA[k];
    for (uint8_t i = PUNTOS - nPuntos; i < PUNTOS; i++) {   // el historial se llena por el final
      if (isnan(c.historial[i])) { hayPrevio = false; continue; }
      float suma = 0; uint8_t usados = 0;               // promedio de las ultimas 'ventana'
      for (uint8_t w = 0; w < ventana && i >= w + (PUNTOS - nPuntos); w++) {
        if (!isnan(c.historial[i - w])) { suma += c.historial[i - w]; usados++; }
      }
      const float v = suma / usados;
      const int16_t x = (G_W - 6) - (PUNTOS - 1 - i) * dx + desplazamiento;
      const float fr = constrain((v - mn) / (mx - mn), 0.0f, 1.0f);
      const int16_t y = abajo - (int16_t)(fr * (abajo - arriba));
      if (ventana > 1) {                                // la lectura real, como punto tenue
        const float fReal = constrain((c.historial[i] - mn) / (mx - mn), 0.0f, 1.0f);
        sprGrafica.drawPixel(x, abajo - (int16_t)(fReal * (abajo - arriba)), mezclar(C_PANEL, c.color, 0.6f));
      }
      if (hayPrevio) {
        for (int16_t xx = max<int16_t>(px, 0); xx <= x && xx < G_W; xx++) {   // area bajo la curva
          const int16_t yy = py + (int32_t)(y - py) * (xx - px) / max<int16_t>(1, x - px);
          sprGrafica.drawFastVLine(xx, yy, abajo - yy + 1, relleno);
        }
        sprGrafica.drawLine(px, py, x, y, c.color);
        sprGrafica.drawLine(px, py - 1, x, y - 1, c.color);
      }
      sprGrafica.drawPixel(x, y, C_BLANCO);            // cada lectura marcada
      hayPrevio = true; px = x; py = y;
    }
    if (hayPrevio) {                                    // lectura mas nueva con brillo
      sprGrafica.fillCircle(px, py, 5, mezclar(C_PANEL, c.color, 0.40f));
      sprGrafica.fillCircle(px, py, 2, C_BLANCO);
    }
  }
  sprGrafica.pushSprite(G_X, G_Y);
}

static void dibujarTableroFijo() {
  tft.fillScreen(C_FONDO);
  dibujarCabeceraFija();
  for (uint8_t i = 0; i < N_CANALES; i++) {
    canales[i].estadoDibujado = (Estado)255;
    dibujarTarjetaFija(canales[i]);
    dibujarEstado(canales[i]);
    dibujarValor(canales[i]);
    dibujarBarra(canales[i]);
  }
  dibujarPanelGraficaFijo();
  dibujarGrafica(1.0f);
}

// ============================================================================
// Ciclo de animacion
// ============================================================================
/** Toma el ultimo lote publicado por el loop(), si hay uno nuevo. */
static bool recibirLote() {
  float valores[N_CANALES];
  uint32_t secuencia;
  secuencia = secuenciaLote;
  for (uint8_t k = 0; k < N_CANALES; k++) valores[k] = publicados[k];
  if (secuencia == secuenciaVista) return false;
  secuenciaVista = secuencia;

  if (nPuntos < PUNTOS) nPuntos++;
  for (uint8_t k = 0; k < N_CANALES; k++) {
    Canal& c = canales[k];
    memmove(c.historial, c.historial + 1, sizeof(float) * (PUNTOS - 1));
    c.historial[PUNTOS - 1] = valores[k];
    c.objetivo = valores[k];
    c.estado = calcularEstado(c, c.objetivo);
    if (!isnan(c.objetivo) && isnan(c.mostrado)) c.mostrado = c.escalaMin;   // crece desde 0
  }
  nLecturas++;
  return true;
}

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
    if (interpolar(c) || sinDato != c.sinDatoDibujado) {
      c.sinDatoDibujado = sinDato;
      dibujarValor(c);
      dibujarBarra(c);
    }
  }
  const uint32_t tScroll = ahora - inicioScrollMs;
  if (tScroll < SCROLL_MS) { dibujarGrafica((float)tScroll / SCROLL_MS); graficaPendiente = true; }
  else if (graficaPendiente) { dibujarGrafica(1.0f); graficaPendiente = false; }
  dibujarRadar(ahora);
  dibujarCabeceraEstado(nLecturas > 0 && ahora - inicioPulsoMs < PULSO_MS);
}

/** Inicializa el controlador ILI9486 y deja la pantalla en el color de fondo. */
static void inicializarControlador() {
  tft.init();
  tft.setRotation(ROTACION);
  tft.fillScreen(C_FONDO);
}

/** Un paso de animacion (como maximo uno cada FRAME_MS). */
static void tick() {
  const uint32_t ahora = millis();
  if (ahora - ultimoFrameMs < FRAME_MS) return;
  ultimoFrameMs = ahora;
  if (!enTablero) { moverBurbujas(); return; }
  if (reinicioPedido) {                             // cambio de calibracion: redibuja (sin tft.init)
    reinicioPedido = false;
    dibujarTableroFijo();
  }
  if (recibirLote()) inicioPulsoMs = inicioScrollMs = ahora;
  if (hayEstadoServidor) {                          // el software ya clasifico el lote
    hayEstadoServidor = false;
    for (uint8_t k = 0; k < N_CANALES; k++) {
      if (estadoServidor[k] >= 0 && !isnan(canales[k].objetivo)) canales[k].estado = (Estado)estadoServidor[k];
    }
    for (uint8_t k = 0; k < N_CANALES; k++) dibujarBarra(canales[k]);
  }
  animarFrame(ahora);
  frames = frames + 1;
}

}  // namespace pant

// ============================================================================
// API publica (la llama bioaqua_ingesta.ino desde setup() y loop())
// ============================================================================
/**
 * Inicializa la pantalla y corre la animacion de encendido hasta "Conectando
 * WiFi...". Va en el setup() despues de configurar los demas pines y ANTES de
 * encender el WiFi, igual que en pantalla_imagen.ino.
 */
static void pantallaIniciar() {
  using namespace pant;
  etapa = "tft.init";
  // Arranque en frio (USB recien conectado): la pantalla y el ESP32 se
  // energizan juntos y el controlador de la pantalla tarda mas en estar listo.
  // Si se inicializa antes, la orden se pierde y solo prende la luz (blanco).
  // Por eso se espera al menos 1,5 s desde el encendido y se inicializa 2 veces.
  const bool enFrio = esp_reset_reason() == ESP_RST_POWERON || esp_reset_reason() == ESP_RST_BROWNOUT;
  const uint32_t minimoMs = enFrio ? 1500 : 300;
  while (millis() < minimoMs) delay(10);
  inicializarControlador();
  delay(150);
  inicializarControlador();
  Serial.printf("[PANTALLA] Inicializada (%s).\n", enFrio ? "arranque en frio" : "reinicio");
  sprValor.createSprite(VAL_W, VAL_H);
  sprBarra.createSprite(BAR_W, BAR_H);
  sprRadar.createSprite(RADAR_D, RADAR_D);
  sprGrafica.setColorDepth(8);                      // 59 KB en vez de 118 KB
  graficaOk = sprGrafica.createSprite(G_W, G_H) != nullptr;
  if (!graficaOk) Serial.println("[PANTALLA] Sin RAM para la grafica; se omite.");
  for (uint8_t k = 0; k < N_CANALES; k++) {
    canales[k].objetivo = canales[k].mostrado = NAN;
    canales[k].estado = SIN_DATO;
    canales[k].sinDatoDibujado = true;
    for (uint8_t i = 0; i < PUNTOS; i++) canales[k].historial[i] = NAN;
  }
  etapa = "encendido";
  iniciarBurbujas();
  bootOndas();
  bootLogo();
  bootCargaInicio();
  Serial.println("[PANTALLA] Animacion de encendido en curso.");
}

/** Reemplazo de delay(): espera 'ms' sin congelar la animacion. */
static void pantallaEsperar(uint32_t ms) {
  const uint32_t inicio = millis();
  do {
    pant::tick();
    delay(2);
  } while (millis() - inicio < ms);
}

/** Termina la animacion de encendido y deja el tablero en vivo. */
static void pantallaTerminarArranque(bool wifiOk) {
  using namespace pant;
  bootCargaFin(wifiOk);
  pausaConBurbujas(PAUSA_NOMBRE_MS);               // tiempo para leer el nombre
  bootOleadaBurbujas();                             // las burbujas se llevan el nombre
  bootPeces();                                      // y aparecen los alevines
  etapa = "tablero";
  dibujarTableroFijo();
  enTablero = true;
  etapa = "en vivo";
  Serial.println("[PANTALLA] Tablero listo.");
}

static void pantallaWifi(bool conectado) { pant::estadoWifi = conectado ? 1 : 0; }

/** Indica si pH y turbidez tienen calibracion guardada; si cambia, redibuja. */
static void pantallaCalibracion(bool phGuardada, bool turbidezGuardada) {
  const bool cambio = pant::calPh != phGuardada || pant::calTurbidez != turbidezGuardada;
  pant::calPh = phGuardada;
  pant::calTurbidez = turbidezGuardada;
  if (cambio && pant::enTablero) pant::reinicioPedido = true;   // redibuja el aviso SIN CAL
}

static void pantallaInicioLote() {
  for (uint8_t k = 0; k < pant::N_CANALES; k++) pant::loteValores[k] = NAN;
}

static void pantallaValor(CanalPantalla canal, float valor) {
  if (canal < pant::N_CANALES) pant::loteValores[canal] = valor;
}

/** Estado que el software asigno a la lectura ("normal", "riesgo" o "critico"). */
static void pantallaEstadoServidor(CanalPantalla canal, const char* estado) {
  if (canal >= pant::N_CANALES || estado == nullptr) return;
  int8_t e = -1;
  if (strcmp(estado, "normal") == 0) e = pant::NORMAL;
  else if (strcmp(estado, "riesgo") == 0) e = pant::RIESGO;
  else if (strcmp(estado, "critico") == 0) e = pant::CRITICO;
  if (e < 0) return;
  pant::estadoServidor[canal] = e;
  pant::hayEstadoServidor = true;
}

static void pantallaPublicar() {
  // Lote nuevo: su estado lo dira la proxima respuesta del software.
  for (uint8_t k = 0; k < pant::N_CANALES; k++) pant::estadoServidor[k] = -1;
  pant::hayEstadoServidor = false;
  for (uint8_t k = 0; k < pant::N_CANALES; k++) pant::publicados[k] = pant::loteValores[k];
  pant::secuenciaLote++;
}

static void pantallaEnvio(ResultadoEnvio resultado) {
  if (resultado == PANT_ENVIADO) pant::lotesEnviados = pant::lotesEnviados + 1;
  pant::resultadoEnvio = resultado;
  pant::versionEnvio = pant::versionEnvio + 1;
}

/** Imprime cada 5 s en que etapa va la pantalla (para diagnostico). */
static void pantallaDiagnostico() {
  static uint32_t ultimo = 0;
  if (millis() - ultimo < 5000) return;
  ultimo = millis();
  Serial.printf("[PANTALLA] etapa=%s frames=%lu heap=%lu\n", (const char*)pant::etapa,
                (unsigned long)pant::frames, (unsigned long)ESP.getFreeHeap());
}

/**
 * Comando PANTALLA: reinicializa la pantalla con el WiFi APAGADO (regla de oro)
 * y redibuja el tablero. El loop() vuelve a conectar el WiFi en el siguiente
 * ciclo de envio.
 */
static void pantallaReiniciar() {
  Serial.println("[PANTALLA] Apagando WiFi para reinicializar la pantalla...");
  WiFi.disconnect(true);
  WiFi.mode(WIFI_OFF);
  delay(300);
  pant::inicializarControlador();
  if (pant::enTablero) pant::dibujarTableroFijo();
  pant::estadoWifi = 0;
  Serial.println("[PANTALLA] Reinicializada y redibujada. El WiFi se reconecta en el proximo envio.");
}
