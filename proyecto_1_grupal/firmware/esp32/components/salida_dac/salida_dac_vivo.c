/** Gestiona DAC continuo GPIO25, seleccion de ruta y silencio sin modificar la reproduccion finita. */
#include "salida_dac_vivo.h"

#include <math.h>
#include <stddef.h>
#include <string.h>

#include "driver/dac_continuous.h"
#include "esp_attr.h"
#include "freertos/FreeRTOS.h"
#include "freertos/queue.h"
#include "freertos/semphr.h"
#include "freertos/task.h"
#include "sdkconfig.h"
#include "senales_embebidas.h"

#if !CONFIG_DAC_DMA_AUTO_16BIT_ALIGN
#error "La salida continua requiere CONFIG_DAC_DMA_AUTO_16BIT_ALIGN=y."
#endif

enum {
    DESCRIPTORES_DMA = 6,
    BYTES_BUFFER_DMA = 512,
    PRELLENADO = 2,
    ESPERA_ESCRITURA_MS = 100,
};

typedef struct {
    uint32_t generacion;
    uint8_t codigos[SALIDA_DAC_VIVO_MUESTRAS];
} tramo_dac_t;

static dac_continuous_handle_t controlador;
static QueueHandle_t cola;
static SemaphoreHandle_t acceso_cola;
static TaskHandle_t tarea;
static portMUX_TYPE bloqueo = portMUX_INITIALIZER_UNLOCKED;
static salida_dac_vivo_estadisticas_t contadores;
static uint32_t generacion;
static bool sesion_activa;
static bool disponible;
static bool controlador_habilitado;
static bool recuperacion_invalidada;

/** Registra un fin de carga DMA; el callback no convierte muestras ni imprime. */
static bool IRAM_ATTR registrar_parada(dac_continuous_handle_t manejador,
                                      const dac_event_data_t *evento, void *contexto)
{
    (void)manejador;
    (void)evento;
    (void)contexto;
    portENTER_CRITICAL_ISR(&bloqueo);
    ++contadores.paradas_dma;
    portEXIT_CRITICAL_ISR(&bloqueo);
    return false;
}

/** Cuantiza voltios con escala comun fija y registra recortes, sin alterar la ganancia. */
static uint8_t convertir_muestra(float muestra, float ganancia, uint32_t *saturadas)
{
    if (!isfinite(muestra)) {
        ++*saturadas;
        return 128;
    }
    const float codigo = 128.0f + muestra * ganancia * (255.0f / 3.3f);
    if (codigo < 0) {
        ++*saturadas;
        return 0;
    }
    if (codigo > 255) {
        ++*saturadas;
        return 255;
    }
    return (uint8_t)(codigo + 0.5f);
}

/** Intenta hasta tres rearmes; el bucle de tarea espacia nuevos intentos sin bloquear al productor. */
static bool recuperar_controlador(void)
{
    if (!recuperacion_invalidada) {
        if (xSemaphoreTake(acceso_cola, pdMS_TO_TICKS(ESPERA_ESCRITURA_MS)) != pdTRUE) {
            portENTER_CRITICAL(&bloqueo);
            disponible = false;
            contadores.ultimo_error = ESP_ERR_TIMEOUT;
            portEXIT_CRITICAL(&bloqueo);
            return false;
        }
        portENTER_CRITICAL(&bloqueo);
        disponible = false;
        sesion_activa = false;
        ++generacion;
        contadores.reproduciendo = false;
        portEXIT_CRITICAL(&bloqueo);
        xQueueReset(cola);
        xSemaphoreGive(acceso_cola);
        recuperacion_invalidada = true;
    }
    for (unsigned intento = 0; intento < 3; ++intento) {
        esp_err_t resultado = ESP_OK;
        if (controlador_habilitado) {
            resultado = dac_continuous_disable(controlador);
            if (resultado == ESP_OK) controlador_habilitado = false;
        }
        /* Si disable fallo, no intentar enable sobre un estado aun habilitado. */
        if (!controlador_habilitado) {
            resultado = dac_continuous_enable(controlador);
            controlador_habilitado = resultado == ESP_OK;
        }
        if (resultado == ESP_OK) {
            portENTER_CRITICAL(&bloqueo);
            disponible = true;
            portEXIT_CRITICAL(&bloqueo);
            recuperacion_invalidada = false;
            return true;
        }
        portENTER_CRITICAL(&bloqueo);
        contadores.ultimo_error = resultado;
        portEXIT_CRITICAL(&bloqueo);
    }
    return false;
}

