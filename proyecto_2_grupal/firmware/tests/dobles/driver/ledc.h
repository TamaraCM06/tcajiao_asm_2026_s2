#ifndef PRUEBA_LEDC_H
#define PRUEBA_LEDC_H
#include <stdint.h>
#include "esp_err.h"
#define LEDC_LOW_SPEED_MODE 0
#define LEDC_TIMER_0 0
#define LEDC_TIMER_1 1
#define LEDC_CHANNEL_0 0
#define LEDC_CHANNEL_1 1
#define LEDC_TIMER_16_BIT 16
#define LEDC_TIMER_12_BIT 12
#define LEDC_USE_APB_CLK 0
typedef struct { int speed_mode; int timer_num; int duty_resolution; unsigned freq_hz; int clk_cfg; } ledc_timer_config_t;
typedef struct { int gpio_num; int speed_mode; int channel; int timer_sel; uint32_t duty; int hpoint; } ledc_channel_config_t;
/* Registra frecuencia y temporizador usados por el codigo original. */
esp_err_t ledc_timer_config(const ledc_timer_config_t *parametros);
/* Registra duty inicial sin generar PWM fisico. */
esp_err_t ledc_channel_config(const ledc_channel_config_t *parametros);
/* Registra duty o simula fallo del periferico. */
esp_err_t ledc_set_duty_and_update(int modo, int canal, uint32_t duty, uint32_t punto);
/* Simula salida PWM detenida en nivel bajo. */
esp_err_t ledc_stop(int modo, int canal, uint32_t nivel);
#endif
