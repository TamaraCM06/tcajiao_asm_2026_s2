#ifndef ASM_SERVO_FRENO_H
#define ASM_SERVO_FRENO_H

#include "hardware.h"
#include "esp_err.h"

/* Prepara PWM con duty cero; no ordena una posicion al arrancar. */
esp_err_t servo_freno_iniciar(const configuracion_hardware_t *parametros);

/* Aplica un angulo calibrado y conserva la orden solo si el controlador la acepta. */
esp_err_t servo_freno_ordenar(double angulo_deg);

/* Devuelve el angulo ordenado o NaN si aun no se ha enviado una posicion. */
double servo_freno_angulo(void);

/* Indica que se ordeno la posicion liberada; no confirma una posicion mecanica medida. */
bool servo_freno_liberado(void);

#endif
