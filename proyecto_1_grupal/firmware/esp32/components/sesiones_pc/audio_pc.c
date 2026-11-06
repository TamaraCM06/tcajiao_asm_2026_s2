#include "servicios_sesion.h"
#include "salida_dac.h"
#include <math.h>
#include <string.h>
#include <stdio.h>

/** Convierte paquetes de hasta 1536 muestras y acredita solo la finalizacion DMA. */
esp_err_t audio_pc_reproducir(uint32_t sesion, size_t longitud, float escala,
    bool voltios, float ganancia)
{
    static pc_paquete_t paquete;
    static uint8_t codigos[1536];
    salida_dac_t salida = {0};
    uint32_t recortes = 0;
    size_t recibidas = 0;
    esp_err_t resultado = sesion_texto(sesion, PC_ACK, "AUDIO ventana=2 bloque=1536");
    if (resultado != ESP_OK) return resultado;
    while (recibidas < longitud) {
        resultado = sesion_recibir(&paquete, 500);
        if (resultado != ESP_OK) break;
        if (paquete.sesion != sesion) { resultado = ESP_ERR_INVALID_STATE; break; }
        if (paquete.tipo == PC_COMANDO && paquete.longitud == 4 && !memcmp(paquete.datos, "STOP", 4)) {
            resultado = ESP_ERR_INVALID_STATE; break;
        }
        size_t cantidad = longitud - recibidas;
        if (cantidad > 1536) cantidad = 1536;
        if (paquete.tipo != PC_AUDIO || paquete.indice != recibidas || paquete.longitud != cantidad * 2) {
            resultado = ESP_ERR_INVALID_SIZE; break;
        }
        for (size_t posicion = 0; posicion < cantidad; ++posicion) {
            const int16_t pcm = (int16_t)((uint16_t)paquete.datos[2 * posicion] |
                               (uint16_t)paquete.datos[2 * posicion + 1] << 8);
            const float muestra = pcm * (escala / 32768.0f);
            const float codigo = floorf(128.0f + muestra * ganancia * (voltios ? 255.0f / 3.3f : 127.5f) + 0.5f);
            if (codigo < 0 || codigo > 255) ++recortes;
            codigos[posicion] = codigo < 0 ? 0 : codigo > 255 ? 255 : (uint8_t)codigo;
        }
        if (recibidas == 0) {
            resultado = salida_dac_inicializar(&salida, 16000, longitud);
            if (resultado != ESP_OK) break;
        }
        resultado = salida_dac_escribir(&salida, codigos, cantidad);
        if (resultado != ESP_OK) break;
        recibidas += cantidad;
        resultado = sesion_texto(sesion, PC_ACK, "BLOQUE_AUDIO");
        if (resultado != ESP_OK) break;
    }
    if (resultado == ESP_OK) resultado = salida_dac_esperar_fin(&salida);
    const esp_err_t cierre = salida_dac_cerrar(&salida);
    if (resultado == ESP_OK) resultado = cierre;
    if (resultado == ESP_OK) {
        char informe[128];
        snprintf(informe, sizeof(informe), "{\"muestras_reproducidas\":%u,\"recortes_dac\":%u}",
                 (unsigned)recibidas, (unsigned)recortes);
        resultado = sesion_texto(sesion, PC_RESULTADO, informe);
    }
    return resultado;
}
