#pragma once
#include <stdbool.h>

enum { FFT_LONGITUD = 1024, FFT_SALTO = 512 };
typedef struct { float real, imaginaria; } complejo_t;
typedef struct { complejo_t giros[FFT_LONGITUD / 2]; } fft_plan_t;

/* Precalcula los giros de una FFT de 1024 puntos, fuera del tiempo por bloque. */
void fft_preparar(fft_plan_t *plan);
/* Transforma en el mismo buffer; la inversa incluye la division entre 1024. */
void fft_transformar(const fft_plan_t *plan, complejo_t *valores, bool inversa);
