#include "sensor_optico.h"
#include "driver/gpio.h"
#include "esp_timer.h"
#include "freertos/FreeRTOS.h"

static portMUX_TYPE proteccion_sensor = portMUX_INITIALIZER_UNLOCKED;
static estimador_velocidad_t estimador;
static uint32_t pulsos_por_vuelta;
static uint32_t ventana_pulsos;
static uint32_t intervalo_minimo_us;
static int64_t tiempo_sin_pulsos_us;

/* Registra un flanco con tiempo monotono; no transmite ni calcula en coma flotante. */
static void registrar_flanco(void *argumento)
{
    (void)argumento;
    int64_t tiempo_us = esp_timer_get_time();
    portENTER_CRITICAL_ISR(&proteccion_sensor);
    estimador_registrar(&estimador, tiempo_us, intervalo_minimo_us, tiempo_sin_pulsos_us);
    portEXIT_CRITICAL_ISR(&proteccion_sensor);
}

/* Instala la interrupcion de un solo flanco para evitar contar dos veces cada marca. */
esp_err_t sensor_optico_iniciar(const configuracion_hardware_t *parametros)
{
    pulsos_por_vuelta = parametros->pulsos_por_vuelta;
    ventana_pulsos = parametros->ventana_pulsos;
    intervalo_minimo_us = parametros->intervalo_minimo_pulso_us;
    estimador_reiniciar(&estimador);
    gpio_config_t entrada = {.pin_bit_mask = 1ULL << parametros->sensor_gpio,
        .mode = GPIO_MODE_INPUT, .pull_up_en = GPIO_PULLUP_DISABLE,
        .pull_down_en = GPIO_PULLDOWN_DISABLE,
        .intr_type = parametros->flanco_bajada ? GPIO_INTR_NEGEDGE : GPIO_INTR_POSEDGE};
    esp_err_t resultado = gpio_config(&entrada);
    if (resultado != ESP_OK) return resultado;
    resultado = gpio_install_isr_service(0);
    if (resultado != ESP_OK) return resultado;
    return gpio_isr_handler_add(parametros->sensor_gpio, registrar_flanco, NULL);
}

/* Evita mezclar intervalos calculados con otra configuracion de parada. */
void sensor_optico_configurar_timeout(int64_t timeout_us)
{
    portENTER_CRITICAL(&proteccion_sensor);
    tiempo_sin_pulsos_us = timeout_us;
    estimador_reiniciar(&estimador);
    portEXIT_CRITICAL(&proteccion_sensor);
}

/* Copia estado atomico y realiza el calculo flotante fuera de la seccion critica. */
lectura_velocidad_t sensor_optico_leer(void)
{
    portENTER_CRITICAL(&proteccion_sensor);
    int64_t tiempo_us = esp_timer_get_time();
    estimador_velocidad_t copia_estimador = estimador;
    int64_t copia_timeout_us = tiempo_sin_pulsos_us;
    portEXIT_CRITICAL(&proteccion_sensor);
    return estimador_leer(&copia_estimador, tiempo_us, pulsos_por_vuelta, ventana_pulsos, copia_timeout_us);
}
