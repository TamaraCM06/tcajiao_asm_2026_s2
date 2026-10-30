#pragma once
#include <stdbool.h>
#include <stddef.h>
typedef struct {
    size_t muestras;
    double energia_referencia, energia_ruido_entrada, energia_error;
    double energia_util, energia_ruido_salida, energia_distorsion;
} metricas_acumulador_t;
typedef struct {
    double snr_entrada_db, snr_salida_db, mejora_snr_db, mse;
    double energia_util_pct, atenuacion_ruido_db, distorsion_util_db;
} metricas_resultado_t;
/* Acumula energias en doble precision; devuelve false ante muestras no finitas. */
bool metricas_acumular(metricas_acumulador_t *estado, float mezcla, float referencia,
                      float salida, float util);
/* Convierte las sumas en medidas; conserva NaN/infinito cuando no hay energia. */
metricas_resultado_t metricas_finalizar(const metricas_acumulador_t *estado);
