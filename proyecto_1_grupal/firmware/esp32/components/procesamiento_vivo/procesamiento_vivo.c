/** Ensambla ventanas continuas y conserva estados independientes para los dos filtros. */
#include "procesamiento_vivo.h"

#include <string.h>

#include "datos_digitales.h"

_Static_assert(PROCESAMIENTO_VIVO_ENTRADA_MUESTRAS == 256 && FFT_LONGITUD == 1024 &&
               FFT_SALTO == 512 && FIR_RETARDO == 37,
               "El flujo vivo requiere el contrato vigente de bloques y filtros.");
_Static_assert(SENALES_FRECUENCIA_MUESTREO_HZ == 16000,
               "Los coeficientes y la conversion Hz/bin actuales requieren 16000 Hz.");

/* El filtro existente exige una segunda entrada para evaluar una referencia.
 * Aqui no existe esa referencia: los ceros solo satisfacen su interfaz. Su salida
 * se descarta y no permite obtener SNR, MSE ni energia util de la captura real. */
static const float REFERENCIA_AUSENTE[FFT_LONGITUD] = {0};

/** Inicializa estados propios y coloca media ventana virtual antes de la captura real. */
bool procesamiento_vivo_inicializar(procesamiento_vivo_t *estado,
                                    espectral_configuracion_t configuracion)
{
    if (estado == NULL) return false;
    memset(estado, 0, sizeof(*estado));
    estado->configuracion = configuracion;
    if (!filtro_espectral_inicializar(&estado->espectral, configuracion)) return false;
    filtro_fir_reiniciar(&estado->fir);
    estado->descartar_ventana_inicial = true;
    estado->iniciada = true;
    return true;
}

/** Reinicia ambas rutas para impedir que una captura discontinua conserve solapamientos. */
void procesamiento_vivo_reiniciar(procesamiento_vivo_t *estado)
{
    if (estado == NULL || !estado->iniciada) return;
    const espectral_configuracion_t configuracion = estado->configuracion;
    (void)procesamiento_vivo_inicializar(estado, configuracion);
}

/** Aplica a la salida espectral el mismo retardo causal de 37 muestras que tiene el FIR. */
static void alinear_salida_espectral(procesamiento_vivo_t *estado, float *salida)
{
    for (size_t n = 0; n < FFT_SALTO; ++n) {
        salida[n] = estado->retardo_espectral[estado->posicion_retardo];
        estado->retardo_espectral[estado->posicion_retardo] = estado->salida_ventana[n];
        estado->posicion_retardo = (estado->posicion_retardo + 1u) % FIR_RETARDO;
    }
}

/** Procesa 256 muestras y publica dos bloques comparables cuando termina un salto util. */
bool procesamiento_vivo_bloque(procesamiento_vivo_t *estado,
                               const float entrada[PROCESAMIENTO_VIVO_ENTRADA_MUESTRAS],
                               float salida_fir[PROCESAMIENTO_VIVO_SALIDA_MUESTRAS],
                               float salida_espectral[PROCESAMIENTO_VIVO_SALIDA_MUESTRAS])
{
    if (estado == NULL || !estado->iniciada || entrada == NULL ||
        salida_fir == NULL || salida_espectral == NULL) return false;

    const size_t inicio = estado->muestras_acumuladas;
    memcpy(estado->ventana_mezcla + FFT_SALTO + inicio, entrada,
           PROCESAMIENTO_VIVO_ENTRADA_MUESTRAS * sizeof(float));
    for (size_t n = 0; n < PROCESAMIENTO_VIVO_ENTRADA_MUESTRAS; ++n) {
        estado->fir_actual[inicio + n] =
            filtro_fir_muestra(&estado->fir, COEFICIENTES_FIR, entrada[n]);
    }
    estado->muestras_acumuladas += PROCESAMIENTO_VIVO_ENTRADA_MUESTRAS;
    if (estado->muestras_acumuladas < FFT_SALTO) return false;

    filtro_espectral_bloque(&estado->espectral, estado->ventana_mezcla,
                           REFERENCIA_AUSENTE, estado->salida_ventana,
                           estado->util_descartada);
    /* La primera ventana abarca [-512, 511]. Su primera mitad es anterior a la
     * captura y solo prepara el solapamiento para reconstruir desde la muestra 0. */
    const bool salida_disponible = !estado->descartar_ventana_inicial;
    if (salida_disponible) {
        memcpy(salida_fir, estado->fir_anterior, sizeof(estado->fir_anterior));
        alinear_salida_espectral(estado, salida_espectral);
    }
    memcpy(estado->fir_anterior, estado->fir_actual, sizeof(estado->fir_anterior));
    memmove(estado->ventana_mezcla, estado->ventana_mezcla + FFT_SALTO,
            FFT_SALTO * sizeof(float));
    estado->muestras_acumuladas = 0;
    estado->descartar_ventana_inicial = false;
    return salida_disponible;
}
