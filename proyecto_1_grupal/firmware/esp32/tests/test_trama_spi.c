/** Comprueba el receptor con el emisor real y tramas alteradas, sin hardware ni SDK. */
#include "trama_spi.h"
#include "nodo1_metodos.h"

#include <assert.h>
#include <stdio.h>
#include <string.h>

_Static_assert(TRAMA_SPI_MUESTRAS == NODO1_N, "Cantidad de muestras incompatible.");
_Static_assert(TRAMA_SPI_BYTES_LOGICOS == NODO1_TRAMA_BYTES, "Trama incompatible.");
_Static_assert(TRAMA_SPI_BYTES_TRANSFERENCIA == NODO1_SPI_BYTES, "Transferencia incompatible.");

static float muestras[NODO1_N];
/* +1 permite comprobar tambien un origen desalineado y longitudes excesivas. */
static uint8_t almacenamiento[NODO1_SPI_BYTES + 1u];
static uint8_t *const trama = almacenamiento + 1u;
static trama_spi_bloque_t bloque;

/** Prepara una trama usando el mismo empaquetador que se ejecuta en la Pico. */
static void preparar_trama(void)
{
    for (size_t n = 0; n < NODO1_N; ++n) muestras[n] = ((float)n - 128.0f) / 256.0f;
    assert(nodo1_empaquetar(UINT32_C(0x12345678), muestras, trama));
}

/** Verifica el resultado y que un rechazo no deje muestras parcialmente publicadas. */
static void comprobar_rechazo(size_t cantidad_bits, trama_spi_resultado_t esperado)
{
    unsigned char anterior[sizeof(bloque)];
    memset(&bloque, 0xa5, sizeof(bloque));
    memcpy(anterior, &bloque, sizeof(bloque));
    assert(trama_spi_decodificar(trama, cantidad_bits, &bloque) == esperado);
    assert(memcmp(anterior, &bloque, sizeof(bloque)) == 0);
}

/** Comprueba datos reales, el orden de bytes y el relleno excluido del CRC. */
static void probar_trama_valida(void)
{
    preparar_trama();
    assert(trama_spi_decodificar(trama, NODO1_SPI_BYTES * 8u, &bloque) == TRAMA_SPI_VALIDA);
    assert(bloque.id == UINT32_C(0x12345678));
    for (size_t n = 0; n < NODO1_N; ++n) assert(bloque.muestras[n] == muestras[n]);
    trama[NODO1_TRAMA_BYTES] = 0xfe;
    assert(trama_spi_decodificar(trama, NODO1_SPI_BYTES * 8u, &bloque) == TRAMA_SPI_VALIDA);
}

/** Rechaza longitudes incompletas, incluso por un bit, cabeceras y CRC alterados. */
static void probar_errores_trama(void)
{
    preparar_trama();
    comprobar_rechazo(0, TRAMA_SPI_LONGITUD_INVALIDA);
    comprobar_rechazo(NODO1_TRAMA_BYTES * 8u, TRAMA_SPI_LONGITUD_INVALIDA);
    comprobar_rechazo(NODO1_SPI_BYTES * 8u - 1u, TRAMA_SPI_LONGITUD_INVALIDA);
    comprobar_rechazo(NODO1_SPI_BYTES * 8u + 1u, TRAMA_SPI_LONGITUD_INVALIDA);
    comprobar_rechazo((NODO1_SPI_BYTES + 1u) * 8u, TRAMA_SPI_LONGITUD_INVALIDA);
    for (size_t n = 0; n < 2; ++n) {
        trama[n] ^= 1u;
        comprobar_rechazo(NODO1_SPI_BYTES * 8u, TRAMA_SPI_CABECERA_INVALIDA);
        trama[n] ^= 1u;
    }
    const size_t posiciones[] = {2u, 6u, NODO1_TRAMA_BYTES - 2u, NODO1_TRAMA_BYTES - 1u};
    for (size_t n = 0; n < sizeof(posiciones) / sizeof(posiciones[0]); ++n) {
        trama[posiciones[n]] ^= 1u;
        comprobar_rechazo(NODO1_SPI_BYTES * 8u, TRAMA_SPI_CRC_INVALIDO);
        trama[posiciones[n]] ^= 1u;
    }
    assert(trama_spi_decodificar(NULL, NODO1_SPI_BYTES * 8u, &bloque) ==
           TRAMA_SPI_ARGUMENTO_INVALIDO);
    assert(trama_spi_decodificar(trama, NODO1_SPI_BYTES * 8u, NULL) ==
           TRAMA_SPI_ARGUMENTO_INVALIDO);
}

