#ifndef GENERADOR_SENALES_H
#define GENERADOR_SENALES_H

#include <stdbool.h>
#include <stddef.h>

#include "emisor_config.h"

enum { EMISOR_CANTIDAD_MAXIMA_COMPONENTES = EMISOR_CANTIDAD_MAXIMA_TONOS + 1 };

/* Estado independiente por instancia. Inicializar mediante emisor_inicializar()
 * antes de generar; el llamador no debe modificar sus campos durante la emisión.
 * Las fases e incrementos usan double; el buffer de salida contiene float. */
typedef struct {
    bool inicializado;
    size_t cantidad_componentes;
    double fases_iniciales_radianes[EMISOR_CANTIDAD_MAXIMA_COMPONENTES];
    double fases_actuales_radianes[EMISOR_CANTIDAD_MAXIMA_COMPONENTES];
    double incrementos_fase_radianes[EMISOR_CANTIDAD_MAXIMA_COMPONENTES];
    double amplitudes_escaladas[EMISOR_CANTIDAD_MAXIMA_COMPONENTES];
    double ganancia_comun;
    double amplitud_interferencia; /* Antes de aplicar ganancia_comun. */
} emisor_generador_t;

/* Contrato de errores: NULL indica éxito; cualquier otro valor es un mensaje estático. */

/* Valida la configuración y copia amplitudes/fases a un estado independiente.
 * La configuración no necesita seguir viva. Un fallo deshabilita el generador. */
const char *emisor_inicializar(emisor_generador_t *generador_senales,
                             const emisor_config_t *configuracion);

/* Escribe las muestras solicitadas y avanza las fases sin reservar memoria.
 * El buffer debe tener capacidad suficiente; cero muestras admite buffer NULL. */
const char *emisor_generar(emisor_generador_t *generador_senales,
                         float *muestras_salida, size_t cantidad_muestras);

/* Restaura las fases configuradas, sin cambiar amplitudes ni ganancia. */
const char *emisor_reiniciar(emisor_generador_t *generador_senales);

#endif
