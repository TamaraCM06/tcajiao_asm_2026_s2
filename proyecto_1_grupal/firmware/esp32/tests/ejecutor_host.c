#include "banco_filtros.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>

/* El reloj del PC sirve al arnes, no se publica como rendimiento ESP32. */
static uint64_t reloj_host(void)
{
    return (uint64_t)clock() * 1000000 / CLOCKS_PER_SEC;
}

/* Guarda cada salida real del nucleo C para compararla contra Python. */
static void guardar_salida(size_t indice, float salida, float util, void *contexto)
{
    (void)indice;
    float par[] = {salida, util};
    if (fwrite(par, sizeof(float), 2, contexto) != 2) exit(5);
}

/* Carga un vector de prueba y ejecuta exactamente el banco usado por el firmware. */
int main(int cantidad_argumentos, char **argumentos)
{
    if (cantidad_argumentos != 6) return 2;
    FILE *entrada = fopen(argumentos[1], "rb");
    if (!entrada) return 3;
    fseek(entrada, 0, SEEK_END);
    long cantidad_bytes = ftell(entrada);
    rewind(entrada);
    if (cantidad_bytes <= 0 || cantidad_bytes % 8) return 3;
    unsigned char *contenido = malloc((size_t)cantidad_bytes);
    if (!contenido || fread(contenido, 1, (size_t)cantidad_bytes, entrada) != (size_t)cantidad_bytes) return 3;
    fclose(entrada);
    FILE *salidas = fopen(argumentos[2], "wb");
    if (!salidas) return 4;
    datos_digitales_t datos = {contenido, (size_t)cantidad_bytes / 8};
    banco_servicios_t servicios = {.reloj = reloj_host, .observar = guardar_salida, .contexto = salidas};
    banco_resultado_t resultado;
    espectral_configuracion_t configuracion = {1600, 100, strtof(argumentos[5], NULL), 0.05f};
    bool correcto = strcmp(argumentos[4], "fir") == 0 ? banco_evaluar_fir(&datos, &servicios, &resultado) :
        banco_evaluar_espectral(&datos, configuracion, &servicios, &resultado);
    fclose(salidas);
    free(contenido);
    if (!correcto) return 6;
    metricas_resultado_t medidas = metricas_finalizar(&resultado.metricas);
    FILE *resumen = fopen(argumentos[3], "w");
    if (!resumen) return 4;
    fprintf(resumen, "snr_entrada_dB,snr_salida_dB,delta_snr_dB,mse,energia_util_conservada_pct,atenuacion_ruido_dB,snr_distorsion_util_dB,muestras\n");
    fprintf(resumen, "%.17g,%.17g,%.17g,%.17g,%.17g,%.17g,%.17g,%lu\n",
        medidas.snr_entrada_db, medidas.snr_salida_db, medidas.mejora_snr_db, medidas.mse,
        medidas.energia_util_pct, medidas.atenuacion_ruido_db, medidas.distorsion_util_db,
        (unsigned long)resultado.metricas.muestras);
    fclose(resumen);
    return 0;
}
