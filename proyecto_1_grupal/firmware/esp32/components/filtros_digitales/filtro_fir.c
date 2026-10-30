#include "filtro_fir.h"
#include <string.h>

/* Reinicia el anillo sin reservar memoria durante el procesamiento. */
void filtro_fir_reiniciar(filtro_fir_t *estado)
{
    memset(estado, 0, sizeof(*estado));
}

/* Evalua la convolucion causal; la muestra actual multiplica el primer coeficiente. */
float filtro_fir_muestra(filtro_fir_t *estado, const float *coeficientes, float entrada)
{
    estado->historia[estado->posicion] = entrada;
    size_t posicion_historia = estado->posicion;
    float salida = 0.0f;
    for (size_t coeficiente = 0; coeficiente < FIR_COEFICIENTES; ++coeficiente) {
        salida += coeficientes[coeficiente] * estado->historia[posicion_historia];
        posicion_historia = posicion_historia == 0 ? FIR_COEFICIENTES - 1 : posicion_historia - 1;
    }
    estado->posicion = (estado->posicion + 1) % FIR_COEFICIENTES;
    return salida;
}
