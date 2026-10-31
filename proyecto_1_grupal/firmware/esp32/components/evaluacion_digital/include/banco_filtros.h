#pragma once
#include <stdint.h>
#include "datos_digitales.h"
#include "filtro_espectral.h"
#include "metricas_digitales.h"

typedef uint64_t (*reloj_microsegundos_t)(void);
typedef void (*ceder_procesador_t)(void);
/* Observador opcional para verificar salidas en PC; no se usa para logs por muestra. */
typedef void (*observar_salida_t)(size_t indice, float salida, float util, void *contexto);
typedef struct {
    reloj_microsegundos_t reloj;
    ceder_procesador_t ceder;
    observar_salida_t observar;
    void *contexto;
} banco_servicios_t;
typedef struct {
    metricas_acumulador_t metricas;
    uint64_t tiempo_total_us, tiempo_maximo_us, tiempo_pared_us;
    size_t bloques, muestras_producidas, memoria_trabajo_bytes;
} banco_resultado_t;
/* Evalua FIR causal con retardo fijo 37, sobre las primeras longitud-37 referencias. */
bool banco_evaluar_fir(const datos_digitales_t *datos, const banco_servicios_t *servicios,
                       banco_resultado_t *resultado);
/* Evalua FFT/IFFT con relleno virtual, entrega salida completa y usa igual intervalo que FIR.
 * Las funciones del banco usan espacio estatico: son secuenciales, no reentrantes. */
bool banco_evaluar_espectral(const datos_digitales_t *datos, espectral_configuracion_t configuracion,
                            const banco_servicios_t *servicios, banco_resultado_t *resultado);
