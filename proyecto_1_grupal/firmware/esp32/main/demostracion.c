#include "demostracion.h"
#include "reproduccion_senal.h"
#include "banco_filtros.h"
#include "filtro_fir.h"
#include "informe_consola.h"
#include "esp_log.h"
#include "esp_timer.h"
#include "esp_heap_caps.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include <inttypes.h>

enum {
    MUESTRAS_EVALUACION_TALLER = 95963,
    METODOS_POR_CASO = 2,
    RESULTADOS_TALLER = (SENAL_CASO_3 - SENAL_CASO_1 + 1) * METODOS_POR_CASO,
};

/* Seis resumenes de tamano fijo; las muestras permanecen en flash y buffers por bloque. */
static informe_resultado_t resultados_taller[RESULTADOS_TALLER];

/* Usa el reloj monotono de la placa, nunca los tiempos de Python. */
static uint64_t leer_reloj(void) { return (uint64_t)esp_timer_get_time(); }

/* Cede a tareas de sistema fuera de la region cronometrada por bloque. */
static void ceder_procesador(void) { vTaskDelay(1); }

/* Compara filtros independientes sobre float32 despues de cerrar el DAC. */
static esp_err_t evaluar_caso(senal_embebida_id_t identificador, const char *nombre,
                             informe_resultado_t *resultados)
{
    datos_digitales_t datos;
    if (!datos_digitales_obtener(identificador, &datos)) return ESP_ERR_INVALID_SIZE;
    const banco_servicios_t servicios = {.reloj = leer_reloj, .ceder = ceder_procesador};
    const espectral_configuracion_t configuracion = {1600, 100, 0.1f, 0.05f};
    resultados[0] = (informe_resultado_t){.caso = nombre, .metodo = "FIR", .presupuesto_us = 16000};
    resultados[1] = (informe_resultado_t){.caso = nombre, .metodo = "ESPECTRAL", .presupuesto_us = 32000};
    ESP_LOGI("demostracion", "%s: iniciando FIR y espectral en secuencia, entrada float32", nombre);
    if (!banco_evaluar_fir(&datos, &servicios, &resultados[0].resultado) ||
        resultados[0].resultado.metricas.muestras != MUESTRAS_EVALUACION_TALLER) return ESP_FAIL;
    informe_consola_publicar(nombre, resultados[0].metodo, &resultados[0].resultado,
                            resultados[0].presupuesto_us);
    if (!banco_evaluar_espectral(&datos, configuracion, &servicios, &resultados[1].resultado) ||
        resultados[1].resultado.metricas.muestras != MUESTRAS_EVALUACION_TALLER) return ESP_FAIL;
    informe_consola_publicar(nombre, resultados[1].metodo, &resultados[1].resultado,
                            resultados[1].presupuesto_us);
    ESP_LOGI("demostracion", "%s COMPLETADO; heap interno libre=%u bytes", nombre,
             (unsigned)heap_caps_get_free_size(MALLOC_CAP_INTERNAL | MALLOC_CAP_8BIT));
    return ESP_OK;
}

/* Conserva el emisor del taller y distingue su evidencia de las metricas digitales. */
esp_err_t demostracion_ejecutar(void)
{
    ESP_LOGI("demostracion", "Flash -> DAC GPIO25; despues flash float32 -> FIR/FFT -> metricas.");
    ESP_LOGI("demostracion", "No hay captura ADC, filtros conectados a Pico ni medicion analogica.");
    ESP_LOGI("demostracion", "Intervalo fijo de evaluacion: %u muestras por caso y metodo.",
             (unsigned)MUESTRAS_EVALUACION_TALLER);
    for (int numero_caso = SENAL_CASO_1; numero_caso <= SENAL_CASO_3; ++numero_caso) {
        const senal_embebida_t *senal = senales_embebidas_obtener((senal_embebida_id_t)numero_caso);
        if (!senal) return ESP_ERR_NOT_FOUND;
        if (senal->cantidad_muestras != MUESTRAS_EVALUACION_TALLER + FIR_RETARDO) {
            ESP_LOGE("demostracion", "%s: se requieren %u muestras de entrada para evaluar %u; recibidas=%u",
                senal->nombre, (unsigned)(MUESTRAS_EVALUACION_TALLER + FIR_RETARDO),
                (unsigned)MUESTRAS_EVALUACION_TALLER, (unsigned)senal->cantidad_muestras);
            return ESP_ERR_INVALID_SIZE;
        }
        ESP_LOGI("demostracion", "%s DAC INICIO: %u muestras; %u Hz; CRC=%08" PRIX32,
            senal->nombre, (unsigned)senal->cantidad_muestras,
            (unsigned)senal->frecuencia_muestreo_hz, senal->crc32);
        salida_dac_estadisticas_t estadisticas;
        esp_err_t resultado = reproduccion_senal_ejecutar(senal, &estadisticas);
        if (resultado != ESP_OK) return resultado;
        ESP_LOGI("demostracion", "%s DAC FIN: reproducidas=%" PRIu64 "; paradas=%" PRIu32
            "; notificadas_dma=%" PRIu64, senal->nombre, estadisticas.codigos_reproducidos,
            estadisticas.paradas_inesperadas, estadisticas.codigos_notificados_dma);
        size_t primer_resultado = (size_t)(numero_caso - SENAL_CASO_1) * METODOS_POR_CASO;
        resultado = evaluar_caso((senal_embebida_id_t)numero_caso, senal->nombre,
                                 &resultados_taller[primer_resultado]);
        if (resultado != ESP_OK) return resultado;
    }
    informe_consola_publicar_resumen(resultados_taller, RESULTADOS_TALLER);
    ESP_LOGI("demostracion", "DEMOSTRACION COMPLETADA: 3 emisiones y 6 evaluaciones. EN para repetir.");
    return ESP_OK;
}
