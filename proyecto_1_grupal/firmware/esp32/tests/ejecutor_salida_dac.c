/* Inyecta eventos del SDK en el controlador real; no reproduce audio ni emula I2S. */
#include "salida_dac.h"
#include <assert.h>
#include <string.h>

struct controlador_simulado {
    dac_event_callbacks_t callbacks;
    void *contexto;
};

static struct controlador_simulado controlador;
static int notificacion;
static uint8_t muestras[96000];
static bool escritura_parcial;
static bool parar_durante_escritura;

/* Crea una notificación inicialmente vacía. */
SemaphoreHandle_t xSemaphoreCreateBinary(void)
{
    notificacion = 0;
    return &notificacion;
}

/* Consume la notificación; sin evento devuelve timeout sin esperar tiempo real. */
BaseType_t xSemaphoreTake(SemaphoreHandle_t semaforo, unsigned espera)
{
    (void)espera;
    if (!*semaforo) return pdFALSE;
    *semaforo = 0;
    return pdTRUE;
}

/* Publica el evento de parada desde el doble de interrupción. */
BaseType_t xSemaphoreGiveFromISR(SemaphoreHandle_t semaforo, BaseType_t *despertar)
{
    *semaforo = 1;
    *despertar = pdFALSE;
    return pdTRUE;
}

/* Libera la notificación al cerrar el controlador. */
void vSemaphoreDelete(SemaphoreHandle_t semaforo) { *semaforo = 0; }

/* Entrega un controlador simulado sin reservar periféricos. */
esp_err_t dac_continuous_new_channels(const dac_continuous_config_t *configuracion,
                                    dac_continuous_handle_t *destino)
{
    (void)configuracion;
    *destino = &controlador;
    return ESP_OK;
}

/* Captura los callbacks reales registrados por salida_dac.c. */
esp_err_t dac_continuous_register_event_callback(dac_continuous_handle_t handle,
    const dac_event_callbacks_t *callbacks, void *contexto)
{
    handle->callbacks = *callbacks;
    handle->contexto = contexto;
    return ESP_OK;
}

/* Habilita el doble sin generar eventos automáticamente. */
esp_err_t dac_continuous_enable(dac_continuous_handle_t handle)
{
    (void)handle;
    return ESP_OK;
}

/* Genera una parada también al cerrar para comprobar que no acredita reproducción. */
esp_err_t dac_continuous_disable(dac_continuous_handle_t handle)
{
    handle->callbacks.on_stop(handle, NULL, handle->contexto);
    return ESP_OK;
}

/* Completa la liberación del doble de controlador. */
esp_err_t dac_continuous_del_channels(dac_continuous_handle_t handle)
{
    (void)handle;
    return ESP_OK;
}

/* Acepta datos o inyecta una escritura parcial o una parada durante la llamada. */
esp_err_t dac_continuous_write(dac_continuous_handle_t handle, uint8_t *datos,
    size_t cantidad, size_t *aceptadas, int espera)
{
    (void)datos;
    (void)espera;
    *aceptadas = escritura_parcial ? cantidad / 2 : cantidad;
    if (parar_durante_escritura) {
        handle->callbacks.on_stop(handle, NULL, handle->contexto);
    }
    return escritura_parcial ? ESP_ERR_TIMEOUT : ESP_OK;
}

/* Notifica una cantidad de muestras, expandida al formato DMA de 16 bits. */
static void notificar_conversion(size_t cantidad)
{
    const dac_event_data_t evento = {
        .write_bytes = cantidad * SALIDA_DAC_BYTES_POR_MUESTRA_DMA,
    };
    controlador.callbacks.on_convert_done(&controlador, &evento, controlador.contexto);
}

/* Reproduce los casos de fin normal, error y cierre mediante la API pública. */
int main(int cantidad_argumentos, char **argumentos)
{
    assert(cantidad_argumentos == 2);
    salida_dac_t salida = {0};
    assert(salida_dac_inicializar(&salida, 16000, 96000) == ESP_OK);

    if (strcmp(argumentos[1], "escritura_parcial") == 0) {
        escritura_parcial = true;
        assert(salida_dac_escribir(&salida, muestras, 256) == ESP_ERR_TIMEOUT);
        controlador.callbacks.on_stop(&controlador, NULL, controlador.contexto);
        assert(salida_dac_esperar_fin(&salida) == ESP_ERR_INVALID_STATE);
        assert(salida.estadisticas.codigos_aceptados == 128);
    } else if (strcmp(argumentos[1], "parada_durante_escritura") == 0) {
        parar_durante_escritura = true;
        assert(salida_dac_escribir(&salida, muestras, 96000) == ESP_ERR_INVALID_STATE);
        assert(salida_dac_esperar_fin(&salida) == ESP_ERR_INVALID_STATE);
        assert(salida.estadisticas.paradas_inesperadas == 1);
    } else if (strcmp(argumentos[1], "parada_prematura") == 0) {
        assert(salida_dac_escribir(&salida, muestras, 256) == ESP_OK);
        notificar_conversion(256);
        controlador.callbacks.on_stop(&controlador, NULL, controlador.contexto);
        assert(salida_dac_esperar_fin(&salida) == ESP_ERR_INVALID_STATE);
        assert(salida_dac_escribir(&salida, muestras, 256) == ESP_ERR_INVALID_STATE);
        assert(salida.estadisticas.codigos_reproducidos == 256);
        assert(salida.estadisticas.paradas_inesperadas == 1);
    } else {
        assert(salida_dac_escribir(&salida, muestras, 96000) == ESP_OK);
        bool aviso_completo = strcmp(argumentos[1], "ultimo_aviso_omitido") != 0;
        notificar_conversion(aviso_completo ? 96000 : 95872);
        /* Copiar todos los datos y recibir avisos parciales no acredita fin total. */
        assert(salida_dac_esperar_fin(&salida) == ESP_ERR_TIMEOUT);
        assert(salida.estadisticas.codigos_reproducidos == 0);
        if (strcmp(argumentos[1], "cierre_voluntario") == 0) {
            assert(salida_dac_cerrar(&salida) == ESP_OK);
            assert(!salida.fin_confirmado);
            assert(salida.estadisticas.codigos_reproducidos == 0);
            return 0;
        }
        bool avisos_excesivos = strcmp(argumentos[1], "avisos_excesivos") == 0;
        if (avisos_excesivos) notificar_conversion(128);
        controlador.callbacks.on_stop(&controlador, NULL, controlador.contexto);
        if (avisos_excesivos) {
            assert(salida_dac_esperar_fin(&salida) == ESP_ERR_INVALID_STATE);
        } else {
            assert(salida_dac_esperar_fin(&salida) == ESP_OK);
            assert(salida.estadisticas.codigos_reproducidos == 96000);
            assert(salida.estadisticas.codigos_notificados_dma ==
                   (aviso_completo ? 96000U : 95872U));
            assert(salida.estadisticas.paradas_inesperadas == 0);
        }
    }
    assert(salida_dac_cerrar(&salida) == ESP_OK);
    salida_dac_estadisticas_t estadisticas;
    assert(salida_dac_obtener_estadisticas(&salida, &estadisticas) == ESP_OK);
    assert(estadisticas.codigos_aceptados == salida.estadisticas.codigos_aceptados);
    return 0;
}
