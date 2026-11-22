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
