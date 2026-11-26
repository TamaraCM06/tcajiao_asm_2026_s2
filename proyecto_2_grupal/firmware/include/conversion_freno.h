#ifndef ASM_CONVERSION_FRENO_H
#define ASM_CONVERSION_FRENO_H

#include "hardware.h"

/* Convierte grados calibrados a microsegundos; rechaza valores fuera de rango. */
bool freno_convertir_pulso(const configuracion_hardware_t *parametros,
    double angulo_deg, uint32_t *pulso_us);


#endif
