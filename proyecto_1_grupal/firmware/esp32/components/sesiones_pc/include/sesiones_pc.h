/** Aplicacion de registros finitos con almacenamiento externo en PC. */
#pragma once
#include "esp_err.h"
/** Inicializa servicios y atiende una operacion por vez hasta reiniciar. */
esp_err_t sesiones_pc_ejecutar(void);
