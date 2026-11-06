/** Ejecuta el serializador real con datos limite; no simula una medicion fisica. */
#include "servicios_sesion.h"
#include "esp_app_desc.h"
#include "esp_heap_caps.h"
#include <stdio.h>
#include <string.h>

static procesamiento_registro_t registro;

/** Publica el JSON real para comprobarlo desde Python. */
esp_err_t sesion_texto(uint32_t sesion, unsigned tipo, const char *texto)
{
    (void)sesion; (void)tipo;
    if (strlen(texto) > PC_PAYLOAD_MAX) return ESP_ERR_INVALID_SIZE;
    puts(texto);
    return ESP_OK;
}
/** Proporciona una version del tamano maximo del descriptor de ESP-IDF. */
const esp_app_desc_t *esp_app_get_description(void)
{
    static const esp_app_desc_t descriptor = {"1234567890123456789012345678901", "v5.5.5-1234567890123456789012345"};
    return &descriptor;
}
/** Fija el reloj del informe; las marcas individuales se prueban por separado. */
int64_t esp_timer_get_time(void) { return 60000000; }
/** Devuelve un valor representable por la ESP32, sin afirmar memoria real. */
size_t heap_caps_get_free_size(unsigned capacidad) { (void)capacidad; return 123456; }
/** Fija un minimo distinto para detectar confusiones de campos. */
size_t heap_caps_get_minimum_free_size(unsigned capacidad) { (void)capacidad; return 98765; }

/** Ensaya campos disponibles y ausentes con el mismo serializador de produccion. */
int main(int cantidad_argumentos, char **argumentos)
{
    (void)argumentos;
    registro.longitud = 960000;
    registro.con_referencia = cantidad_argumentos == 1;
    regional_iniciar(&registro.regional, 2500, 3800);
    registro.regional.bloques = 937;
    registro.regional.energia[0] = 123456.123456;
    registro.regional.energia[1] = 1.23456789;
    registro.regional.energia[2] = 123.456789;
    const tiempo_acumulado_t tiempo = {3750, 123456789, 1234567};
    registro.tiempos.fir = registro.tiempos.espectral = tiempo;
    registro.tiempos.cola = registro.tiempos.latencia = tiempo;
    registro.tiempos.arranque = registro.tiempos.cierre = tiempo;
    registro.tiempos.evaluacion = registro.tiempos.publicacion = tiempo;
    for (unsigned metodo = 0; metodo < 2; ++metodo) {
        metricas_acumular(&registro.metricas[metodo], .2f, .1f, .11f, .09f);
        registro.energia_salida[metodo] = 12345.6789;
    }
    const uint32_t recortes[3] = {960000, 960000, 960000};
    return informe_pc_enviar(1, &registro, 59999999, 123456, 3751, 0, recortes, false, 0);
}
