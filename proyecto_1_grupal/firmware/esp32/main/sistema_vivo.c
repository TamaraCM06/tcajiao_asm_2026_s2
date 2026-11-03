/** Conecta SPI, los filtros originales y audio seleccionable con memoria acotada. */
#include "sistema_vivo.h"

#include <fcntl.h>
#include <inttypes.h>
#include <math.h>
#include <stdio.h>
#include <string.h>
#include <unistd.h>

#include "esp_log.h"
#include "esp_timer.h"
#include "freertos/FreeRTOS.h"
#include "freertos/queue.h"
#include "freertos/semphr.h"
#include "freertos/task.h"
#include "procesamiento_vivo.h"
#include "recepcion_spi.h"
#include "salida_dac_vivo.h"

enum { CAPACIDAD_ENTRADA = 8, ESPERA_ENTRADA_MS = 50, REPORTE_MS = 2000 };

typedef struct {
    trama_spi_bloque_t bloque;
    uint32_t generacion;
    bool discontinuidad;
} entrada_t;

typedef struct {
    bool activo;
    uint32_t generacion;
    float ganancia;
    salida_dac_vivo_escucha_t escucha;
    espectral_configuracion_t espectral;
} control_t;

typedef struct {
    uint64_t validos, huecos, rechazos[TRAMA_SPI_MUESTRA_NO_FINITA + 1];
    uint32_t duplicados, retrocesos, desbordamientos, reinicios, errores_spi;
    uint32_t ultimo_id, calculo_max_us;
    int64_t ultimo_valido_us;
} diagnostico_t;

_Static_assert(TRAMA_SPI_MUESTRAS == PROCESAMIENTO_VIVO_ENTRADA_MUESTRAS,
               "El transporte y el procesador deben recibir el mismo bloque.");
_Static_assert((int)SALIDA_DAC_VIVO_MUESTRAS == (int)PROCESAMIENTO_VIVO_SALIDA_MUESTRAS,
               "El DAC debe consumir un salto espectral completo.");

static const char *ETIQUETA = "vivo";
static QueueHandle_t entradas;
static SemaphoreHandle_t bloqueo_control;
static portMUX_TYPE bloqueo_diagnostico = portMUX_INITIALIZER_UNLOCKED;
static diagnostico_t diagnostico;
static control_t control = {
    .activo = true, .generacion = 1, .ganancia = 1.0f,
    .escucha = SALIDA_DAC_VIVO_FIR,
    .espectral = {1600, 100, 0.1f, 0.05f},
};
/* Los estados no caben en la pila de una tarea; no se comparten con el banco de flash. */
static procesamiento_vivo_t procesamiento;
static float salida_fir[PROCESAMIENTO_VIVO_SALIDA_MUESTRAS];
static float salida_espectral[PROCESAMIENTO_VIVO_SALIDA_MUESTRAS];

/** Copia controles bajo un mutex; no mantiene el bloqueo durante DSP ni esperas de SPI. */
static control_t consultar_control(void)
{
    xSemaphoreTake(bloqueo_control, portMAX_DELAY);
    const control_t copia = control;
    xSemaphoreGive(bloqueo_control);
    return copia;
}

