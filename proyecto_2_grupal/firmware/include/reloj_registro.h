#ifndef ASM_RELOJ_REGISTRO_H
#define ASM_RELOJ_REGISTRO_H

#include <stdbool.h>
#include <stdint.h>

typedef struct {
    int64_t inicio_us;
    int64_t ultima_muestra_us;
    int64_t ultimo_indice;
    int64_t intervalo_minimo_us;
    int64_t intervalo_maximo_us;
    uint32_t muestras_producidas;
    uint32_t vencimientos_perdidos;
} reloj_registro_t;

/* Fija el origen monotono de un ensayo sin conservar contadores anteriores. */
void reloj_registro_iniciar(reloj_registro_t *reloj, int64_t inicio_us);

/* Admite una muestra real por periodo; contabiliza huecos sin rellenarlos. */
bool reloj_registro_muestrear(reloj_registro_t *reloj, int64_t tiempo_us, uint32_t periodo_ms);

#endif
