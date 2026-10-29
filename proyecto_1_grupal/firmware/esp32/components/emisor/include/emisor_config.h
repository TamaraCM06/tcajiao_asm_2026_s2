#ifndef EMISOR_CONFIG_H
#define EMISOR_CONFIG_H

#include <stddef.h>
#include <stdint.h>

enum {
    EMISOR_CANTIDAD_MAXIMA_TONOS = 3,
    EMISOR_MUESTRAS_POR_BLOQUE = 256
};

typedef enum {
    EMISOR_TONO,
    EMISOR_MULTITONO,
    EMISOR_MULTITONO_CON_INTERFERENCIA
} emisor_modo_t;

typedef struct {
    float frecuencia_hz;
    float amplitud;          /* Peso relativo, antes de la ganancia común. */
    float fase_grados;
} emisor_tono_t;

typedef struct {
    emisor_modo_t modo;
    uint32_t frecuencia_muestreo_hz;
    size_t cantidad_tonos;
    emisor_tono_t tonos[EMISOR_CANTIDAD_MAXIMA_TONOS];
    float frecuencia_interferencia_hz;
    float fase_interferencia_grados;
    float snr_db;
    float limite_amplitud;   /* Límite normalizado de salida: 0 < límite <= 1. */
} emisor_config_t;

/* Contrato de errores: las operaciones devuelven NULL si tienen éxito o un
 * mensaje estático que el llamador puede mostrar. No hay que liberar el mensaje. */

/* Completa la configuración con los parámetros predeterminados del modo elegido. */
const char *emisor_config_predeterminada(emisor_modo_t modo,
                                       emisor_config_t *configuracion);

/* Valida modo, muestreo, amplitudes, fases y frecuencias de la configuración.
 * Los tonos inactivos no se evalúan; en mezcla se exigen frecuencias distintas. */
const char *emisor_validar_configuracion(const emisor_config_t *configuracion);

#endif
