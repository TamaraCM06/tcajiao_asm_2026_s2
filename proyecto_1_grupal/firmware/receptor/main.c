#include "nodo1_metodos.h"

#include <inttypes.h>
#include <math.h>
#include <stdio.h>
#include <string.h>

#include "hardware/adc.h"
#include "hardware/clocks.h"
#include "hardware/dma.h"
#include "hardware/irq.h"
#include "hardware/spi.h"
#include "hardware/sync.h"
#include "pico/stdlib.h"
#include "pico/stdio_usb.h"

#ifndef NODO1_HABILITAR_SPI
#define NODO1_HABILITAR_SPI 0
#endif

/* Indicador de nivel electrico, no detector de voz ni umbral calibrado. */
#ifndef NODO1_UMBRAL_ACTIVIDAD_MV
#define NODO1_UMBRAL_ACTIVIDAD_MV 5.0f
#endif

enum { CAPACIDAD_COLA = 4 };
typedef struct {
    uint32_t id;
    uint16_t adc[NODO1_N];
} bloque_adc_t;

/* Dos destinos DMA encadenados; la ISR publica copias en una cola acotada.
 * El bucle principal copia una entrada antes de liberarla. Solo se usa core 0. */
static uint16_t buffers_dma[2][NODO1_N];
static bloque_adc_t cola[CAPACIDAD_COLA];
static volatile unsigned escritura, lectura;
static volatile uint32_t bloques_capturados, descartados_cola, errores_adc;
static volatile bool reiniciar_adc;
static unsigned siguiente_dma;
static int canales[2];
static uint32_t mascara_dma, siguiente_id;
static uint32_t reinicios_adc;

static nodo1_tablas_t tablas;
static bloque_adc_t bloque;
static float muestras[NODO1_N], real_fft[NODO1_N], imag_fft[NODO1_N];
static uint8_t trama[NODO1_SPI_BYTES] __attribute__((aligned(4)));

/* Una captura bajo demanda evita transmitir todo el ADC por USB.
 * Protocolo: ADC1,id,Fs,Vref,perdidos,errores,reinicios,N,codigo0,...,codigoN-1 */
static void imprimir_captura_usb(void)
{
    static char linea[1600]; /* 256 codigos de hasta 4 digitos + cabecera. */
    int usados = snprintf(linea, sizeof(linea),
                         "ADC1,%" PRIu32 ",%u,%.6f,%" PRIu32 ",%" PRIu32 ",%" PRIu32 ",%u",
                         bloque.id, NODO1_FS_HZ, (double)NODO1_ADC_VREF,
                         descartados_cola, errores_adc, reinicios_adc, NODO1_N);
    if (usados < 0 || (size_t)usados >= sizeof(linea)) return;
    for (size_t i = 0; i < NODO1_N; ++i) {
        const int escritos = snprintf(linea + usados, sizeof(linea) - (size_t)usados,
                                      ",%u", (unsigned)bloque.adc[i]);
        if (escritos < 0 || (size_t)escritos >= sizeof(linea) - (size_t)usados) return;
        usados += escritos;
    }
    printf("%s\n", linea);
}

/* No se imprime ni se ejecuta DSP desde interrupciones. Si se pierde el plazo
 * de rearme, se detiene la captura: nunca se publica un bloque discontinuo. */
static void __not_in_flash_func(atender_dma)(void)
{
    const uint32_t pendientes = dma_hw->ints0 & mascara_dma;
    if (!pendientes) return;
    dma_hw->ints0 = pendientes;
    if (pendientes != (1u << canales[siguiente_dma]) ||
        (adc_hw->fcs & ADC_FCS_OVER_BITS)) {
        adc_run(false);
        for (unsigned i = 0; i < 2; ++i) dma_channel_set_irq0_enabled(canales[i], false);
        reiniciar_adc = true;
        return;
    }

    const unsigned actual = siguiente_dma;
    const uint32_t id = siguiente_id++;
    ++bloques_capturados;
    bool valido = true;
    for (size_t n = 0; n < NODO1_N; ++n) {
        if (buffers_dma[actual][n] & 0x8000u) valido = false;
    }
    const unsigned proxima = (escritura + 1u) % CAPACIDAD_COLA;
    if (!valido) {
        ++errores_adc;
    } else if (proxima == lectura) {
        ++descartados_cola;
    } else {
        cola[escritura].id = id;
        memcpy(cola[escritura].adc, buffers_dma[actual], sizeof(buffers_dma[actual]));
        __dmb();
        escritura = proxima;
    }

    dma_channel_set_write_addr(canales[actual], buffers_dma[actual], false);
    dma_channel_set_trans_count(canales[actual], NODO1_N, false);
    siguiente_dma ^= 1u;
}

