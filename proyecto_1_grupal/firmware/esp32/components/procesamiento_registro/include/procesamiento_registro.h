/** Procesa registros finitos por bloques, sin almacenar la grabacion completa. */
#pragma once
#include "filtro_espectral.h"
#include "filtro_fir.h"
#include "metricas_digitales.h"

typedef bool (*registro_publicar_t)(size_t indice, size_t cantidad,
    const float *fir, const float *espectral, void *contexto);

typedef struct {
    filtro_fir_t fir, fir_referencia;
    filtro_espectral_t espectral;
    float ventana[1024], referencia[1024];
    float temporal[512], temporal_anterior[512];
    float util_temporal[512], util_temporal_anterior[512];
    float espectro_salida[512], espectro_util[512], salida[512];
    float retardo[37], retardo_util[37];
    float historia[2048], historia_referencia[2048];
    metricas_acumulador_t metricas[2];
    double energia_salida[2];
    size_t longitud, recibidas, producidas, acumuladas, posicion_retardo;
    bool primera_ventana, con_referencia, iniciado, finalizado;
    registro_publicar_t publicar;
    void *contexto;
} procesamiento_registro_t;

/** Reinicia un registro de longitud multiplo de 256 y sus metricas. */
bool registro_iniciar(procesamiento_registro_t *estado, size_t longitud,
    bool con_referencia, espectral_configuracion_t configuracion,
    registro_publicar_t publicar, void *contexto);
/** Consume exactamente 256 muestras; referencia es obligatoria cuando se declaro. */
bool registro_agregar(procesamiento_registro_t *estado, const float *entrada,
    const float *referencia);
/** Vacia el solapamiento con ceros virtuales y publica exactamente longitud muestras. */
bool registro_finalizar(procesamiento_registro_t *estado);
