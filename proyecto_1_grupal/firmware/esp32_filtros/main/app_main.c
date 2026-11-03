#include "audio_vivo.h"
#include "pantalla.h"
#include "sdkconfig.h"
#include <inttypes.h>
#include <math.h>
#include <string.h>
#include "driver/gpio.h"
#include "driver/spi_slave.h"
#include "esp_attr.h"
#include "esp_log.h"
#include "esp_timer.h"
#include "freertos/FreeRTOS.h"
#include "freertos/queue.h"
#include "freertos/task.h"

enum { PIN_READY = 21, RX_CAPACIDAD = AUDIO_TRAMA + 4 };
static const char *TAG = "filtros";
static QueueHandle_t cola_pantalla, cola_monitor;
typedef struct {
    uint32_t id, aceptados, rechazados, crc, longitud, secuencia, dsp_max, discontinuidades;
    audio_metricas_t fir, fft;
    bool fft_lista;
} monitor_estado_t;

static void tarea_monitor(void *arg)
{
    (void)arg;
    monitor_estado_t e;
    for (;;) {
        if (xQueueReceive(cola_monitor, &e, portMAX_DELAY) != pdTRUE) continue;
        ESP_LOGI(TAG, "id=%" PRIu32 " OK=%" PRIu32 " rechazados=%" PRIu32
                 " CRC=%" PRIu32 " longitud=%" PRIu32 " secuencia=%" PRIu32
                 " discontinuidades=%" PRIu32 " DSPmax=%" PRIu32 " us (presupuesto 25600 us)",
                 e.id, e.aceptados, e.rechazados, e.crc, e.longitud, e.secuencia,
                 e.discontinuidades, e.dsp_max);
        ESP_LOGI(TAG, "FIR RMS=%.2f mV E=%.1f%% | FFT lista=%d RMS=%.2f mV E=%.1f%% | referencia=%s",
                 (double)e.fir.rms * 1000, (double)e.fir.energia_pct, e.fft_lista,
                 (double)e.fft.rms * 1000, (double)e.fft.energia_pct,
                 e.fir.referencia ? "SIM" : "NO: SNR/MSE N/D");
        if (e.dsp_max >= 25600) ESP_LOGW(TAG, "DSP excede plazo: revisar perdidas y latencia en hardware");
    }
}
static audio_vivo_t filtros;
static audio_resultado_t resultado;
static float entrada[AUDIO_N];
#if CONFIG_AUDIO_AUTOPRUEBA
static float referencia[AUDIO_N];
#endif
static pantalla_datos_t vista;
#if !CONFIG_AUDIO_AUTOPRUEBA
/* Margen para detectar maestros que envian mas de 1032 bytes: el driver
 * puede truncar trans_len a length cuando la transaccion excede el buffer. */
static DMA_ATTR uint8_t rx[RX_CAPACIDAD], tx[RX_CAPACIDAD];

