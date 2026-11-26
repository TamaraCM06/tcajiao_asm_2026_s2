#ifndef ASM_HARDWARE_H
#define ASM_HARDWARE_H

#include <stdbool.h>
#include <stdint.h>

typedef struct {
    int sensor_gpio;
    bool flanco_bajada;
    uint32_t pulsos_por_vuelta;
    uint32_t intervalo_minimo_pulso_us;
    uint32_t ventana_pulsos;
    int servo_gpio;
    int servo_frecuencia_hz;
    int servo_minimo_deg;
    int servo_maximo_deg;
    int servo_liberado_deg;
    int servo_pulso_minimo_us;
    int servo_pulso_maximo_us;
    int motor_enable_gpio;
    int motor_entrada1_gpio;
    int motor_entrada2_gpio;
    int motor_frecuencia_hz;
    int motor_maximo_porcentaje;
    int motor_maximo_impulso_ms;
} configuracion_hardware_t;

/* Carga los parametros compilados; no configura ni activa ningun GPIO. */
configuracion_hardware_t hardware_cargar(void);

/* Rechaza pines reservados, repetidos y calibraciones incompletas. */
const char *hardware_validar(const configuracion_hardware_t *parametros);

#endif