/** Recibe y valida fuera de ISR; descarta duplicados y marca toda rotura de continuidad. */
static void recibir_entrada(void *argumento)
{
    (void)argumento;
    /* No armar DMA hasta que todos los servicios hayan arrancado correctamente. */
    (void)ulTaskNotifyTake(pdTRUE, portMAX_DELAY);
    entrada_t entrada;
    trama_spi_secuencia_t secuencia = {0};
    bool discontinuidad = true;
    while (true) {
        trama_spi_resultado_t validacion;
        const esp_err_t resultado = recepcion_spi_recibir(&entrada.bloque, &validacion, 100);
        if (resultado == ESP_ERR_TIMEOUT) continue;
        if (resultado != ESP_OK) {
            portENTER_CRITICAL(&bloqueo_diagnostico);
            ++diagnostico.errores_spi;
            portEXIT_CRITICAL(&bloqueo_diagnostico);
            discontinuidad = true;
            vTaskDelay(pdMS_TO_TICKS(10));
            continue;
        }
        if (validacion != TRAMA_SPI_VALIDA) {
            portENTER_CRITICAL(&bloqueo_diagnostico);
            ++diagnostico.rechazos[validacion];
            portEXIT_CRITICAL(&bloqueo_diagnostico);
            discontinuidad = true;
            continue;
        }
        const trama_spi_continuidad_t continuidad =
            trama_spi_actualizar_secuencia(&secuencia, entrada.bloque.id);
        portENTER_CRITICAL(&bloqueo_diagnostico);
        ++diagnostico.validos;
        diagnostico.ultimo_id = entrada.bloque.id;
        diagnostico.ultimo_valido_us = esp_timer_get_time();
        diagnostico.huecos += continuidad.ids_omitidos;
        if (continuidad.evento == TRAMA_SPI_DUPLICADO) ++diagnostico.duplicados;
        if (continuidad.evento == TRAMA_SPI_RETROCESO) ++diagnostico.retrocesos;
        portEXIT_CRITICAL(&bloqueo_diagnostico);
        if (continuidad.evento == TRAMA_SPI_DUPLICADO) continue;
        discontinuidad |= continuidad.evento == TRAMA_SPI_SALTO ||
                          continuidad.evento == TRAMA_SPI_RETROCESO;
        const control_t actual = consultar_control();
        if (!actual.activo) {
            discontinuidad = true;
            continue;
        }
        entrada.generacion = actual.generacion;
        entrada.discontinuidad = discontinuidad;
        if (xQueueSend(entradas, &entrada, 0) != pdTRUE) {
            portENTER_CRITICAL(&bloqueo_diagnostico);
            ++diagnostico.desbordamientos;
            portEXIT_CRITICAL(&bloqueo_diagnostico);
            /* Invalida tambien los paquetes antiguos que ya llenaron la cola. */
            xSemaphoreTake(bloqueo_control, portMAX_DELAY);
            ++control.generacion;
            xSemaphoreGive(bloqueo_control);
            xQueueReset(entradas);
            discontinuidad = true;
        } else {
            discontinuidad = false;
        }
    }
}

/** Borra historia y audio pendiente; solo esta tarea es productora del DAC continuo. */
static void reiniciar_rutas(espectral_configuracion_t configuracion)
{
    salida_dac_vivo_silenciar();
    (void)procesamiento_vivo_inicializar(&procesamiento, configuracion);
    portENTER_CRITICAL(&bloqueo_diagnostico);
    ++diagnostico.reinicios;
    portEXIT_CRITICAL(&bloqueo_diagnostico);
}

/** Procesa ambas rutas sobre la misma entrada, fuera de ISR y sin esperar al DAC. */
static void procesar_entrada(void *argumento)
{
    (void)argumento;
    (void)ulTaskNotifyTake(pdTRUE, portMAX_DELAY);
    entrada_t entrada;
    uint32_t generacion_local = 0;
    bool habia_datos = false;
    while (true) {
        control_t actual = consultar_control();
        if (actual.generacion != generacion_local) {
            reiniciar_rutas(actual.espectral);
            generacion_local = actual.generacion;
            habia_datos = false;
        }
        if (xQueueReceive(entradas, &entrada, pdMS_TO_TICKS(ESPERA_ENTRADA_MS)) != pdTRUE) {
            if (habia_datos) {
                reiniciar_rutas(actual.espectral);
                habia_datos = false;
            }
            continue;
        }
        actual = consultar_control();
        if (!actual.activo || entrada.generacion != actual.generacion ||
            actual.generacion != generacion_local) continue;
        if (entrada.discontinuidad && habia_datos) reiniciar_rutas(actual.espectral);
        habia_datos = true;
        const int64_t inicio = esp_timer_get_time();
        const bool disponible = procesamiento_vivo_bloque(&procesamiento,
            entrada.bloque.muestras, salida_fir, salida_espectral);
        const uint32_t duracion_us = (uint32_t)(esp_timer_get_time() - inicio);
        portENTER_CRITICAL(&bloqueo_diagnostico);
        if (duracion_us > diagnostico.calculo_max_us) diagnostico.calculo_max_us = duracion_us;
        portEXIT_CRITICAL(&bloqueo_diagnostico);
        if (!disponible) continue;
        /* El control no puede detener/reconfigurar entre esta comprobacion y la oferta. */
        xSemaphoreTake(bloqueo_control, portMAX_DELAY);
        if (control.activo && control.generacion == generacion_local &&
            !salida_dac_vivo_ofrecer(salida_fir, salida_espectral,
                                    control.ganancia, control.escucha)) {
            /* Relojes ADC y DAC distintos: descartar y rearmar, nunca crecer sin limite. */
            ++control.generacion;
            salida_dac_vivo_silenciar();
            xQueueReset(entradas);
        }
        xSemaphoreGive(bloqueo_control);
    }
}

