#include "enlace_pc.h"
#include "driver/uart.h"
#include "freertos/FreeRTOS.h"
#include "freertos/queue.h"
#include "freertos/task.h"

static QueueHandle_t paquetes, eventos;
static volatile bool fallo_recepcion;
static uint32_t secuencia_salida;
static uint8_t salida[PC_TRAMA_MAX];

/** Ensambla paquetes fuera de ISR y detecta errores UART y colas llenas. */
static void recibir_uart(void *contexto)
{
    (void)contexto;
    uint8_t trama[PC_TRAMA_MAX], fragmento[256];
    pc_paquete_t paquete;
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
                        if (!pc_decodificar(trama, usados, &paquete) ||
                            xQueueSend(paquetes, &paquete, 0) != pdTRUE) fallo_recepcion = true;
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
/** Configura el puente USB-UART sin reasignar pines y sin control de flujo fisico. */
esp_err_t enlace_pc_iniciar(void)
{
    const uart_config_t configuracion = {.baud_rate = 2000000, .data_bits = UART_DATA_8_BITS,
        .parity = UART_PARITY_DISABLE, .stop_bits = UART_STOP_BITS_1,
        .flow_ctrl = UART_HW_FLOWCTRL_DISABLE, .source_clk = UART_SCLK_DEFAULT};
    paquetes = xQueueCreate(4, sizeof(pc_paquete_t));
    if (!paquetes) return ESP_ERR_NO_MEM;
    esp_err_t resultado = uart_driver_install(UART_NUM_0, 16384, 0, 32, &eventos, 0);
    if (resultado != ESP_OK) return resultado;
    resultado = uart_param_config(UART_NUM_0, &configuracion);
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
    return uart_wait_tx_done(UART_NUM_0, pdMS_TO_TICKS(200));
}
/** Prioriza los fallos sobre los datos para no declarar continua una captura corrupta. */
esp_err_t enlace_pc_recibir(pc_paquete_t *paquete, unsigned espera_ms)
{
    if (fallo_recepcion) { fallo_recepcion = false; return ESP_ERR_INVALID_CRC; }
    return xQueueReceive(paquetes, paquete, pdMS_TO_TICKS(espera_ms)) == pdTRUE ? ESP_OK : ESP_ERR_TIMEOUT;
}