/** Consume muestras a ritmo del DAC; ante vacio escribe silencio y vuelve a prellenar. */
static void reproducir_continuamente(void *argumento)
{
    (void)argumento;
    tramo_dac_t tramo;
    uint32_t generacion_local = 0;
    bool reproduciendo = false;
    bool recuperando = false;
    while (true) {
        if (recuperando) {
            recuperando = !recuperar_controlador();
            reproduciendo = false;
            if (recuperando) vTaskDelay(pdMS_TO_TICKS(ESPERA_ESCRITURA_MS));
            continue;
        }
        portENTER_CRITICAL(&bloqueo);
        const uint32_t generacion_actual = generacion;
        const bool activa = sesion_activa;
        portEXIT_CRITICAL(&bloqueo);
        if (generacion_actual != generacion_local || !activa) {
            reproduciendo = false;
            generacion_local = generacion_actual;
        }
        if (!reproduciendo && activa && uxQueueMessagesWaiting(cola) >= PRELLENADO) {
            reproduciendo = true;
        }
        bool hay_audio = false;
        if (reproduciendo) {
            hay_audio = xQueueReceive(cola, &tramo, 0) == pdTRUE;
            if (!hay_audio) {
                reproduciendo = false;
                portENTER_CRITICAL(&bloqueo);
                if (sesion_activa && generacion_actual == generacion) {
                    ++contadores.faltas_datos;
                }
                portEXIT_CRITICAL(&bloqueo);
            }
        }
        portENTER_CRITICAL(&bloqueo);
        hay_audio = hay_audio && tramo.generacion == generacion && sesion_activa;
        contadores.reproduciendo = hay_audio;
        portEXIT_CRITICAL(&bloqueo);
        if (!hay_audio) memset(tramo.codigos, 128, sizeof(tramo.codigos));

        size_t cargados = 0;
        esp_err_t resultado = dac_continuous_write(controlador, tramo.codigos,
                                                  sizeof(tramo.codigos), &cargados,
                                                  ESPERA_ESCRITURA_MS);
        if (resultado == ESP_OK && cargados != sizeof(tramo.codigos)) {
            resultado = ESP_ERR_INVALID_SIZE;
        }
        portENTER_CRITICAL(&bloqueo);
        contadores.muestras_cargadas += cargados;
        if (resultado != ESP_OK) {
            ++contadores.errores_escritura;
            contadores.ultimo_error = resultado;
            disponible = false;
        }
        portEXIT_CRITICAL(&bloqueo);
        recuperando = resultado != ESP_OK;
    }
}

/** Reserva solo GPIO25 y arranca su unico escritor, limpiando fallos parciales. */
esp_err_t salida_dac_vivo_iniciar(void)
{
    if (tarea != NULL || controlador != NULL) return ESP_ERR_INVALID_STATE;
    cola = xQueueCreate(SALIDA_DAC_VIVO_CAPACIDAD, sizeof(tramo_dac_t));
    if (cola == NULL) return ESP_ERR_NO_MEM;
    acceso_cola = xSemaphoreCreateMutex();
    if (acceso_cola == NULL) {
        vQueueDelete(cola);
        cola = NULL;
        return ESP_ERR_NO_MEM;
    }
    const dac_continuous_config_t configuracion = {
        .chan_mask = DAC_CHANNEL_MASK_CH0,
        .desc_num = DESCRIPTORES_DMA,
        .buf_size = BYTES_BUFFER_DMA,
        /* La misma tasa que adquisicion y filtros; GPIO26 no pertenece a este servicio. */
        .freq_hz = SENALES_FRECUENCIA_MUESTREO_HZ,
        .offset = 0,
        .clk_src = DAC_DIGI_CLK_SRC_APLL,
        .chan_mode = DAC_CHANNEL_MODE_SIMUL,
    };
    bool habilitado = false;
    esp_err_t resultado = dac_continuous_new_channels(&configuracion, &controlador);
    if (resultado == ESP_OK) {
        const dac_event_callbacks_t callbacks = {.on_stop = registrar_parada};
        resultado = dac_continuous_register_event_callback(controlador, &callbacks, NULL);
    }
    if (resultado == ESP_OK) {
        resultado = dac_continuous_enable(controlador);
        habilitado = resultado == ESP_OK;
        controlador_habilitado = habilitado;
    }
    if (resultado == ESP_OK) {
        disponible = true;
        if (xTaskCreate(reproducir_continuamente, "dac_vivo", 4096, NULL, 5, &tarea) != pdPASS) {
            disponible = false;
            resultado = ESP_ERR_NO_MEM;
        }
    }
    if (resultado != ESP_OK) {
        if (habilitado) dac_continuous_disable(controlador);
        if (controlador != NULL) {
            dac_continuous_del_channels(controlador);
            controlador = NULL;
        }
        vQueueDelete(cola);
        cola = NULL;
        vSemaphoreDelete(acceso_cola);
        acceso_cola = NULL;
        controlador_habilitado = false;
    }
    return resultado;
}

