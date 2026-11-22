#ifndef ASM_MOTOR_H
#define ASM_MOTOR_H

#include "hardware.h"
#include "esp_err.h"

/* Inicializa ENA deshabilitado y ambas entradas bajas, sin impulsar el disco. */
esp_err_t motor_iniciar(const configuracion_hardware_t *parametros);

/* Aplica impulso en un sentido; cero deshabilita ENA para marcha libre. */
esp_err_t motor_ordenar(double porcentaje, int64_t tiempo_us);

/* Corta el impulso al alcanzar el maximo continuo; no reinicia por cambiar duty. */
bool motor_vigilar(int64_t tiempo_us);

/* Devuelve la ultima orden de impulso aplicada correctamente. */
double motor_porcentaje(void);

#endif
