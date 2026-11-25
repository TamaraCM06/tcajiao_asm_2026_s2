#include "conversion_freno.h"
#include <math.h>

/* Interpola solo dentro de la calibracion; admite que el sentido de pulsos sea inverso. */
bool freno_convertir_pulso(const configuracion_hardware_t *parametros,
    double angulo_deg, uint32_t *pulso_us)
{
    if (!isfinite(angulo_deg) || parametros->servo_minimo_deg < 0 ||
        parametros->servo_maximo_deg <= parametros->servo_minimo_deg ||
        parametros->servo_pulso_minimo_us <= 0 || parametros->servo_pulso_maximo_us <= 0 ||
        parametros->servo_pulso_minimo_us == parametros->servo_pulso_maximo_us ||
        angulo_deg < parametros->servo_minimo_deg || angulo_deg > parametros->servo_maximo_deg)
        return false;
    double proporcion = (angulo_deg - parametros->servo_minimo_deg) /
        (parametros->servo_maximo_deg - parametros->servo_minimo_deg);
    *pulso_us = (uint32_t)lround(parametros->servo_pulso_minimo_us + proporcion *
        (parametros->servo_pulso_maximo_us - parametros->servo_pulso_minimo_us));
    return true;
}

/* Recupera grados desde microsegundos con los mismos dos puntos de calibracion. */
double freno_grados_de_pulso(const configuracion_hardware_t *parametros, uint32_t pulso_us)
{
    return parametros->servo_minimo_deg + ((double)pulso_us - parametros->servo_pulso_minimo_us) *
        (parametros->servo_maximo_deg - parametros->servo_minimo_deg) /
        (parametros->servo_pulso_maximo_us - parametros->servo_pulso_minimo_us);
}

/* La ventana segura es el recorrido calibrado; ampliarla exige editar sdkconfig.defaults. */
bool freno_pulso_admitido(const configuracion_hardware_t *parametros, uint32_t pulso_us)
{
    int minimo = parametros->servo_pulso_minimo_us, maximo = parametros->servo_pulso_maximo_us;
    if (minimo > maximo) { int cambio = minimo; minimo = maximo; maximo = cambio; }
    return minimo > 0 && (int64_t)pulso_us >= minimo && (int64_t)pulso_us <= maximo;
}
