/** Coordina adquisicion remota, filtros existentes, audio seleccionable y consola local. */
#pragma once

#include "esp_err.h"

/** Inicia servicios y atiende consola hasta reiniciar la placa; llamar desde app_main. */
esp_err_t sistema_vivo_ejecutar(void);
