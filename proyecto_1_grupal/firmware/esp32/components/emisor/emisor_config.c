#include "emisor_config.h"

#include <math.h>

// ---------------------------------------------------------------------------
// 1. Configuraciones de las señales
// ---------------------------------------------------------------------------

/* Indica si el modo corresponde a una de las señales disponibles del emisor. */
static int modo_valido(emisor_modo_t modo)
{
    return modo == EMISOR_TONO || modo == EMISOR_MULTITONO ||
           modo == EMISOR_MULTITONO_CON_INTERFERENCIA;
}

/* Carga frecuencias, amplitudes, fases y SNR iniciales para el modo solicitado. */
const char *emisor_config_predeterminada(emisor_modo_t modo,
                                       emisor_config_t *configuracion)
{
    if (configuracion == NULL) {
        return "Falta el destino de la configuración.";
    }
    if (!modo_valido(modo)) {
        return "Modo de emisión desconocido.";
    }

    *configuracion = (emisor_config_t){
        .modo = modo,
        .frecuencia_muestreo_hz = 16000,
        .cantidad_tonos = modo == EMISOR_TONO ? 1 : EMISOR_CANTIDAD_MAXIMA_TONOS,
        .tonos = {
            {.frecuencia_hz = 440.0f, .amplitud = 1.0f, .fase_grados = 0.0f},
            {.frecuencia_hz = 880.0f, .amplitud = 0.55f, .fase_grados = 35.0f},
            {.frecuencia_hz = 1320.0f, .amplitud = 0.3f, .fase_grados = -50.0f},
        },
        .frecuencia_interferencia_hz = 4000.0f,
        .fase_interferencia_grados = 0.0f,
        .snr_db = 10.0f,
        .limite_amplitud = 0.8f,
    };
    return NULL;
}

// ---------------------------------------------------------------------------
// 2. Validación de parámetros
// ---------------------------------------------------------------------------

/* Comprueba que una frecuencia sea finita y esté entre cero y Nyquist. */
static int frecuencia_valida(float frecuencia_hz, double frecuencia_nyquist_hz)
{
    return isfinite(frecuencia_hz) && frecuencia_hz > 0.0f &&
           frecuencia_hz < frecuencia_nyquist_hz;
}

/* Verifica la cantidad de tonos y sus parámetros, además de exigir señal útil. */
static const char *validar_tonos_utiles(const emisor_config_t *configuracion)
{
    if (configuracion->cantidad_tonos == 0 ||
        configuracion->cantidad_tonos > EMISOR_CANTIDAD_MAXIMA_TONOS ||
        (configuracion->modo == EMISOR_TONO && configuracion->cantidad_tonos != 1) ||
        (configuracion->modo != EMISOR_TONO && configuracion->cantidad_tonos < 2)) {
        return "Se requiere un tono en modo individual o entre dos y tres en multitono.";
    }

    const double frecuencia_nyquist_hz = configuracion->frecuencia_muestreo_hz / 2.0;
    double suma_amplitudes = 0.0;
    for (size_t indice_tono = 0; indice_tono < configuracion->cantidad_tonos; ++indice_tono) {
        const emisor_tono_t *tono = &configuracion->tonos[indice_tono];
        if (!frecuencia_valida(tono->frecuencia_hz, frecuencia_nyquist_hz)) {
            return "Cada tono debe tener frecuencia finita, mayor que cero y menor que Nyquist.";
        }
        if (!isfinite(tono->amplitud) || tono->amplitud < 0.0f ||
            !isfinite(tono->fase_grados)) {
            return "Cada tono requiere amplitud finita no negativa y fase finita.";
        }
        suma_amplitudes += tono->amplitud;
    }
    if (suma_amplitudes == 0.0) {
        return "Al menos un tono útil debe tener amplitud positiva.";
    }
    return NULL;
}

/* Valida el ruido configurado y la separación de frecuencias necesaria para la SNR. */
static const char *validar_interferencia(const emisor_config_t *configuracion)
{
    const double frecuencia_nyquist_hz = configuracion->frecuencia_muestreo_hz / 2.0;
    /* Estos parámetros también quedan definidos en los modos sin ruido, pero
     * solo se utilizan para sintetizar la mezcla con interferencia. */
    if (!frecuencia_valida(configuracion->frecuencia_interferencia_hz, frecuencia_nyquist_hz) ||
        !isfinite(configuracion->fase_interferencia_grados) || !isfinite(configuracion->snr_db)) {
        return "La interferencia requiere frecuencia dentro de Nyquist, fase y SNR finitas.";
    }
    if (configuracion->modo == EMISOR_MULTITONO_CON_INTERFERENCIA) {
        for (size_t indice_tono = 0; indice_tono < configuracion->cantidad_tonos; ++indice_tono) {
            if (configuracion->tonos[indice_tono].frecuencia_hz ==
                configuracion->frecuencia_interferencia_hz) {
                return "La interferencia debe tener frecuencia distinta de los tonos útiles.";
            }
            for (size_t indice_tono_anterior = 0; indice_tono_anterior < indice_tono;
                 ++indice_tono_anterior) {
                if (configuracion->tonos[indice_tono].frecuencia_hz ==
                    configuracion->tonos[indice_tono_anterior].frecuencia_hz) {
                    return "La SNR de la mezcla requiere tonos útiles de frecuencias distintas.";
                }
            }
        }
    }
    return NULL;
}

/* Coordina las comprobaciones generales y las validaciones específicas de la señal. */
const char *emisor_validar_configuracion(const emisor_config_t *configuracion)
{
    if (configuracion == NULL) {
        return "Falta la configuración del emisor.";
    }
    if (!modo_valido(configuracion->modo)) {
        return "Modo de emisión desconocido.";
    }
    if (configuracion->frecuencia_muestreo_hz == 0) {
        return "La frecuencia de muestreo debe ser positiva.";
    }

    const char *mensaje_error = validar_tonos_utiles(configuracion);
    if (mensaje_error != NULL) {
        return mensaje_error;
    }
    if (!isfinite(configuracion->limite_amplitud) || configuracion->limite_amplitud <= 0.0f ||
        configuracion->limite_amplitud > 1.0f) {
        return "El límite de amplitud debe ser finito, mayor que cero y no mayor que uno.";
    }
    return validar_interferencia(configuracion);
}
