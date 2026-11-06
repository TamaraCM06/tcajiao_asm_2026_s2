/** Inicia la aplicación de captura en PC y reproducción diferida. */
#include "esp_log.h"
#include "sesiones_pc.h"

static const char *ETIQUETA_REGISTRO = "sesiones";

/** Inicia el servicio de sesiones y publica fallos de inicialización. */
void app_main(void)
{
    const esp_err_t resultado = sesiones_pc_ejecutar();
    if (resultado != ESP_OK) {
        ESP_LOGE(ETIQUETA_REGISTRO, "Ejecucion incompleta: %s", esp_err_to_name(resultado));
    }
}
