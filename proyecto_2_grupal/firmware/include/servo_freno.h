#ifndef ASM_SERVO_FRENO_H
#define ASM_SERVO_FRENO_H

#include "hardware.h"
#include "esp_err.h"

/* Prepara PWM con duty cero; no ordena una posicion al arrancar. */
esp_err_t servo_freno_iniciar(const configuracion_hardware_t *parametros);

/* Aplica un angulo calibrado y conserva la orden solo si el controlador la acepta. */
esp_err_t servo_freno_ordenar(double angulo_deg);

/* Calibracion: ordena un pulso dentro del recorrido calibrado; el angulo queda sin definir. */
esp_err_t servo_freno_ordenar_pulso(uint32_t pulso_us);

/* Ultimo pulso ordenado en microsegundos, 0 si no hay orden o el PWM esta apagado. */
uint32_t servo_freno_pulso(void);

/* Detiene los pulsos (el servo deja de hacer fuerza); se usa por inactividad en calibracion. */
esp_err_t servo_freno_apagar(void);

/* Devuelve el angulo ordenado o NaN si aun no se ha enviado una posicion. */
double servo_freno_angulo(void);

/* Indica que se ordeno la posicion liberada; no confirma una posicion mecanica medida. */
bool servo_freno_liberado(void);

#endif