/** Muestra comandos cortos, unidades y limites; no promete tamanos de bloque variables. */
static void mostrar_ayuda(void)
{
    puts("\nComandos: ayuda | estado | iniciar | detener | reiniciar");
    puts("salida fir|espectral  (un solo amplificador/parlante por GPIO25)");
    puts("ganancia VALOR  (0..100; misma escala para ambos filtros, inicial 1)");
    puts("Para ajustar: escribir detener, luego espectral MIN_HZ ANCHO_HZ FACTOR UMBRAL,");
    puts("y finalmente iniciar. Cada comando en una linea separada, sin punto y coma.");
    puts("MIN_HZ [0,8000), ANCHO_HZ [0,8000], FACTOR [0,1], UMBRAL (0,1].");
    puts("Iniciales: espectral 1600 100 0.1 0.05. Tamano fijo: entrada256, FFT1024, salto512.");
    puts("El MAX4466 no aporta referencia limpia: MSE/SNR exactos no disponibles en vivo.");
}

/** Publica contadores observables; la falta de referencia no se reemplaza con flash. */
static void mostrar_estado(void)
{
    diagnostico_t copia;
    portENTER_CRITICAL(&bloqueo_diagnostico);
    copia = diagnostico;
    portEXIT_CRITICAL(&bloqueo_diagnostico);
    const control_t actual = consultar_control();
    salida_dac_vivo_estadisticas_t dac;
    salida_dac_vivo_obtener_estadisticas(&dac);
    ESP_LOGI(ETIQUETA, "%s | Fs=%d Hz | validos=%" PRIu64 " id=%" PRIu32
             " | sin datos=%" PRIi64 " ms | cola=%u/%u",
             actual.activo ? "ACTIVO" : "DETENIDO", PROCESAMIENTO_VIVO_FRECUENCIA_HZ,
             copia.validos, copia.ultimo_id,
             copia.ultimo_valido_us ? (esp_timer_get_time() - copia.ultimo_valido_us) / 1000 : -1,
             (unsigned)uxQueueMessagesWaiting(entradas), CAPACIDAD_ENTRADA);
    ESP_LOGI(ETIQUETA, "Errores longitud/cabecera/CRC/muestra=%" PRIu64 "/%" PRIu64
             "/%" PRIu64 "/%" PRIu64 " | huecos_ID=%" PRIu64
             " duplicados=%" PRIu32 " retrocesos=%" PRIu32 " cola_llena=%" PRIu32
             " SPI=%" PRIu32, copia.rechazos[TRAMA_SPI_LONGITUD_INVALIDA],
             copia.rechazos[TRAMA_SPI_CABECERA_INVALIDA], copia.rechazos[TRAMA_SPI_CRC_INVALIDO],
             copia.rechazos[TRAMA_SPI_MUESTRA_NO_FINITA], copia.huecos, copia.duplicados,
             copia.retrocesos, copia.desbordamientos, copia.errores_spi);
    ESP_LOGI(ETIQUETA, "DAC cola=%" PRIu32 " faltas=%" PRIu32 " cola_llena=%" PRIu32
             " recortes=%" PRIu64 " errores=%" PRIu32 " ultimo=%s | calculo_max=%" PRIu32
             " us reinicios=%" PRIu32 " ganancia=%.2f salida=%d",
             dac.pendientes, dac.faltas_datos, dac.desbordamientos, dac.muestras_saturadas,
             dac.errores_escritura, esp_err_to_name(dac.ultimo_error), copia.calculo_max_us,
             copia.reinicios, (double)actual.ganancia, actual.escucha);
    ESP_LOGI(ETIQUETA, "Espectral: min=%.1f Hz ancho=%.1f Hz factor=%.3f umbral=%.3f",
             (double)actual.espectral.frecuencia_minima_hz, (double)actual.espectral.ancho_hz,
             (double)actual.espectral.factor, (double)actual.espectral.umbral_relativo);
}

