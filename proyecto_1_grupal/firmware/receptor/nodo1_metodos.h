#ifndef NODO1_METODOS_H
#define NODO1_METODOS_H

#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

#define NODO1_N 256u
#define NODO1_FS_HZ 10000u
#define NODO1_ADC_GPIO 26u
#define NODO1_ADC_CANAL 0u
#define NODO1_ADC_VREF 3.3f /* Sustituir por la referencia medida para calibrar voltios. */
#define NODO1_SPI_HZ 2000000u
#define NODO1_SPI_SCK 18u
#define NODO1_SPI_MOSI 19u
#define NODO1_SPI_CS 17u
#define NODO1_SPI_READY 20u
#define NODO1_SPI_TIMEOUT_US 2000u
#define NODO1_TRAMA_BYTES (2u + 4u + 4u * NODO1_N + 1u)
#define NODO1_SPI_BYTES (NODO1_TRAMA_BYTES + 1u)

/* Formato lógico: float IEEE-754 binario32, little-endian, en voltios sin DC.
 * Usar nodo1_empaquetar(): no depender de accesos float desalineados ni del
 * endianness del compilador. El relleno SPI queda fuera de esta estructura. */
typedef struct __attribute__((packed)) {
    uint8_t cabecera[2];
    uint32_t id_bloque;
    float muestras[NODO1_N];
    uint8_t crc8;
} nodo1_paquete_t;

typedef struct {
    float hann[NODO1_N];
    float giro_re[NODO1_N / 2u];
    float giro_im[NODO1_N / 2u];
} nodo1_tablas_t;

typedef struct {
    uint16_t adc_min;
    uint16_t adc_max;
    uint32_t saturadas;
    float media_v;
    float rms_ac_v;
    float energia_ac_v2; /* Suma de cuadrados del bloque, sin normalizar. */
    float pico_hz;      /* Pico dominante de la mezcla, no identifica ruido por sí solo. */
    float candidata_ruido_hz;
    bool candidata_valida;
} nodo1_metricas_t;

void nodo1_preparar_tablas(nodo1_tablas_t *tablas);
void nodo1_convertir_adc(const uint16_t adc[NODO1_N], float salida[NODO1_N],
                         nodo1_metricas_t *metricas);
/* Devuelve la media sustraída, calculada con acumulador float. */
float nodo1_eliminar_dc(float muestras[NODO1_N]);
void nodo1_aplicar_hann(const float entrada[NODO1_N], const nodo1_tablas_t *tablas,
                        float real[NODO1_N], float imaginaria[NODO1_N]);
/* FFT directa radix-2, sin normalizar, modifica ambos arreglos. */
void nodo1_fft(float real[NODO1_N], float imaginaria[NODO1_N],
               const nodo1_tablas_t *tablas);
/* Banda candidata configurable; un pico útil dentro de ella también será detectado. */
void nodo1_estimar_ruido(const float real[NODO1_N], const float imaginaria[NODO1_N],
                         float frecuencia_minima_hz, nodo1_metricas_t *metricas);
uint8_t nodo1_crc8(const uint8_t *datos, size_t cantidad);
/* Devuelve false ante NaN/Inf. Salida: 1031 bytes + relleno cero para DMA ESP32. */
bool nodo1_empaquetar(uint32_t id, const float muestras[NODO1_N],
                      uint8_t salida[NODO1_SPI_BYTES]);

#endif
