/* Pruebas del DSP y del contrato binario; ejecutables sin Pico SDK. */
#include "nodo1_metodos.h"

#include <assert.h>
#include <math.h>
#include <stdio.h>
#include <string.h>

static nodo1_tablas_t tablas;
static float x[NODO1_N], re[NODO1_N], im[NODO1_N];
static uint8_t trama[NODO1_SPI_BYTES];

static void probar_adc(void)
{
    uint16_t adc[NODO1_N];
    nodo1_metricas_t m;
    for (size_t n = 0; n < NODO1_N; ++n) adc[n] = 2048;
    nodo1_convertir_adc(adc, x, &m);
    assert(fabsf(m.media_v - 1.65f) < 1e-5f);
    assert(m.rms_ac_v < 1e-5f);
    assert(m.adc_min == 2048 && m.adc_max == 2048 && m.saturadas == 0);
    for (size_t n = 0; n < NODO1_N; ++n) adc[n] = (n & 1u) ? 4095 : 0;
    nodo1_convertir_adc(adc, x, &m);
    const float amplitud = 4095.0f * NODO1_ADC_VREF / 8192.0f;
    assert(m.adc_min == 0 && m.adc_max == 4095 && m.saturadas == NODO1_N);
    assert(fabsf(m.rms_ac_v - amplitud) < 1e-5f);
    assert(fabsf(m.energia_ac_v2 - NODO1_N * amplitud * amplitud) < 0.01f);
}

static void probar_fft_con_dft(void)
{
    /* Mezcla determinista sin simetría especial: comparar TODOS los bins con
     * una DFT independiente en double permite detectar signo, escala y orden. */
    for (size_t n = 0; n < NODO1_N; ++n) {
        x[n] = sinf((float)n * 0.31f) + 0.4f * cosf((float)n * 1.71f);
    }
    nodo1_aplicar_hann(x, &tablas, re, im);
    nodo1_fft(re, im, &tablas);
    for (size_t k = 0; k < NODO1_N; ++k) {
        double esperada_re = 0, esperada_im = 0;
        for (size_t n = 0; n < NODO1_N; ++n) {
            const double angulo = -2.0 * 3.14159265358979323846 * k * n / NODO1_N;
            const double ventana = 0.5 * (1.0 - cos(2.0 * 3.14159265358979323846 * n /
                                                  (NODO1_N - 1u)));
            esperada_re += x[n] * ventana * cos(angulo);
            esperada_im += x[n] * ventana * sin(angulo);
        }
        assert(fabs(re[k] - esperada_re) < 0.0002);
        assert(fabs(im[k] - esperada_im) < 0.0002);
    }
    assert(tablas.hann[0] == 0 && tablas.hann[NODO1_N - 1u] < 1e-6f);
}

static void probar_estimacion(void)
{
    nodo1_metricas_t m = {0};
    for (size_t n = 0; n < NODO1_N; ++n) {
        x[n] = sinf(2.0f * 3.14159265358979323846f * 16.0f * n / NODO1_N) +
               0.5f * sinf(2.0f * 3.14159265358979323846f * 64.0f * n / NODO1_N);
    }
    float original[NODO1_N];
    memcpy(original, x, sizeof(x));
    nodo1_aplicar_hann(x, &tablas, re, im);
    nodo1_fft(re, im, &tablas);
    assert(memcmp(original, x, sizeof(x)) == 0); /* Enviar muestras sin Hann. */
    nodo1_estimar_ruido(re, im, 1600, &m);
    assert(m.pico_hz == 625.0f && m.candidata_valida && m.candidata_ruido_hz == 2500.0f);
    memset(re, 0, sizeof(re));
    memset(im, 0, sizeof(im));
    nodo1_estimar_ruido(re, im, 1600, &m);
    assert(m.pico_hz == 0 && !m.candidata_valida);
}

static void probar_contrato(void)
{
    assert(nodo1_crc8((const uint8_t *)"123456789", 9) == 0xf4); /* Vector SMBUS. */
    assert(nodo1_crc8(NULL, 0) == 0);
    memset(x, 0, sizeof(x));
    x[0] = 1.0f;
    x[1] = -0.5f;
    assert(nodo1_empaquetar(0x12345678, x, trama));
    const uint8_t prefijo[] = {0xaa, 0xbb, 0x78, 0x56, 0x34, 0x12,
                              0x00, 0x00, 0x80, 0x3f, 0x00, 0x00, 0x00, 0xbf};
    assert(memcmp(trama, prefijo, sizeof(prefijo)) == 0);
    assert(sizeof(trama) == 1032 && trama[1031] == 0);
    assert(nodo1_crc8(trama, 1031) == 0); /* Residuo de trama completa con CRC. */
    trama[26] ^= 1;
    assert(nodo1_crc8(trama, 1031) != 0);
    x[4] = NAN;
    assert(!nodo1_empaquetar(0, x, trama));
    x[4] = INFINITY;
    assert(!nodo1_empaquetar(0, x, trama));
    x[4] = 0;
    assert(nodo1_empaquetar(UINT32_MAX, x, trama));
    assert(trama[2] == 0xff && trama[5] == 0xff);
    assert(nodo1_empaquetar(0, x, trama));
    assert(trama[2] == 0 && trama[5] == 0);
}

int main(void)
{
    nodo1_preparar_tablas(&tablas);
    probar_adc();
    probar_fft_con_dft();
    probar_estimacion();
    probar_contrato();
    puts("OK: ADC/DC/RMS, FFT vs DFT, Hann, estimacion, CRC8 y trama SPI.");
    return 0;
}
