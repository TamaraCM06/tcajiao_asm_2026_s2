#include "protocolo_serial.h"
#include "comandos.h"
#include "driver/uart.h"
#include "freertos/FreeRTOS.h"
#include "freertos/queue.h"
#include "freertos/task.h"
#include <stdarg.h>
#include <stdio.h>
#include <string.h>

typedef struct { char texto[512]; } mensaje_serial_t;
static QueueHandle_t cola_transmision;
static portMUX_TYPE proteccion_transmision = portMUX_INITIALIZER_UNLOCKED;
static bool fallo_transmision;

/* Es el unico escritor UART; el orden FIFO conserva cabecera, muestras y cierre. */
static void tarea_transmitir(void *argumento)
{
    (void)argumento;
    mensaje_serial_t mensaje;
    for (;;) {
        xQueueReceive(cola_transmision, &mensaje, portMAX_DELAY);
        size_t longitud = strlen(mensaje.texto);
        int enviados = uart_write_bytes(UART_NUM_0, mensaje.texto, longitud);
        if (enviados != (int)longitud) {
            portENTER_CRITICAL(&proteccion_transmision);
            fallo_transmision = true;
            portEXIT_CRITICAL(&proteccion_transmision);
        }
    }
}

/* Reserva 64 mensajes y buffers UART; la adquisicion nunca espera a esta cola. */
esp_err_t protocolo_iniciar(void)
{
    uart_config_t parametros = {.baud_rate = 115200, .data_bits = UART_DATA_8_BITS,
        .parity = UART_PARITY_DISABLE, .stop_bits = UART_STOP_BITS_1,
        .flow_ctrl = UART_HW_FLOWCTRL_DISABLE, .source_clk = UART_SCLK_DEFAULT};
    esp_err_t resultado = uart_param_config(UART_NUM_0, &parametros);
    if (resultado != ESP_OK) return resultado;
    resultado = uart_driver_install(UART_NUM_0, 2048, 4096, 0, NULL, 0);
    if (resultado != ESP_OK) return resultado;
    cola_transmision = xQueueCreate(64, sizeof(mensaje_serial_t));
    if (!cola_transmision) return ESP_ERR_NO_MEM;
    return xTaskCreate(tarea_transmitir, "asm2_tx", 3072, NULL, 3, NULL) == pdPASS ? ESP_OK : ESP_ERR_NO_MEM;
}

/* Formatea en espacio fijo y rechaza truncamientos en lugar de enviar filas parciales. */
bool protocolo_emitir(const char *formato, ...)
{
    mensaje_serial_t mensaje;
    va_list argumentos;
    va_start(argumentos, formato);
    int longitud = vsnprintf(mensaje.texto, sizeof(mensaje.texto) - 1, formato, argumentos);
    va_end(argumentos);
    if (longitud < 0 || longitud >= (int)sizeof(mensaje.texto) - 1) return false;
    mensaje.texto[longitud] = '\n';
    mensaje.texto[longitud + 1] = '\0';
    return xQueueSend(cola_transmision, &mensaje, 0) == pdTRUE;
}

/* Descarta toda la linea desbordada; nunca ejecuta su sufijo como otro comando. */
int protocolo_recibir(char *linea, size_t capacidad)
{
    static char acumulado[COMANDO_LONGITUD_MAXIMA];
    static size_t longitud;
    static bool descartando;
    unsigned char caracter;
    for (unsigned cantidad_leida = 0; cantidad_leida < 256; ++cantidad_leida) {
        if (uart_read_bytes(UART_NUM_0, &caracter, 1, 0) != 1) return 0;
        if (caracter == '\r') continue;
        if (caracter == '\n') {
            int resultado = 0;
            if (descartando || longitud >= capacidad) resultado = -1;
            else if (longitud > 0) {
                memcpy(linea, acumulado, longitud);
                linea[longitud] = '\0';
                resultado = 1;
            }
            longitud = 0;
            descartando = false;
            if (resultado) return resultado;
            continue;
        }
        if (caracter != '\t' && (caracter < 32 || caracter > 126)) descartando = true;
        if (longitud >= sizeof(acumulado) - 1) descartando = true;
        if (!descartando) acumulado[longitud++] = (char)caracter;
    }
    return 0;
}

/* Expone la capacidad libre sin modificar el contenido de la cola. */
unsigned protocolo_espacios(void)
{
    return (unsigned)uxQueueSpacesAvailable(cola_transmision);
}

/* Lee de forma protegida el fallo observado por la tarea transmisora. */
bool protocolo_fallo(void)
{
    portENTER_CRITICAL(&proteccion_transmision);
    bool fallo = fallo_transmision;
    portEXIT_CRITICAL(&proteccion_transmision);
    return fallo;
}
