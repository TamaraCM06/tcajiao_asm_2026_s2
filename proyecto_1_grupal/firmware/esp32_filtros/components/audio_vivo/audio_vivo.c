#include "audio_vivo.h"
#include <math.h>
#include <string.h>

static audio_metricas_t medir(const float *entrada, const float *salida,
                             const float *ref, const float *util, unsigned primero, unsigned n)
{
    double ei = 0, eo = 0, er = 0, ee = 0, eu = 0;
    for (unsigned i = primero; i < n; ++i) {
        ei += (double)entrada[i] * entrada[i];
        eo += (double)salida[i] * salida[i];
        if (ref) {
            double error = salida[i] - ref[i];
            er += (double)ref[i] * ref[i];
            ee += error * error;
            eu += (double)util[i] * util[i];
        }
    }
    audio_metricas_t m = {.referencia = ref != NULL, .snr_db = NAN, .mse = NAN,
                         .energia_pct = NAN, .rms = (float)sqrt(eo / (n - primero))};
    if (ref) {
        m.mse = (float)(ee / (n - primero));
        if (er > 1e-20) {
            m.snr_db = ee > 1e-20 ? (float)(10 * log10(er / ee)) : INFINITY;
            m.energia_pct = (float)(100 * eu / er);
        }
    } else if (ei > 1e-20) m.energia_pct = (float)(100 * eo / ei);
    return m;
}

void audio_vivo_iniciar(audio_vivo_t *e)
{
    memset(e, 0, sizeof(*e));
    /* FIR Hamming 75 taps para Fs=10 kHz; los del banco original son para 16 kHz. */
    float suma = 0;
    const float fc = 1800.0f / AUDIO_FS;
    for (int i = 0; i < FIR_COEFICIENTES; ++i) {
        int k = i - FIR_RETARDO;
        float sinc = k == 0 ? 2 * fc : sinf(6.28318530718f * fc * k) / (3.14159265359f * k);
        e->coeficientes[i] = sinc * (0.54f - 0.46f * cosf(6.28318530718f * i / (FIR_COEFICIENTES - 1)));
        suma += e->coeficientes[i];
    }
    for (int i = 0; i < FIR_COEFICIENTES; ++i) e->coeficientes[i] /= suma;
    const espectral_configuracion_t config = {1600.0f, 100.0f, 0.1f, 0.05f};
    (void)filtro_espectral_inicializar_fs(&e->espectral, config, AUDIO_FS);
    e->llenas = FFT_SALTO; /* Prefijo virtual de ceros para overlap-add. */
}

bool audio_vivo_procesar(audio_vivo_t *e, uint32_t id, const float entrada[AUDIO_N],
                        const float *referencia, audio_resultado_t *r)
{
    bool reiniciar = e->con_referencia != (referencia != NULL);
    if (e->secuencia) {
        uint32_t delta = id - e->ultimo_id;
        if (delta == 0 || (delta >= 0x80000000u && id != 0)) return false;
        if (delta != 1) reiniciar = true;
    }
    if (reiniciar) {
        uint32_t discontinuidades = e->discontinuidades + (e->secuencia ? 1u : 0u);
        audio_vivo_iniciar(e);
        e->discontinuidades = discontinuidades;
        memset(r, 0, sizeof(*r));
    }
    e->con_referencia = referencia != NULL;
    e->secuencia = true;
    e->ultimo_id = id;
    r->discontinuidades = e->discontinuidades;
    float ref_fir[AUDIO_N], util_fir[AUDIO_N];
    unsigned primero = e->muestras_fir < FIR_RETARDO ? FIR_RETARDO - e->muestras_fir : 0;
    for (unsigned i = 0; i < AUDIO_N; ++i) {
        unsigned pos = e->pos_historia;
        r->entrada_fir[i] = e->historia[pos];
        ref_fir[i] = e->historia_ref[pos];
        e->historia[pos] = entrada[i];
        e->historia_ref[pos] = referencia ? referencia[i] : 0;
        e->pos_historia = (pos + 1) % FIR_RETARDO;
        r->salida_fir[i] = filtro_fir_muestra(&e->fir, e->coeficientes, entrada[i]);
        util_fir[i] = referencia ? filtro_fir_muestra(&e->fir_ref, e->coeficientes, referencia[i]) : 0;
    }
    e->muestras_fir = FIR_RETARDO; /* Solo se necesita distinguir el calentamiento. */
    r->fir = medir(r->entrada_fir, r->salida_fir, referencia ? ref_fir : NULL, util_fir, primero, AUDIO_N);
    memcpy(e->ventana + e->llenas, entrada, AUDIO_N * sizeof(float));
    if (referencia) memcpy(e->referencia + e->llenas, referencia, AUDIO_N * sizeof(float));
    e->llenas += AUDIO_N;
    if (e->llenas == FFT_LONGITUD) {
        filtro_espectral_bloque(&e->espectral, e->ventana, e->referencia, r->salida_fft, e->util);
        memcpy(r->entrada_fft, e->ventana, FFT_SALTO * sizeof(float));
        r->fft_lista = e->pasos > 0; /* Primera salida corresponde al prefijo virtual. */
        if (r->fft_lista) {
            r->fft_id_inicial = id - 3u;
            r->fft = medir(r->entrada_fft, r->salida_fft,
                           referencia ? e->referencia : NULL, e->util, 0, FFT_SALTO);
        }
        ++e->pasos;
        memmove(e->ventana, e->ventana + FFT_SALTO, FFT_SALTO * sizeof(float));
        memmove(e->referencia, e->referencia + FFT_SALTO, FFT_SALTO * sizeof(float));
        e->llenas = FFT_SALTO;
    }
    return true;
}