static void iniciar_captura(void)
{
    adc_fifo_drain();
    adc_hw->fcs |= ADC_FCS_OVER_BITS | ADC_FCS_UNDER_BITS; /* W1C. */
    siguiente_dma = 0;
    dma_hw->ints0 = mascara_dma;
    for (unsigned i = 0; i < 2; ++i) {
        dma_channel_config configuracion = dma_channel_get_default_config(canales[i]);
        channel_config_set_transfer_data_size(&configuracion, DMA_SIZE_16);
        channel_config_set_read_increment(&configuracion, false);
        channel_config_set_write_increment(&configuracion, true);
        channel_config_set_dreq(&configuracion, DREQ_ADC);
        channel_config_set_chain_to(&configuracion, canales[i ^ 1u]);
        dma_channel_configure(canales[i], &configuracion, buffers_dma[i],
                              &adc_hw->fifo, NODO1_N, false);
        dma_channel_set_irq0_enabled(canales[i], true);
    }
    dma_start_channel_mask(1u << canales[0]);
    adc_run(true);
}

static void inicializar_adc(void)
{
    adc_init();
    adc_gpio_init(NODO1_ADC_GPIO);
    adc_select_input(NODO1_ADC_CANAL);
    adc_set_round_robin(0);
    adc_fifo_setup(true, true, 1, true, false);
    /* El período ADC es (1 + divisor) ciclos del reloj de 48 MHz. */
    adc_set_clkdiv((float)clock_get_hz(clk_adc) / NODO1_FS_HZ - 1.0f);
    for (unsigned i = 0; i < 2; ++i) canales[i] = dma_claim_unused_channel(true);
    mascara_dma = (1u << canales[0]) | (1u << canales[1]);
    irq_set_exclusive_handler(DMA_IRQ_0, atender_dma);
    irq_set_enabled(DMA_IRQ_0, true);
    iniciar_captura();
}

static void recuperar_captura(void)
{
    /* La ISR ya detuvo ADC y deshabilitó sus IRQ DMA. E13: abortar con IRQ
     * deshabilitada y limpiar pendientes antes de volver a habilitarla. */
    for (unsigned i = 0; i < 2; ++i) {
        dma_channel_hw_addr(canales[i])->al1_ctrl &= ~DMA_CH0_CTRL_TRIG_EN_BITS;
    }
    for (unsigned i = 0; i < 2; ++i) dma_channel_abort(canales[i]);
    while (!(adc_hw->cs & ADC_CS_READY_BITS)) tight_loop_contents();
    /* Vaciar también la cola: sus bloques son anteriores a la discontinuidad. */
    descartados_cola += (escritura + CAPACIDAD_COLA - lectura) % CAPACIDAD_COLA;
    lectura = escritura;
    siguiente_id += 2u; /* Hueco de secuencia para los destinos DMA invalidados. */
    ++reinicios_adc;
    reiniciar_adc = false;
    iniciar_captura();
}

static bool extraer_bloque(bloque_adc_t *destino)
{
    /* Sección corta: solo copia 512 bytes y libera una entrada, sin DSP ni USB. */
    const uint32_t estado = save_and_disable_interrupts();
    const bool disponible = lectura != escritura;
    if (disponible) {
        *destino = cola[lectura];
        lectura = (lectura + 1u) % CAPACIDAD_COLA;
    }
    restore_interrupts(estado);
    return disponible;
}