/** Copia 512 muestras de la ruta elegida; rechaza el tramo entero si no cabe. */
bool salida_dac_vivo_ofrecer(const float fir[SALIDA_DAC_VIVO_MUESTRAS],
                            const float espectral[SALIDA_DAC_VIVO_MUESTRAS],
                            float ganancia, salida_dac_vivo_escucha_t escucha)
{
    if (fir == NULL || espectral == NULL || !isfinite(ganancia) || ganancia < 0 ||
        ganancia > 100 || escucha < SALIDA_DAC_VIVO_FIR ||
        escucha > SALIDA_DAC_VIVO_ESPECTRAL || cola == NULL) return false;
    tramo_dac_t tramo;
    portENTER_CRITICAL(&bloqueo);
    const bool listo = disponible;
    tramo.generacion = generacion;
    portEXIT_CRITICAL(&bloqueo);
    if (!listo) return false;
    uint32_t saturadas = 0;
    for (size_t n = 0; n < SALIDA_DAC_VIVO_MUESTRAS; ++n) {
        const float seleccionada = escucha == SALIDA_DAC_VIVO_ESPECTRAL ? espectral[n] : fir[n];
        tramo.codigos[n] = convertir_muestra(seleccionada, ganancia, &saturadas);
    }
    /* La conversion ocurre fuera del bloqueo; un rearme puede invalidar su
     * generacion mientras se calculan los codigos. Revalidar antes de publicar. */
    if (xSemaphoreTake(acceso_cola, 0) != pdTRUE) return false;
    portENTER_CRITICAL(&bloqueo);
    const bool vigente = disponible && tramo.generacion == generacion;
    portEXIT_CRITICAL(&bloqueo);
    if (!vigente) {
        xSemaphoreGive(acceso_cola);
        return false;
    }
    const bool aceptado = xQueueSend(cola, &tramo, 0) == pdTRUE;
    portENTER_CRITICAL(&bloqueo);
    const bool publicado = aceptado && disponible && tramo.generacion == generacion;
    if (publicado) {
        sesion_activa = true;
        contadores.muestras_saturadas += saturadas;
    } else if (!aceptado) {
        ++contadores.desbordamientos;
    }
    portEXIT_CRITICAL(&bloqueo);
    xSemaphoreGive(acceso_cola);
    return publicado;
}

/** Invalida la generacion previa sin tocar buffers que ya pertenecen al controlador. */
void salida_dac_vivo_silenciar(void)
{
    portENTER_CRITICAL(&bloqueo);
    ++generacion;
    sesion_activa = false;
    contadores.reproduciendo = false;
    portEXIT_CRITICAL(&bloqueo);
    if (cola != NULL) xQueueReset(cola);
}

/** Obtiene una instantanea protegida de la tarea de salida y del callback DMA. */
void salida_dac_vivo_obtener_estadisticas(salida_dac_vivo_estadisticas_t *estadisticas)
{
    if (estadisticas == NULL) return;
    portENTER_CRITICAL(&bloqueo);
    *estadisticas = contadores;
    portEXIT_CRITICAL(&bloqueo);
    estadisticas->pendientes = cola == NULL ? 0 : uxQueueMessagesWaiting(cola);
}
