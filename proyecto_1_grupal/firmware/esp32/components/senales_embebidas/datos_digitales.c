#include "datos_digitales.h"
#include <stdint.h>

extern const unsigned char caso_1_inicio[] asm("_binary_caso_1_f32_start");
extern const unsigned char caso_1_fin[] asm("_binary_caso_1_f32_end");
extern const unsigned char caso_2_inicio[] asm("_binary_caso_2_f32_start");
extern const unsigned char caso_2_fin[] asm("_binary_caso_2_f32_end");
extern const unsigned char caso_3_inicio[] asm("_binary_caso_3_f32_start");
extern const unsigned char caso_3_fin[] asm("_binary_caso_3_f32_end");
_Static_assert(sizeof(float) == 4, "Los datos requieren float32");

/* Verifica que las dos representaciones del caso tengan igual cantidad de muestras. */
bool datos_digitales_obtener(senal_embebida_id_t identificador, datos_digitales_t *datos)
{
    const unsigned char *inicios[] = {caso_1_inicio, caso_2_inicio, caso_3_inicio};
    const unsigned char *finales[] = {caso_1_fin, caso_2_fin, caso_3_fin};
    const senal_embebida_t *senal = senales_embebidas_obtener(identificador);
    if (!datos || !senal || (unsigned)identificador >= 3) return false;
    size_t bytes = (uintptr_t)finales[identificador] - (uintptr_t)inicios[identificador];
    if (bytes != senal->cantidad_muestras * 2 * sizeof(float)) return false;
    *datos = (datos_digitales_t){inicios[identificador], senal->cantidad_muestras};
    return true;
}

