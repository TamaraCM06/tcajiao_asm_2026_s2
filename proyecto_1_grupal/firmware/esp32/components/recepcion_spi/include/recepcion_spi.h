/** Recibe bloques de la Pico por SPI esclavo y controla el permiso READY. */
#pragma once

#include "esp_err.h"
#include "trama_spi.h"

#include <stdint.h>

#define RECEPCION_SPI_GPIO_SCK 18
#define RECEPCION_SPI_GPIO_MOSI 23
#define RECEPCION_SPI_GPIO_CS 27
#define RECEPCION_SPI_GPIO_READY 21

/**
 * Inicializa SPI3 del ESP32 clasico en modo 1 con DMA y una transaccion pendiente.
 * READY comienza bajo y solo sube cuando recibir() prepara el hardware.
 * CS tiene pull-up interno; la Pico debe mantener su GPIO17 alto entre envios.
 * @return ESP_OK o error de configuracion/reserva del controlador.
 * Inicializar antes de recibir. La tarea receptora debe quedar en el mismo nucleo
 * que inicializo el controlador; ninguna de estas operaciones admite concurrencia.
 */
esp_err_t recepcion_spi_inicializar(void);

/**
 * Espera una transferencia y valida su contenido fuera de las interrupciones.
 * @param bloque Destino del llamador; solo se modifica si la trama es valida.
 * @param validacion Recibe el resultado de interpretar la trama solo ante ESP_OK.
 * @param espera_ms Espera maxima aproximada en milisegundos, redondeada a al menos
 * un tick de FreeRTOS; nunca se convierte en una espera infinita.
 * @return ESP_OK indica transferencia terminada, no CRC correcto: consultar
 * validacion. ESP_ERR_TIMEOUT conserva el descriptor armado para la proxima llamada.
 * Otros errores identifican fallos del controlador o argumentos invalidos.
 * La funcion copia el bloque valido: no entrega punteros al buffer DMA interno.
 * Ejecutar desde una unica tarea; no usar desde ISR, callbacks ni otro nucleo.
 */
esp_err_t recepcion_spi_recibir(trama_spi_bloque_t *bloque,
                              trama_spi_resultado_t *validacion,
                              uint32_t espera_ms);

/**
 * Libera SPI y deja READY bajo cuando no hay transferencias en curso.
 * @return ESP_OK si cerro o ya estaba cerrado; ESP_ERR_INVALID_STATE si una
 * transaccion sigue pendiente. En ese caso no cancela ni libera el buffer:
 * conservar el servicio y llamar a recibir() para recuperar la transaccion.
 * No bloquea esperando un emisor ausente; ejecutar desde la tarea propietaria.
 */
esp_err_t recepcion_spi_cerrar(void);
