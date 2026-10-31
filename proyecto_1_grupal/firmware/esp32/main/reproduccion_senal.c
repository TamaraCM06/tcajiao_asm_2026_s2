#include "reproduccion_senal.h"

#include "esp_log.h"
#include <inttypes.h>
#include <string.h>

/* Duración estática para conservar válido el contexto ISR incluso si falla el cierre. */
static salida_dac_t salida_reproduccion;
/* Solo este bloque de trabajo se copia a RAM; las señales completas son constantes en flash. */
static uint8_t buffer_reproduccion[SALIDA_DAC_CAPACIDAD_MUESTRAS];

/* Copia el arranque y luego bloques de 256 desde flash, sin alterar los datos originales. */
static esp_err_t enviar_registro(const senal_embebida_t *senal)
{
    size_t posicion = 0;
    while (posicion < senal->cantidad_muestras) {
        size_t capacidad_bloque = posicion == 0 ? SALIDA_DAC_CAPACIDAD_MUESTRAS :
                                                 SENALES_MUESTRAS_POR_BLOQUE;
        size_t muestras_restantes = senal->cantidad_muestras - posicion;
        size_t cantidad_bloque = muestras_restantes < capacidad_bloque ?
                                 muestras_restantes : capacidad_bloque;
        memcpy(buffer_reproduccion, senal->codigos_dac + posicion, cantidad_bloque);
        esp_err_t resultado = salida_dac_escribir(&salida_reproduccion,
                                                 buffer_reproduccion, cantidad_bloque);
        if (resultado != ESP_OK) {
            return resultado;
        }
        posicion += cantidad_bloque;
    }
    return ESP_OK;
}

/* Emite una vez, espera el final DMA y libera el periférico incluso ante un error. */
esp_err_t reproduccion_senal_ejecutar(const senal_embebida_t *senal,
                                    salida_dac_estadisticas_t *estadisticas)
{
    if (senal == NULL || senal->codigos_dac == NULL ||
        estadisticas == NULL) {
        return ESP_ERR_INVALID_ARG;
    }
    *estadisticas = (salida_dac_estadisticas_t){0};
    if (senal->frecuencia_muestreo_hz != SENALES_FRECUENCIA_MUESTREO_HZ ||
        senal->cantidad_muestras < SENALES_MUESTRAS_POR_BLOQUE ||
        senal->cantidad_muestras > SENALES_MAXIMO_MUESTRAS ||
        senal->cantidad_muestras % SENALES_MUESTRAS_POR_BLOQUE != 0) {
        return ESP_ERR_INVALID_ARG;
    }
    const char *etapa = "inicializacion";
    esp_err_t resultado = salida_dac_inicializar(&salida_reproduccion,
        senal->frecuencia_muestreo_hz, senal->cantidad_muestras);
    if (resultado == ESP_OK) {
        etapa = "escritura";
        resultado = enviar_registro(senal);
    }
    if (resultado == ESP_OK) {
        etapa = "espera_fin";
        resultado = salida_dac_esperar_fin(&salida_reproduccion);
    }
    esp_err_t resultado_cierre = salida_dac_cerrar(&salida_reproduccion);
    if (salida_reproduccion.estadisticas_disponibles) {
        (void)salida_dac_obtener_estadisticas(&salida_reproduccion, estadisticas);
    }
    if (resultado != ESP_OK) {
        ESP_LOGE("reproduccion", "%s: etapa=%s; error=%s; previstas=%" PRIu64
            "; aceptadas=%" PRIu64 "; reproducidas=%" PRIu64 "; paradas=%" PRIu32
            "; notificadas_dma=%" PRIu64,
            senal->nombre, etapa, esp_err_to_name(resultado), estadisticas->codigos_previstos,
            estadisticas->codigos_aceptados, estadisticas->codigos_reproducidos,
            estadisticas->paradas_inesperadas, estadisticas->codigos_notificados_dma);
    }
    if (resultado_cierre != ESP_OK) {
        ESP_LOGE("reproduccion", "%s: etapa=cierre; error=%s", senal->nombre,
                 esp_err_to_name(resultado_cierre));
    }
    return resultado_cierre != ESP_OK ? resultado_cierre : resultado;
}
