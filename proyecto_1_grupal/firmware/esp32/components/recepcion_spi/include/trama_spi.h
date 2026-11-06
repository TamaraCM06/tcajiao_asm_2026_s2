/** Interpreta el contrato binario de la Pico y sigue su secuencia, sin perifericos. */
#pragma once

#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

/* Contrato v1 de nodo1_metodos.h; las pruebas comprueban ambos extremos. */
#define TRAMA_SPI_MUESTRAS 256u
#define TRAMA_SPI_BYTES_LOGICOS (2u + 4u + 4u * TRAMA_SPI_MUESTRAS + 1u)
#define TRAMA_SPI_BYTES_TRANSFERENCIA (TRAMA_SPI_BYTES_LOGICOS + 1u)

typedef struct {
    uint32_t id;
    float muestras[TRAMA_SPI_MUESTRAS]; /* Voltios sin componente DC. */
} trama_spi_bloque_t;

typedef enum {
    TRAMA_SPI_VALIDA,
    TRAMA_SPI_ARGUMENTO_INVALIDO,
    TRAMA_SPI_LONGITUD_INVALIDA,
    TRAMA_SPI_CABECERA_INVALIDA,
    TRAMA_SPI_CRC_INVALIDO,
    TRAMA_SPI_MUESTRA_NO_FINITA,
    TRAMA_SPI_MUESTRA_FUERA_RANGO,
} trama_spi_resultado_t;

typedef struct {
    bool iniciada;
    uint32_t ultimo_id;
} trama_spi_secuencia_t;

typedef enum {
    TRAMA_SPI_PRIMER_BLOQUE,
    TRAMA_SPI_CONTINUO,
    TRAMA_SPI_SALTO,
    TRAMA_SPI_DUPLICADO,
    TRAMA_SPI_RETROCESO,
} trama_spi_evento_t;

typedef struct {
    trama_spi_evento_t evento;
    uint32_t ids_omitidos; /* Solo para SALTO; no atribuye una causa a los huecos. */
} trama_spi_continuidad_t;

/**
 * Valida una transferencia completa y solo entonces escribe el bloque de salida.
 * @param datos Buffer del llamador, sin requisito de alineacion; no puede solaparse
 * con bloque. Debe contener los bytes indicados por cantidad_bits.
 * @param cantidad_bits Longitud observada por SPI en bits, incluidos los de relleno.
 * Se exige exactamente TRAMA_SPI_BYTES_TRANSFERENCIA * 8; el relleno no lleva CRC.
 * @param bloque Salida propiedad del llamador; queda intacta ante cualquier error.
 * @return Causa del rechazo o TRAMA_SPI_VALIDA. No conserva punteros ni reserva memoria.
 * Ejecutar en tarea, nunca desde callbacks de interrupcion.
 */
trama_spi_resultado_t trama_spi_decodificar(const uint8_t *datos, size_t cantidad_bits,
                                          trama_spi_bloque_t *bloque);

/**
 * Actualiza la referencia usando exclusivamente identificadores de bloques validos.
 * @param secuencia Estado no nulo, inicializado a cero y usado por una sola tarea.
 * @param id Identificador recibido. La primera llamada establece la referencia.
 * @return Evento y cantidad de identificadores omitidos si hubo un salto hacia delante.
 * La diferencia se calcula modulo 2^32: UINT32_MAX -> 0 es continuo. Diferencias
 * desde 2^31 se consideran retroceso y establecen otra referencia sin sumar perdidas.
 * Un duplicado conserva la referencia. Un retroceso puede ser reinicio o desorden;
 * el protocolo no permite confirmarlo, ni distinguir saltos de media vuelta o mas.
 */
trama_spi_continuidad_t trama_spi_actualizar_secuencia(trama_spi_secuencia_t *secuencia,
                                                     uint32_t id);
