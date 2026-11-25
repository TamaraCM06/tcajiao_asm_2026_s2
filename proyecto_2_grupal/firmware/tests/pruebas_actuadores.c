#include "motor.h"
#include "servo_freno.h"
#include "driver/gpio.h"
#include "driver/ledc.h"
#include <assert.h>
#include <math.h>
#include <string.h>

static uint32_t orden_pwm[2];
static unsigned frecuencias[2];
static unsigned niveles[40];
static bool fallar_pwm;

/* Acepta configuracion de salidas sin aplicarla a una placa. */
esp_err_t gpio_config(const gpio_config_t *parametros) { (void)parametros; return ESP_OK; }
/* Conserva niveles para comprobar la deshabilitacion del puente. */
esp_err_t gpio_set_level(int numero_gpio, unsigned nivel) { niveles[numero_gpio] = nivel; return ESP_OK; }
/* Conserva frecuencias para detectar colisiones de temporizadores. */
esp_err_t ledc_timer_config(const ledc_timer_config_t *parametros)
{ frecuencias[parametros->timer_num] = parametros->freq_hz; return ESP_OK; }
/* Conserva duty inicial para comprobar arranque sin movimiento. */
esp_err_t ledc_channel_config(const ledc_channel_config_t *parametros)
{ orden_pwm[parametros->channel] = parametros->duty; return ESP_OK; }
/* Inyecta fallo o registra el duty solicitado por el controlador original. */
esp_err_t ledc_set_duty_and_update(int modo, int canal, uint32_t duty, uint32_t punto)
{ (void)modo; (void)punto; if (fallar_pwm) return ESP_FAIL; orden_pwm[canal] = duty; return ESP_OK; }
/* Registra la via alternativa de corte ante un fallo de actualizacion. */
esp_err_t ledc_stop(int modo, int canal, uint32_t nivel)
{ (void)modo; assert(nivel == 0); orden_pwm[canal] = 0; return ESP_OK; }

/* Ejecuta los controladores de produccion contra fronteras de GPIO y PWM simuladas. */
int main(int cantidad_argumentos, char **argumentos)
{
    assert(cantidad_argumentos == 2);
    configuracion_hardware_t parametros = {.servo_gpio = 18, .servo_frecuencia_hz = 50,
        .servo_minimo_deg = 10, .servo_maximo_deg = 90, .servo_liberado_deg = 10,
        .servo_pulso_minimo_us = 1000, .servo_pulso_maximo_us = 1800,
        .motor_enable_gpio = 19, .motor_entrada1_gpio = 21, .motor_entrada2_gpio = 22,
        .motor_frecuencia_hz = 1000, .motor_maximo_porcentaje = 30, .motor_maximo_impulso_ms = 2000};
    assert(motor_iniciar(&parametros) == ESP_OK);
    assert(servo_freno_iniciar(&parametros) == ESP_OK);
    if (!strcmp(argumentos[1], "arranque")) {
        assert(orden_pwm[0] == 0 && orden_pwm[1] == 0 && isnan(servo_freno_angulo()));
        assert(frecuencias[0] == 50 && frecuencias[1] == 1000);
    } else if (!strcmp(argumentos[1], "limite_impulso")) {
        assert(motor_ordenar(20, 1000000) == ESP_OK);
        assert(motor_ordenar(25, 1500000) == ESP_OK);
        assert(!motor_vigilar(2999999));
        assert(motor_vigilar(3000000));
        assert(motor_porcentaje() == 0 && orden_pwm[1] == 0 && niveles[21] == 0 && niveles[22] == 0);
    } else if (!strcmp(argumentos[1], "limites")) {
        assert(motor_ordenar(31, 0) == ESP_ERR_INVALID_ARG && orden_pwm[1] == 0);
        assert(motor_ordenar(NAN, 0) == ESP_ERR_INVALID_ARG);
        assert(servo_freno_ordenar(181) == ESP_ERR_INVALID_ARG && orden_pwm[0] == 0);
        assert(servo_freno_ordenar(50) == ESP_OK && orden_pwm[0] == 4588);
        assert(!servo_freno_liberado());
        assert(servo_freno_ordenar(10) == ESP_OK && servo_freno_liberado());
    } else if (!strcmp(argumentos[1], "pulso_directo")) {
        assert(servo_freno_ordenar_pulso(999) == ESP_ERR_INVALID_ARG && orden_pwm[0] == 0);
        assert(servo_freno_ordenar_pulso(1801) == ESP_ERR_INVALID_ARG && servo_freno_pulso() == 0);
        assert(servo_freno_ordenar_pulso(1400) == ESP_OK && orden_pwm[0] == 4588);
        assert(servo_freno_pulso() == 1400 && isnan(servo_freno_angulo()) && !servo_freno_liberado());
        assert(servo_freno_apagar() == ESP_OK && orden_pwm[0] == 0 && servo_freno_pulso() == 0);
        assert(servo_freno_ordenar(10) == ESP_OK && servo_freno_pulso() == 1000 && servo_freno_liberado());
    } else if (!strcmp(argumentos[1], "fallo_pwm")) {
        assert(motor_ordenar(20, 0) == ESP_OK && orden_pwm[1] > 0);
        fallar_pwm = true;
        assert(motor_ordenar(0, 100) == ESP_FAIL);
        assert(orden_pwm[1] == 0 && motor_porcentaje() == 0);
        assert(motor_ordenar(20, 200) == ESP_ERR_INVALID_STATE);
    } else return 2;
    return 0;
}