/** Valida los mismos limites aceptados por el filtro existente, sin modificarlo. */
static bool configuracion_valida(espectral_configuracion_t c)
{
    return isfinite(c.frecuencia_minima_hz) && c.frecuencia_minima_hz >= 0 &&
        c.frecuencia_minima_hz < 8000 && isfinite(c.ancho_hz) && c.ancho_hz >= 0 &&
        c.ancho_hz <= 8000 && isfinite(c.factor) && c.factor >= 0 && c.factor <= 1 &&
        isfinite(c.umbral_relativo) && c.umbral_relativo > 0 && c.umbral_relativo <= 1;
}

/** Aplica comandos en contexto de tarea; los cambios estructurales exigen detener. */
static void ejecutar_comando(const char *linea)
{
    if (strcmp(linea, "ayuda") == 0) { mostrar_ayuda(); return; }
    if (strcmp(linea, "estado") == 0) { mostrar_estado(); return; }
    xSemaphoreTake(bloqueo_control, portMAX_DELAY);
    bool valido = true;
    char sobrante;
    if (strcmp(linea, "iniciar") == 0 || strcmp(linea, "detener") == 0) {
        control.activo = strcmp(linea, "iniciar") == 0;
        ++control.generacion;
    } else if (strcmp(linea, "reiniciar") == 0) {
        ++control.generacion;
    } else if (strncmp(linea, "ganancia ", 9) == 0) {
        float ganancia;
        valido = sscanf(linea + 9, "%f %c", &ganancia, &sobrante) == 1 &&
                 isfinite(ganancia) && ganancia >= 0 && ganancia <= 100;
        if (valido) { control.ganancia = ganancia; ++control.generacion; }
    } else if (strncmp(linea, "salida ", 7) == 0) {
        if (strcmp(linea + 7, "fir") == 0) control.escucha = SALIDA_DAC_VIVO_FIR;
        else if (strcmp(linea + 7, "espectral") == 0) control.escucha = SALIDA_DAC_VIVO_ESPECTRAL;
        else valido = false;
        if (valido) ++control.generacion;
    } else if (strncmp(linea, "espectral ", 10) == 0) {
        espectral_configuracion_t c;
        valido = !control.activo && sscanf(linea + 10, "%f %f %f %f %c",
            &c.frecuencia_minima_hz, &c.ancho_hz, &c.factor,
            &c.umbral_relativo, &sobrante) == 4 && configuracion_valida(c);
        if (valido) { control.espectral = c; ++control.generacion; }
    } else valido = false;
    xSemaphoreGive(bloqueo_control);
    puts(valido ? "OK. Aplicando; el audio ya cargado puede tardar hasta ~180 ms en salir."
                : "Comando invalido o fuera de limites. Para espectral: detener primero. Escribi ayuda.");
}

