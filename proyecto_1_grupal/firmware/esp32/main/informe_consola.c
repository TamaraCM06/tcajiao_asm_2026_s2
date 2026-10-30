#include "informe_consola.h"
#include "esp_log.h"
#include <inttypes.h>
#include <stdio.h>

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

/* Compara las metricas de los seis resultados sobre el mismo intervalo de referencia. */
static void imprimir_tabla_calidad(const informe_resultado_t *resultados, size_t cantidad_resultados)
{
    printf("\nCALIDAD DIGITAL: SNR, mejora, atenuacion y distorsion en dB; util en %%\n");
    printf("| Caso   | Metodo    | SNR ent  | SNR sal  | Mejora   | MSE        | Util %%    | Aten dB  | Dist dB  |\n");
    printf("|--------|-----------|----------|----------|----------|------------|-----------|----------|----------|\n");
    for (size_t indice_resultado = 0; indice_resultado < cantidad_resultados; ++indice_resultado) {
        const informe_resultado_t *fila = &resultados[indice_resultado];
        metricas_resultado_t medidas = metricas_finalizar(&fila->resultado.metricas);
        printf("| %-6s | %-9s | %8.4f | %8.4f | %8.4f | %10.3e | %9.4f | %8.4f | %8.4f |\n",
            fila->caso, fila->metodo, medidas.snr_entrada_db, medidas.snr_salida_db,
            medidas.mejora_snr_db, medidas.mse, medidas.energia_util_pct,
            medidas.atenuacion_ruido_db, medidas.distorsion_util_db);
    }
}

/* Separa tiempos por bloque de calculo acumulado y duracion total de cada evaluacion. */
static void imprimir_tabla_costos(const informe_resultado_t *resultados, size_t cantidad_resultados)
{
    printf("\nTIEMPOS: media, maximo y presupuesto por bloque en ms; calculo y total en s\n");
    printf("| Caso   | Metodo    | Evaluadas | Media ms | Max ms   | Pres ms | Cumple | Calculo s | Total s  |\n");
    printf("|--------|-----------|-----------|----------|----------|---------|--------|-----------|----------|\n");
    for (size_t indice_resultado = 0; indice_resultado < cantidad_resultados; ++indice_resultado) {
        const informe_resultado_t *fila = &resultados[indice_resultado];
        const banco_resultado_t *resultado = &fila->resultado;
        double media_ms = resultado->bloques ?
            (double)resultado->tiempo_total_us / resultado->bloques / 1000.0 : 0;
        printf("| %-6s | %-9s | %9u | %8.3f | %8.3f | %7.3f | %-6s | %9.3f | %8.3f |\n",
            fila->caso, fila->metodo, (unsigned)resultado->metricas.muestras, media_ms,
            resultado->tiempo_maximo_us / 1000.0, fila->presupuesto_us / 1000.0,
            resultado->tiempo_maximo_us <= fila->presupuesto_us ? "SI" : "NO",
            resultado->tiempo_total_us / 1000000.0, resultado->tiempo_pared_us / 1000000.0);
    }
}

/* Publica tablas compactas sin prefijos de log que desplacen sus columnas. */
void informe_consola_publicar_resumen(const informe_resultado_t *resultados,
                                    size_t cantidad_resultados)
{
    if (!resultados || cantidad_resultados == 0) return;
    printf("\n================ RESUMEN FINAL ================\n");
    printf("Comparacion comun: %u muestras evaluadas por metodo.\n",
        (unsigned)resultados[0].resultado.metricas.muestras);
    imprimir_tabla_calidad(resultados, cantidad_resultados);
    imprimir_tabla_costos(resultados, cantidad_resultados);
    printf("===============================================\n\n");
}
