#include "generador_senales.h"

#include <math.h>

static const double RADIANES_POR_CICLO = 6.28318530717958647692;

// ---------------------------------------------------------------------------
// 1. Preparación de amplitudes y fases
// ---------------------------------------------------------------------------

/* Convierte la fase inicial a radianes y prepara el avance de una componente. */
static void preparar_componente(emisor_generador_t *generador_senales,
                               size_t indice_componente, double frecuencia_hz,
                               double amplitud, double fase_grados,
                               double frecuencia_muestreo_hz)
{
    double fase_radianes = fmod(fase_grados, 360.0) * (RADIANES_POR_CICLO / 360.0);
    if (fase_radianes < 0.0) {
        fase_radianes += RADIANES_POR_CICLO;
    }
    generador_senales->fases_iniciales_radianes[indice_componente] = fase_radianes;
    generador_senales->fases_actuales_radianes[indice_componente] = fase_radianes;
    generador_senales->incrementos_fase_radianes[indice_componente] =
        RADIANES_POR_CICLO * frecuencia_hz / frecuencia_muestreo_hz;
    generador_senales->amplitudes_escaladas[indice_componente] =
        amplitud * generador_senales->ganancia_comun;
}

/* Calcula el ruido para la SNR solicitada y la ganancia fija que limita la mezcla. */
static const char *preparar_amplitudes(emisor_generador_t *generador_senales,
                                     const emisor_config_t *configuracion)
{
    double suma_amplitudes = 0.0;
    double suma_cuadrados_amplitudes = 0.0;
    for (size_t indice_tono = 0; indice_tono < configuracion->cantidad_tonos; ++indice_tono) {
        const double amplitud = configuracion->tonos[indice_tono].amplitud;
        suma_amplitudes += amplitud;
        suma_cuadrados_amplitudes += amplitud * amplitud;
    }

    if (configuracion->modo == EMISOR_MULTITONO_CON_INTERFERENCIA) {
        /* Tonos distintos: potencia útil = sum(A_i²)/2; potencia de ruido = A_r²/2.
         * Por tanto A_r = sqrt(sum(A_i²)) * 10^(-SNR/20).
         * Es una relación de potencia estable, no una medida de un bloque corto. */
        generador_senales->amplitud_interferencia =
            sqrt(suma_cuadrados_amplitudes) * pow(10.0, -(double)configuracion->snr_db / 20.0);
        if (!isfinite(generador_senales->amplitud_interferencia) ||
            generador_senales->amplitud_interferencia <= 0.0) {
            return "La SNR solicitada produce una amplitud de ruido no representable.";
        }
        suma_amplitudes += generador_senales->amplitud_interferencia;
    }

    /* Esta cota usa |sin| <= 1. La ganancia se aplica por igual a útil y ruido
     * y se conserva durante toda la emisión, independientemente del bloque. */
    generador_senales->ganancia_comun = configuracion->limite_amplitud / suma_amplitudes;
    if (!isfinite(suma_amplitudes) || !isfinite(generador_senales->ganancia_comun) ||
        generador_senales->ganancia_comun <= 0.0) {
        return "Las amplitudes no permiten calcular una ganancia común representable.";
    }
    return NULL;
}

/* Inicializa un generador validado con amplitudes y fases propias de su configuración. */
const char *emisor_inicializar(emisor_generador_t *generador_senales,
                             const emisor_config_t *configuracion)
{
    if (generador_senales == NULL) {
        return "Falta el estado del generador.";
    }
    *generador_senales = (emisor_generador_t){0};
    const char *mensaje_error = emisor_validar_configuracion(configuracion);
    if (mensaje_error != NULL) {
        return mensaje_error;
    }
    mensaje_error = preparar_amplitudes(generador_senales, configuracion);
    if (mensaje_error != NULL) {
        return mensaje_error;
    }

    generador_senales->cantidad_componentes = configuracion->cantidad_tonos;
    for (size_t indice_tono = 0; indice_tono < configuracion->cantidad_tonos; ++indice_tono) {
        const emisor_tono_t *tono = &configuracion->tonos[indice_tono];
        preparar_componente(generador_senales, indice_tono, tono->frecuencia_hz,
                            tono->amplitud, tono->fase_grados,
                            configuracion->frecuencia_muestreo_hz);
    }
    if (configuracion->modo == EMISOR_MULTITONO_CON_INTERFERENCIA) {
        preparar_componente(generador_senales, generador_senales->cantidad_componentes,
                            configuracion->frecuencia_interferencia_hz,
                            generador_senales->amplitud_interferencia,
                            configuracion->fase_interferencia_grados,
                            configuracion->frecuencia_muestreo_hz);
        ++generador_senales->cantidad_componentes;
    }
    generador_senales->inicializado = true;
    return NULL;
}

// ---------------------------------------------------------------------------
// 2. Generación continua y reinicio
// ---------------------------------------------------------------------------

/* Produce muestras sumando senoides y conserva sus fases para la siguiente llamada. */
const char *emisor_generar(emisor_generador_t *generador_senales,
                         float *muestras_salida, size_t cantidad_muestras)
{
    if (generador_senales == NULL || !generador_senales->inicializado) {
        return "El generador debe inicializarse antes de producir muestras.";
    }
    if (cantidad_muestras > 0 && muestras_salida == NULL) {
        return "Falta el buffer de salida.";
    }

    for (size_t indice_muestra = 0; indice_muestra < cantidad_muestras; ++indice_muestra) {
        double muestra = 0.0;
        for (size_t indice_componente = 0;
             indice_componente < generador_senales->cantidad_componentes;
             ++indice_componente) {
            muestra += generador_senales->amplitudes_escaladas[indice_componente] *
                       sinf((float)generador_senales->fases_actuales_radianes[indice_componente]);

            /* Se conserva la fase entre llamadas. Como f < fs/2, basta restar
             * un ciclo cuando se alcanza 2*pi; no crece un contador de tiempo. */
            double fase_radianes = generador_senales->fases_actuales_radianes[indice_componente] +
                                   generador_senales->incrementos_fase_radianes[indice_componente];
            if (fase_radianes >= RADIANES_POR_CICLO) {
                fase_radianes -= RADIANES_POR_CICLO;
            }
            generador_senales->fases_actuales_radianes[indice_componente] = fase_radianes;
        }
        muestras_salida[indice_muestra] = (float)muestra;
    }
    return NULL;
}

/* Restaura las fases configuradas sin alterar amplitudes ni ganancia común. */
const char *emisor_reiniciar(emisor_generador_t *generador_senales)
{
    if (generador_senales == NULL || !generador_senales->inicializado) {
        return "El generador debe inicializarse antes de reiniciarlo.";
    }
    for (size_t indice_componente = 0;
         indice_componente < generador_senales->cantidad_componentes;
         ++indice_componente) {
        generador_senales->fases_actuales_radianes[indice_componente] =
            generador_senales->fases_iniciales_radianes[indice_componente];
    }
    return NULL;
}
