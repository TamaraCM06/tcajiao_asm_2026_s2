#include "servo_freno.h"
#include "conversion_freno.h"
#include "driver/ledc.h"
#include <math.h>

static configuracion_hardware_t calibracion;
static bool inicializado;
static double angulo_ordenado_deg = NAN;

/* Usa un temporizador exclusivo para no cambiar la frecuencia del motor. */
esp_err_t servo_freno_iniciar(const configuracion_hardware_t *parametros)
{
    calibracion = *parametros;
    ledc_timer_config_t temporizador = {.speed_mode = LEDC_LOW_SPEED_MODE,
        .timer_num = LEDC_TIMER_0, .duty_resolution = LEDC_TIMER_16_BIT,
        .freq_hz = parametros->servo_frecuencia_hz, .clk_cfg = LEDC_USE_APB_CLK};
    esp_err_t resultado = ledc_timer_config(&temporizador);
    if (resultado != ESP_OK) return resultado;
    ledc_channel_config_t canal = {.gpio_num = parametros->servo_gpio,
        .speed_mode = LEDC_LOW_SPEED_MODE, .channel = LEDC_CHANNEL_0,
        .timer_sel = LEDC_TIMER_0, .duty = 0, .hpoint = 0};
    resultado = ledc_channel_config(&canal);
    inicializado = resultado == ESP_OK;
    return resultado;
}

/* Rechaza ordenes fuera del intervalo validado, sin saturarlas silenciosamente. */
esp_err_t servo_freno_ordenar(double angulo_deg)
{
    uint32_t pulso_us;
    if (!inicializado) return ESP_ERR_INVALID_STATE;
    if (!freno_convertir_pulso(&calibracion, angulo_deg, &pulso_us)) return ESP_ERR_INVALID_ARG;
    uint32_t duty = (uint32_t)llround((double)pulso_us * calibracion.servo_frecuencia_hz * 65536.0 / 1000000.0);
    esp_err_t resultado = ledc_set_duty_and_update(LEDC_LOW_SPEED_MODE, LEDC_CHANNEL_0, duty, 0);
    if (resultado == ESP_OK) angulo_ordenado_deg = angulo_deg;
    return resultado;
}

/* Expone la orden logica, no una lectura de posicion del MG90S. */
double servo_freno_angulo(void)
{
    return angulo_ordenado_deg;
}

/* Comprueba liberacion comandada antes de permitir impulsar el disco. */
bool servo_freno_liberado(void)
{
    return inicializado && isfinite(angulo_ordenado_deg) &&
        fabs(angulo_ordenado_deg - calibracion.servo_liberado_deg) < 0.0001;
}
