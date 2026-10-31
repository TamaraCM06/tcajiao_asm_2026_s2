#pragma once

#include "senales_embebidas.h"
#include "salida_dac.h"

/* Reproduce una vez y devuelve únicamente después de drenar DMA y cerrar el controlador. */
esp_err_t reproduccion_senal_ejecutar(const senal_embebida_t *senal,
                                    salida_dac_estadisticas_t *estadisticas);
