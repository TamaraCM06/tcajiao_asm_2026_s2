#include "estimador_velocidad.h"
#include <math.h>
#include <string.h>

/* Reinicia estado y contadores; hasta dos pulsos no hay un intervalo medido. */
void estimador_reiniciar(estimador_velocidad_t *estimador)
{
    memset(estimador, 0, sizeof(*estimador));
}

/* Acepta flancos monotonicamente crecientes y reinicia tras una pausa larga. */
void estimador_registrar(estimador_velocidad_t *estimador, int64_t tiempo_us,
    uint32_t intervalo_minimo_us, int64_t timeout_us)
{
    if (tiempo_us < 0) { ++estimador->pulsos_rechazados; return; }
    if (estimador->tiene_pulso) {
        int64_t intervalo_us = tiempo_us - estimador->ultimo_pulso_us;
        if (intervalo_us <= 0 || intervalo_us < intervalo_minimo_us) {
            ++estimador->pulsos_rechazados;
            return;
        }
        estimador->tiene_intervalo = timeout_us > 0 && intervalo_us < timeout_us;
        estimador->intervalo_us = intervalo_us;
    }
    estimador->tiene_pulso = true;
    estimador->ultimo_pulso_us = tiempo_us;
    ++estimador->pulsos_aceptados;
}

/* Devuelve NaN mientras falta informacion; conserva el ultimo intervalo hasta timeout. */
lectura_velocidad_t estimador_leer(const estimador_velocidad_t *estimador,
    int64_t tiempo_us, uint32_t pulsos_por_vuelta, int64_t timeout_us)
{
    lectura_velocidad_t lectura = {.estado = VELOCIDAD_ESPERANDO,
        .velocidad_rpm = NAN, .edad_pulso_us = -1,
        .pulsos_aceptados = estimador->pulsos_aceptados,
        .pulsos_rechazados = estimador->pulsos_rechazados};
    if (!estimador->tiene_pulso || tiempo_us < estimador->ultimo_pulso_us ||
        pulsos_por_vuelta == 0 || timeout_us <= 0) return lectura;
    lectura.edad_pulso_us = tiempo_us - estimador->ultimo_pulso_us;
    if (lectura.edad_pulso_us >= timeout_us) {
        lectura.estado = VELOCIDAD_SIN_PULSOS;
        lectura.velocidad_rpm = 0.0;
    } else if (estimador->tiene_intervalo && estimador->intervalo_us > 0) {
        lectura.estado = VELOCIDAD_VALIDA;
        lectura.velocidad_rpm = 60000000.0 / pulsos_por_vuelta / estimador->intervalo_us;
    }
    return lectura;
}
