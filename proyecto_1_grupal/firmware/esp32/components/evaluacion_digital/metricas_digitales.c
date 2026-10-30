#include "metricas_digitales.h"
#include <math.h>

/* Mantiene las convenciones del modulo metricas.py para ceros e infinitos. */
static double relacion_db(double numerador, double denominador)
{
    if (numerador == 0) return denominador == 0 ? NAN : -INFINITY;
    return denominador == 0 ? INFINITY : 10 * log10(numerador / denominador);
}

/* Compara muestras ya alineadas sin utilizar la referencia para filtrar. */
bool metricas_acumular(metricas_acumulador_t *estado, float mezcla, float referencia,
                      float salida, float util)
{
    if (!isfinite(mezcla) || !isfinite(referencia) || !isfinite(salida) || !isfinite(util)) return false;
    double ruido = (double)mezcla - referencia;
    double error = (double)referencia - salida;
    double residual = (double)salida - util;
    double distorsion = (double)referencia - util;
    estado->energia_referencia += (double)referencia * referencia;
    estado->energia_ruido_entrada += ruido * ruido;
    estado->energia_error += error * error;
    estado->energia_util += (double)util * util;
    estado->energia_ruido_salida += residual * residual;
    estado->energia_distorsion += distorsion * distorsion;
    ++estado->muestras;
    return true;
}

/* Resume calidad digital: la atenuacion corresponde al ruido total, no a un solo pico. */
metricas_resultado_t metricas_finalizar(const metricas_acumulador_t *estado)
{
    double entrada = relacion_db(estado->energia_referencia, estado->energia_ruido_entrada);
    double salida = relacion_db(estado->energia_referencia, estado->energia_error);
    return (metricas_resultado_t){
        .snr_entrada_db = entrada, .snr_salida_db = salida, .mejora_snr_db = salida - entrada,
        .mse = estado->muestras ? estado->energia_error / estado->muestras : NAN,
        .energia_util_pct = estado->energia_referencia ? 100 * estado->energia_util / estado->energia_referencia : NAN,
        .atenuacion_ruido_db = relacion_db(estado->energia_ruido_entrada, estado->energia_ruido_salida),
        .distorsion_util_db = relacion_db(estado->energia_referencia, estado->energia_distorsion),
    };
}
