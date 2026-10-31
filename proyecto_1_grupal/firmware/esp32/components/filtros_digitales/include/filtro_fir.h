#pragma once
#include <stddef.h>
enum { FIR_COEFICIENTES = 75, FIR_RETARDO = 37, FIR_BLOQUE = 256 };
typedef struct { float historia[FIR_COEFICIENTES]; size_t posicion; } filtro_fir_t;
/* Borra la historia al comenzar un registro independiente. */
void filtro_fir_reiniciar(filtro_fir_t *estado);
/* Procesa una muestra con estado persistente y los 75 coeficientes exportados. */
float filtro_fir_muestra(filtro_fir_t *estado, const float *coeficientes, float entrada);
