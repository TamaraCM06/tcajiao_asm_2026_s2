#include "sesiones_pc.h"
#include "servicios_sesion.h"
#include "esp_log.h"
#include "esp_timer.h"
#include <inttypes.h>
#include <math.h>
#include <stdio.h>
#include <string.h>

static procesamiento_registro_t registro;
static pc_paquete_t respuesta, entrada;
static uint32_t secuencia_entrada, sesion_actual, recortes[3];
static bool secuencia_iniciada, enlace_comprobado;
static float escala_actual;
static uint64_t tiempo_transporte;

/** Valida orden de paquetes; HELLO permite reconectar tras un reinicio o error. */
esp_err_t sesion_recibir(pc_paquete_t *paquete, unsigned espera_ms)
{
    const esp_err_t resultado = enlace_pc_recibir(paquete, espera_ms);
    if (resultado != ESP_OK) return resultado;
    const bool saludo = paquete->tipo == PC_COMANDO && paquete->longitud == 5 &&
                        !memcmp(paquete->datos, "HELLO", 5);
    if (!saludo && secuencia_iniciada && paquete->secuencia != secuencia_entrada + 1)
        return ESP_ERR_INVALID_RESPONSE;
    secuencia_entrada = paquete->secuencia;
    secuencia_iniciada = true;
    return ESP_OK;
}

/** Publica texto sin mezclar printf/logs con el enlace binario. */
esp_err_t sesion_texto(uint32_t sesion, unsigned tipo, const char *texto)
{
    const size_t longitud = strlen(texto);
    if (longitud > PC_PAYLOAD_MAX) return ESP_ERR_INVALID_SIZE;
    respuesta = (pc_paquete_t){.sesion = sesion, .tipo = tipo, .longitud = longitud};
    memcpy(respuesta.datos, texto, longitud);
    return enlace_pc_enviar(&respuesta);
}

/** Publica PCM16 con indices absolutos y contabiliza la cuantizacion de cada ruta. */
static bool enviar_muestras(unsigned canal, size_t indice, size_t cantidad, const float *muestras)
{
    const int64_t inicio = esp_timer_get_time();
    respuesta = (pc_paquete_t){.sesion = sesion_actual, .tipo = PC_SALIDA,
        .canal = canal, .indice = indice, .longitud = cantidad * 2};
    for (size_t posicion = 0; posicion < cantidad; ++posicion) {
        if (!isfinite(muestras[posicion])) return false;
        const uint16_t pcm = (uint16_t)pc_cuantizar(muestras[posicion], escala_actual, &recortes[canal - 1]);
        respuesta.datos[2 * posicion] = pcm;
        respuesta.datos[2 * posicion + 1] = pcm >> 8;
    }
    const bool correcto = enlace_pc_enviar(&respuesta) == ESP_OK;
    tiempo_transporte += esp_timer_get_time() - inicio;
    return correcto;
}

/** Entrega ambas salidas del mismo intervalo al almacen externo. */
static bool publicar_salidas(size_t indice, size_t cantidad, const float *fir,
    const float *espectral, void *contexto)
{
    (void)contexto;
    return enviar_muestras(2, indice, cantidad, fir) && enviar_muestras(3, indice, cantidad, espectral);
}

