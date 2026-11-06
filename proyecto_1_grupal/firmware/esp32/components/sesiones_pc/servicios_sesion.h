/** Servicios internos compartidos; ningun modulo conserva una grabacion completa. */
#pragma once
#include "enlace_pc.h"
#include "procesamiento_registro.h"
#include "trama_spi.h"

/** Inicializa el receptor y su tarea dedicada en el nucleo del controlador SPI. */
esp_err_t captura_pico_iniciar(void);
/** Abre/cierra una epoca de captura y descarta paquetes de epocas anteriores. */
void captura_pico_activar(bool activa);
/** Espera un bloque nuevo y exige continuidad de su identificador. */
esp_err_t captura_pico_leer(trama_spi_bloque_t *bloque, int64_t *recepcion_us);
/** Estima la cadencia de los bloques recibidos, sin afirmar calibracion del reloj ADC. */
double captura_pico_tasa(void);
/** Recibe y valida la secuencia de paquetes del cliente, incluido STOP. */
esp_err_t sesion_recibir(pc_paquete_t *paquete, unsigned espera_ms);
/** Envia una respuesta de texto identificada por sesion. */
esp_err_t sesion_texto(uint32_t sesion, unsigned tipo, const char *texto);
/** Recibe audio PCM16 con ventana de dos paquetes y espera el fin real del DAC. */
esp_err_t audio_pc_reproducir(uint32_t sesion, size_t longitud, float escala,
    bool voltios, float ganancia);
/** Publica metricas digitales y diagnostico de la sesion en JSON. */
esp_err_t informe_pc_enviar(uint32_t sesion, const procesamiento_registro_t *registro,
    uint64_t total_us, uint32_t maximo_us, size_t bloques, int64_t inicio_us,
    const uint32_t recortes[3], bool fisica, double tasa_adquisicion);
