#include <inttypes.h>

#include "esp_log.h"
#include "generador_senales.h"

static const char *ETIQUETA_REGISTRO = "emisor";
static const emisor_modo_t MODO_EMISION_INICIAL = EMISOR_MULTITONO_CON_INTERFERENCIA;

/* Persisten al terminar app_main. El siguiente bloque conectará este estado
 * y el buffer inicial con la reproducción continua mediante DAC/DMA. */
static emisor_generador_t generador_senales;
static float muestras_primer_bloque[EMISOR_MUESTRAS_POR_BLOQUE];

/* Prepara el generador y el primer bloque numérico para integrar posteriormente el DAC. */
void app_main(void)
{
    emisor_config_t configuracion;
    const char *mensaje_error = emisor_config_predeterminada(MODO_EMISION_INICIAL, &configuracion);
    if (mensaje_error != NULL) {
        ESP_LOGE(ETIQUETA_REGISTRO, "%s", mensaje_error);
        return;
    }

    mensaje_error = emisor_inicializar(&generador_senales, &configuracion);
    if (mensaje_error != NULL) {
        ESP_LOGE(ETIQUETA_REGISTRO, "%s", mensaje_error);
        return;
    }

    mensaje_error = emisor_generar(&generador_senales, muestras_primer_bloque,
                                 EMISOR_MUESTRAS_POR_BLOQUE);
    if (mensaje_error != NULL) {
        ESP_LOGE(ETIQUETA_REGISTRO, "%s", mensaje_error);
        return;
    }

    ESP_LOGI(ETIQUETA_REGISTRO, "Generador preparado: muestreo=%" PRIu32 " Hz, buffer=%u muestras",
             configuracion.frecuencia_muestreo_hz, (unsigned)EMISOR_MUESTRAS_POR_BLOQUE);
    ESP_LOGI(ETIQUETA_REGISTRO, "Ganancia común=%.6f, límite=%.3f",
             generador_senales.ganancia_comun, (double)configuracion.limite_amplitud);
    if (configuracion.modo == EMISOR_MULTITONO_CON_INTERFERENCIA) {
        ESP_LOGI(ETIQUETA_REGISTRO, "SNR objetivo=%.1f dB, amplitud de interferencia sin escalar=%.6f",
                 (double)configuracion.snr_db, generador_senales.amplitud_interferencia);
    }
    ESP_LOGI(ETIQUETA_REGISTRO, "Primer buffer numérico preparado; salida DAC pendiente de integración.");
}
