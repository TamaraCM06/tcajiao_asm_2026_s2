/** Ejecuta el mismo procesador finito en PC y exporta salidas y metricas. */
#include "procesamiento_registro.h"
#include <stdio.h>
#include <stdlib.h>
#include <inttypes.h>
static procesamiento_registro_t registro;
static int64_t instante_us;

/** Reloj determinista para verificar que el perfil no altera las salidas. */
static int64_t reloj_prueba(void *contexto)
{
    (void)contexto;
    instante_us += 10;
    return instante_us;
}

/** Publica ambos metodos intercalados para contrastarlos con Python. */
static bool publicar(size_t indice, size_t cantidad, const float *fir, const float *espectral, void *contexto)
{
    (void)indice;
    FILE *archivo = contexto;
    for (size_t posicion = 0; posicion < cantidad; ++posicion) {
        const float pareja[2] = {fir[posicion], espectral[posicion]};
        if (fwrite(pareja, sizeof(float), 2, archivo) != 2) return false;
    }
    return true;
}
/** Procesa parejas float32 hasta el final declarado; nunca usa los filtros Python. */
int main(int cantidad_argumentos, char **argumentos)
{
    if (cantidad_argumentos != 5 && cantidad_argumentos != 7) return 1;
    FILE *entrada = fopen(argumentos[1], "rb"), *salida = fopen(argumentos[2], "wb");
    if (!entrada || !salida) return 2;
    fseek(entrada, 0, SEEK_END);
    size_t longitud = (size_t)ftell(entrada) / (2 * sizeof(float));
    rewind(entrada);
    const espectral_configuracion_t configuracion = {1600, 100, (float)atof(argumentos[3]), 0.05f};
    if (!registro_iniciar(&registro, longitud, atoi(argumentos[4]) != 0, configuracion, publicar, salida)) return 3;
    if (cantidad_argumentos == 7) {
        if (!regional_iniciar(&registro.regional, (float)atof(argumentos[5]), (float)atof(argumentos[6]))) return 3;
        registro.tiempos.reloj = reloj_prueba;
    }
    float pares[512], mezcla[256], referencia[256];
    for (size_t inicio = 0; inicio < longitud; inicio += 256) {
        if (fread(pares, sizeof(float), 512, entrada) != 512) return 4;
        for (size_t posicion = 0; posicion < 256; ++posicion) {
            mezcla[posicion] = pares[2 * posicion]; referencia[posicion] = pares[2 * posicion + 1];
        }
        if (!tiempos_recibir(&registro.tiempos, inicio, instante_us) ||
            !registro_agregar(&registro, mezcla, referencia)) return 5;
    }
    if (!registro_finalizar(&registro) || registro_finalizar(&registro)) return 6;
    fclose(entrada); fclose(salida);
    for (unsigned metodo = 0; metodo < 2; ++metodo) {
        const metricas_resultado_t metricas = metricas_finalizar(&registro.metricas[metodo]);
        printf("%u,%.17g,%.17g,%.17g,%.17g\n", (unsigned)registro.metricas[metodo].muestras,
               metricas.mse, metricas.snr_salida_db, metricas.energia_util_pct, metricas.atenuacion_ruido_db);
    }
    if (cantidad_argumentos == 7) {
        fprintf(stderr, "%u,%.17g,%.17g,%.17g\n", (unsigned)(registro.regional.bloques * 1024),
            registro.regional.energia[0], registro.regional.energia[1], registro.regional.energia[2]);
        fprintf(stderr, "%" PRIu64 ",%" PRIu64 ",%" PRIu64 ",%" PRIu64 "\n",
            registro.tiempos.fir.cantidad, registro.tiempos.espectral.cantidad,
            registro.tiempos.arranque.cantidad, registro.tiempos.cierre.cantidad);
    }
    return 0;
}
