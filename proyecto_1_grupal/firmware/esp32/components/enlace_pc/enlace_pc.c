#include "enlace_pc.h"
#include "driver/uart.h"
#include "freertos/FreeRTOS.h"
#include "freertos/queue.h"
#include "freertos/task.h"
#include "esp_timer.h"

typedef struct { pc_paquete_t paquete; int64_t recepcion_us; } entrada_uart_t;

static QueueHandle_t paquetes, eventos;
static volatile bool fallo_recepcion;
static uint32_t secuencia_salida;
static uint8_t salida[PC_TRAMA_MAX];

/** Ensambla paquetes fuera de ISR y detecta errores UART y colas llenas. */
static void recibir_uart(void *contexto)
{
    (void)contexto;
    uint8_t trama[PC_TRAMA_MAX], fragmento[256];
    entrada_uart_t entrada;
    size_t usados = 0;
    bool descartando = false;
    while (true) {
        uart_event_t evento;
        if (xQueueReceive(eventos, &evento, pdMS_TO_TICKS(20)) != pdTRUE) continue;
        if (evento.type == UART_FIFO_OVF || evento.type == UART_BUFFER_FULL ||
            evento.type == UART_FRAME_ERR || evento.type == UART_PARITY_ERR) {
            fallo_recepcion = true; usados = 0; descartando = true;
            uart_flush_input(UART_NUM_0);
            continue;
        }
        if (evento.type != UART_DATA) continue;
        size_t pendientes = evento.size;
        while (pendientes) {
            const int recibidos = uart_read_bytes(UART_NUM_0, fragmento,
                pendientes > sizeof(fragmento) ? sizeof(fragmento) : pendientes, 0);
            if (recibidos <= 0) break;
            pendientes -= recibidos;
            for (int posicion = 0; posicion < recibidos; ++posicion) {
                if (fragmento[posicion] == 0) {
                    if (!descartando && usados) {
                        entrada.recepcion_us = esp_timer_get_time();
                        if (!pc_decodificar(trama, usados, &entrada.paquete) ||
                            xQueueSend(paquetes, &entrada, 0) != pdTRUE) fallo_recepcion = true;
                    }
                    usados = 0; descartando = false;
                } else if (!descartando) {
                    if (usados < sizeof(trama)) trama[usados++] = fragmento[posicion];
                    else { fallo_recepcion = true; descartando = true; }
                }
            }
        }
    }
}
/** Configura explicitamente UART0 del puente USB: TX GPIO1 y RX GPIO3. */
esp_err_t enlace_pc_iniciar(void)
{
    const uart_config_t configuracion = {.baud_rate = 1000000, .data_bits = UART_DATA_8_BITS,
        .parity = UART_PARITY_DISABLE, .stop_bits = UART_STOP_BITS_1,
        .flow_ctrl = UART_HW_FLOWCTRL_DISABLE, .source_clk = UART_SCLK_DEFAULT};
    paquetes = xQueueCreate(4, sizeof(entrada_uart_t));
    if (!paquetes) return ESP_ERR_NO_MEM;
    esp_err_t resultado = uart_param_config(UART_NUM_0, &configuracion);
    if (resultado != ESP_OK) return resultado;
    resultado = uart_set_pin(UART_NUM_0, 1, 3, UART_PIN_NO_CHANGE, UART_PIN_NO_CHANGE);
    if (resultado != ESP_OK) return resultado;
    resultado = uart_driver_install(UART_NUM_0, 16384, 16384, 32, &eventos, 0);
    if (resultado != ESP_OK) return resultado;
    /* Deja margen al FIFO durante las interrupciones SPI; a 120/128 bytes
     * solo quedaban 80 us a 1 Mbaud antes de perder datos de un CSV. */
    resultado = uart_set_rx_full_threshold(UART_NUM_0, 64);
    if (resultado != ESP_OK) return resultado;
    resultado = uart_set_rx_timeout(UART_NUM_0, 10);
    if (resultado != ESP_OK) return resultado;
    return xTaskCreate(recibir_uart, "pc_rx", 16384, NULL, 8, NULL) == pdPASS ? ESP_OK : ESP_ERR_NO_MEM;
}
/** Serializa desde una sola tarea para que los paquetes nunca se mezclen. */
esp_err_t enlace_pc_enviar(pc_paquete_t *paquete)
{
    paquete->secuencia = secuencia_salida++;
    const size_t cantidad = pc_codificar(paquete, salida);
    if (!cantidad) return ESP_ERR_INVALID_SIZE;
    if (uart_write_bytes(UART_NUM_0, salida, cantidad) != (int)cantidad) return ESP_FAIL;
    /* El buffer TX permite transmitir mientras main calcula el siguiente salto.
     * Esperar drenaje por paquete impediria sostener las tres rutas a 1 Mbaud. */
    return ESP_OK;
}
/** La marca usa esp_timer igual que SPI, calculo y publicacion. */
esp_err_t enlace_pc_recibir_marcado(pc_paquete_t *paquete, unsigned espera_ms, int64_t *recepcion_us)
{
    if (fallo_recepcion) { fallo_recepcion = false; return ESP_ERR_INVALID_CRC; }
    entrada_uart_t entrada;
    const BaseType_t recibido = xQueueReceive(paquetes, &entrada, pdMS_TO_TICKS(espera_ms));
    if (fallo_recepcion) { fallo_recepcion = false; return ESP_ERR_INVALID_CRC; }
    if (recibido == pdTRUE) {
        *paquete = entrada.paquete;
        if (recepcion_us) *recepcion_us = entrada.recepcion_us;
    }
    return recibido == pdTRUE ? ESP_OK : ESP_ERR_TIMEOUT;
}
