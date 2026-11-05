/** Selecciona al arrancar el sistema vivo o la demostracion original de flash. */
#include "demostracion.h"
#include "sistema_vivo.h"
#include "esp_log.h"
#include "sdkconfig.h"
#include "sesiones_pc.h"

static const char *ETIQUETA_REGISTRO = "emisor";

/** Inicia el modo elegido en menuconfig y publica fallos de inicializacion. */
void app_main(void)
{
#if CONFIG_APLICACION_PC
    const esp_err_t resultado = sesiones_pc_ejecutar();
#elif CONFIG_APLICACION_VIVO
    const esp_err_t resultado = sistema_vivo_ejecutar();
#else
    const esp_err_t resultado = demostracion_ejecutar();
#endif
    if (resultado != ESP_OK) {
        ESP_LOGE(ETIQUETA_REGISTRO, "Ejecucion incompleta: %s", esp_err_to_name(resultado));
    }
}