/** Introduce NaN e infinitos con CRC correcto: el CRC solo no garantiza muestras validas. */
static void probar_muestras_no_finitas(void)
{
    const uint8_t valores[][4] = {{0x00, 0x00, 0xc0, 0x7f},
                                  {0x00, 0x00, 0x80, 0x7f},
                                  {0x00, 0x00, 0x80, 0xff}};
    for (size_t n = 0; n < sizeof(valores) / sizeof(valores[0]); ++n) {
        preparar_trama();
        memcpy(trama + 6u + 4u * (NODO1_N - 1u), valores[n], 4u);
        trama[NODO1_TRAMA_BYTES - 1u] = nodo1_crc8(trama, NODO1_TRAMA_BYTES - 1u);
        comprobar_rechazo(NODO1_SPI_BYTES * 8u, TRAMA_SPI_MUESTRA_NO_FINITA);
    }
}

/** Comprueba un paso de secuencia, su diagnostico y la nueva referencia. */
static void comprobar_secuencia(trama_spi_secuencia_t *secuencia, uint32_t id,
                                trama_spi_evento_t evento, uint32_t omitidos)
{
    const trama_spi_continuidad_t resultado = trama_spi_actualizar_secuencia(secuencia, id);
    assert(resultado.evento == evento && resultado.ids_omitidos == omitidos);
    assert(secuencia->iniciada && secuencia->ultimo_id == id);
}

/** Comprueba huecos, duplicados, reinicio aparente y continuidad al desbordar uint32. */
static void probar_secuencia(void)
{
    trama_spi_secuencia_t secuencia = {0};
    comprobar_secuencia(&secuencia, 100, TRAMA_SPI_PRIMER_BLOQUE, 0);
    comprobar_secuencia(&secuencia, 101, TRAMA_SPI_CONTINUO, 0);
    comprobar_secuencia(&secuencia, 104, TRAMA_SPI_SALTO, 2);
    comprobar_secuencia(&secuencia, 104, TRAMA_SPI_DUPLICADO, 0);
    comprobar_secuencia(&secuencia, 0, TRAMA_SPI_RETROCESO, 0);
    comprobar_secuencia(&secuencia, 1, TRAMA_SPI_CONTINUO, 0);
    comprobar_secuencia(&secuencia, 0, TRAMA_SPI_RETROCESO, 0);
    comprobar_secuencia(&secuencia, UINT32_C(0x80000000), TRAMA_SPI_RETROCESO, 0);
    secuencia = (trama_spi_secuencia_t){0};
    comprobar_secuencia(&secuencia, UINT32_MAX - 1u, TRAMA_SPI_PRIMER_BLOQUE, 0);
    comprobar_secuencia(&secuencia, UINT32_MAX, TRAMA_SPI_CONTINUO, 0);
    comprobar_secuencia(&secuencia, 0, TRAMA_SPI_CONTINUO, 0);
    secuencia = (trama_spi_secuencia_t){.iniciada = true, .ultimo_id = UINT32_MAX - 1u};
    comprobar_secuencia(&secuencia, 1, TRAMA_SPI_SALTO, 2);
}

/** Ejecuta las comprobaciones del contrato y de la secuencia en la computadora. */
int main(void)
{
    probar_trama_valida();
    probar_errores_trama();
    probar_muestras_no_finitas();
    probar_secuencia();
    puts("Tramas SPI: contrato Pico/ESP32, rechazos y secuencia OK (sin hardware).");
    return 0;
}
