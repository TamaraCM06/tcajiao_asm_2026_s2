/** UART0 binaria: un productor TX y una tarea RX con cola acotada. */
#pragma once
#include "esp_err.h"
#include "protocolo_pc.h"
/** Instala UART0 a 1 Mbaud y arranca la recepcion en segundo plano. */
esp_err_t enlace_pc_iniciar(void);
/** Copia el paquete completo a TX acotado; el hardware lo transmite en segundo plano. */
esp_err_t enlace_pc_enviar(pc_paquete_t *paquete);
/** Devuelve tambien el instante de trama validada, anterior a su espera en cola. */
esp_err_t enlace_pc_recibir_marcado(pc_paquete_t *paquete, unsigned espera_ms, int64_t *recepcion_us);
