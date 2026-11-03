/** Gestiona una recepcion SPI con DMA, handshake READY y almacenamiento fijo. */
#include "recepcion_spi.h"

#include "driver/gpio.h"
#include "driver/spi_slave.h"
#include "esp_attr.h"
#include "esp_rom_sys.h"
#include "freertos/FreeRTOS.h"
#include "soc/gpio_struct.h"

#include <stdbool.h>

/* El margen evita que una transferencia larga quede truncada a 1032 bytes y
 * aparente una longitud valida. Longitudes mayores al margen siguen siendo invalidas. */
enum {
    CAPACIDAD_DMA_BYTES = TRAMA_SPI_BYTES_TRANSFERENCIA + 4u,
    READY_BAJO_MINIMO_US = 10u,
};

_Static_assert(CAPACIDAD_DMA_BYTES % 4u == 0, "DMA requiere multiplos de cuatro bytes.");
_Static_assert(RECEPCION_SPI_GPIO_READY < 32, "READY usa registros GPIO0..31.");

static DMA_ATTR uint8_t buffer_dma[CAPACIDAD_DMA_BYTES];
static spi_slave_transaction_t transaccion;
static bool inicializado;
static bool pendiente;

/** Sube READY desde ISR solo despues de que el controlador preparo la transaccion. */
static void IRAM_ATTR anunciar_transaccion(spi_slave_transaction_t *actual)
{
    (void)actual;
    /* Acceso directo acotado del ESP32 clasico: no depende de codigo en flash. */
    GPIO.out_w1ts = UINT32_C(1) << RECEPCION_SPI_GPIO_READY;
}

/** Baja READY desde ISR al terminar la transferencia, antes de validar su contenido. */
static void IRAM_ATTR registrar_consumo(spi_slave_transaction_t *actual)
{
    (void)actual;
    GPIO.out_w1tc = UINT32_C(1) << RECEPCION_SPI_GPIO_READY;
}

/** Convierte milisegundos a ticks acotados, evitando cero y portMAX_DELAY. */
static TickType_t convertir_espera_ticks(uint32_t espera_ms)
{
    uint64_t ticks = ((uint64_t)espera_ms * configTICK_RATE_HZ + 999u) / 1000u;
    if (ticks == 0) ticks = 1;
    if (ticks >= portMAX_DELAY) ticks = portMAX_DELAY - 1u;
    return (TickType_t)ticks;
}

/** Configura READY inicialmente bajo, CS en reposo alto y SPI3 esclavo con DMA. */
esp_err_t recepcion_spi_inicializar(void)
{
    if (inicializado) return ESP_ERR_INVALID_STATE;
    esp_err_t resultado = gpio_set_level(RECEPCION_SPI_GPIO_READY, 0);
    if (resultado != ESP_OK) return resultado;
    const gpio_config_t configuracion_ready = {
        .pin_bit_mask = UINT64_C(1) << RECEPCION_SPI_GPIO_READY,
        .mode = GPIO_MODE_OUTPUT,
        .pull_up_en = GPIO_PULLUP_DISABLE,
        .pull_down_en = GPIO_PULLDOWN_DISABLE,
        .intr_type = GPIO_INTR_DISABLE,
    };
    resultado = gpio_config(&configuracion_ready);
    if (resultado != ESP_OK) return resultado;

    const gpio_config_t configuracion_cs = {
        .pin_bit_mask = UINT64_C(1) << RECEPCION_SPI_GPIO_CS,
        .mode = GPIO_MODE_INPUT,
        .pull_up_en = GPIO_PULLUP_ENABLE,
        .pull_down_en = GPIO_PULLDOWN_DISABLE,
        .intr_type = GPIO_INTR_DISABLE,
    };
    resultado = gpio_config(&configuracion_cs);
    if (resultado != ESP_OK) return resultado;

    const spi_bus_config_t bus = {
        .mosi_io_num = RECEPCION_SPI_GPIO_MOSI,
        .miso_io_num = -1,
        .sclk_io_num = RECEPCION_SPI_GPIO_SCK,
        .quadwp_io_num = -1,
        .quadhd_io_num = -1,
        .max_transfer_sz = CAPACIDAD_DMA_BYTES,
    };
    const spi_slave_interface_config_t esclavo = {
        .spics_io_num = RECEPCION_SPI_GPIO_CS,
        .queue_size = 1,
        .mode = 1,
        .post_setup_cb = anunciar_transaccion,
        .post_trans_cb = registrar_consumo,
    };
    resultado = spi_slave_initialize(SPI3_HOST, &bus, &esclavo, SPI_DMA_CH_AUTO);
    if (resultado == ESP_OK) {
        pendiente = false;
        inicializado = true;
    }
    return resultado;
}

/** Arma una sola transaccion y conserva su propiedad en el driver ante un timeout. */
esp_err_t recepcion_spi_recibir(trama_spi_bloque_t *bloque,
                              trama_spi_resultado_t *validacion,
                              uint32_t espera_ms)
{
    if (bloque == NULL || validacion == NULL) return ESP_ERR_INVALID_ARG;
    if (!inicializado) return ESP_ERR_INVALID_STATE;

    if (!pendiente) {
        /* La Pico registra una arista descendente para cada consumo. Mantener
         * READY bajo permite observarla antes de anunciar el siguiente permiso. */
        esp_rom_delay_us(READY_BAJO_MINIMO_US);
        transaccion = (spi_slave_transaction_t){
            .length = CAPACIDAD_DMA_BYTES * 8u,
            .rx_buffer = buffer_dma,
        };
        const esp_err_t resultado_cola = spi_slave_queue_trans(SPI3_HOST, &transaccion, 0);
        if (resultado_cola != ESP_OK) return resultado_cola;
        pendiente = true;
    }

    spi_slave_transaction_t *terminada = NULL;
    const esp_err_t resultado = spi_slave_get_trans_result(
        SPI3_HOST, &terminada, convertir_espera_ticks(espera_ms));
    /* Algunos SDK devuelven el descriptor junto a un error DMA. Recuperarlo
     * tambien en ese caso permite cerrar sin reutilizar memoria aun en uso. */
    if (terminada == &transaccion) pendiente = false;
    if (resultado != ESP_OK) return resultado;
    if (terminada != &transaccion) return ESP_ERR_INVALID_STATE;

    *validacion = trama_spi_decodificar(buffer_dma, transaccion.trans_len, bloque);
    return ESP_OK;
}

/** Cierra solo tras recuperar el descriptor; disable() no acredita cancelacion DMA. */
esp_err_t recepcion_spi_cerrar(void)
{
    if (!inicializado) return ESP_OK;
    if (pendiente) {
        spi_slave_transaction_t *terminada = NULL;
        (void)spi_slave_get_trans_result(SPI3_HOST, &terminada, 0);
        if (terminada != &transaccion) return ESP_ERR_INVALID_STATE;
        pendiente = false;
    }
    const esp_err_t resultado_ready = gpio_set_level(RECEPCION_SPI_GPIO_READY, 0);
    if (resultado_ready != ESP_OK) return resultado_ready;
    const esp_err_t resultado = spi_slave_free(SPI3_HOST);
    if (resultado == ESP_OK) inicializado = false;
    return resultado;
}
