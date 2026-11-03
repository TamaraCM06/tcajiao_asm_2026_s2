#include "audio_vivo.h"
#include "nodo1_metodos.h"
#include <assert.h>
#include <math.h>
#include <stdio.h>
#include <string.h>
static audio_vivo_t estado;
static audio_resultado_t resultado;
static float mezcla[AUDIO_N], referencia[AUDIO_N], decodificada[AUDIO_N];
static uint8_t trama[AUDIO_TRAMA];

static void contrato(void)
{
    _Static_assert(AUDIO_N == NODO1_N && AUDIO_TRAMA == NODO1_SPI_BYTES && AUDIO_FS == NODO1_FS_HZ,
                   "Pico y ESP32 deben compartir contrato");
    for (unsigned i = 0; i < AUDIO_N; ++i) mezcla[i] = (float)i / 1000 - 0.128f;
    assert(nodo1_empaquetar(0x12345678, mezcla, trama));
    uint32_t id = 0;
    assert(audio_decodificar(trama, sizeof(trama), &id, decodificada) == AUDIO_OK);
    assert(id == 0x12345678 && memcmp(mezcla, decodificada, sizeof(mezcla)) == 0);
    assert(audio_decodificar(trama, 1031, &id, decodificada) == AUDIO_LONGITUD);
    trama[0] ^= 1;
    assert(audio_decodificar(trama, sizeof(trama), &id, decodificada) == AUDIO_CABECERA);
    trama[0] ^= 1; trama[200] ^= 1;
    assert(audio_decodificar(trama, sizeof(trama), &id, decodificada) == AUDIO_CRC);
    trama[200] ^= 1;
    uint32_t nan = 0x7fc00000;
    memcpy(trama + 6, &nan, 4);
    trama[1030] = nodo1_crc8(trama, 1030);
    assert(audio_decodificar(trama, sizeof(trama), &id, decodificada) == AUDIO_MUESTRA);
    trama[1031] = 1;
    assert(audio_decodificar(trama, sizeof(trama), &id, decodificada) == AUDIO_CABECERA);
}
static void filtros_y_metricas(void)
{
    audio_vivo_iniciar(&estado);
    memset(&resultado, 0, sizeof(resultado));
    for (uint32_t bloque = 0; bloque < 100; ++bloque) {
        for (unsigned i = 0; i < AUDIO_N; ++i) {
            double t = (bloque * AUDIO_N + i) / (double)AUDIO_FS;
            referencia[i] = (float)(0.3 * sin(6.283185307179586 * 440 * t));
            mezcla[i] = referencia[i] + (float)(0.15 * sin(6.283185307179586 * 3000 * t));
        }
        assert(audio_vivo_procesar(&estado, bloque, mezcla, referencia, &resultado));
        if (bloque < 3) assert(!resultado.fft_lista);
    }
    printf("Referencia conocida: FIR SNR=%.2f MSE=%g Eutil=%.2f%% | FFT SNR=%.2f MSE=%g Eutil=%.2f%%\n",
           resultado.fir.snr_db, resultado.fir.mse, resultado.fir.energia_pct,
           resultado.fft.snr_db, resultado.fft.mse, resultado.fft.energia_pct);
    assert(resultado.fir.referencia && resultado.fft.referencia && resultado.fft_lista);
    assert(resultado.fir.snr_db > 30 && resultado.fft.snr_db > 20);
    assert(resultado.fir.energia_pct > 95 && resultado.fir.energia_pct < 105);
    assert(resultado.fft.energia_pct > 95 && resultado.fft.energia_pct < 105);
    assert(!audio_vivo_procesar(&estado, 99, mezcla, referencia, &resultado));
    assert(!audio_vivo_procesar(&estado, 98, mezcla, referencia, &resultado));
    assert(audio_vivo_procesar(&estado, 105, mezcla, referencia, &resultado));
    assert(resultado.discontinuidades == 1 && !resultado.fft_lista);
    assert(audio_vivo_procesar(&estado, 0, mezcla, NULL, &resultado));
    assert(!resultado.fir.referencia && isnan(resultado.fir.snr_db) && isnan(resultado.fir.mse));
    assert(resultado.discontinuidades == 2 && !resultado.fft_lista);
    /* Silencio no debe inventar relaciones de energia. */
    memset(mezcla, 0, sizeof(mezcla));
    audio_vivo_iniciar(&estado);
    assert(audio_vivo_procesar(&estado, UINT32_MAX, mezcla, NULL, &resultado));
    assert(audio_vivo_procesar(&estado, 0, mezcla, NULL, &resultado));
    assert(resultado.discontinuidades == 0 && isnan(resultado.fir.energia_pct));
    assert(resultado.fir.rms == 0);
}
int main(void)
{
    contrato(); filtros_y_metricas(); puts("OK: contrato Pico/ESP32, filtros 10 kHz, alineacion, metricas y secuencia");
    return 0;
}
