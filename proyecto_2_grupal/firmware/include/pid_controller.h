#ifndef PID_CONTROLLER_H
#define PID_CONTROLLER_H

#include <stdbool.h>

/* PID discreto de posicion con periodo fijo Ts.
 * Convencion del banco: e = omega - omega_ref. Un disco mas rapido que la
 * referencia (e > 0) aumenta el mando del freno u, normalizado en [u_min, u_max].
 * No depende del Pico SDK: se compila igual en la placa y en las pruebas del PC. */
typedef struct {
    float kp, ki, kd;     /* Ganancias en unidades de u por rad/s */
    float ts;             /* Periodo de muestreo de diseno [s] */
    float tf;             /* Constante del filtro del derivativo [s] */
    float u_min, u_max;   /* Limites fisicos calibrados del freno */
    bool anti_windup;     /* Integracion condicional (clamping) */

    float integral;       /* Estado del termino integral, ya multiplicado por Ki */
    float derivada;       /* Estado del derivativo filtrado */
    float omega_previa;
    bool primera;
    bool saturado;        /* Ultimo mando quedo recortado */
} pid_controlador_t;

void pid_iniciar(pid_controlador_t *pid, float kp, float ki, float kd, float ts,
                 float tf, float u_min, float u_max, bool anti_windup);

/* Borra los estados; se llama al empezar cada frenado. */
void pid_reiniciar(pid_controlador_t *pid);

/* Un paso de control: recibe referencia y medicion de la muestra k y
 * devuelve el mando saturado que se aplica hasta la muestra k + 1 (ZOH). */
float pid_paso(pid_controlador_t *pid, float omega_ref, float omega);

#endif
