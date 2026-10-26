// =====================================================================
//  User_Setup.h  —  Sigmap Aqua
//  Pantalla: 3.5inch RPi Display (480x320, ILI9486 + touch XPT2046)
//  Placa:    ESP32 DevKit
//
//  DONDE VA ESTE ARCHIVO (no se queda en esta carpeta):
//    Documentos\Arduino\libraries\TFT_eSPI\User_Setup.h
//  Reemplaza el que trae la libreria. Sin esto la pantalla queda en blanco
//  aunque el codigo compile.
// =====================================================================

// ---------- Controlador de la pantalla ----------
#define ILI9486_DRIVER
#define RPI_DISPLAY_TYPE      // Pantallas RPi: SPI de 16 bits (74HC4094)

// ---------- Pines SPI (bus VSPI del ESP32) ----------
#define TFT_MISO 19           // Solo lo usa el touch
#define TFT_MOSI 23           // Datos ESP32 -> pantalla
#define TFT_SCLK 18           // Reloj SPI

// ---------- Control de la pantalla ----------
#define TFT_CS   5            // Chip Select de la pantalla (LCD_CS)
#define TFT_DC   16           // Data/Command (en la placa dice LCD_RS)
#define TFT_RST  17           // Reset

// ---------- Touch XPT2046 (cuando se conecte) ----------
#define TOUCH_CS 22

// ---------- Fuentes ----------
#define LOAD_GLCD
#define LOAD_FONT2
#define LOAD_FONT4
#define LOAD_FONT6
#define LOAD_FONT7
#define LOAD_GFXFF
#define SMOOTH_FONT

// ---------- Velocidades SPI ----------
#define SPI_FREQUENCY        20000000  // Si sale basura, bajar a 10000000
#define SPI_TOUCH_FREQUENCY   2500000
