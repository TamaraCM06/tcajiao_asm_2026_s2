#include "nodo1_metodos.h"

#include <float.h>
#include <math.h>
#include <string.h>

_Static_assert(sizeof(float) == 4 && FLT_RADIX == 2 && FLT_MANT_DIG == 24 &&
               FLT_MAX_EXP == 128, "Se requiere float IEEE-754 binario32.");
_Static_assert(sizeof(nodo1_paquete_t) == NODO1_TRAMA_BYTES, "Trama sin padding.");
_Static_assert(offsetof(nodo1_paquete_t, muestras) == 6, "Offset de muestras.");
_Static_assert(offsetof(nodo1_paquete_t, crc8) == 1030, "Offset del CRC.");
_Static_assert(NODO1_SPI_BYTES % 4 == 0, "Longitud compatible con DMA ESP32.");

static const float PI = 3.14159265358979323846f;

void nodo1_preparar_tablas(nodo1_tablas_t *tablas)
{
    for (size_t n = 0; n < NODO1_N; ++n) {
        /* Hann simétrica, equivalente a np.hanning(256). */
        tablas->hann[n] = 0.5f * (1.0f - cosf(2.0f * PI * (float)n / (NODO1_N - 1u)));
    }
    for (size_t k = 0; k < NODO1_N / 2u; ++k) {
        const float angulo = -2.0f * PI * (float)k / NODO1_N;
        tablas->giro_re[k] = cosf(angulo);
        tablas->giro_im[k] = sinf(angulo);
    }
}

float nodo1_eliminar_dc(float muestras[NODO1_N])
{
    float suma = 0.0f;
    for (size_t n = 0; n < NODO1_N; ++n) {
        suma += muestras[n];
    }
    const float media = suma / NODO1_N;
    for (size_t n = 0; n < NODO1_N; ++n) {
        muestras[n] -= media;
    }
    return media;
}

void nodo1_convertir_adc(const uint16_t adc[NODO1_N], float salida[NODO1_N],
                         nodo1_metricas_t *metricas)
{
    *metricas = (nodo1_metricas_t){.adc_min = 4095};
    for (size_t n = 0; n < NODO1_N; ++n) {
        const uint16_t codigo = adc[n] & 0x0fffu;
        if (codigo < metricas->adc_min) metricas->adc_min = codigo;
        if (codigo > metricas->adc_max) metricas->adc_max = codigo;
        if (codigo == 0 || codigo == 4095) ++metricas->saturadas;
        salida[n] = (float)codigo * (NODO1_ADC_VREF / 4096.0f);
    }
    metricas->media_v = nodo1_eliminar_dc(salida);
    for (size_t n = 0; n < NODO1_N; ++n) {
        metricas->energia_ac_v2 += salida[n] * salida[n];
    }
    metricas->rms_ac_v = sqrtf(metricas->energia_ac_v2 / NODO1_N);
}

void nodo1_aplicar_hann(const float entrada[NODO1_N], const nodo1_tablas_t *tablas,
                        float real[NODO1_N], float imaginaria[NODO1_N])
{
    for (size_t n = 0; n < NODO1_N; ++n) {
        real[n] = entrada[n] * tablas->hann[n];
        imaginaria[n] = 0.0f;
    }
}

void nodo1_fft(float real[NODO1_N], float imaginaria[NODO1_N],
               const nodo1_tablas_t *tablas)
{
    /* Permutación por inversión de bits, seguida de mariposas iterativas. */
    for (size_t i = 1, j = 0; i < NODO1_N; ++i) {
        size_t bit = NODO1_N >> 1u;
        for (; j & bit; bit >>= 1u) j ^= bit;
        j ^= bit;
        if (i < j) {
            float temporal = real[i]; real[i] = real[j]; real[j] = temporal;
            temporal = imaginaria[i]; imaginaria[i] = imaginaria[j]; imaginaria[j] = temporal;
        }
    }
    for (size_t longitud = 2; longitud <= NODO1_N; longitud <<= 1u) {
        const size_t mitad = longitud / 2u;
        const size_t paso = NODO1_N / longitud;
        for (size_t base = 0; base < NODO1_N; base += longitud) {
            for (size_t j = 0; j < mitad; ++j) {
                const size_t a = base + j, b = a + mitad, k = j * paso;
                const float tr = tablas->giro_re[k] * real[b] -
                                 tablas->giro_im[k] * imaginaria[b];
                const float ti = tablas->giro_re[k] * imaginaria[b] +
                                 tablas->giro_im[k] * real[b];
                real[b] = real[a] - tr;
                imaginaria[b] = imaginaria[a] - ti;
                real[a] += tr;
                imaginaria[a] += ti;
            }
        }
    }
}

void nodo1_estimar_ruido(const float real[NODO1_N], const float imaginaria[NODO1_N],
                         float frecuencia_minima_hz, nodo1_metricas_t *metricas)
{
    float maxima = 0.0f, candidata = 0.0f;
    size_t pico = 0, pico_candidato = 0;
    for (size_t k = 1; k <= NODO1_N / 2u; ++k) {
        const float energia = real[k] * real[k] + imaginaria[k] * imaginaria[k];
        const float hz = (float)k * NODO1_FS_HZ / NODO1_N;
        if (energia > maxima) { maxima = energia; pico = k; }
        if (hz >= frecuencia_minima_hz && energia > candidata) {
            candidata = energia;
            pico_candidato = k;
        }
    }
    metricas->pico_hz = (float)pico * NODO1_FS_HZ / NODO1_N;
    metricas->candidata_valida = maxima > 1e-12f && candidata >= 1e-3f * maxima;
    metricas->candidata_ruido_hz = metricas->candidata_valida ?
        (float)pico_candidato * NODO1_FS_HZ / NODO1_N : 0.0f;
}

uint8_t nodo1_crc8(const uint8_t *datos, size_t cantidad)
{
    /* CRC-8/SMBUS: poly=07, init=00, refin=false, refout=false, xorout=00. */
    uint8_t crc = 0;
    for (size_t n = 0; n < cantidad; ++n) {
        crc ^= datos[n];
        for (unsigned bit = 0; bit < 8; ++bit) {
            crc = (uint8_t)((crc & 0x80u) ? ((unsigned)crc << 1u) ^ 0x07u :
                                                        (unsigned)crc << 1u);
        }
    }
    return crc;
}

static void escribir_u32_le(uint8_t *destino, uint32_t valor)
{
    for (unsigned byte = 0; byte < 4; ++byte) destino[byte] = (uint8_t)(valor >> (8u * byte));
}

bool nodo1_empaquetar(uint32_t id, const float muestras[NODO1_N],
                      uint8_t salida[NODO1_SPI_BYTES])
{
    salida[0] = 0xaa;
    salida[1] = 0xbb;
    escribir_u32_le(salida + 2, id);
    for (size_t n = 0; n < NODO1_N; ++n) {
        if (!isfinite(muestras[n])) return false;
        uint32_t bits;
        memcpy(&bits, &muestras[n], sizeof(bits));
        escribir_u32_le(salida + 6 + 4 * n, bits);
    }
    salida[NODO1_TRAMA_BYTES - 1u] = nodo1_crc8(salida, NODO1_TRAMA_BYTES - 1u);
    salida[NODO1_TRAMA_BYTES] = 0; /* Relleno fuera del CRC; longitud múltiplo de 4. */
    return true;
}
