#include "tiempos_registro.h"

/** Evita dependencias ESP-IDF en el nucleo portable. */
int64_t tiempos_ahora(const tiempos_registro_t *estado)
{
    return estado->reloj ? estado->reloj(estado->contexto) : 0;
}
/** Los contadores se reinician junto con el registro. */
void tiempo_acumular(tiempo_acumulado_t *estado, int64_t duracion_us)
{
    if (duracion_us < 0) return;
    ++estado->cantidad;
    estado->total_us += (uint64_t)duracion_us;
    if ((uint64_t)duracion_us > estado->maximo_us) estado->maximo_us = (uint64_t)duracion_us;
}
/** Rechaza sobrescrituras y marcas futuras en lugar de inventar latencias. */
bool tiempos_recibir(tiempos_registro_t *estado, size_t indice, int64_t recepcion_us)
{
    if (!estado->reloj) return true;
    marca_bloque_t *marca = &estado->pendientes[(indice / 256) % 16];
    const int64_t ahora = tiempos_ahora(estado);
    if (indice % 256 || marca->valida || recepcion_us < 0 || recepcion_us > ahora) return false;
    *marca = (marca_bloque_t){indice, recepcion_us, true};
    tiempo_acumular(&estado->cola, ahora - recepcion_us);
    return true;
}
/** La publicacion termina al aceptar UART el paquete, no al llegar a la computadora. */
void tiempos_publicar(tiempos_registro_t *estado, size_t indice, size_t cantidad, int64_t instante_us)
{
    if (!estado->reloj) return;
    for (size_t desplazamiento = 0; desplazamiento < cantidad; desplazamiento += 256) {
        const size_t bloque = indice + desplazamiento;
        marca_bloque_t *marca = &estado->pendientes[(bloque / 256) % 16];
        if (!marca->valida || marca->indice != bloque) continue;
        const int64_t duracion = instante_us - marca->recepcion_us;
        if (estado->en_cierre) tiempo_acumular(&estado->cierre, duracion);
        else if (indice == 0) tiempo_acumular(&estado->arranque, duracion);
        else tiempo_acumular(&estado->latencia, duracion);
        marca->valida = false;
    }
}
