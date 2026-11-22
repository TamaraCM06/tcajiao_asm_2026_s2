#ifndef ASM_SENSOR_OPTICO_H
#define ASM_SENSOR_OPTICO_H

#include "hardware.h"
#include "estimador_velocidad.h"
#include "esp_err.h"

/* Inicializa una entrada digital sin resistencias internas y un solo flanco. */
esp_err_t sensor_optico_iniciar(const configuracion_hardware_t *parametros);

/* Cambia el timeout con la adquisicion detenida e invalida el historial anterior. */
void sensor_optico_configurar_timeout(int64_t timeout_us);

/* Obtiene una instantanea protegida frente a la interrupcion de pulsos. */
lectura_velocidad_t sensor_optico_leer(void);

#endif