/** Procesa una captura acotada y falla ante cualquier interrupcion, sin rellenar huecos. */
static esp_err_t procesar_registro(size_t longitud, bool fisica, bool con_referencia,
    espectral_configuracion_t configuracion)
{
    if (!registro_iniciar(&registro, longitud, con_referencia, configuracion, publicar_salidas, NULL))
        return ESP_ERR_INVALID_ARG;
    memset(recortes, 0, sizeof(recortes)); tiempo_transporte = 0;
    uint64_t total_us = 0;
    uint32_t maximo_us = 0;
    size_t bloques = 0;
    const int64_t inicio_sesion = esp_timer_get_time();
    int64_t ultimo_latido = inicio_sesion;
    esp_err_t resultado = sesion_texto(sesion_actual, PC_ACK, "INICIO");
    if (resultado != ESP_OK) return resultado;
    captura_pico_activar(fisica);
    float mezcla[256], referencia[256];
    trama_spi_bloque_t bloque;
    while (registro.recibidas < longitud) {
        if (fisica) {
            resultado = sesion_recibir(&entrada, 0);
            if (resultado == ESP_OK) {
                if (entrada.sesion != sesion_actual || entrada.tipo != PC_COMANDO ||
                    entrada.longitud != 4 || memcmp(entrada.datos, "PING", 4)) {
                    resultado = ESP_ERR_INVALID_STATE; break;
                }
                ultimo_latido = esp_timer_get_time();
            } else if (resultado != ESP_ERR_TIMEOUT) break;
            if (esp_timer_get_time() - ultimo_latido > 2000000) { resultado = ESP_ERR_TIMEOUT; break; }
            resultado = captura_pico_leer(&bloque);
            if (resultado != ESP_OK) break;
            for (size_t posicion = 0; posicion < 256; ++posicion) {
                const int16_t pcm = pc_cuantizar(bloque.muestras[posicion], escala_actual, &recortes[0]);
                mezcla[posicion] = pcm * (escala_actual / 32768.0f);
            }
        } else {
            resultado = sesion_recibir(&entrada, 2000);
            if (resultado != ESP_OK) break;
            const unsigned canales = con_referencia ? 2 : 1;
            if (entrada.sesion != sesion_actual || entrada.tipo != PC_ENTRADA ||
                entrada.indice != registro.recibidas || entrada.longitud != 256 * 2 * canales) {
                resultado = ESP_ERR_INVALID_RESPONSE; break;
            }
            for (size_t posicion = 0; posicion < 256; ++posicion) {
                const size_t desplazamiento = posicion * canales * 2;
                const int16_t pcm = (int16_t)((uint16_t)entrada.datos[desplazamiento] |
                                   (uint16_t)entrada.datos[desplazamiento + 1] << 8);
                mezcla[posicion] = pcm * (escala_actual / 32768.0f);
                if (con_referencia) {
                    const int16_t limpia = (int16_t)((uint16_t)entrada.datos[desplazamiento + 2] |
                                          (uint16_t)entrada.datos[desplazamiento + 3] << 8);
                    referencia[posicion] = limpia * (escala_actual / 32768.0f);
                }
            }
        }
        if (!enviar_muestras(1, registro.recibidas, 256, mezcla)) { resultado = ESP_FAIL; break; }
        const uint64_t transporte_anterior = tiempo_transporte;
        const int64_t inicio = esp_timer_get_time();
        if (!registro_agregar(&registro, mezcla, con_referencia ? referencia : NULL)) {
            resultado = ESP_FAIL; break;
        }
        const uint32_t duracion = esp_timer_get_time() - inicio - (tiempo_transporte - transporte_anterior);
        total_us += duracion; ++bloques;
        if (duracion > maximo_us) maximo_us = duracion;
        if (!fisica) {
            resultado = sesion_texto(sesion_actual, PC_ACK, "BLOQUE");
            if (resultado != ESP_OK) break;
        }
        resultado = ESP_OK;
    }
    const double tasa_adquisicion = fisica ? captura_pico_tasa() : 0;
    captura_pico_activar(false);
    if (resultado != ESP_OK) return resultado;
    if (fisica && longitud >= 16000 && (tasa_adquisicion < 15200 || tasa_adquisicion > 16800))
        return ESP_ERR_INVALID_RESPONSE;
    const uint64_t transporte_anterior = tiempo_transporte;
    const int64_t inicio = esp_timer_get_time();
    if (!registro_finalizar(&registro)) return ESP_FAIL;
    const uint32_t duracion = esp_timer_get_time() - inicio - (tiempo_transporte - transporte_anterior);
    total_us += duracion; ++bloques;
    if (duracion > maximo_us) maximo_us = duracion;
    return informe_pc_enviar(sesion_actual, &registro, total_us, maximo_us, bloques,
                            inicio_sesion, recortes, fisica, tasa_adquisicion);
}

/** Emite 393216 bytes verificables para medir capacidad real del enlace en la PC. */
static esp_err_t comprobar_enlace(void)
{
    enlace_comprobado = false;
    for (unsigned numero = 0; numero < 128; ++numero) {
        respuesta = (pc_paquete_t){.sesion = sesion_actual, .tipo = PC_SONDA,
                                  .indice = numero * 3072, .longitud = 3072};
        for (unsigned posicion = 0; posicion < 3072; ++posicion)
            respuesta.datos[posicion] = (numero + posicion) % 251;
        esp_err_t resultado = enlace_pc_enviar(&respuesta);
        if (resultado != ESP_OK) return resultado;
    }
    return ESP_OK;
}

