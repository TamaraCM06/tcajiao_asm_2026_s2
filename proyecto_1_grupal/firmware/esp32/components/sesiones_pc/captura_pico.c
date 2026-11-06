#include "servicios_sesion.h"
#include "recepcion_spi.h"
#include "esp_timer.h"
#include "freertos/FreeRTOS.h"
#include "freertos/queue.h"
#include "freertos/task.h"

typedef struct { uint32_t epoca; esp_err_t resultado; int64_t instante_us; trama_spi_bloque_t bloque; } entrada_pico_t;
static QueueHandle_t entradas;
static portMUX_TYPE bloqueo = portMUX_INITIALIZER_UNLOCKED;
static uint32_t epoca_actual;
static bool activa, desbordamiento;
static trama_spi_secuencia_t secuencia;
static int64_t primer_bloque_us, ultimo_bloque_us;
static uint32_t bloques_leidos;

/** Drena SPI incluso en reposo, sin bloquear la adquisicion de la Pico por USB. */
static void recibir_pico(void *contexto)
{
    (void)contexto;
    entrada_pico_t entrada;
    while (true) {
        portENTER_CRITICAL(&bloqueo);
        const uint32_t epoca = activa ? epoca_actual : 0;
        portEXIT_CRITICAL(&bloqueo);
        trama_spi_resultado_t validacion;
        entrada.resultado = recepcion_spi_recibir(&entrada.bloque, &validacion, 100);
        entrada.instante_us = esp_timer_get_time();
        if (entrada.resultado == ESP_ERR_TIMEOUT) continue;
        if (entrada.resultado == ESP_OK && validacion != TRAMA_SPI_VALIDA)
            entrada.resultado = ESP_ERR_INVALID_RESPONSE;
        entrada.epoca = epoca;
        portENTER_CRITICAL(&bloqueo);
        if (activa && epoca && epoca == epoca_actual && xQueueSend(entradas, &entrada, 0) != pdTRUE)
            desbordamiento = true;
        portEXIT_CRITICAL(&bloqueo);
        if (entrada.resultado != ESP_OK) vTaskDelay(1);
    }
}
/** Reserva la cola e instala SPI antes de iniciar su unico consumidor hardware. */
esp_err_t captura_pico_iniciar(void)
{
    entradas = xQueueCreate(8, sizeof(entrada_pico_t));
    if (!entradas) return ESP_ERR_NO_MEM;
    esp_err_t resultado = recepcion_spi_inicializar();
    if (resultado != ESP_OK) return resultado;
    return xTaskCreatePinnedToCore(recibir_pico, "pico_rx", 4096, NULL, 7, NULL,
        xPortGetCoreID()) == pdPASS ? ESP_OK : ESP_ERR_NO_MEM;
}
/** Invalida datos viejos sin cambiar el contrato ni los pines de la Pico. */
void captura_pico_activar(bool nueva_activa)
{
    portENTER_CRITICAL(&bloqueo);
    activa = nueva_activa; ++epoca_actual; desbordamiento = false;
    xQueueReset(entradas);
    secuencia = (trama_spi_secuencia_t){0};
    primer_bloque_us = ultimo_bloque_us = 0;
    bloques_leidos = 0;
    portEXIT_CRITICAL(&bloqueo);
}
/** Rechaza discontinuidades, duplicados, errores de trama y saturacion de cola. */
esp_err_t captura_pico_leer(trama_spi_bloque_t *bloque, int64_t *recepcion_us)
{
    entrada_pico_t entrada;
    if (xQueueReceive(entradas, &entrada, pdMS_TO_TICKS(200)) != pdTRUE) return ESP_ERR_TIMEOUT;
    portENTER_CRITICAL(&bloqueo);
    const bool perdida = desbordamiento || entrada.epoca != epoca_actual;
    portEXIT_CRITICAL(&bloqueo);
    if (perdida) return ESP_ERR_NO_MEM;
    if (entrada.resultado != ESP_OK) return entrada.resultado;
    const trama_spi_continuidad_t continuidad = trama_spi_actualizar_secuencia(&secuencia, entrada.bloque.id);
    if (continuidad.evento != TRAMA_SPI_PRIMER_BLOQUE && continuidad.evento != TRAMA_SPI_CONTINUO)
        return ESP_ERR_INVALID_RESPONSE;
    *bloque = entrada.bloque;
    if (recepcion_us) *recepcion_us = entrada.instante_us;
    if (!bloques_leidos) primer_bloque_us = entrada.instante_us;
    ultimo_bloque_us = entrada.instante_us;
    ++bloques_leidos;
    return ESP_OK;
}

/** Usa las marcas del receptor, no los tiempos variables de escritura USB. */
double captura_pico_tasa(void)
{
    return bloques_leidos > 1 && ultimo_bloque_us > primer_bloque_us ?
        (double)(bloques_leidos - 1) * 256 * 1000000 / (ultimo_bloque_us - primer_bloque_us) : 0;
}
