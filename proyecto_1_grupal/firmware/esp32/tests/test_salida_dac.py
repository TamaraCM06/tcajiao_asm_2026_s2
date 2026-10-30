"""Regresión del cierre DAC con eventos controlados; no simula la salida analógica."""

from pathlib import Path
import shutil
import subprocess

import pytest


FIRMWARE = Path(__file__).resolve().parents[1]
CABECERA_IDF = """
#ifndef IDF_SIMULADO_H
#define IDF_SIMULADO_H
#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>
#define IRAM_ATTR
#define CONFIG_DAC_DMA_AUTO_16BIT_ALIGN 1
#define ESP_OK 0
#define ESP_ERR_INVALID_ARG 1
#define ESP_ERR_INVALID_STATE 2
#define ESP_ERR_INVALID_SIZE 3
#define ESP_ERR_NO_MEM 4
#define ESP_ERR_TIMEOUT 5
#define pdFALSE 0
#define pdTRUE 1
#define pdMS_TO_TICKS(milisegundos) (milisegundos)
#define portMUX_INITIALIZER_UNLOCKED 0
#define portENTER_CRITICAL(bloqueo) ((void)(bloqueo))
#define portEXIT_CRITICAL(bloqueo) ((void)(bloqueo))
#define portENTER_CRITICAL_ISR(bloqueo) ((void)(bloqueo))
#define portEXIT_CRITICAL_ISR(bloqueo) ((void)(bloqueo))
#define DAC_CHANNEL_MASK_CH0 1
#define DAC_DIGI_CLK_SRC_APLL 1
#define DAC_CHANNEL_MODE_SIMUL 1
typedef int esp_err_t;
typedef int BaseType_t;
typedef int portMUX_TYPE;
typedef int *SemaphoreHandle_t;
typedef struct controlador_simulado *dac_continuous_handle_t;
typedef struct {
    void *buf;
    size_t buf_size;
    size_t write_bytes;
} dac_event_data_t;
typedef bool (*dac_isr_callback_t)(dac_continuous_handle_t, const dac_event_data_t *, void *);
typedef struct {
    dac_isr_callback_t on_convert_done;
    dac_isr_callback_t on_stop;
} dac_event_callbacks_t;
typedef struct {
    int chan_mask;
    unsigned desc_num;
    size_t buf_size;
    uint32_t freq_hz;
    int offset;
    int clk_src;
    int chan_mode;
} dac_continuous_config_t;
SemaphoreHandle_t xSemaphoreCreateBinary(void);
BaseType_t xSemaphoreTake(SemaphoreHandle_t, unsigned);
BaseType_t xSemaphoreGiveFromISR(SemaphoreHandle_t, BaseType_t *);
void vSemaphoreDelete(SemaphoreHandle_t);
esp_err_t dac_continuous_new_channels(const dac_continuous_config_t *, dac_continuous_handle_t *);
esp_err_t dac_continuous_register_event_callback(dac_continuous_handle_t, const dac_event_callbacks_t *, void *);
esp_err_t dac_continuous_enable(dac_continuous_handle_t);
esp_err_t dac_continuous_disable(dac_continuous_handle_t);
esp_err_t dac_continuous_del_channels(dac_continuous_handle_t);
esp_err_t dac_continuous_write(dac_continuous_handle_t, uint8_t *, size_t, size_t *, int);
#endif
"""


# Compila el controlador real con dobles de las API del SDK, sin placa ni filtros.
@pytest.fixture(scope="module")
def ejecutor_salida_dac(tmp_path_factory):
    """Construye el ejecutable que inyecta conversiones, paradas y escrituras parciales."""
    compilador = shutil.which("gcc")
    if not compilador:
        pytest.fail("Se necesita GCC para comprobar el cierre DAC en computadora.")
    carpeta = tmp_path_factory.mktemp("salida_dac")
    (carpeta / "idf_simulado.h").write_text(CABECERA_IDF, encoding="utf-8")
    for nombre in ("driver/dac_continuous.h", "esp_err.h", "esp_attr.h", "sdkconfig.h",
                   "freertos/FreeRTOS.h", "freertos/semphr.h"):
        cabecera = carpeta / nombre
        cabecera.parent.mkdir(parents=True, exist_ok=True)
        cabecera.write_text('#include "idf_simulado.h"\n', encoding="utf-8")
    ejecutable = carpeta / "salida_dac.exe"
    subprocess.run([
        compilador, "-std=c11", "-Wall", "-Wextra", "-Werror",
        "-I", str(carpeta), "-I", str(FIRMWARE / "components/salida_dac/include"),
        str(FIRMWARE / "components/salida_dac/salida_dac.c"),
        str(Path(__file__).with_name("ejecutor_salida_dac.c")), "-o", str(ejecutable),
    ], capture_output=True, text=True, check=True)
    return ejecutable


# Reproduce el fallo observado y comprueba que la corrección conserva los errores reales.
@pytest.mark.parametrize("escenario", [
    "ultimo_aviso_omitido", "avisos_completos", "parada_prematura",
    "avisos_excesivos", "escritura_parcial", "cierre_voluntario", "parada_durante_escritura",
])
def test_cierre_dac(ejecutor_salida_dac, escenario):
    """Verifica la API pública del mismo controlador C mediante secuencias de eventos."""
    resultado = subprocess.run([str(ejecutor_salida_dac), escenario],
                               capture_output=True, text=True)
    assert resultado.returncode == 0, resultado.stdout + resultado.stderr
