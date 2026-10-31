#include "senales_embebidas.h"

/* Los descriptores y sus arreglos se exportan desde los CSV; no hay generación matemática C. */
extern const senal_embebida_t DATOS_CASO_1;
extern const senal_embebida_t DATOS_CASO_2;
extern const senal_embebida_t DATOS_CASO_3;

/* Mantiene visibles las tres opciones sin copiar el registro completo a RAM. */
const senal_embebida_t *senales_embebidas_obtener(senal_embebida_id_t identificador)
{
    switch (identificador) {
        case SENAL_CASO_1:
            return &DATOS_CASO_1;
        case SENAL_CASO_2:
            return &DATOS_CASO_2;
        case SENAL_CASO_3:
            return &DATOS_CASO_3;
        default:
            return NULL;
    }
}