/** Atiende operaciones mutuamente excluyentes y conserva errores explicitos. */
esp_err_t sesiones_pc_ejecutar(void)
{
    esp_log_level_set("*", ESP_LOG_NONE);
    esp_err_t resultado = enlace_pc_iniciar();
    if (resultado != ESP_OK) return resultado;
    resultado = captura_pico_iniciar();
    if (resultado != ESP_OK) return resultado;
    while (true) {
        resultado = sesion_recibir(&entrada, 1000);
        if (resultado == ESP_ERR_TIMEOUT) continue;
        if (resultado != ESP_OK) { sesion_texto(sesion_actual, PC_ERROR, "Trama UART corrupta o cola llena; reconectar"); continue; }
        sesion_actual = entrada.sesion;
        if (entrada.tipo != PC_COMANDO || entrada.longitud >= 256) {
            sesion_texto(sesion_actual, PC_ERROR, "Se esperaba un comando"); continue;
        }
        char comando[256]; memcpy(comando, entrada.datos, entrada.longitud); comando[entrada.longitud] = 0;
        if (!strcmp(comando, "HELLO") || !strcmp(comando, "STATUS")) {
            sesion_texto(sesion_actual, PC_ACK, enlace_comprobado ?
                "ASM2 16000 Hz bloque256 FFT1024 salto512; detenido; enlace=1" :
                "ASM2 16000 Hz bloque256 FFT1024 salto512; detenido; enlace=0"); continue;
        }
        if (!strcmp(comando, "LINK_OK")) {
            enlace_comprobado = true; sesion_texto(sesion_actual, PC_ACK, "ENLACE_CONFIRMADO"); continue;
        }
        if (!strcmp(comando, "STOP")) { sesion_texto(sesion_actual, PC_ACK, "DETENIDO"); continue; }
        unsigned longitud = 0, con_referencia = 0, voltios = 0;
        float ganancia = 1;
        char sobrante;
        espectral_configuracion_t configuracion;
        if (!strcmp(comando, "PROBE")) resultado = comprobar_enlace();
        else if (sscanf(comando, "CAPTURE %u %f %f %f %f %c", &longitud,
            &configuracion.frecuencia_minima_hz, &configuracion.ancho_hz,
            &configuracion.factor, &configuracion.umbral_relativo, &sobrante) == 5 &&
            longitud >= 256 && longitud <= 960000 && longitud % 256 == 0 && enlace_comprobado) {
            escala_actual = 3.3f;
            resultado = procesar_registro(longitud, true, false, configuracion);
        } else if (sscanf(comando, "EVALUATE %u %u %f %f %f %f %f %c", &longitud, &con_referencia,
            &escala_actual, &configuracion.frecuencia_minima_hz, &configuracion.ancho_hz,
            &configuracion.factor, &configuracion.umbral_relativo, &sobrante) == 7 &&
            longitud >= 256 && longitud <= 960000 && longitud % 256 == 0 && con_referencia <= 1 &&
            isfinite(escala_actual) && escala_actual > 0 && escala_actual <= 100) {
            resultado = procesar_registro(longitud, false, con_referencia, configuracion);
        } else if (sscanf(comando, "PLAY %u %f %u %f %c", &longitud, &escala_actual,
            &voltios, &ganancia, &sobrante) == 4 && longitud >= 256 && longitud <= 960000 &&
            longitud % 256 == 0 && isfinite(escala_actual) && escala_actual > 0 && escala_actual <= 100 &&
            voltios <= 1 && isfinite(ganancia) && ganancia >= 0 && ganancia <= 100 && enlace_comprobado) {
            resultado = audio_pc_reproducir(sesion_actual, longitud, escala_actual, voltios, ganancia);
        } else resultado = ESP_ERR_INVALID_ARG;
        if (resultado == ESP_OK) sesion_texto(sesion_actual, PC_FIN, "COMPLETADO");
        else {
            char causa[160];
            snprintf(causa, sizeof(causa), "Operacion incompleta: %s; revisar enlace, Pico, parametros o cancelacion", esp_err_to_name(resultado));
            sesion_texto(sesion_actual, PC_ERROR, causa);
        }
    }
}
