#include "reloj_registro.h"
#include <string.h>

/* Inicia una serie independiente con primer indice aun no registrado. */
void reloj_registro_iniciar(reloj_registro_t *reloj, int64_t inicio_us)
{
    memset(reloj, 0, sizeof(*reloj));
    reloj->inicio_us = inicio_us;
    reloj->ultimo_indice = -1;
}

/* Usa el tiempo observado, aunque el callback haya llegado con retraso. */
bool reloj_registro_muestrear(reloj_registro_t *reloj, int64_t tiempo_us, uint32_t periodo_ms)
{
    if (!periodo_ms || tiempo_us < reloj->inicio_us) return false;
    int64_t indice = (tiempo_us - reloj->inicio_us) / ((int64_t)periodo_ms * 1000);
    if (indice <= reloj->ultimo_indice) return false;
    reloj->vencimientos_perdidos += (uint32_t)(indice - reloj->ultimo_indice - 1);
    if (reloj->muestras_producidas) {
        int64_t intervalo = tiempo_us - reloj->ultima_muestra_us;
        if (!reloj->intervalo_minimo_us || intervalo < reloj->intervalo_minimo_us)
            reloj->intervalo_minimo_us = intervalo;
        if (intervalo > reloj->intervalo_maximo_us) reloj->intervalo_maximo_us = intervalo;
    }
    reloj->ultima_muestra_us = tiempo_us;
    reloj->ultimo_indice = indice;
    ++reloj->muestras_producidas;
    return true;
}
