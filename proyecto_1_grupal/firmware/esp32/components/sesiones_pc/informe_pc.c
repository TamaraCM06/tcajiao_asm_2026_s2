#include "servicios_sesion.h"
#include "cJSON.h"
#include "esp_heap_caps.h"
#include "esp_timer.h"
#include "esp_app_desc.h"
#include <stdlib.h>

/** Agrega una metrica o null; cJSON representa los valores no finitos como null. */
static void agregar_numero(cJSON *objeto, const char *nombre, double valor, bool disponible)
{
    if (disponible) cJSON_AddNumberToObject(objeto, nombre, valor);
    else cJSON_AddNullToObject(objeto, nombre);
}
/** Publica ambas rutas antes de FIN; las metricas preceden a la cuantizacion WAV. */
esp_err_t informe_pc_enviar(uint32_t sesion, const procesamiento_registro_t *registro,
    uint64_t total_us, uint32_t maximo_us, size_t bloques, int64_t inicio_us,
    const uint32_t recortes[3], bool fisica, double tasa_adquisicion)
{
    cJSON *informe = cJSON_CreateObject();
    if (!informe) return ESP_ERR_NO_MEM;
    cJSON_AddStringToObject(informe, "origen", fisica ? "pico" : "archivo");
    cJSON_AddStringToObject(informe, "firmware", esp_app_get_description()->version);
    cJSON_AddStringToObject(informe, "esp_idf", esp_app_get_description()->idf_ver);
    agregar_numero(informe, "tasa_bloques_estimada_hz", tasa_adquisicion, fisica && tasa_adquisicion > 0);
    cJSON_AddBoolToObject(informe, "con_referencia", registro->con_referencia);
    cJSON_AddNumberToObject(informe, "muestras", registro->longitud);
    cJSON_AddNumberToObject(informe, "muestras_evaluadas", registro->con_referencia ? registro->longitud - 37 : 0);
    cJSON_AddNumberToObject(informe, "retardo_muestras", 37);
    cJSON_AddNumberToObject(informe, "calculo_total_us", total_us);
    cJSON_AddNumberToObject(informe, "calculo_max_us", maximo_us);
    cJSON_AddNumberToObject(informe, "calculo_medio_us", bloques ? (double)total_us / bloques : 0);
    cJSON_AddNumberToObject(informe, "tiempo_sesion_us", esp_timer_get_time() - inicio_us);
    cJSON_AddNumberToObject(informe, "estado_dsp_bytes", sizeof(*registro));
    cJSON_AddNumberToObject(informe, "heap_libre_bytes", heap_caps_get_free_size(MALLOC_CAP_8BIT));
    cJSON_AddNumberToObject(informe, "heap_minimo_bytes", heap_caps_get_minimum_free_size(MALLOC_CAP_8BIT));
    cJSON_AddNumberToObject(informe, "perdidas", 0);
    cJSON_AddNumberToObject(informe, "recortes_entrada", recortes[0]);
    for (unsigned metodo = 0; metodo < 2; ++metodo) {
        const metricas_resultado_t resultado = metricas_finalizar(&registro->metricas[metodo]);
        cJSON *ruta = cJSON_AddObjectToObject(informe, metodo == 0 ? "fir" : "espectral");
        if (!ruta) { cJSON_Delete(informe); return ESP_ERR_NO_MEM; }
        agregar_numero(ruta, "mse", resultado.mse, registro->con_referencia);
        agregar_numero(ruta, "snr_entrada_db", resultado.snr_entrada_db, registro->con_referencia);
        agregar_numero(ruta, "snr_salida_db", resultado.snr_salida_db, registro->con_referencia);
        agregar_numero(ruta, "mejora_snr_db", resultado.mejora_snr_db, registro->con_referencia);
        agregar_numero(ruta, "energia_util_pct", resultado.energia_util_pct, registro->con_referencia);
        agregar_numero(ruta, "atenuacion_ruido_total_db", resultado.atenuacion_ruido_db, registro->con_referencia);
        agregar_numero(ruta, "distorsion_util_db", resultado.distorsion_util_db, registro->con_referencia);
        cJSON_AddNumberToObject(ruta, "energia_total", registro->energia_salida[metodo]);
        cJSON_AddNumberToObject(ruta, "recortes_salida", recortes[metodo + 1]);
    }
    char *texto = cJSON_PrintUnformatted(informe);
    esp_err_t resultado = texto ? sesion_texto(sesion, PC_RESULTADO, texto) : ESP_ERR_NO_MEM;
    free(texto); cJSON_Delete(informe);
    return resultado;
}
