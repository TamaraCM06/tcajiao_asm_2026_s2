/** Conserva el FIR causal y retrasa el espectral 37 muestras para comparar sus salidas. */
#include "procesamiento_registro.h"
#include "coeficientes_fir.h"
#include <math.h>
#include <string.h>

/** Inicializa memoria propia y valida el contrato antes de aceptar entradas. */
bool registro_iniciar(procesamiento_registro_t *estado, size_t longitud,
    bool con_referencia, espectral_configuracion_t configuracion,
    registro_publicar_t publicar, void *contexto)
{
    if (!estado || !publicar || longitud < 256 || longitud % 256) return false;
    memset(estado, 0, sizeof(*estado));
    if (!filtro_espectral_inicializar(&estado->espectral, configuracion)) return false;
    estado->longitud = longitud;
    estado->con_referencia = con_referencia;
    estado->primera_ventana = true;
    estado->publicar = publicar;
    estado->contexto = contexto;
    estado->iniciado = true;
    return true;
}

/** Acumula solo indices reales y alinea referencia/entrada con el retardo causal. */
static bool publicar_salto(procesamiento_registro_t *estado)
{
    size_t cantidad = estado->longitud - estado->producidas;
    if (cantidad > 512) cantidad = 512;
    for (size_t desplazamiento = 0; desplazamiento < cantidad; ++desplazamiento) {
        const size_t posicion = estado->posicion_retardo;
        const float espectral = estado->retardo[posicion];
        const float util = estado->retardo_util[posicion];
        estado->retardo[posicion] = estado->espectro_salida[desplazamiento];
        estado->retardo_util[posicion] = estado->espectro_util[desplazamiento];
        estado->posicion_retardo = (posicion + 1) % 37;
        const float temporal = estado->temporal_anterior[desplazamiento];
        if (!isfinite(espectral) || !isfinite(temporal) || !isfinite(util)) return false;
        estado->salida[desplazamiento] = espectral;
        estado->energia_salida[0] += (double)temporal * temporal;
        estado->energia_salida[1] += (double)espectral * espectral;
        const size_t indice = estado->producidas + desplazamiento;
        if (estado->con_referencia && indice >= 37) {
            const size_t original = (indice - 37) % 2048;
            if (!metricas_acumular(&estado->metricas[0], estado->historia[original],
                    estado->historia_referencia[original], temporal,
                    estado->util_temporal_anterior[desplazamiento]) ||
                !metricas_acumular(&estado->metricas[1], estado->historia[original],
                    estado->historia_referencia[original], espectral, util)) return false;
        }
    }
    if (!estado->publicar(estado->producidas, cantidad, estado->temporal_anterior,
                         estado->salida, estado->contexto)) return false;
    estado->producidas += cantidad;
    return true;
}

/** Alimenta medio salto; los ceros de cierre nunca entran en la historia de referencia. */
static bool procesar_medio_salto(procesamiento_registro_t *estado,
    const float *entrada, const float *referencia, bool virtual)
{
    for (size_t desplazamiento = 0; desplazamiento < 256; ++desplazamiento) {
        const size_t posicion = estado->acumuladas + desplazamiento;
        const float muestra = virtual ? 0 : entrada[desplazamiento];
        const float limpia = virtual || !estado->con_referencia ? 0 : referencia[desplazamiento];
        if (!isfinite(muestra) || !isfinite(limpia)) return false;
        estado->ventana[512 + posicion] = muestra;
        estado->referencia[512 + posicion] = limpia;
        estado->temporal[posicion] = filtro_fir_muestra(&estado->fir, COEFICIENTES_FIR, muestra);
        estado->util_temporal[posicion] = filtro_fir_muestra(&estado->fir_referencia, COEFICIENTES_FIR, limpia);
        if (!virtual) {
            const size_t historia = (estado->recibidas + desplazamiento) % 2048;
            estado->historia[historia] = muestra;
            estado->historia_referencia[historia] = limpia;
        }
    }
    if (!virtual) estado->recibidas += 256;
    estado->acumuladas += 256;
    if (estado->acumuladas != 512) return true;
    filtro_espectral_bloque(&estado->espectral, estado->ventana, estado->referencia,
                           estado->espectro_salida, estado->espectro_util);
    if (!estado->primera_ventana && !publicar_salto(estado)) return false;
    estado->primera_ventana = false;
    memcpy(estado->temporal_anterior, estado->temporal, sizeof(estado->temporal));
    memcpy(estado->util_temporal_anterior, estado->util_temporal, sizeof(estado->util_temporal));
    memmove(estado->ventana, estado->ventana + 512, 512 * sizeof(float));
    memmove(estado->referencia, estado->referencia + 512, 512 * sizeof(float));
    estado->acumuladas = 0;
    return true;
}

/** Rechaza entradas fuera del registro declarado o despues de finalizar. */
bool registro_agregar(procesamiento_registro_t *estado, const float *entrada, const float *referencia)
{
    if (!estado || !estado->iniciado || estado->finalizado || !entrada ||
        (estado->con_referencia && !referencia) || estado->recibidas >= estado->longitud) return false;
    return procesar_medio_salto(estado, entrada, referencia, false);
}

/** Completa el ultimo salto, incluso cuando longitud no es multiplo de 512. */
bool registro_finalizar(procesamiento_registro_t *estado)
{
    if (!estado || !estado->iniciado || estado->finalizado || estado->recibidas != estado->longitud) return false;
    while (estado->producidas < estado->longitud)
        if (!procesar_medio_salto(estado, NULL, NULL, true)) return false;
    estado->finalizado = true;
    return true;
}
