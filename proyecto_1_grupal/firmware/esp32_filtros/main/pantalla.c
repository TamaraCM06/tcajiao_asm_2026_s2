#include "pantalla.h"
#include "sdkconfig.h"
#include <math.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "driver/gpio.h"
#include "driver/spi_master.h"
#include "esp_attr.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"

#if CONFIG_AUDIO_LCD
/* LCD ST7735S 160x80 horizontal. GPIO9/10 se reservan a flash. */
enum { W = 160, H = 80, LCD_RST = 27, LCD_DC = 26 };
static spi_device_handle_t lcd;
static DMA_ATTR uint16_t pixeles[W * H];
static const uint16_t BLANCO = 0xffff, ROJO = 0xf800, VERDE = 0x07e0;
static void enviar(bool datos, const void *p, size_t n)
{
    if (!n) return;
    gpio_set_level(LCD_DC, datos);
    spi_transaction_t t = {.length = n * 8, .tx_buffer = p};
    ESP_ERROR_CHECK(spi_device_transmit(lcd, &t));
}
static void comando(uint8_t cmd, const uint8_t *datos, size_t n)
{
    enviar(false, &cmd, 1);
    enviar(true, datos, n);
}
static void pixel(int x, int y, uint16_t c)
{
    if (x >= 0 && x < W && y >= 0 && y < H) pixeles[y * W + x] = (uint16_t)((c << 8) | (c >> 8));
}
static void linea(int x, int y, int xx, int yy, uint16_t c)
{
    int dx = abs(xx - x), sx = x < xx ? 1 : -1;
    int dy = -abs(yy - y), sy = y < yy ? 1 : -1, err = dx + dy;
    for (;;) {
        pixel(x, y, c);
        if (x == xx && y == yy) break;
        int doble = 2 * err;
        if (doble >= dy) { err += dy; x += sx; }
        if (doble <= dx) { err += dx; y += sy; }
    }
}
/* Fuente 5x7 en columnas; alfabeto reducido para las metricas en 160x80. */
static void texto(int x, int y, const char *s, uint16_t c)
{
    static const uint8_t numeros[10][5] = {
        {0x3e,0x51,0x49,0x45,0x3e},{0,0x42,0x7f,0x40,0},{0x42,0x61,0x51,0x49,0x46},
        {0x21,0x41,0x45,0x4b,0x31},{0x18,0x14,0x12,0x7f,0x10},{0x27,0x45,0x45,0x45,0x39},
        {0x3c,0x4a,0x49,0x49,0x30},{1,0x71,9,5,3},{0x36,0x49,0x49,0x49,0x36},{6,0x49,0x49,0x29,0x1e}};
    static const uint8_t letras[26][5] = {
        {0x7e,9,9,9,0x7e},{0x7f,0x49,0x49,0x49,0x36},{0x3e,0x41,0x41,0x41,0x22},
        {0x7f,0x41,0x41,0x22,0x1c},{0x7f,0x49,0x49,0x49,0x41},{0x7f,9,9,9,1},
        {0x3e,0x41,0x49,0x49,0x7a},{0x7f,8,8,8,0x7f},{0,0x41,0x7f,0x41,0},
        {0x20,0x40,0x41,0x3f,1},{0x7f,8,0x14,0x22,0x41},{0x7f,0x40,0x40,0x40,0x40},
        {0x7f,2,0x0c,2,0x7f},{0x7f,4,8,0x10,0x7f},{0x3e,0x41,0x41,0x41,0x3e},
        {0x7f,9,9,9,6},{0x3e,0x41,0x51,0x21,0x5e},{0x7f,9,0x19,0x29,0x46},
        {0x46,0x49,0x49,0x49,0x31},{1,1,0x7f,1,1},{0x3f,0x40,0x40,0x40,0x3f},
        {0x1f,0x20,0x40,0x20,0x1f},{0x3f,0x40,0x38,0x40,0x3f},{0x63,0x14,8,0x14,0x63},
        {7,8,0x70,8,7},{0x61,0x51,0x49,0x45,0x43}};
    for (; *s && x + 5 <= W; ++s, x += 6) {
        uint8_t glifo[5] = {0};
        unsigned char caracter = (unsigned char)*s;
        if (caracter >= 'a' && caracter <= 'z') caracter -= 'a' - 'A';
        if (caracter >= '0' && caracter <= '9') memcpy(glifo, numeros[caracter - '0'], 5);
        else if (caracter >= 'A' && caracter <= 'Z') memcpy(glifo, letras[caracter - 'A'], 5);
        else switch (caracter) {
            case '.': glifo[2] = 0x60; break;
            case ':': glifo[2] = 0x36; break;
            case '-': memset(glifo, 8, 5); break;
            case '+': memset(glifo, 8, 5); glifo[2] = 0x3e; break;
            case '/': glifo[0]=0x40; glifo[1]=0x20; glifo[2]=0x10; glifo[3]=8; glifo[4]=4; break;
            case '%': glifo[0]=0x63; glifo[1]=0x13; glifo[2]=8; glifo[3]=0x64; glifo[4]=0x63; break;
            default: break;
        }
        for (int col = 0; col < 5; ++col)
            for (int fila = 0; fila < 7; ++fila)
                if (glifo[col] & (1 << fila)) pixel(x + col, y + fila, c);
    }
}
static void refrescar(void)
{
    uint16_t x0 = CONFIG_AUDIO_LCD_X, y0 = CONFIG_AUDIO_LCD_Y;
    uint16_t x1 = x0 + W - 1, y1 = y0 + H - 1;
    uint8_t xs[] = {x0 >> 8, x0, x1 >> 8, x1};
    uint8_t ys[] = {y0 >> 8, y0, y1 >> 8, y1};
    comando(0x2a, xs, 4); comando(0x2b, ys, 4); comando(0x2c, NULL, 0);
    for (int fila = 0; fila < H; fila += 8) enviar(true, pixeles + fila * W, W * 8 * 2);
}
#endif

