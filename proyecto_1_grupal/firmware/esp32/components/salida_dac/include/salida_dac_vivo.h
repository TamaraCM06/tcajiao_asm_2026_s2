/** Reproduce la ruta seleccionada en GPIO25 mediante una cola acotada y una tarea DAC. */
#pragma once

#include <stdbool.h>
#include <stdint.h>

#include "esp_err.h"

enum { SALIDA_DAC_VIVO_MUESTRAS = 512, SALIDA_DAC_VIVO_CAPACIDAD = 4 };

typedef enum {
    SALIDA_DAC_VIVO_FIR = 1,
    SALIDA_DAC_VIVO_ESPECTRAL = 2,
} salida_dac_vivo_escucha_t;

typedef struct {
    uint64_t muestras_cargadas; /* Copiadas al controlador; no acredita salida analogica. */
    uint64_t muestras_saturadas; /* Codigos recortados en la ruta seleccionada. */
    uint32_t desbordamientos; /* Tramos que no cupieron en la cola. */
    uint32_t faltas_datos; /* Veces que se agotaron los tramos durante una escucha. */
    uint32_t paradas_dma; /* Eventos on_stop; no incluye una medicion analogica. */
    uint32_t errores_escritura;
    uint32_t pendientes;
    esp_err_t ultimo_error;
    bool reproduciendo;
} salida_dac_vivo_estadisticas_t;

/**
 * Reserva DAC GPIO25, seis buffers DMA y una tarea dedicada a 16000 Hz.
 * Usar solo en modo vivo: excluye al reproductor finito que tambien posee GPIO25.
 * La reserva ocurre una vez; no se asigna memoria por bloque. Ante fallo libera
 * lo reservado. El servicio permanece activo hasta reiniciar el firmware.
 * @return Resultado ESP-IDF; ESP_ERR_INVALID_STATE si ya esta iniciado.
 */
esp_err_t salida_dac_vivo_iniciar(void);

/**
 * Copia un tramo a la cola sin esperar espacio. Un solo productor llama a esta
 * funcion y a silenciar(); la tarea DAC nunca conserva los punteros de entrada.
 * @param fir 512 muestras en voltios sin DC, alineadas con la ruta espectral.
 * @param espectral 512 muestras en voltios sin DC.
 * @param ganancia Ganancia fija para cualquiera de las rutas; finita entre 0 y 100.
 * La conversion es 128 + muestra * ganancia * 255 / 3.3, limitada a 0..255.
 * @param escucha FIR o ESPECTRAL: selecciona que ruta se reproduce por GPIO25.
 * @return false si faltan argumentos, el servicio no esta listo o la cola esta llena.
 * El llamador debe reiniciar la continuidad tras un desbordamiento. No normaliza
 * por bloque. Ejecutar en tarea; la salida comienza tras reunir dos tramos.
 */
bool salida_dac_vivo_ofrecer(const float fir[SALIDA_DAC_VIVO_MUESTRAS],
                            const float espectral[SALIDA_DAC_VIVO_MUESTRAS],
                            float ganancia, salida_dac_vivo_escucha_t escucha);

/**
 * Descarta la cola e invalida tramos previos; la tarea sigue cargando codigo 128.
 * No cancela muestras ya copiadas a DMA: pueden persistir hasta unos 128 ms
 * (96 ms de DMA y un tramo de 32 ms en curso). Llamar desde el productor.
 */
void salida_dac_vivo_silenciar(void);

/** Copia contadores coherentes; los acumulados no se borran al silenciar. */
void salida_dac_vivo_obtener_estadisticas(salida_dac_vivo_estadisticas_t *estadisticas);
