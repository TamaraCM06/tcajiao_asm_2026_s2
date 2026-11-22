#ifndef PRUEBA_GPIO_H
#define PRUEBA_GPIO_H
#include <stdint.h>
#include "esp_err.h"
#define GPIO_MODE_OUTPUT 1
typedef struct { uint64_t pin_bit_mask; int mode; } gpio_config_t;
/* Registra configuracion de salidas en los ensayos de actuadores. */
esp_err_t gpio_config(const gpio_config_t *parametros);
/* Registra nivel logico sin accionar hardware. */
esp_err_t gpio_set_level(int numero_gpio, unsigned nivel);
#define GPIO_IS_VALID_GPIO(numero) ((numero) >= 0 && (numero) <= 39 && (numero) != 20 && (numero) != 24 && ((numero) < 28 || (numero) > 31))
#define GPIO_IS_VALID_OUTPUT_GPIO(numero) (GPIO_IS_VALID_GPIO(numero) && (numero) < 34)
#endif
