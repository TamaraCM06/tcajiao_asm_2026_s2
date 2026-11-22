#ifndef ASM_PROTOCOLO_SERIAL_H
#define ASM_PROTOCOLO_SERIAL_H

#include <stdbool.h>
#include <stddef.h>
#include "esp_err.h"

/* Inicializa UART0 y una unica tarea transmisora con memoria acotada. */
esp_err_t protocolo_iniciar(void);

/* Encola una linea sin esperar; false indica desbordamiento o formato excesivo. */
bool protocolo_emitir(const char *formato, ...) __attribute__((format(printf, 1, 2)));

/* Recibe una linea: 1 completa, 0 pendiente, -1 descartada por longitud o caracteres. */
int protocolo_recibir(char *linea, size_t capacidad);

/* Consulta slots para reservar espacio suficiente al iniciar un ensayo. */
unsigned protocolo_espacios(void);

/* Informa un fallo latente de transmision; requiere reinicio para otro ensayo. */
bool protocolo_fallo(void);

#endif
