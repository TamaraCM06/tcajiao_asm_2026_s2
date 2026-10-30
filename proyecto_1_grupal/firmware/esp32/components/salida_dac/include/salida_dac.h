#ifndef SALIDA_DAC_H
#define SALIDA_DAC_H

#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

#include "driver/dac_continuous.h"
#include "esp_err.h"
#include "freertos/FreeRTOS.h"
#include "freertos/semphr.h"

enum {
    SALIDA_DAC_CANTIDAD_DESCRIPTORES = 6,
    SALIDA_DAC_BYTES_POR_BUFFER = 512,
    SALIDA_DAC_BYTES_POR_MUESTRA_DMA = 2,
    SALIDA_DAC_CAPACIDAD_MUESTRAS = SALIDA_DAC_CANTIDAD_DESCRIPTORES *
                                  SALIDA_DAC_BYTES_POR_BUFFER /
                                  SALIDA_DAC_BYTES_POR_MUESTRA_DMA,
    SALIDA_DAC_TIMEOUT_MILISEGUNDOS = 1000
};

typedef struct {
    uint64_t codigos_aceptados; /* Copiados a DMA, no necesariamente emitidos aún. */
    uint64_t codigos_reproducidos; /* Consumidos según eventos DMA, con alineación de 16 bits. */
    uint64_t codigos_previstos;
    uint32_t paradas_inesperadas;
} salida_dac_estadisticas_t;

/* Estado del controlador, reservado con duración mayor que toda la reproducción.
 * Inicializar a cero antes del primer uso. Solo una tarea gestiona su ciclo de vida;
 * el callback únicamente modifica contadores protegidos por la sección crítica.
 * No mover/copiar el estado después de registrar el callback. */
typedef struct {
    dac_continuous_handle_t controlador;
    bool habilitado;
    bool estadisticas_disponibles;
    bool contabilizar_paradas;
    bool fin_confirmado;
    SemaphoreHandle_t notificacion_final;
    portMUX_TYPE bloqueo_estadisticas;
    salida_dac_estadisticas_t estadisticas;
} salida_dac_t;

/* Reserva GPIO25 y DMA con reloj APLL y habilita el controlador sin emitir aún.
 * Devuelve errores ESP-IDF. Ante fallo parcial, llamar a salida_dac_cerrar(). */
esp_err_t salida_dac_inicializar(salida_dac_t *salida_dac,
                               uint32_t frecuencia_muestreo_hz, size_t cantidad_total_codigos);

/* Carga códigos con espera de hasta 1000 ms y comprueba la cantidad aceptada.
 * El buffer puede reutilizarse cuando retorna. Una parada inesperada, escritura
 * parcial o error se devuelve al llamador, que debe cerrar la salida. */
esp_err_t salida_dac_escribir(salida_dac_t *salida_dac,
                            uint8_t *codigos_entrada, size_t cantidad_codigos);

/* Espera el fin DMA y comprueba que se consumió exactamente todo el registro. */
esp_err_t salida_dac_esperar_fin(salida_dac_t *salida_dac);

/* Copia contadores coherentes; siguen disponibles después de cerrar la salida. */
esp_err_t salida_dac_obtener_estadisticas(salida_dac_t *salida_dac,
                                        salida_dac_estadisticas_t *estadisticas);

/* Detiene y libera lo reservado; admite estado a cero o cierre ya completado.
 * Si un paso falla, conserva el estado necesario para permitir otro cierre. */
esp_err_t salida_dac_cerrar(salida_dac_t *salida_dac);

#endif
