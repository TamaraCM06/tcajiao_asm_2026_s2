#include "demostracion.h"
#include "esp_log.h"

static const char *ETIQUETA_REGISTRO = "emisor";

/* Ejecuta la demostracion una vez; EN/RESET permite repetirla. */
void app_main(void)
{
    const esp_err_t resultado = demostracion_ejecutar();
    if (resultado != ESP_OK) {
        ESP_LOGE(ETIQUETA_REGISTRO, "Ejecucion incompleta: %s", esp_err_to_name(resultado));
    }
}
