#ifndef ASM_COMANDOS_H
#define ASM_COMANDOS_H

#include <stdbool.h>
#include <stdint.h>

#define COMANDO_LONGITUD_MAXIMA 128
typedef enum { COMANDO_INVALIDO, COMANDO_CONFIG_CONSULTA, COMANDO_CONFIG,
    COMANDO_MOTOR, COMANDO_FRENO, COMANDO_STOP, COMANDO_STATUS, COMANDO_ENSAYO } tipo_comando_t;
typedef struct { tipo_comando_t tipo; double valores[3]; } comando_t;
typedef struct { uint32_t periodo_ms; uint32_t duracion_ms; uint32_t timeout_ms; } configuracion_ensayo_t;

/* Reconoce comandos completos y numeros finitos, sin aceptar texto sobrante. */
comando_t comando_interpretar(const char *linea);

/* Valida limites de transporte y tiempos enteros antes de aplicar CONFIG. */
bool comando_configuracion(const comando_t *comando, uint32_t minimo_pulso_us,
    configuracion_ensayo_t *parametros);

#endif
