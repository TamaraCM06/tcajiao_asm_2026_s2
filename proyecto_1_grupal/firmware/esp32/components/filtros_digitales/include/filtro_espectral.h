#pragma once
#include "fft_radix2.h"

typedef struct {
    float frecuencia_minima_hz, ancho_hz, factor, umbral_relativo;
} espectral_configuracion_t;
typedef struct {
    fft_plan_t transformada;
    float ventana[FFT_LONGITUD];
    complejo_t mezcla[FFT_LONGITUD], referencia[FFT_LONGITUD];
    float energia[FFT_SALTO + 1], ganancias[FFT_SALTO + 1];
    float acumulada[FFT_LONGITUD], util[FFT_LONGITUD], pesos[FFT_LONGITUD];
    espectral_configuracion_t configuracion;
} filtro_espectral_t;
/* Reinicia la reconstruccion y valida parametros a 16000 Hz; devuelve false si son invalidos. */
bool filtro_espectral_inicializar(filtro_espectral_t *estado, espectral_configuracion_t configuracion);
/* Procesa ventanas sucesivas separadas 512 muestras y entrega 512 muestras definitivas.
 * La referencia solo se filtra con las ganancias calculadas desde la mezcla. */
void filtro_espectral_bloque(filtro_espectral_t *estado, const float *mezcla,
    const float *referencia, float *salida, float *util);
