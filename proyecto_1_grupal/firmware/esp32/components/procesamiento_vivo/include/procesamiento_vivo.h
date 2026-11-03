/** Coordina FIR y espectral sobre la misma captura continua, con salidas alineadas. */
#pragma once

#include <stdbool.h>
#include <stddef.h>

#include "filtro_espectral.h"
#include "filtro_fir.h"
#include "senales_embebidas.h"

enum {
    PROCESAMIENTO_VIVO_ENTRADA_MUESTRAS = 256,
    PROCESAMIENTO_VIVO_SALIDA_MUESTRAS = FFT_SALTO,
    PROCESAMIENTO_VIVO_FRECUENCIA_HZ = SENALES_FRECUENCIA_MUESTREO_HZ,
};

/**
 * Estado propio del procesamiento vivo; nunca usa la memoria del banco secuencial.
 * Reservar con duracion estatica o fuera de la pila de la tarea: contiene la FFT,
 * ventanas y salidas pendientes. Una sola tarea debe usar y reiniciar cada estado.
 */
typedef struct {
    filtro_fir_t fir;
    filtro_espectral_t espectral;
    espectral_configuracion_t configuracion;
    float ventana_mezcla[FFT_LONGITUD];
    float fir_actual[FFT_SALTO];
    float fir_anterior[FFT_SALTO];
    float salida_ventana[FFT_SALTO];
    float util_descartada[FFT_SALTO];
    float retardo_espectral[FIR_RETARDO];
    size_t muestras_acumuladas;
    size_t posicion_retardo;
    bool iniciada;
    bool descartar_ventana_inicial;
} procesamiento_vivo_t;

/**
 * Prepara ambas rutas a 16000 Hz usando los filtros y coeficientes existentes.
 * @param estado Memoria del llamador, no nula; no requiere inicializacion previa.
 * @param configuracion Parametros espectrales, con los limites del filtro existente.
 * @return true si la configuracion es valida; false deja el estado sin iniciar.
 * Ejecutar en tarea. No reserva memoria y no calcula metricas sin referencia limpia.
 */
bool procesamiento_vivo_inicializar(procesamiento_vivo_t *estado,
                                    espectral_configuracion_t configuracion);

/**
 * Descarta ventanas, historia y salidas pendientes conservando la configuracion.
 * @param estado Estado inicializado; usar tras perdida de captura o nueva sesion.
 * Ejecutar desde la misma tarea que procesa, nunca mientras otro contexto lo usa.
 */
void procesamiento_vivo_reiniciar(procesamiento_vivo_t *estado);

/**
 * Entrega la misma entrada al FIR y al ensamblado espectral de 1024, con salto 512.
 * @param estado Estado inicializado, exclusivo de la tarea llamadora.
 * @param entrada 256 muestras consecutivas a 16000 Hz, finitas y en voltios sin DC.
 * @param salida_fir Destino del llamador para 512 muestras FIR sin cuantizar.
 * @param salida_espectral Destino para las 512 muestras espectrales correspondientes.
 * Los buffers no deben solaparse entre si ni con el estado. No se conservan punteros.
 * @return true cuando hay dos salidas completas; false durante el arranque o mientras
 * falta medio salto. Ante false los destinos quedan intactos. Tras iniciar o reiniciar,
 * la primera salida llega con el cuarto bloque; despues, una por cada dos bloques.
 * La salida espectral se retrasa 37 muestras para igualar el retardo del FIR. Ambas
 * rutas comparten la espera necesaria para reunir la ventana, sin ser latencia medida.
 */
bool procesamiento_vivo_bloque(procesamiento_vivo_t *estado,
                               const float entrada[PROCESAMIENTO_VIVO_ENTRADA_MUESTRAS],
                               float salida_fir[PROCESAMIENTO_VIVO_SALIDA_MUESTRAS],
                               float salida_espectral[PROCESAMIENTO_VIVO_SALIDA_MUESTRAS]);
