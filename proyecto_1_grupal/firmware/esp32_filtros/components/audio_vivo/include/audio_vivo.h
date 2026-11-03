#pragma once
#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>
#include "filtro_fir.h"
#include "filtro_espectral.h"

enum { AUDIO_N = 256, AUDIO_FS = 10000, AUDIO_TRAMA = 1032 };
typedef enum { AUDIO_OK, AUDIO_LONGITUD, AUDIO_CABECERA, AUDIO_CRC, AUDIO_MUESTRA } audio_error_t;
/* Campos little endian; no hacer cast de la trama a float*. */
audio_error_t audio_decodificar(const uint8_t *trama, size_t bytes, uint32_t *id, float salida[AUDIO_N]);

typedef struct {
    bool referencia;
    float snr_db, mse, energia_pct, rms;
} audio_metricas_t;
typedef struct {
    float entrada_fir[AUDIO_N], salida_fir[AUDIO_N];
    float entrada_fft[FFT_SALTO], salida_fft[FFT_SALTO];
    audio_metricas_t fir, fft;
    bool fft_lista;
    uint32_t discontinuidades, fft_id_inicial;
} audio_resultado_t;
typedef struct {
    filtro_fir_t fir, fir_ref;
    filtro_espectral_t espectral;
    float coeficientes[FIR_COEFICIENTES];
    float ventana[FFT_LONGITUD], referencia[FFT_LONGITUD], util[FFT_SALTO];
    float historia[FIR_RETARDO], historia_ref[FIR_RETARDO];
    unsigned pos_historia, muestras_fir, llenas, pasos;
    uint32_t ultimo_id, discontinuidades;
    bool secuencia, con_referencia;
} audio_vivo_t;
void audio_vivo_iniciar(audio_vivo_t *estado);
/* referencia NULL: SNR/MSE no disponibles; E es energia total salida/entrada.
 * Referencia conocida: SNR/MSE respecto a referencia alineada; E es util filtrada/ref.
 * Devuelve false para duplicados o paquetes fuera de orden (id=0 reinicia epoca).
 * Un salto de secuencia reinicia ambas historias y el calentamiento FFT. */
bool audio_vivo_procesar(audio_vivo_t *estado, uint32_t id, const float entrada[AUDIO_N],
                        const float *referencia, audio_resultado_t *resultado);
