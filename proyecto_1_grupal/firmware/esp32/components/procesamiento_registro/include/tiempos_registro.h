/** Estadisticas y marcas digitales acotadas; todos los instantes usan el mismo reloj. */
#pragma once
#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

typedef int64_t (*registro_reloj_t)(void *contexto);
typedef struct { uint64_t cantidad, total_us, maximo_us; } tiempo_acumulado_t;
typedef struct {
    size_t indice;
    int64_t recepcion_us;
    bool valida;
} marca_bloque_t;
typedef struct {
    registro_reloj_t reloj;
    void *contexto;
    tiempo_acumulado_t fir, espectral, evaluacion, publicacion;
    tiempo_acumulado_t cola, latencia, arranque, cierre;
    marca_bloque_t pendientes[16];
    bool en_cierre;
} tiempos_registro_t;

/** Lee el reloj opcional; sin instrumentacion devuelve cero. */
int64_t tiempos_ahora(const tiempos_registro_t *estado);
/** Acumula una duracion no negativa sin guardar historial. */
void tiempo_acumular(tiempo_acumulado_t *estado, int64_t duracion_us);
/** Conserva llegada por indice de entrada y mide su espera hasta el consumidor. */
bool tiempos_recibir(tiempos_registro_t *estado, size_t indice, int64_t recepcion_us);
/** Cierra las marcas de los bloques publicados; no estima tiempos analogicos. */
void tiempos_publicar(tiempos_registro_t *estado, size_t indice, size_t cantidad, int64_t instante_us);