#if NODO1_HABILITAR_SPI
static volatile bool ready_descendio;
static bool consumo_pendiente;
static uint32_t spi_hz_real;

static void atender_ready(uint gpio, uint32_t eventos)
{
    if (gpio == NODO1_SPI_READY && (eventos & GPIO_IRQ_EDGE_FALL)) ready_descendio = true;
}

static void inicializar_spi(void)
{
    gpio_init(NODO1_SPI_CS);
    gpio_put(NODO1_SPI_CS, 1);
    gpio_set_dir(NODO1_SPI_CS, GPIO_OUT);
    gpio_init(NODO1_SPI_READY);
    gpio_set_dir(NODO1_SPI_READY, GPIO_IN);
    gpio_pull_down(NODO1_SPI_READY); /* Sin receptor: no iniciar transacciones. */
    gpio_set_irq_enabled_with_callback(NODO1_SPI_READY, GPIO_IRQ_EDGE_FALL, true, atender_ready);
    spi_hz_real = spi_init(spi0, NODO1_SPI_HZ);
    spi_set_slave(spi0, false);
    /* Modo 1 para compatibilidad con DMA del esclavo ESP32 clásico. */
    spi_set_format(spi0, 8, SPI_CPOL_0, SPI_CPHA_1, SPI_MSB_FIRST);
    gpio_set_function(NODO1_SPI_SCK, GPIO_FUNC_SPI);
    gpio_set_function(NODO1_SPI_MOSI, GPIO_FUNC_SPI);
}

typedef enum { ENVIO_OK, ENVIO_SIN_READY, ENVIO_SIN_CONSUMO } resultado_spi_t;

static resultado_spi_t transmitir_bloque(void)
{
    uint64_t limite = time_us_64() + NODO1_SPI_TIMEOUT_US;
    /* Si READY quedó alto tras un envío anterior, no volver a usar ese nivel
     * como permiso: primero observar que se consumió aquella transacción. */
    if (consumo_pendiente) {
        while (!ready_descendio) {
            if (time_us_64() >= limite) return ENVIO_SIN_CONSUMO;
            tight_loop_contents();
        }
        consumo_pendiente = false;
        limite = time_us_64() + NODO1_SPI_TIMEOUT_US;
    }
    while (!gpio_get(NODO1_SPI_READY)) {
        if (time_us_64() >= limite) return ENVIO_SIN_READY;
        tight_loop_contents();
    }
    ready_descendio = false;
    consumo_pendiente = true;
    gpio_put(NODO1_SPI_CS, 0);
    busy_wait_us_32(2); /* Tiempo de establecimiento de CS. */
    spi_write_blocking(spi0, trama, sizeof(trama));
    while (spi_is_busy(spi0)) tight_loop_contents();
    busy_wait_us_32(2);
    gpio_put(NODO1_SPI_CS, 1);
    /* El esclavo debe bajar READY al consumir la transacción antes de rearmar.
     * Se conserva la arista aunque el siguiente READY llegue inmediatamente. */
    limite = time_us_64() + NODO1_SPI_TIMEOUT_US;
    while (!ready_descendio) {
        if (time_us_64() >= limite) return ENVIO_SIN_CONSUMO;
        tight_loop_contents();
    }
    consumo_pendiente = false;
    return ENVIO_OK; /* Significa envío/rearme observado, no ACK del CRC remoto. */
}
#endif

