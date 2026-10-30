#include "datos_digitales.h"
#include <string.h>

/* memcpy evita accesos float desalineados sobre simbolos binarios del enlazador. */
void datos_digitales_leer(const datos_digitales_t *datos, int indice, float *mezcla, float *referencia)
{
    *mezcla = 0;
    *referencia = 0;
    if (indice < 0 || (size_t)indice >= datos->cantidad_muestras) return;
    const unsigned char *par = datos->pares_float32 + (size_t)indice * 2 * sizeof(float);
    memcpy(mezcla, par, sizeof(float));
    memcpy(referencia, par + sizeof(float), sizeof(float));
}
