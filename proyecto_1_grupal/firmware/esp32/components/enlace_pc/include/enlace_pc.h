/** UART0 binaria: un productor TX y una tarea RX con cola acotada. */
#pragma once
#include "esp_err.h"
#include "protocolo_pc.h"
/** Instala UART0 a 2 Mbaud y arranca la recepcion en segundo plano. */
esp_err_t enlace_pc_iniciar(void);
/** Envia un paquete completo y espera drenaje fisico con limite de 200 ms. */
esp_err_t enlace_pc_enviar(pc_paquete_t *paquete);
/** Recibe una copia; corrupcion o desbordamiento se comunican como error. */
esp_err_t enlace_pc_recibir(pc_paquete_t *paquete, unsigned espera_ms);
