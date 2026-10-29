#pragma once

#include <stddef.h>
#include <stdint.h>

enum {
    SENALES_FRECUENCIA_MUESTREO_HZ = 16000,
    SENALES_MUESTRAS_POR_BLOQUE = 256,
    SENALES_MAXIMO_MUESTRAS = 96000,
};

typedef enum {
    SENAL_CASO_1,
    SENAL_CASO_2,
    SENAL_CASO_3,
} senal_embebida_id_t;

typedef struct {
    const char *nombre;
    const uint8_t *codigos_dac;
    size_t cantidad_muestras;
    uint32_t frecuencia_muestreo_hz;
    uint32_t crc32; /* Identificador de los códigos exportados, sin cálculo durante la reproducción. */
} senal_embebida_t;

/* Devuelve un registro de solo lectura; un identificador desconocido devuelve NULL. */
const senal_embebida_t *senales_embebidas_obtener(senal_embebida_id_t identificador);
