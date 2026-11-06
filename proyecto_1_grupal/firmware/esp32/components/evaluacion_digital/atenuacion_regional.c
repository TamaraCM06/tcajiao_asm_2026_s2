#include "atenuacion_regional.h"
#include <math.h>
#include <string.h>

/** El intervalo es inclusivo y usa la rejilla fija de 15.625 Hz. */
bool regional_iniciar(atenuacion_regional_t *estado, float minimo_hz, float maximo_hz)
{
    if (!estado || !isfinite(minimo_hz) || !isfinite(maximo_hz) || minimo_hz < 0 ||
        maximo_hz > 8000 || minimo_hz >= maximo_hz ||
        ceilf(minimo_hz / 15.625f) > floorf(maximo_hz / 15.625f)) return false;
    memset(estado, 0, sizeof(*estado));
    estado->minimo_hz = minimo_hz;
    estado->maximo_hz = maximo_hz;
    estado->habilitada = true;
    return true;
}
/** Usa exactamente la misma region, Hann y longitud para los tres residuos. */
void regional_agregar(atenuacion_regional_t *estado, float ruido, float residual_fir,
    float residual_espectral, const fft_plan_t *plan, const float *ventana)
{
    if (!estado->habilitada) return;
    const float valores[3] = {ruido, residual_fir, residual_espectral};
    for (unsigned canal = 0; canal < 3; ++canal)
        estado->residuos[canal][estado->acumuladas] = valores[canal];
    if (++estado->acumuladas != FFT_LONGITUD) return;
    const unsigned primero = (unsigned)ceilf(estado->minimo_hz / 15.625f);
    const unsigned ultimo = (unsigned)floorf(estado->maximo_hz / 15.625f);
    for (unsigned canal = 0; canal < 3; ++canal) {
        for (unsigned muestra = 0; muestra < FFT_LONGITUD; ++muestra)
            estado->transformada[muestra] = (complejo_t){estado->residuos[canal][muestra] * ventana[muestra], 0};
        fft_transformar(plan, estado->transformada, false);
        for (unsigned bin = primero; bin <= ultimo; ++bin) {
            const complejo_t valor = estado->transformada[bin];
            const double peso = bin == 0 || bin == FFT_SALTO ? 1 : 2;
            estado->energia[canal] += peso * ((double)valor.real * valor.real + (double)valor.imaginaria * valor.imaginaria);
        }
    }
    estado->acumuladas = 0;
    ++estado->bloques;
}
/** No convierte silencio, falta de referencia ni division por cero en resultados aprobados. */
const char *regional_motivo(const atenuacion_regional_t *estado, unsigned metodo, bool con_referencia)
{
    if (!con_referencia) return "sin_referencia";
    if (!estado->habilitada) return "sin_region";
    if (!estado->bloques) return "sin_bloques_completos";
    if (!(estado->energia[0] > 0) || !isfinite(estado->energia[0])) return "sin_energia_entrada";
    if (metodo > 1 || !(estado->energia[metodo + 1] > 0) || !isfinite(estado->energia[metodo + 1]))
        return "residuo_no_resuelto";
    return NULL;
}
/** La razon cancela el factor comun de normalizacion de la FFT y de Hann. */
double regional_atenuacion(const atenuacion_regional_t *estado, unsigned metodo, bool con_referencia)
{
    return regional_motivo(estado, metodo, con_referencia) ? NAN :
        10 * log10(estado->energia[0] / estado->energia[metodo + 1]);
}
