#include "filtro_espectral.h"
#include <math.h>
#include <string.h>

/* Prepara Hann simetrica como numpy.hanning y estado acotado de overlap-add. */
bool filtro_espectral_inicializar(filtro_espectral_t *estado, espectral_configuracion_t configuracion)
{
    if (!estado || !isfinite(configuracion.frecuencia_minima_hz) ||
        !isfinite(configuracion.ancho_hz) || !isfinite(configuracion.factor) ||
        !isfinite(configuracion.umbral_relativo) || configuracion.frecuencia_minima_hz < 0 ||
        configuracion.frecuencia_minima_hz >= 8000 || configuracion.ancho_hz < 0 ||
        configuracion.ancho_hz > 8000 || configuracion.factor < 0 || configuracion.factor > 1 ||
        configuracion.umbral_relativo <= 0 || configuracion.umbral_relativo > 1) return false;
    memset(estado, 0, sizeof(*estado));
    estado->configuracion = configuracion;
    fft_preparar(&estado->transformada);
    for (int indice = 0; indice < FFT_LONGITUD; ++indice)
        estado->ventana[indice] = (float)(0.5 - 0.5 * cos(6.2831853071795864769 * indice / (FFT_LONGITUD - 1)));
    return true;
}

/* Estima el umbral regional y expande bins seleccionados sin invadir la banda protegida. */
static void estimar_ganancias(filtro_espectral_t *estado)
{
    int primer_bin = (int)ceilf(estado->configuracion.frecuencia_minima_hz / 15.625f);
    int radio = (int)floorf(estado->configuracion.ancho_hz / 31.25f);
    float pico_global = 0, pico_regional = 0;
    for (int indice = 0; indice <= FFT_SALTO; ++indice) {
        complejo_t valor = estado->mezcla[indice];
        estado->energia[indice] = valor.real * valor.real + valor.imaginaria * valor.imaginaria;
        pico_global = fmaxf(pico_global, estado->energia[indice]);
        if (indice >= primer_bin) pico_regional = fmaxf(pico_regional, estado->energia[indice]);
        estado->ganancias[indice] = 1;
    }
    if (pico_global == 0 || pico_regional < 0.001f * pico_global) return;
    float umbral = fmaxf(estado->configuracion.umbral_relativo * pico_regional, 0.001f * pico_global);
    for (int indice = primer_bin; indice <= FFT_SALTO; ++indice) {
        if (estado->energia[indice] < umbral) continue;
        int primero = indice - radio > primer_bin ? indice - radio : primer_bin;
        int ultimo = indice + radio < FFT_SALTO ? indice + radio : FFT_SALTO;
        for (int vecino = primero; vecino <= ultimo; ++vecino)
            estado->ganancias[vecino] = estado->configuracion.factor;
    }
}

/* Reconstruye ambas rutas con las mismas ganancias reales y simetria conjugada. */
void filtro_espectral_bloque(filtro_espectral_t *estado, const float *mezcla,
    const float *referencia, float *salida, float *util)
{
    for (int indice = 0; indice < FFT_LONGITUD; ++indice) {
        estado->mezcla[indice] = (complejo_t){mezcla[indice] * estado->ventana[indice], 0};
        estado->referencia[indice] = (complejo_t){referencia[indice] * estado->ventana[indice], 0};
    }
    fft_transformar(&estado->transformada, estado->mezcla, false);
    estimar_ganancias(estado);
    fft_transformar(&estado->transformada, estado->referencia, false);
    for (int indice = 0; indice < FFT_LONGITUD; ++indice) {
        int bin_positivo = indice <= FFT_SALTO ? indice : FFT_LONGITUD - indice;
        float ganancia = estado->ganancias[bin_positivo];
        estado->mezcla[indice].real *= ganancia;
        estado->mezcla[indice].imaginaria *= ganancia;
        estado->referencia[indice].real *= ganancia;
        estado->referencia[indice].imaginaria *= ganancia;
    }
    fft_transformar(&estado->transformada, estado->mezcla, true);
    fft_transformar(&estado->transformada, estado->referencia, true);
    for (int indice = 0; indice < FFT_LONGITUD; ++indice) {
        float ventana = estado->ventana[indice];
        estado->acumulada[indice] += estado->mezcla[indice].real * ventana;
        estado->util[indice] += estado->referencia[indice].real * ventana;
        estado->pesos[indice] += ventana * ventana;
    }
    for (int indice = 0; indice < FFT_SALTO; ++indice) {
        float peso = estado->pesos[indice];
        salida[indice] = peso > 0 ? estado->acumulada[indice] / peso : 0;
        util[indice] = peso > 0 ? estado->util[indice] / peso : 0;
    }
    memmove(estado->acumulada, estado->acumulada + FFT_SALTO, FFT_SALTO * sizeof(float));
    memmove(estado->util, estado->util + FFT_SALTO, FFT_SALTO * sizeof(float));
    memmove(estado->pesos, estado->pesos + FFT_SALTO, FFT_SALTO * sizeof(float));
    memset(estado->acumulada + FFT_SALTO, 0, FFT_SALTO * sizeof(float));
    memset(estado->util + FFT_SALTO, 0, FFT_SALTO * sizeof(float));
    memset(estado->pesos + FFT_SALTO, 0, FFT_SALTO * sizeof(float));
}
