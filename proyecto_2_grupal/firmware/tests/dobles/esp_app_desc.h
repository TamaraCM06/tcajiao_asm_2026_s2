#ifndef PRUEBA_ESP_APP_DESC_H
#define PRUEBA_ESP_APP_DESC_H
typedef struct { char version[32]; } esp_app_desc_t;
/* Devuelve una revision etiquetada como simulacion. */
const esp_app_desc_t *esp_app_get_description(void);
#endif
