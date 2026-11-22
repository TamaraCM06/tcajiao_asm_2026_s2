#ifndef PRUEBA_ESP_TIMER_H
#define PRUEBA_ESP_TIMER_H
#include <stdint.h>
#include "esp_err.h"
typedef void *esp_timer_handle_t;
typedef struct { void (*callback)(void *); const char *name; } esp_timer_create_args_t;
/* Dobles de frontera SDK; no representan perifericos fisicos. */
int64_t esp_timer_get_time(void);
/* Registra el estado logico del temporizador simulado. */
esp_err_t esp_timer_stop(esp_timer_handle_t temporizador);
/* Registra el inicio logico del temporizador simulado. */
esp_err_t esp_timer_start_periodic(esp_timer_handle_t temporizador, uint64_t periodo);
/* Proporciona un identificador ficticio para enlazar la aplicacion de produccion. */
esp_err_t esp_timer_create(const esp_timer_create_args_t *argumentos, esp_timer_handle_t *temporizador);
#endif
