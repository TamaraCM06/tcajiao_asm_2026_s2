#include "informe_consola.h"
#include "esp_log.h"
#include <inttypes.h>

/* Publica resumenes por registro sin logs dentro del procesamiento por bloques. */
void informe_consola_publicar(const char *caso, const char *metodo,
    const banco_resultado_t *resultado, unsigned presupuesto_us)
{
    metricas_resultado_t medidas = metricas_finalizar(&resultado->metricas);
    ESP_LOGI("resultados", "%s %s: evaluadas=%u; producidas=%u", caso, metodo,
        (unsigned)resultado->metricas.muestras, (unsigned)resultado->muestras_producidas);
    ESP_LOGI("resultados", "SNR entrada=%.4f dB; salida=%.4f dB; mejora=%.4f dB; MSE=%.9g",
        medidas.snr_entrada_db, medidas.snr_salida_db, medidas.mejora_snr_db, medidas.mse);
    ESP_LOGI("resultados", "Energia util=%.4f %%; atenuacion ruido total=%.4f dB; SNR distorsion=%.4f dB",
        medidas.energia_util_pct, medidas.atenuacion_ruido_db, medidas.distorsion_util_db);
    ESP_LOGI("resultados", "Calculo+referencia+metricas=%" PRIu64 " us; media=%.1f us/bloque; max=%" PRIu64
        " us; tiempo transcurrido=%" PRIu64 " us", resultado->tiempo_total_us,
        resultado->bloques ? (double)resultado->tiempo_total_us / resultado->bloques : 0,
        resultado->tiempo_maximo_us, resultado->tiempo_pared_us);
    ESP_LOGI("resultados", "Espacio estatico compartido=%u bytes (excluye pila/SDK/DMA); presupuesto=%u us; max compatible=%s",
        (unsigned)resultado->memoria_trabajo_bytes, presupuesto_us,
        resultado->tiempo_maximo_us <= presupuesto_us ? "SI" : "NO");
}