int main(void)
{
    stdio_init_all();
    nodo1_preparar_tablas(&tablas);
#if NODO1_HABILITAR_SPI
    inicializar_spi();
#endif
    inicializar_adc();

    uint32_t procesados = 0, enviados = 0, sin_ready = 0, sin_consumo = 0;
    uint32_t capturados_anteriores = 0, reinicios_anteriores = 0;
    uint32_t procesamiento_max_us = 0, ciclo_max_us = 0;
    uint64_t ultimo_reporte = time_us_64();
    bool consola_anunciada = false;
    uint32_t reportes = 0, bloques_intervalo = 0, saturadas_intervalo = 0;
    float suma_rms2 = 0.0f, suma_dc = 0.0f, rms_max = 0.0f, pico_intervalo = 0.0f;
    uint16_t adc_min = 4095, adc_max = 0;
    bool captura_usb_pendiente = false;
    uint64_t ultima_peticion_usb = 0;
    while (true) {
        /* g pide el proximo bloque; t recupera la tabla inmediatamente.
         * Sin peticiones durante 2 s la tabla se recupera automaticamente. */
        const int comando = getchar_timeout_us(0);
        if (comando == 'g') {
            captura_usb_pendiente = true;
            ultima_peticion_usb = time_us_64();
            consola_anunciada = false;
        } else if (comando == 't' || !stdio_usb_connected()) {
            captura_usb_pendiente = false;
            ultima_peticion_usb = 0;
        }
        if (reiniciar_adc) recuperar_captura();
        if (!extraer_bloque(&bloque)) {
            tight_loop_contents();
            continue;
        }
        const uint64_t inicio = time_us_64();
        nodo1_metricas_t metricas;
        nodo1_convertir_adc(bloque.adc, muestras, &metricas);
        nodo1_aplicar_hann(muestras, &tablas, real_fft, imag_fft);
        nodo1_fft(real_fft, imag_fft, &tablas);
        nodo1_estimar_ruido(real_fft, imag_fft, 1600.0f, &metricas);
        /* Resumir todos los bloques: un sonido breve entre reportes debe verse. */
        ++bloques_intervalo;
        suma_rms2 += metricas.rms_ac_v * metricas.rms_ac_v;
        suma_dc += metricas.media_v;
        saturadas_intervalo += metricas.saturadas;
        if (metricas.adc_min < adc_min) adc_min = metricas.adc_min;
        if (metricas.adc_max > adc_max) adc_max = metricas.adc_max;
        if (metricas.rms_ac_v > rms_max) {
            rms_max = metricas.rms_ac_v;
            pico_intervalo = metricas.pico_hz;
        }
        const bool paquete_valido = nodo1_empaquetar(bloque.id, muestras, trama);
        ++procesados;
        const uint32_t procesamiento_us = (uint32_t)(time_us_64() - inicio);
        if (procesamiento_us > procesamiento_max_us) procesamiento_max_us = procesamiento_us;
#if NODO1_HABILITAR_SPI
        if (paquete_valido) {
            const resultado_spi_t resultado = transmitir_bloque();
            if (resultado == ENVIO_OK) ++enviados;
            else if (resultado == ENVIO_SIN_READY) ++sin_ready;
            else ++sin_consumo;
        }
#else
        (void)paquete_valido;
#endif
        const uint64_t ahora = time_us_64();
        const uint32_t ciclo_us = (uint32_t)(ahora - inicio);
        if (ciclo_us > ciclo_max_us) ciclo_max_us = ciclo_us;
        const bool modo_grafica = ultima_peticion_usb != 0 &&
                                 ahora - ultima_peticion_usb < 2000000u;
        if (captura_usb_pendiente && modo_grafica && stdio_usb_connected()) {
            imprimir_captura_usb();
            captura_usb_pendiente = false;
        }
        if (!stdio_usb_connected()) consola_anunciada = false;
        if (ahora - ultimo_reporte < 1000000u) continue;

        /* Contador DMA: tasa entregada por hardware, no tasa de iteraciones del
         * bucle. Ventana de ~1 s cuantizada en bloques; no calibra el reloj ADC. */
        const uint32_t capturados = bloques_capturados;
        const float tasa = (float)(capturados - capturados_anteriores) * NODO1_N *
                           1000000.0f / (float)(ahora - ultimo_reporte);
        const bool tasa_valida = reinicios_anteriores == reinicios_adc;
        capturados_anteriores = capturados;
        reinicios_anteriores = reinicios_adc;
        ultimo_reporte = ahora;
        if (stdio_usb_connected() && !modo_grafica) {
            if (!consola_anunciada) {
                printf("\nRECEPTOR | entrada analogica GPIO26/ADC0 | Fs=%u Hz | SPI=%s\n",
                       NODO1_FS_HZ, NODO1_HABILITAR_SPI ? "ON" : "OFF");
                printf("Una fila resume ~1 s. # cuenta reportes enviados; t es tiempo desde arranque.\n");
                printf("RMS: nivel AC medio; Max: RMS del bloque mas intenso (mV).\n");
                printf("Pico: frecuencia de ese bloque; resolucion %.2f Hz, no identifica sonidos.\n",
                       (double)NODO1_FS_HZ / NODO1_N);
                printf("Nivel: BAJO / ACTIVIDAD si Max >= %.1f mV; umbral orientativo, incluye ruido.\n",
                       (double)NODO1_UMBRAL_ACTIVIDAD_MV);
                printf("DC: offset medio; Vpp: rango del intervalo; Sat: muestras en extremos ADC.\n");
                printf("Perd/Err/Rein: perdidas de cola, errores ADC y reinicios acumulados. Fs con !: intervalo invalido.\n");
                printf("Una entrada flotante tambien puede mostrar actividad. MAX4466: DC suele rondar 1.65 V.\n");
#if NODO1_HABILITAR_SPI
                printf("SPI: reloj real=%" PRIu32 " Hz, %u bytes/transaccion\n",
                       spi_hz_real, NODO1_SPI_BYTES);
#endif
            }
            if (!consola_anunciada || reportes % 20u == 0) {
                printf("\n|      # |    t(s) | Nivel     | RMS mV | Max mV | Pico Hz | DC V | Vpp V |   Sat | Fs Hz   | Perd/Err/Rein |\n");
                printf("|--------|---------|-----------|--------|--------|---------|------|-------|-------|---------|---------------|\n");
            }
            consola_anunciada = true;
            ++reportes;
            const bool actividad = rms_max * 1000.0f >= NODO1_UMBRAL_ACTIVIDAD_MV;
            char frecuencia[24];
            if (actividad) snprintf(frecuencia, sizeof(frecuencia), "%.1f", (double)pico_intervalo);
            else snprintf(frecuencia, sizeof(frecuencia), "--");
            printf("| %6" PRIu32 " | %7.1f | %-9s | %6.1f | %6.1f | %7s | %4.2f | %5.3f | %5" PRIu32
                   " | %6.0f%c | %3" PRIu32 "/%3" PRIu32 "/%3" PRIu32 " |\n",
                   reportes, (double)ahora / 1000000.0,
                   actividad ? "ACTIVIDAD" : "BAJO",
                   (double)sqrtf(suma_rms2 / bloques_intervalo) * 1000.0,
                   (double)rms_max * 1000.0, frecuencia,
                   (double)suma_dc / bloques_intervalo,
                   (double)(adc_max - adc_min) * NODO1_ADC_VREF / 4095.0,
                   saturadas_intervalo, (double)tasa, tasa_valida ? ' ' : '!',
                   descartados_cola, errores_adc, reinicios_adc);
#if NODO1_HABILITAR_SPI
            printf("  SPI acumulado: emitidos=%" PRIu32 " sin_READY=%" PRIu32 " sin_consumo=%" PRIu32 "\n",
                   enviados, sin_ready, sin_consumo);
#else
            (void)enviados;
            (void)sin_ready;
            (void)sin_consumo;
#endif
            /* Contadores de bloques y tiempos disponibles sin saturar cada fila. */
            if (reportes % 20u == 0) {
                printf("  Capturados=%" PRIu32 " procesados=%" PRIu32
                       " | ultimo intervalo: DSP max=%" PRIu32 " us ciclo max=%" PRIu32 " us\n",
                       capturados, procesados, procesamiento_max_us, ciclo_max_us);
            }
        }
        bloques_intervalo = saturadas_intervalo = 0;
        suma_rms2 = suma_dc = rms_max = pico_intervalo = 0.0f;
        adc_min = 4095;
        adc_max = 0;
        procesamiento_max_us = 0;
        ciclo_max_us = 0;
    }
}
