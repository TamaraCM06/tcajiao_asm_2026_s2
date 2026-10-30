#pragma once
#include <stdbool.h>
#include "senales_embebidas.h"

typedef struct {
    const unsigned char *pares_float32;
    size_t cantidad_muestras;
} datos_digitales_t;
extern const float COEFICIENTES_FIR[75];
/* Obtiene mezcla y referencia de flash y comprueba longitud contra el registro DAC. */
bool datos_digitales_obtener(senal_embebida_id_t identificador, datos_digitales_t *datos);
/* Lee un par sin asumir alineacion; los indices fuera del registro producen ceros. */
void datos_digitales_leer(const datos_digitales_t *datos, int indice, float *mezcla, float *referencia);
