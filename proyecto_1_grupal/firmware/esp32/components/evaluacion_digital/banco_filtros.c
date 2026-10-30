#include "banco_filtros.h"
#include "filtro_fir.h"
#include <math.h>
#include <string.h>

/* Espacio compartido entre metodos; no guarda registros completos ni usa malloc. */
static union {
    struct { filtro_fir_t mezcla, referencia; } temporal;
    filtro_espectral_t espectral;
} filtros;
static float entrada_mezcla[FFT_LONGITUD], entrada_referencia[FFT_LONGITUD];
static float salida_mezcla[FFT_SALTO], salida_referencia[FFT_SALTO];

/* Acepta registros acotados que permitan la comparacion con retardo FIR. */
static bool preparar(const datos_digitales_t *datos, const banco_servicios_t *servicios,
                     banco_resultado_t *resultado)
{
    if (!datos || !datos->pares_float32 || !servicios || !servicios->reloj || !resultado ||
        datos->cantidad_muestras < 256 || datos->cantidad_muestras > 96000 ||
        datos->cantidad_muestras % 256) return false;
    memset(resultado, 0, sizeof(*resultado));
    resultado->memoria_trabajo_bytes = sizeof(filtros) + sizeof(entrada_mezcla) +
        sizeof(entrada_referencia) + sizeof(salida_mezcla) + sizeof(salida_referencia);
    return true;
}

/* Registra costo de calculo sin incluir espera voluntaria ni impresion de resultados. */
static void registrar_tiempo(banco_resultado_t *resultado, uint64_t duracion)
{
    resultado->tiempo_total_us += duracion;
    if (duracion > resultado->tiempo_maximo_us) resultado->tiempo_maximo_us = duracion;
    ++resultado->bloques;
}

/* Acumula el intervalo comun y entrega cualquier muestra valida al observador de pruebas. */
static bool registrar_salida(const datos_digitales_t *datos, const banco_servicios_t *servicios,
    banco_resultado_t *resultado, size_t indice, float salida, float util)
{
    if (!isfinite(salida) || !isfinite(util)) return false;
    if (servicios->observar) servicios->observar(indice, salida, util, servicios->contexto);
    ++resultado->muestras_producidas;
    if (indice >= datos->cantidad_muestras - FIR_RETARDO) return true;
    float mezcla, referencia;
    datos_digitales_leer(datos, (int)indice, &mezcla, &referencia);
    return metricas_acumular(&resultado->metricas, mezcla, referencia, salida, util);
}

/* Conserva estados independientes para la mezcla y la referencia de evaluacion FIR. */
bool banco_evaluar_fir(const datos_digitales_t *datos, const banco_servicios_t *servicios,
                       banco_resultado_t *resultado)
{
    if (!preparar(datos, servicios, resultado)) return false;
    uint64_t inicio_total = servicios->reloj();
    filtro_fir_reiniciar(&filtros.temporal.mezcla);
    filtro_fir_reiniciar(&filtros.temporal.referencia);
    for (size_t inicio = 0; inicio < datos->cantidad_muestras; inicio += FIR_BLOQUE) {
        uint64_t inicio_bloque = servicios->reloj();
        for (size_t desplazamiento = 0; desplazamiento < FIR_BLOQUE; ++desplazamiento) {
            size_t indice = inicio + desplazamiento;
            float mezcla, referencia;
            datos_digitales_leer(datos, (int)indice, &mezcla, &referencia);
            float salida = filtro_fir_muestra(&filtros.temporal.mezcla, COEFICIENTES_FIR, mezcla);
            float util = filtro_fir_muestra(&filtros.temporal.referencia, COEFICIENTES_FIR, referencia);
            if (indice >= FIR_RETARDO && !registrar_salida(datos, servicios, resultado,
                indice - FIR_RETARDO, salida, util)) return false;
        }
        registrar_tiempo(resultado, servicios->reloj() - inicio_bloque);
        if (servicios->ceder) servicios->ceder();
    }
    resultado->tiempo_pared_us = servicios->reloj() - inicio_total;
    return resultado->metricas.muestras == datos->cantidad_muestras - FIR_RETARDO;
}

/* Reproduce el padding de Python con ceros virtuales y vaciado del ultimo solapamiento. */
bool banco_evaluar_espectral(const datos_digitales_t *datos, espectral_configuracion_t configuracion,
                            const banco_servicios_t *servicios, banco_resultado_t *resultado)
{
    if (!preparar(datos, servicios, resultado)) return false;
    uint64_t inicio_total = servicios->reloj();
    if (!filtro_espectral_inicializar(&filtros.espectral, configuracion)) return false;
    for (int inicio = -FFT_LONGITUD; inicio <= (int)datos->cantidad_muestras; inicio += FFT_SALTO) {
        uint64_t inicio_bloque = servicios->reloj();
        for (int desplazamiento = 0; desplazamiento < FFT_LONGITUD; ++desplazamiento)
            datos_digitales_leer(datos, inicio + desplazamiento,
                &entrada_mezcla[desplazamiento], &entrada_referencia[desplazamiento]);
        filtro_espectral_bloque(&filtros.espectral, entrada_mezcla, entrada_referencia,
                               salida_mezcla, salida_referencia);
        for (int desplazamiento = 0; desplazamiento < FFT_SALTO; ++desplazamiento) {
            int indice = inicio + desplazamiento;
            if (indice >= 0 && (size_t)indice < datos->cantidad_muestras &&
                !registrar_salida(datos, servicios, resultado, (size_t)indice,
                    salida_mezcla[desplazamiento], salida_referencia[desplazamiento])) return false;
        }
        registrar_tiempo(resultado, servicios->reloj() - inicio_bloque);
        if (servicios->ceder) servicios->ceder();
    }
    resultado->tiempo_pared_us = servicios->reloj() - inicio_total;
    return resultado->muestras_producidas == datos->cantidad_muestras &&
           resultado->metricas.muestras == datos->cantidad_muestras - FIR_RETARDO;
}
