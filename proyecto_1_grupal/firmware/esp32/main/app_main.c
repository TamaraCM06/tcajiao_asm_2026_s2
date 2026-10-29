#include <inttypes.h>

#include "reproduccion_senal.h"
#include "esp_log.h"

static const char *ETIQUETA_REGISTRO = "emisor";
/* Cambiar a SENAL_CASO_2 o SENAL_CASO_3 y recompilar para elegir otra señal. */
static const senal_embebida_id_t CASO_EMISION_INICIAL = SENAL_CASO_1;

/* Reproduce una vez el caso incluido en flash; reiniciar la placa permite emitirlo otra vez. */
void app_main(void)
{
    const senal_embebida_t *senal = senales_embebidas_obtener(CASO_EMISION_INICIAL);
    if (senal == NULL) {
        ESP_LOGE(ETIQUETA_REGISTRO, "El identificador del caso no existe.");
        return;
    }
    ESP_LOGI(ETIQUETA_REGISTRO, "Caso=%s, muestras=%u, muestreo=%" PRIu32 " Hz, CRC=%08" PRIX32,
             senal->nombre, (unsigned)senal->cantidad_muestras,
             senal->frecuencia_muestreo_hz, senal->crc32);
    salida_dac_estadisticas_t estadisticas;
    const esp_err_t resultado = reproduccion_senal_ejecutar(senal, &estadisticas);
    if (resultado != ESP_OK) {
        ESP_LOGE(ETIQUETA_REGISTRO, "El emisor quedó detenido: %s", esp_err_to_name(resultado));
        return;
    }
    ESP_LOGI(ETIQUETA_REGISTRO, "Reproducción terminada: %" PRIu64 " muestras consumidas por DMA.",
             estadisticas.codigos_reproducidos);
}
