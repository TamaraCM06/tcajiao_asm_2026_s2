/** Energia regional del ruido real de entrada y de los dos residuos filtrados. */
#pragma once
#include "fft_radix2.h"
#include <stddef.h>

typedef struct {
    float minimo_hz, maximo_hz;
    bool habilitada;
    size_t acumuladas, bloques;
    double energia[3];
    float residuos[3][FFT_LONGITUD];
    complejo_t transformada[FFT_LONGITUD];
} atenuacion_regional_t;

/** Valida una region con al menos un bin y reinicia sus acumuladores. */
bool regional_iniciar(atenuacion_regional_t *estado, float minimo_hz, float maximo_hz);
/** Agrega una muestra alineada; solo transforma bloques reales completos, sin relleno. */
void regional_agregar(atenuacion_regional_t *estado, float ruido, float residual_fir,
    float residual_espectral, const fft_plan_t *plan, const float *ventana);
/** Explica por que una razon no esta disponible; devuelve NULL si es medible. */
const char *regional_motivo(const atenuacion_regional_t *estado, unsigned metodo, bool con_referencia);
/** Devuelve decibelios o NaN cuando no existe una razon medible. */
double regional_atenuacion(const atenuacion_regional_t *estado, unsigned metodo, bool con_referencia);
