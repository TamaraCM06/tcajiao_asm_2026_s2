#ifndef ASM_CONVERSION_FRENO_H
#define ASM_CONVERSION_FRENO_H

#include "hardware.h"

/* Convierte grados calibrados a microsegundos; rechaza valores fuera de rango. */
bool freno_convertir_pulso(const configuracion_hardware_t *parametros,
    double angulo_deg, uint32_t *pulso_us);

/* Inversa lineal de la calibracion: grados equivalentes a un pulso (puede salir del rango). */
double freno_grados_de_pulso(const configuracion_hardware_t *parametros, uint32_t pulso_us);

/* Indica si el pulso queda dentro del recorrido calibrado, en cualquier sentido. */
bool freno_pulso_admitido(const configuracion_hardware_t *parametros, uint32_t pulso_us);

#endif
