#include "estimador_velocidad.h"
#include <math.h>
#include <string.h>

/* Reinicia estado y contadores; hasta dos pulsos no hay un intervalo medido. */
void estimador_reiniciar(estimador_velocidad_t *estimador)
{
    memset(estimador, 0, sizeof(*estimador));
}

/* Acepta flancos monotonicamente crecientes y reinicia la ventana tras una pausa larga. */
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
        if (estimador->tiene_intervalo) {
            estimador->intervalos_us[estimador->siguiente_intervalo] = intervalo_us;
            estimador->siguiente_intervalo = (estimador->siguiente_intervalo + 1) % ESTIMADOR_VENTANA_MAXIMA;
            if (estimador->cantidad_intervalos < ESTIMADOR_VENTANA_MAXIMA) ++estimador->cantidad_intervalos;
        } else {
            estimador->cantidad_intervalos = 0;
        }
    }
    estimador->tiene_pulso = true;
    estimador->ultimo_pulso_us = tiempo_us;
}

/* Devuelve NaN mientras falta informacion; conserva la ultima ventana hasta timeout. */
lectura_velocidad_t estimador_leer(const estimador_velocidad_t *estimador,
    int64_t tiempo_us, uint32_t pulsos_por_vuelta, uint32_t ventana, int64_t timeout_us)
{
    lectura_velocidad_t lectura = {.estado = VELOCIDAD_ESPERANDO,
        .tiempo_lectura_us = tiempo_us,
        .ultimo_pulso_us = estimador->tiene_pulso ? estimador->ultimo_pulso_us : -1,
        .velocidad_rpm = NAN,
        .pulsos_rechazados = estimador->pulsos_rechazados};
    if (!estimador->tiene_pulso || tiempo_us < estimador->ultimo_pulso_us ||
        pulsos_por_vuelta == 0 || timeout_us <= 0) return lectura;
    if (tiempo_us - estimador->ultimo_pulso_us >= timeout_us) {
        lectura.estado = VELOCIDAD_SIN_PULSOS;
        lectura.velocidad_rpm = 0.0;
        return lectura;
    }
    uint32_t cantidad = estimador->tiene_intervalo ? estimador->cantidad_intervalos : 0;
    if (ventana > ESTIMADOR_VENTANA_MAXIMA) ventana = ESTIMADOR_VENTANA_MAXIMA;
    if (cantidad > ventana) cantidad = ventana;
    if (cantidad == 0) return lectura;
    int64_t suma_us = 0;
    for (uint32_t indice = 1; indice <= cantidad; ++indice)
        suma_us += estimador->intervalos_us[(estimador->siguiente_intervalo + ESTIMADOR_VENTANA_MAXIMA - indice)
            % ESTIMADOR_VENTANA_MAXIMA];
    lectura.estado = VELOCIDAD_VALIDA;
    lectura.velocidad_rpm = 60000000.0 * cantidad / pulsos_por_vuelta / (double)suma_us;
    return lectura;
}
