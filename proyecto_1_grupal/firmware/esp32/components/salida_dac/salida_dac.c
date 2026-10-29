#include "salida_dac.h"

#include "esp_attr.h"
#include "sdkconfig.h"

#if !CONFIG_DAC_DMA_AUTO_16BIT_ALIGN
#error "La salida DAC requiere CONFIG_DAC_DMA_AUTO_16BIT_ALIGN=y."
#endif

// ---------------------------------------------------------------------------
// 1. Registro de interrupciones y estado
// ---------------------------------------------------------------------------

/* Cuenta muestras terminadas por DMA; cada código ocupa dos bytes en el formato interno. */
static bool IRAM_ATTR registrar_consumo_dac(dac_continuous_handle_t controlador,
                                          const dac_event_data_t *evento,
                                          void *contexto_salida)
{
    (void)controlador;
    salida_dac_t *salida_dac = contexto_salida;
    portENTER_CRITICAL_ISR(&salida_dac->bloqueo_estadisticas);
    salida_dac->estadisticas.codigos_reproducidos +=
        evento->write_bytes / SALIDA_DAC_BYTES_POR_MUESTRA_DMA;
    portEXIT_CRITICAL_ISR(&salida_dac->bloqueo_estadisticas);
    return false;
}

/* Distingue fin normal de agotamiento prematuro y despierta la tarea que espera el cierre. */
static bool IRAM_ATTR registrar_parada_dac(dac_continuous_handle_t controlador,
                                         const dac_event_data_t *evento,
                                         void *contexto_salida)
{
    (void)controlador;
    (void)evento;
    salida_dac_t *salida_dac = contexto_salida;
    bool notificar = false;
    portENTER_CRITICAL_ISR(&salida_dac->bloqueo_estadisticas);
    if (salida_dac->contabilizar_paradas) {
        if (salida_dac->estadisticas.codigos_reproducidos ==
            salida_dac->estadisticas.codigos_previstos) {
            salida_dac->fin_confirmado = true;
        } else {
            ++salida_dac->estadisticas.paradas_inesperadas;
        }
        notificar = true;
    }
    portEXIT_CRITICAL_ISR(&salida_dac->bloqueo_estadisticas);
    BaseType_t despertar_tarea = pdFALSE;
    if (notificar) {
        xSemaphoreGiveFromISR(salida_dac->notificacion_final, &despertar_tarea);
    }
    return despertar_tarea == pdTRUE;
}

/* Devuelve una instantánea de contadores sin competir con la interrupción DAC. */
esp_err_t salida_dac_obtener_estadisticas(salida_dac_t *salida_dac,
                                        salida_dac_estadisticas_t *estadisticas)
{
    if (salida_dac == NULL || estadisticas == NULL) {
        return ESP_ERR_INVALID_ARG;
    }
    if (!salida_dac->estadisticas_disponibles) {
        return ESP_ERR_INVALID_STATE;
    }
    portENTER_CRITICAL(&salida_dac->bloqueo_estadisticas);
    *estadisticas = salida_dac->estadisticas;
    portEXIT_CRITICAL(&salida_dac->bloqueo_estadisticas);
    return ESP_OK;
}

// ---------------------------------------------------------------------------
// 2. Inicialización, escritura y cierre
// ---------------------------------------------------------------------------

/* Configura un canal DAC a la tasa solicitada con seis buffers DMA y reloj APLL. */
esp_err_t salida_dac_inicializar(salida_dac_t *salida_dac,
                               uint32_t frecuencia_muestreo_hz, size_t cantidad_total_codigos)
{
    if (salida_dac == NULL || frecuencia_muestreo_hz == 0 || cantidad_total_codigos == 0) {
        return ESP_ERR_INVALID_ARG;
    }
    if (salida_dac->controlador != NULL || salida_dac->notificacion_final != NULL) {
        return ESP_ERR_INVALID_STATE;
    }
    *salida_dac = (salida_dac_t){
        .bloqueo_estadisticas = portMUX_INITIALIZER_UNLOCKED,
        .estadisticas_disponibles = true,
        .estadisticas.codigos_previstos = cantidad_total_codigos,
    };
    salida_dac->notificacion_final = xSemaphoreCreateBinary();
    if (salida_dac->notificacion_final == NULL) {
        return ESP_ERR_NO_MEM;
    }
    const dac_continuous_config_t configuracion_dac = {
        .chan_mask = DAC_CHANNEL_MASK_CH0,
        .desc_num = SALIDA_DAC_CANTIDAD_DESCRIPTORES,
        .buf_size = SALIDA_DAC_BYTES_POR_BUFFER,
        .freq_hz = frecuencia_muestreo_hz,
        .offset = 0,
        .clk_src = DAC_DIGI_CLK_SRC_APLL,
        .chan_mode = DAC_CHANNEL_MODE_SIMUL,
    };
    esp_err_t resultado = dac_continuous_new_channels(&configuracion_dac,
                                                     &salida_dac->controlador);
    if (resultado != ESP_OK) {
        return resultado;
    }
    const dac_event_callbacks_t callbacks_dac = {
        .on_convert_done = registrar_consumo_dac,
        .on_stop = registrar_parada_dac,
    };
    resultado = dac_continuous_register_event_callback(salida_dac->controlador,
                                                       &callbacks_dac, salida_dac);
    if (resultado != ESP_OK) {
        return resultado;
    }
    resultado = dac_continuous_enable(salida_dac->controlador);
    if (resultado == ESP_OK) {
        salida_dac->habilitado = true;
    }
    return resultado;
}

