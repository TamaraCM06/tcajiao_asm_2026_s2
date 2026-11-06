/** Comprueba marcas con reloj controlado y exporta energias sobre residuos conocidos. */
#include "procesamiento_registro.h"
#include <assert.h>
#include <stdio.h>
#include <stdlib.h>
#include <math.h>

static procesamiento_registro_t registro;

/** Permite fijar el instante exacto desde el caso de prueba. */
static int64_t reloj_controlado(void *contexto)
{
    return *(int64_t *)contexto;
}
/** Publicador sin E/S utilizado para comprobar el reinicio del estado. */
static bool publicar_vacio(size_t indice, size_t cantidad, const float *fir, const float *espectral, void *contexto)
{
    (void)indice; (void)cantidad; (void)fir; (void)espectral; (void)contexto;
    return true;
}
/** Exige clasificacion correcta de cola, latencia, arranque y vaciado. */
static void probar_tiempos(void)
{
    int64_t instante = 100;
    tiempos_registro_t tiempos = {.reloj = reloj_controlado, .contexto = &instante};
    assert(tiempos_recibir(&tiempos, 0, 90));
    instante = 120;
    assert(tiempos_recibir(&tiempos, 256, 110));
    tiempos_publicar(&tiempos, 0, 512, 200);
    assert(tiempos.arranque.cantidad == 2 && tiempos.arranque.total_us == 200 && tiempos.arranque.maximo_us == 110);
    instante = 220;
    assert(tiempos_recibir(&tiempos, 512, 210));
    instante = 240;
    assert(tiempos_recibir(&tiempos, 768, 230));
    tiempos_publicar(&tiempos, 512, 256, 300);
    tiempos.en_cierre = true;
    tiempos_publicar(&tiempos, 768, 256, 350);
    assert(tiempos.latencia.cantidad == 1 && tiempos.latencia.total_us == 90);
    assert(tiempos.cierre.cantidad == 1 && tiempos.cierre.total_us == 120);
    assert(tiempos.cola.cantidad == 4 && tiempos.cola.total_us == 40);
    assert(!tiempos_recibir(&tiempos, 1024, 999));
    assert(tiempos_recibir(&tiempos, 1024, 230));
    assert(!tiempos_recibir(&tiempos, 5120, 230));
    tiempo_acumular(&tiempos.publicacion, -1);
    assert(!tiempos.publicacion.cantidad);
    registro.tiempos = tiempos;
    const espectral_configuracion_t configuracion = {1600, 100, .1f, .05f};
    assert(registro_iniciar(&registro, 256, false, configuracion, publicar_vacio, NULL));
    assert(!registro.tiempos.reloj && !registro.tiempos.cola.cantidad && !registro.regional.habilitada);
    puts("OK tiempos, indices, cierre y reinicio");
}
/** Lee ternas float32: ruido de entrada, residuo FIR y residuo espectral. */
int main(int cantidad_argumentos, char **argumentos)
{
    if (cantidad_argumentos == 1) { probar_tiempos(); return 0; }
    if (cantidad_argumentos != 4) return 1;
    if (!regional_iniciar(&registro.regional, (float)atof(argumentos[2]), (float)atof(argumentos[3]))) return 3;
    FILE *archivo = fopen(argumentos[1], "rb");
    if (!archivo) return 2;
    const espectral_configuracion_t configuracion = {1600, 100, .1f, .05f};
    if (!filtro_espectral_inicializar(&registro.espectral, configuracion)) return 4;
    float residuos[3];
    while (fread(residuos, sizeof(float), 3, archivo) == 3)
        regional_agregar(&registro.regional, residuos[0], residuos[1], residuos[2],
            &registro.espectral.transformada, registro.espectral.ventana);
    fclose(archivo);
    printf("%u,%.17g,%.17g,%.17g\n", (unsigned)(registro.regional.bloques * 1024),
        registro.regional.energia[0], registro.regional.energia[1], registro.regional.energia[2]);
    for (unsigned metodo = 0; metodo < 2; ++metodo) {
        const char *motivo = regional_motivo(&registro.regional, metodo, true);
        puts(motivo ? motivo : "disponible");
    }
    assert(regional_motivo(&registro.regional, 0, false));
    return 0;
}
