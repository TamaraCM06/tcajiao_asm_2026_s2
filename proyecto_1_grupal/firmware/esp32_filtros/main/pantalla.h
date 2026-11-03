#pragma once
#include <stdbool.h>
#include <stdint.h>
#include "audio_vivo.h"
#include "esp_err.h"

enum { PANTALLA_PUNTOS = 160 };
typedef struct {
    float entrada[PANTALLA_PUNTOS], salida[PANTALLA_PUNTOS];
    audio_metricas_t metricas;
    uint32_t bloque, rechazados, discontinuidades;
    bool espectral, simulacion, lista;
} pantalla_datos_t;
esp_err_t pantalla_iniciar(void);
void pantalla_dibujar(const pantalla_datos_t *datos, bool conectado);