/** Reserva servicios una vez y mantiene la consola independiente de recepcion y audio. */
esp_err_t sistema_vivo_ejecutar(void)
{
    const int flags = fcntl(STDIN_FILENO, F_GETFL, 0);
    if (flags < 0 || fcntl(STDIN_FILENO, F_SETFL, flags | O_NONBLOCK) < 0) {
        ESP_LOGE(ETIQUETA, "No se pudo configurar lectura no bloqueante de consola");
        return ESP_FAIL;
    }
    setvbuf(stdin, NULL, _IONBF, 0);
    TaskHandle_t tarea_rx = NULL, tarea_dsp = NULL;
    esp_err_t resultado = ESP_ERR_NO_MEM;
    entradas = xQueueCreate(CAPACIDAD_ENTRADA, sizeof(entrada_t));
    bloqueo_control = xSemaphoreCreateMutex();
    if (entradas == NULL || bloqueo_control == NULL) goto fallo_arranque;
    if (!procesamiento_vivo_inicializar(&procesamiento, control.espectral)) {
        resultado = ESP_ERR_INVALID_ARG;
        goto fallo_arranque;
    }
    resultado = recepcion_spi_inicializar();
    if (resultado != ESP_OK) goto fallo_arranque;
    /* La recepcion queda en el nucleo que inicializo la ISR del controlador SPI. */
    const BaseType_t nucleo_spi = xPortGetCoreID();
#if CONFIG_FREERTOS_UNICORE
    const BaseType_t nucleo_dsp = 0;
#else
    const BaseType_t nucleo_dsp = 1 - nucleo_spi;
#endif
    resultado = ESP_ERR_NO_MEM;
    if (xTaskCreatePinnedToCore(recibir_entrada, "entrada_spi", 4096, NULL, 7,
                               &tarea_rx, nucleo_spi) != pdPASS) goto fallo_arranque;
    if (xTaskCreatePinnedToCore(procesar_entrada, "filtros_vivo", 6144, NULL, 5,
                               &tarea_dsp, nucleo_dsp) != pdPASS) goto fallo_arranque;
    resultado = salida_dac_vivo_iniciar();
    if (resultado != ESP_OK) goto fallo_arranque;
    xTaskNotifyGive(tarea_rx);
    xTaskNotifyGive(tarea_dsp);
    ESP_LOGI(ETIQUETA, "MAX4466/Pico -> SPI -> FIR y espectral originales -> escucha por GPIO25");
    ESP_LOGI(ETIQUETA, "GPIO26 libre para DC/RS de pantalla; la pantalla no se inicializa en este modo");
    ESP_LOGI(ETIQUETA, "16 kHz; SPI SCK18 MOSI23 CS5 READY21; sin retorno MISO");
    ESP_LOGI(ETIQUETA, "Estados DSP=%u bytes; colas acotadas; reinicio si faltan/sobran datos",
             (unsigned)sizeof(procesamiento));
    mostrar_ayuda();
    char linea[128];
    size_t usados = 0;
    bool descartando = false;
    int64_t ultimo_reporte = esp_timer_get_time();
    while (true) {
        for (unsigned n = 0; n < sizeof(linea); ++n) {
            const int caracter = getchar();
            if (caracter == EOF) { clearerr(stdin); break; }
            if (caracter == '\r' || caracter == '\n') {
                linea[usados] = '\0';
                if (!descartando && usados != 0) ejecutar_comando(linea);
                usados = 0;
                descartando = false;
            } else if (caracter == '\b' || caracter == 127) {
                if (usados) --usados;
            } else if (!descartando) {
                if (usados + 1u < sizeof(linea)) linea[usados++] = (char)caracter;
                else { descartando = true; puts("Comando demasiado largo; repetir tras Enter."); }
            }
        }
        const int64_t ahora = esp_timer_get_time();
        if (ahora - ultimo_reporte >= REPORTE_MS * INT64_C(1000)) {
            mostrar_estado();
            ultimo_reporte = ahora;
        }
        vTaskDelay(pdMS_TO_TICKS(20));
    }

fallo_arranque:
    /* Las tareas aun esperan permiso y SPI no posee ningun descriptor pendiente. */
    if (tarea_rx != NULL) vTaskDelete(tarea_rx);
    if (tarea_dsp != NULL) vTaskDelete(tarea_dsp);
    (void)recepcion_spi_cerrar();
    if (entradas != NULL) { vQueueDelete(entradas); entradas = NULL; }
    if (bloqueo_control != NULL) { vSemaphoreDelete(bloqueo_control); bloqueo_control = NULL; }
    return resultado;
}
