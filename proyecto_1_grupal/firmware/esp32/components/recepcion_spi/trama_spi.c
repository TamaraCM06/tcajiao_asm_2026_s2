/** Valida tramas SPI de la Pico y clasifica discontinuidades sin depender del SDK. */
#include "trama_spi.h"

#include <float.h>
#include <limits.h>
#include <math.h>
#include <string.h>

_Static_assert(CHAR_BIT == 8 && sizeof(float) == 4 && FLT_RADIX == 2 &&
               FLT_MANT_DIG == 24 && FLT_MAX_EXP == 128,
               "El contrato requiere bytes de 8 bits y float IEEE-754 binario32.");

/** Reconstruye un entero little-endian sin exigir alineacion del buffer. */
static uint32_t leer_u32_le(const uint8_t *datos)
{
    return (uint32_t)datos[0] | (uint32_t)datos[1] << 8u |
           (uint32_t)datos[2] << 16u | (uint32_t)datos[3] << 24u;
}

/** Calcula CRC-8/SMBUS: polinomio 0x07, inicio y xor final cero, sin reflexion. */
static uint8_t calcular_crc8(const uint8_t *datos, size_t cantidad)
{
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

/** Lee los bits IEEE-754 mediante un entero alineado y memcpy, sin aliasing inseguro. */
static float leer_float32_le(const uint8_t *datos)
{
    const uint32_t bits = leer_u32_le(datos);
    float muestra;
    memcpy(&muestra, &bits, sizeof(muestra));
    return muestra;
}

/** Revisa toda la trama antes de publicar identificador o muestras al llamador. */
trama_spi_resultado_t trama_spi_decodificar(const uint8_t *datos, size_t cantidad_bits,
                                          trama_spi_bloque_t *bloque)
{
    if (datos == NULL || bloque == NULL) return TRAMA_SPI_ARGUMENTO_INVALIDO;
    if (cantidad_bits != TRAMA_SPI_BYTES_TRANSFERENCIA * 8u) {
        return TRAMA_SPI_LONGITUD_INVALIDA;
    }
    if (datos[0] != 0xaa || datos[1] != 0xbb) return TRAMA_SPI_CABECERA_INVALIDA;
    const size_t posicion_crc = TRAMA_SPI_BYTES_LOGICOS - 1u;
    if (calcular_crc8(datos, posicion_crc) != datos[posicion_crc]) {
        return TRAMA_SPI_CRC_INVALIDO;
    }
    /* Dos recorridos evitan modificar la salida si falla la ultima muestra,
     * sin necesitar una copia adicional de 1 KiB en la pila de la tarea. */
    for (size_t n = 0; n < TRAMA_SPI_MUESTRAS; ++n) {
        if (!isfinite(leer_float32_le(datos + 6u + 4u * n))) {
            return TRAMA_SPI_MUESTRA_NO_FINITA;
        }
    }
    bloque->id = leer_u32_le(datos + 2u);
    for (size_t n = 0; n < TRAMA_SPI_MUESTRAS; ++n) {
        bloque->muestras[n] = leer_float32_le(datos + 6u + 4u * n);
    }
    return TRAMA_SPI_VALIDA;
}

/** Clasifica la diferencia modular; un retroceso inicia una nueva referencia. */
trama_spi_continuidad_t trama_spi_actualizar_secuencia(trama_spi_secuencia_t *secuencia,
                                                     uint32_t id)
{
    trama_spi_continuidad_t resultado = {.evento = TRAMA_SPI_PRIMER_BLOQUE};
    if (secuencia->iniciada) {
        const uint32_t diferencia = id - secuencia->ultimo_id;
        if (diferencia == 0) {
            resultado.evento = TRAMA_SPI_DUPLICADO;
        } else if (diferencia == 1) {
            resultado.evento = TRAMA_SPI_CONTINUO;
        } else if (diferencia < UINT32_C(0x80000000)) {
            resultado.evento = TRAMA_SPI_SALTO;
            resultado.ids_omitidos = diferencia - 1u;
        } else {
            resultado.evento = TRAMA_SPI_RETROCESO;
        }
    }
    secuencia->iniciada = true;
    secuencia->ultimo_id = id;
    return resultado;
}
