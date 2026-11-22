#include "pid_controller.h"

static float recortar(float x, float minimo, float maximo)
{
    if (x < minimo) return minimo;
    if (x > maximo) return maximo;
    return x;
}

void pid_iniciar(pid_controlador_t *pid, float kp, float ki, float kd, float ts,
                 float tf, float u_min, float u_max, bool anti_windup)
{
    pid->kp = kp;
    pid->ki = ki;
    pid->kd = kd;
    pid->ts = ts;
    pid->tf = tf;
    pid->u_min = u_min;
    pid->u_max = u_max;
    pid->anti_windup = anti_windup;
    pid_reiniciar(pid);
}

void pid_reiniciar(pid_controlador_t *pid)
{
    pid->integral = 0.0f;
    pid->derivada = 0.0f;
    pid->omega_previa = 0.0f;
    pid->primera = true;
    pid->saturado = false;
}

float pid_paso(pid_controlador_t *pid, float omega_ref, float omega)
{
    const float e = omega - omega_ref;

    /* Derivativo sobre la medicion (sin salto por la referencia), filtrado con
     * Kd*s/(Tf*s + 1) discretizado por Euler hacia atras. */
    if (pid->primera) {
        pid->omega_previa = omega;
        pid->primera = false;
    }
    const float alfa = pid->tf / (pid->tf + pid->ts);
    pid->derivada = alfa * pid->derivada +
                    pid->kd / (pid->tf + pid->ts) * (omega - pid->omega_previa);
    pid->omega_previa = omega;

    const float p = pid->kp * e;
    const float u_sin_limite = p + pid->integral + pid->derivada;
    const float u = recortar(u_sin_limite, pid->u_min, pid->u_max);
    pid->saturado = (u != u_sin_limite);

    /* Clamping: no se integra si el mando ya esta en un limite y el error
     * empuja hacia ese mismo limite. Asi el integrador no acumula mientras
     * el freno no puede responder (actuador unilateral). */
    const bool empuja_arriba = (u_sin_limite > pid->u_max) && (e > 0.0f);
    const bool empuja_abajo = (u_sin_limite < pid->u_min) && (e < 0.0f);
    if (!pid->anti_windup || !(empuja_arriba || empuja_abajo)) {
        pid->integral += pid->ki * pid->ts * e;
    }
    return u;
}