esp_err_t pantalla_iniciar(void)
{
#if CONFIG_AUDIO_LCD
    gpio_config_t gc = {.pin_bit_mask = (1ULL << LCD_RST) | (1ULL << LCD_DC), .mode = GPIO_MODE_OUTPUT};
    esp_err_t err = gpio_config(&gc);
    if (err != ESP_OK) return err;
    spi_bus_config_t bus = {.mosi_io_num = 13, .miso_io_num = -1, .sclk_io_num = 14,
                           .quadwp_io_num = -1, .quadhd_io_num = -1, .max_transfer_sz = 2560};
    err = spi_bus_initialize(SPI2_HOST, &bus, SPI_DMA_CH_AUTO);
    if (err != ESP_OK) return err;
    spi_device_interface_config_t dev = {.clock_speed_hz = 20000000, .mode = 0,
                                        .spics_io_num = 15, .queue_size = 1};
    err = spi_bus_add_device(SPI2_HOST, &dev, &lcd);
    if (err != ESP_OK) return err;
    gpio_set_level(LCD_RST, 0); vTaskDelay(pdMS_TO_TICKS(20));
    gpio_set_level(LCD_RST, 1); vTaskDelay(pdMS_TO_TICKS(120));
    comando(0x01, NULL, 0); vTaskDelay(pdMS_TO_TICKS(150));
    comando(0x11, NULL, 0); vTaskDelay(pdMS_TO_TICKS(120));
    const uint8_t frame[] = {1, 0x2c, 0x2d};
    comando(0xb1, frame, 3); comando(0xb2, frame, 3);
    const uint8_t frame2[] = {1,0x2c,0x2d,1,0x2c,0x2d}; comando(0xb3, frame2, 6);
    const uint8_t inv = 7; comando(0xb4, &inv, 1);
    const uint8_t power[] = {0xa2,2,0x84}; comando(0xc0, power, 3);
    const uint8_t c1 = 0xc5; comando(0xc1, &c1, 1);
    const uint8_t c2[] = {0x0a,0}; comando(0xc2, c2, 2);
    const uint8_t c3[] = {0x8a,0x2a}; comando(0xc3, c3, 2);
    const uint8_t c4[] = {0x8a,0xee}; comando(0xc4, c4, 2);
    const uint8_t vcom = 0x0e; comando(0xc5, &vcom, 1);
    const uint8_t formato = 5, orientacion = CONFIG_AUDIO_LCD_MADCTL;
    comando(0x3a, &formato, 1); comando(0x36, &orientacion, 1);
#if CONFIG_AUDIO_LCD_INVERTIR
    comando(0x21, NULL, 0);
#else
    comando(0x20, NULL, 0);
#endif
    comando(0x13, NULL, 0); comando(0x29, NULL, 0);
    vTaskDelay(pdMS_TO_TICKS(100));
    pantalla_dibujar(NULL, false);
#endif
    return ESP_OK;
}

void pantalla_dibujar(const pantalla_datos_t *d, bool conectado)
{
#if CONFIG_AUDIO_LCD
    memset(pixeles, 0, sizeof(pixeles));
    if (!conectado || !d) {
        texto(8, 12, "SIN DATOS SPI", BLANCO);
        texto(8, 30, "REVISAR READY/CS", BLANCO);
        texto(8, 48, "MODO Y CRC", BLANCO);
        refrescar(); return;
    }
    char s[40];
    snprintf(s, sizeof(s), "%s %s %lu", d->espectral ? "FFT" : "FIR",
             d->simulacion ? "SIM" : "MIC", (unsigned long)d->bloque);
    texto(0, 0, s, BLANCO);
    texto(112, 0, "IN", ROJO); texto(136, 0, "OUT", VERDE);
    if (d->lista) {
        float escala = 0.001f;
        for (int i = 0; i < PANTALLA_PUNTOS; ++i)
            escala = fmaxf(escala, fmaxf(fabsf(d->entrada[i]), fabsf(d->salida[i])));
        linea(0, 28, 159, 28, 0x4208);
        for (int i = 1; i < PANTALLA_PUNTOS; ++i) {
            linea(i-1, 28-(int)(d->entrada[i-1]/escala*17), i, 28-(int)(d->entrada[i]/escala*17), ROJO);
            linea(i-1, 28-(int)(d->salida[i-1]/escala*17), i, 28-(int)(d->salida[i]/escala*17), VERDE);
        }
        snprintf(s, sizeof(s), "SNR:%+.1f DB", (double)d->metricas.snr_db);
        texto(0, 48, !d->metricas.referencia ? "SNR:N/D SIN REF" :
              isnan(d->metricas.snr_db) ? "SNR:N/D" : s, BLANCO);
        snprintf(s, sizeof(s), "MSE:%.2E", (double)d->metricas.mse);
        texto(0, 59, d->metricas.referencia ? s : "MSE:N/D SIN REF", BLANCO);
        snprintf(s, sizeof(s), "%s:%.1f%%", d->metricas.referencia ? "E UTIL" : "E TOTAL",
                 (double)d->metricas.energia_pct);
        texto(0, 70, isfinite(d->metricas.energia_pct) ? s : "E:N/D ENTRADA CERO", BLANCO);
    } else texto(0, 28, "CALENTANDO FFT", BLANCO);
    if (d->rechazados || d->discontinuidades) texto(120, 70, "ERROR", ROJO);
    refrescar();
#else
    (void)d; (void)conectado;
#endif
}