/* Carga el bloque y registra bytes aceptados, errores y discontinuidades detectadas. */
esp_err_t salida_dac_escribir(salida_dac_t *salida_dac,
                            uint8_t *codigos_entrada, size_t cantidad_codigos)
{
    if (salida_dac == NULL || (cantidad_codigos > 0 && codigos_entrada == NULL)) {
        return ESP_ERR_INVALID_ARG;
    }
    if (salida_dac->controlador == NULL || !salida_dac->habilitado) {
        return ESP_ERR_INVALID_STATE;
    }
    if (cantidad_codigos == 0) {
        return ESP_OK;
    }

    portENTER_CRITICAL(&salida_dac->bloqueo_estadisticas);
    salida_dac->contabilizar_paradas = true;
    const bool hubo_parada = salida_dac->estadisticas.paradas_inesperadas > 0 ||
                            salida_dac->fin_confirmado;
    const bool excede_total = salida_dac->estadisticas.codigos_aceptados + cantidad_codigos >
                             salida_dac->estadisticas.codigos_previstos;
    if (hubo_parada || excede_total) {
        salida_dac->estadisticas.ultima_cantidad_solicitada = cantidad_codigos;
        salida_dac->estadisticas.ultima_cantidad_aceptada = 0;
        ++salida_dac->estadisticas.errores_escritura;
    }
    portEXIT_CRITICAL(&salida_dac->bloqueo_estadisticas);
    if (hubo_parada) {
        return ESP_ERR_INVALID_STATE;
    }
    if (excede_total) {
        return ESP_ERR_INVALID_SIZE;
    }

    size_t cantidad_aceptada = 0;
    esp_err_t resultado = dac_continuous_write(salida_dac->controlador,
                                              codigos_entrada, cantidad_codigos,
                                              &cantidad_aceptada,
                                              SALIDA_DAC_TIMEOUT_MILISEGUNDOS);
    if (resultado == ESP_OK && cantidad_aceptada != cantidad_codigos) {
        resultado = ESP_ERR_INVALID_SIZE;
    }

    portENTER_CRITICAL(&salida_dac->bloqueo_estadisticas);
    salida_dac->estadisticas.codigos_aceptados += cantidad_aceptada;
    salida_dac->estadisticas.ultima_cantidad_solicitada = cantidad_codigos;
    salida_dac->estadisticas.ultima_cantidad_aceptada = cantidad_aceptada;
    if (resultado == ESP_OK && salida_dac->estadisticas.paradas_inesperadas > 0) {
        resultado = ESP_ERR_INVALID_STATE;
    }
    if (resultado == ESP_OK) {
        ++salida_dac->estadisticas.escrituras_completas;
    } else {
        ++salida_dac->estadisticas.errores_escritura;
    }
    portEXIT_CRITICAL(&salida_dac->bloqueo_estadisticas);
    return resultado;
}

/* Espera el evento de fin, no una estimación basada en duración ni bytes aceptados. */
esp_err_t salida_dac_esperar_fin(salida_dac_t *salida_dac)
{
    if (salida_dac == NULL || !salida_dac->habilitado || salida_dac->notificacion_final == NULL) {
        return ESP_ERR_INVALID_STATE;
    }
    if (xSemaphoreTake(salida_dac->notificacion_final,
                       pdMS_TO_TICKS(SALIDA_DAC_TIMEOUT_MILISEGUNDOS)) != pdTRUE) {
        return ESP_ERR_TIMEOUT;
    }
    portENTER_CRITICAL(&salida_dac->bloqueo_estadisticas);
    bool completo = salida_dac->fin_confirmado &&
        salida_dac->estadisticas.paradas_inesperadas == 0 &&
        salida_dac->estadisticas.codigos_aceptados == salida_dac->estadisticas.codigos_previstos &&
        salida_dac->estadisticas.codigos_reproducidos == salida_dac->estadisticas.codigos_previstos;
    portEXIT_CRITICAL(&salida_dac->bloqueo_estadisticas);
    return completo ? ESP_OK : ESP_ERR_INVALID_STATE;
}

/* Deshabilita el periférico antes de liberar DMA y conserva contadores para el cierre. */
esp_err_t salida_dac_cerrar(salida_dac_t *salida_dac)
{
    if (salida_dac == NULL) {
        return ESP_ERR_INVALID_ARG;
    }
    if (salida_dac->controlador == NULL && salida_dac->notificacion_final == NULL) {
        return ESP_OK;
    }
    portENTER_CRITICAL(&salida_dac->bloqueo_estadisticas);
    salida_dac->contabilizar_paradas = false;
    portEXIT_CRITICAL(&salida_dac->bloqueo_estadisticas);

    if (salida_dac->habilitado) {
        const esp_err_t resultado = dac_continuous_disable(salida_dac->controlador);
        if (resultado != ESP_OK) {
            return resultado;
        }
        salida_dac->habilitado = false;
    }
    if (salida_dac->controlador != NULL) {
        const esp_err_t resultado = dac_continuous_del_channels(salida_dac->controlador);
        if (resultado != ESP_OK) {
            return resultado;
        }
        salida_dac->controlador = NULL;
    }
    if (salida_dac->notificacion_final != NULL) {
        vSemaphoreDelete(salida_dac->notificacion_final);
        salida_dac->notificacion_final = NULL;
    }
    return ESP_OK;
}
