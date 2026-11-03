#include "audio_vivo.h"
#include <float.h>
#include <math.h>
#include <string.h>

_Static_assert(sizeof(float) == 4 && FLT_RADIX == 2 && FLT_MANT_DIG == 24 && FLT_MAX_EXP == 128,
               "Se requiere float32 IEEE754");
static uint8_t crc8(const uint8_t *datos, size_t n)
{
    uint8_t crc = 0;
    for (size_t i = 0; i < n; ++i) {
        crc ^= datos[i];
        for (unsigned j = 0; j < 8; ++j)
            crc = (uint8_t)((crc & 0x80u) ? ((unsigned)crc << 1) ^ 7u : (unsigned)crc << 1);
    }
    return crc;
}
static uint32_t leer32(const uint8_t *p)
{
    return (uint32_t)p[0] | (uint32_t)p[1] << 8 | (uint32_t)p[2] << 16 | (uint32_t)p[3] << 24;
}
audio_error_t audio_decodificar(const uint8_t *trama, size_t bytes, uint32_t *id, float salida[AUDIO_N])
{
    if (!trama || !id || !salida || bytes != AUDIO_TRAMA) return AUDIO_LONGITUD;
    if (trama[0] != 0xAA || trama[1] != 0xBB || trama[AUDIO_TRAMA - 1] != 0) return AUDIO_CABECERA;
    if (crc8(trama, 1030) != trama[1030]) return AUDIO_CRC;
    for (unsigned i = 0; i < AUDIO_N; ++i) {
        uint32_t bits = leer32(trama + 6 + 4 * i);
        memcpy(salida + i, &bits, sizeof(bits));
        /* ADC 0..3.3 V sin DC: no aceptar valores fisicamente imposibles. */
        if (!isfinite(salida[i]) || fabsf(salida[i]) > 3.3f) return AUDIO_MUESTRA;
    }
    *id = leer32(trama + 2);
    return AUDIO_OK;
}