static void IRAM_ATTR preparada(spi_slave_transaction_t *t)
{
    (void)t;
    gpio_set_level(PIN_READY, 1); /* Solo cuando el driver ya armo DMA. */
}
static void IRAM_ATTR completada(spi_slave_transaction_t *t)
{
    (void)t;
    gpio_set_level(PIN_READY, 0); /* Pulso visible hasta el siguiente armado. */
}
#endif
static void tarea_pantalla(void *arg)
{
    (void)arg;
    pantalla_datos_t datos;
    bool conectada = false;
    int64_t ultima = 0;
    ESP_ERROR_CHECK(pantalla_iniciar());
    for (;;) {
        if (xQueueReceive(cola_pantalla, &datos, pdMS_TO_TICKS(200)) == pdTRUE) {
            ultima = esp_timer_get_time();
            conectada = true;
            pantalla_dibujar(&datos, true);
        } else if (conectada && esp_timer_get_time() - ultima > 1000000) {
            pantalla_dibujar(NULL, false);
            conectada = false;
        }
    }
}
static void publicar(uint32_t id, uint32_t rechazados, bool simulacion)
{
    static int64_t ultima;
    int64_t ahora = esp_timer_get_time();
    if (ahora - ultima < 200000) return;
    ultima = ahora;
    vista.espectral = (ahora / 4000000) % 2 != 0;
    vista.lista = !vista.espectral || resultado.fft_lista;
    vista.metricas = vista.espectral ? resultado.fft : resultado.fir;
    vista.bloque = vista.espectral ? resultado.fft_id_inicial : id;
    vista.simulacion = simulacion;
    vista.rechazados = rechazados;
    vista.discontinuidades = resultado.discontinuidades;
    const float *in = vista.espectral ? resultado.entrada_fft : resultado.entrada_fir;
    const float *out = vista.espectral ? resultado.salida_fft : resultado.salida_fir;
    /* Primeras 160 muestras consecutivas: 16 ms, misma escala para ambas curvas. */
    memcpy(vista.entrada, in, sizeof(vista.entrada));
    memcpy(vista.salida, out, sizeof(vista.salida));
    xQueueOverwrite(cola_pantalla, &vista); /* La pantalla nunca bloquea el DSP. */
}
/* UART puede tardar mas que un bloque: nunca imprimir desde la ruta RX/DSP. */
static void informar_monitor(monitor_estado_t *e, uint32_t id)
{
    static int64_t ultima;
    int64_t ahora = esp_timer_get_time();
    if (ahora - ultima < 1000000) return;
    ultima = ahora;
    e->id = id;
    e->fir = resultado.fir;
    e->fft = resultado.fft;
    e->fft_lista = resultado.fft_lista;
    e->discontinuidades = resultado.discontinuidades;
    xQueueOverwrite(cola_monitor, e);
    e->dsp_max = 0;
}
static void tarea_audio(void *arg)
{
    (void)arg;
    audio_vivo_iniciar(&filtros);
    uint32_t id = 0;
    monitor_estado_t estado = {0};
#if !CONFIG_AUDIO_AUTOPRUEBA
    gpio_config_t gc = {.pin_bit_mask = 1ULL << PIN_READY, .mode = GPIO_MODE_OUTPUT};
    ESP_ERROR_CHECK(gpio_config(&gc));
    gpio_set_level(PIN_READY, 0);
    gpio_set_pull_mode(5, GPIO_PULLUP_ONLY);
    spi_bus_config_t bus = {.mosi_io_num = 23, .miso_io_num = 19, .sclk_io_num = 18,
                           .quadwp_io_num = -1, .quadhd_io_num = -1,
                           .max_transfer_sz = RX_CAPACIDAD};
    spi_slave_interface_config_t esclavo = {.spics_io_num = 5, .mode = CONFIG_AUDIO_SPI_MODO,
        .queue_size = 1, .post_setup_cb = preparada, .post_trans_cb = completada};
    ESP_ERROR_CHECK(spi_slave_initialize(SPI3_HOST, &bus, &esclavo, SPI_DMA_CH_AUTO));
    ESP_LOGI(TAG, "VSPI esclavo DMA modo %d | 1032 bytes | READY=21 | Fs=%d Hz", CONFIG_AUDIO_SPI_MODO, AUDIO_FS);
    if (CONFIG_AUDIO_SPI_MODO == 0)
        ESP_LOGW(TAG, "Modo 0+DMA experimental en ESP32 clasico: validar CRC/timing; alternativa modo 1 en AMBOS lados");
    spi_slave_transaction_t transaccion = {.length = RX_CAPACIDAD * 8, .rx_buffer = rx, .tx_buffer = tx};
#else
    ESP_LOGW(TAG, "AUTOPRUEBA SIMULADA: mezcla sintetica y referencia conocidas, NO audio de la Pico");
    int64_t proximo = esp_timer_get_time();
#endif
    for (;;) {
        const float *ref = NULL;
#if CONFIG_AUDIO_AUTOPRUEBA
        for (unsigned i = 0; i < AUDIO_N; ++i) {
            double t = ((uint64_t)id * AUDIO_N + i) / (double)AUDIO_FS;
            referencia[i] = (float)(0.3 * sin(6.283185307179586 * 440 * t));
            entrada[i] = referencia[i] + (float)(0.15 * sin(6.283185307179586 * 3000 * t));
        }
        ref = referencia;
#else
        transaccion.trans_len = 0;
        ESP_ERROR_CHECK(spi_slave_queue_trans(SPI3_HOST, &transaccion, portMAX_DELAY));
        spi_slave_transaction_t *terminada = NULL;
        ESP_ERROR_CHECK(spi_slave_get_trans_result(SPI3_HOST, &terminada, portMAX_DELAY));
        audio_error_t error = terminada->trans_len == AUDIO_TRAMA * 8
            ? audio_decodificar(rx, AUDIO_TRAMA, &id, entrada) : AUDIO_LONGITUD;
        if (error != AUDIO_OK) {
            ++estado.rechazados;
            if (error == AUDIO_CRC) ++estado.crc;
            if (error == AUDIO_LONGITUD) ++estado.longitud;
            /* Rechazar antes de alimentar filtros: el proximo ID valida continuidad. */
            informar_monitor(&estado, id);
            continue;
        }
#endif
        int64_t inicio = esp_timer_get_time();
        if (!audio_vivo_procesar(&filtros, id, entrada, ref, &resultado)) {
            ++estado.rechazados; ++estado.secuencia; informar_monitor(&estado, id); continue;
        }
        uint32_t duracion = (uint32_t)(esp_timer_get_time() - inicio);
        if (duracion > estado.dsp_max) estado.dsp_max = duracion;
        ++estado.aceptados;
        publicar(id, estado.rechazados, ref != NULL);
        informar_monitor(&estado, id);
#if CONFIG_AUDIO_AUTOPRUEBA
        ++id;
        proximo += 25600;
        int64_t espera = proximo - esp_timer_get_time();
        if (espera > 1000) vTaskDelay(pdMS_TO_TICKS((uint32_t)(espera / 1000)));
        else { proximo = esp_timer_get_time(); vTaskDelay(1); }
#endif
    }
}
void app_main(void)
{
    cola_pantalla = xQueueCreate(1, sizeof(pantalla_datos_t));
    cola_monitor = xQueueCreate(1, sizeof(monitor_estado_t));
    ESP_ERROR_CHECK(cola_pantalla && cola_monitor ? ESP_OK : ESP_ERR_NO_MEM);
    ESP_ERROR_CHECK(xTaskCreatePinnedToCore(tarea_monitor, "monitor", 4096, NULL, 1, NULL, 0) == pdPASS ? ESP_OK : ESP_ERR_NO_MEM);
    ESP_ERROR_CHECK(xTaskCreatePinnedToCore(tarea_pantalla, "pantalla", 4096, NULL, 2, NULL, 0) == pdPASS ? ESP_OK : ESP_ERR_NO_MEM);
    ESP_ERROR_CHECK(xTaskCreatePinnedToCore(tarea_audio, "audio_spi", 8192, NULL, 10, NULL, 1) == pdPASS ? ESP_OK : ESP_ERR_NO_MEM);
}
