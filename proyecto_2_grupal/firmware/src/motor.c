#include "motor.h"
#include "driver/gpio.h"
#include "driver/ledc.h"
#include <math.h>

static configuracion_hardware_t limites;
static bool inicializado;
static double impulso_porcentaje;
static int64_t inicio_impulso_us;

/* Prepara direccion y PWM independiente, manteniendo el puente deshabilitado. */
esp_err_t motor_iniciar(const configuracion_hardware_t *parametros)
{
    limites = *parametros;
    gpio_config_t salidas = {.pin_bit_mask = (1ULL << parametros->motor_enable_gpio) |
        (1ULL << parametros->motor_entrada1_gpio) | (1ULL << parametros->motor_entrada2_gpio),
        .mode = GPIO_MODE_OUTPUT};
    esp_err_t resultado = gpio_config(&salidas);
    if (resultado != ESP_OK) return resultado;
    gpio_set_level(parametros->motor_enable_gpio, 0);
    gpio_set_level(parametros->motor_entrada1_gpio, 0);
    gpio_set_level(parametros->motor_entrada2_gpio, 0);
    ledc_timer_config_t temporizador = {.speed_mode = LEDC_LOW_SPEED_MODE,
        .timer_num = LEDC_TIMER_1, .duty_resolution = LEDC_TIMER_12_BIT,
        .freq_hz = parametros->motor_frecuencia_hz, .clk_cfg = LEDC_USE_APB_CLK};
    resultado = ledc_timer_config(&temporizador);
    if (resultado != ESP_OK) return resultado;
    ledc_channel_config_t canal = {.gpio_num = parametros->motor_enable_gpio,
        .speed_mode = LEDC_LOW_SPEED_MODE, .channel = LEDC_CHANNEL_1,
        .timer_sel = LEDC_TIMER_1, .duty = 0, .hpoint = 0};
    resultado = ledc_channel_config(&canal);
    inicializado = resultado == ESP_OK;
    return resultado;
}

/* Conserva el inicio del impulso continuo aunque el operador cambie su porcentaje. */
esp_err_t motor_ordenar(double porcentaje, int64_t tiempo_us)
{
    if (!inicializado) return ESP_ERR_INVALID_STATE;
    if (!isfinite(porcentaje) || porcentaje < 0 || porcentaje > limites.motor_maximo_porcentaje)
        return ESP_ERR_INVALID_ARG;
    if (porcentaje > 0) {
        esp_err_t resultado = gpio_set_level(limites.motor_entrada1_gpio, 1);
        if (resultado == ESP_OK) resultado = gpio_set_level(limites.motor_entrada2_gpio, 0);
        if (resultado != ESP_OK) return resultado;
    }
    uint32_t duty = (uint32_t)lround(porcentaje * 4095.0 / 100.0);
    esp_err_t resultado = ledc_set_duty_and_update(LEDC_LOW_SPEED_MODE, LEDC_CHANNEL_1, duty, 0);
    if (resultado != ESP_OK) {
        ledc_stop(LEDC_LOW_SPEED_MODE, LEDC_CHANNEL_1, 0);
        gpio_set_level(limites.motor_entrada1_gpio, 0);
        gpio_set_level(limites.motor_entrada2_gpio, 0);
        impulso_porcentaje = 0;
        inicializado = false;
        return resultado;
    }
    if (porcentaje == 0) {
        gpio_set_level(limites.motor_entrada1_gpio, 0);
        gpio_set_level(limites.motor_entrada2_gpio, 0);
    } else if (impulso_porcentaje == 0) {
        inicio_impulso_us = tiempo_us;
    }
    impulso_porcentaje = porcentaje;
    return ESP_OK;
}

/* Limita el tiempo de motor incluso sin conexion con la computadora. */
bool motor_vigilar(int64_t tiempo_us)
{
    if (inicializado && impulso_porcentaje > 0 &&
        tiempo_us - inicio_impulso_us >= (int64_t)limites.motor_maximo_impulso_ms * 1000) {
        motor_ordenar(0, tiempo_us);
        return true;
    }
    return false;
}

/* Informa el mando aplicado para estado y metadatos. */
double motor_porcentaje(void)
{
    return impulso_porcentaje;
}
