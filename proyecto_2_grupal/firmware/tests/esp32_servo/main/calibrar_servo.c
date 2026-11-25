#include "comandos.h"
#include "driver/ledc.h"
#include "esp_timer.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "protocolo_serial.h"
#include "sensor_optico.h"

#include <math.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

enum {
    GPIO_SERVO = 18,
    GPIO_SENSOR = 27,
    PULSOS_POR_VUELTA = 20,
    INTERVALO_MINIMO_ENTRE_FLANCOS_US = 200,
    SIN_PULSOS_US = 1000000,
    PERIODO_REGISTRO_US = 1000000,
    FRECUENCIA_PWM_HZ = 50,
    PERIODO_PWM_US = 1000000 / FRECUENCIA_PWM_HZ,
    ESCALA_PWM = 1 << 16,
    PULSO_MINIMO_US = 1000,
    PULSO_MAXIMO_US = 2200,
    PULSO_REFERENCIA_CERO_US = 500,
    RANGO_REFERENCIA_US = 2000,
    RANGO_REFERENCIA_DEG = 180,
    PASO_INICIAL_DEG = 2,
    PRUEBA_LIBERADO_US = 1500,
    PRUEBA_FRENO_US = 2194,
    DURACION_FRENADO_INICIAL_S = 15,
    DURACION_FRENADO_MAXIMA_S = 30,
    PAUSA_ENTRE_PASOS_US = 350000,
    INACTIVIDAD_US = 15000000
};

typedef struct {
    bool pwm_activo;
    bool prueba_manual;
    int pulso_us;
    int minimo_us;
    int maximo_us;
    int paso_us;
    int liberado_us;
    int contacto_us;
    int64_t ultimo_movimiento_us;
    int64_t ultima_orden_us;
    int64_t fin_frenado_us;
    int64_t inicio_registro_us;
    int64_t proxima_muestra_us;
    int64_t referencia_rpm_us;
    uint32_t pulsos_referencia_rpm;
    double rpm_registro;
} calibracion_t;

/* Equivalencia nominal del montaje anterior, sin lectura del eje. */
static double grados_de_intervalo(int intervalo_us)
{
    return (double)intervalo_us * RANGO_REFERENCIA_DEG / RANGO_REFERENCIA_US;
}

static void emitir_muestra(const calibracion_t *calibracion, int64_t ahora_us)
{
    const double tiempo_s = (ahora_us - calibracion->inicio_registro_us) / 1000000.0;
    const double angulo = grados_de_intervalo(calibracion->pulso_us - PULSO_REFERENCIA_CERO_US);
    protocolo_emitir("%.3f,%.2f,%.1f", tiempo_s, calibracion->rpm_registro, angulo);
}

static void registrar_muestra(calibracion_t *calibracion, int64_t ahora_us)
{
    const lectura_velocidad_t lectura = sensor_optico_leer();
    const int64_t intervalo_us = lectura.tiempo_lectura_us - calibracion->referencia_rpm_us;
    // Evita estimar RPM sobre una fraccion muy corta al cerrar la tabla.
    if (intervalo_us >= PERIODO_REGISTRO_US / 2) {
        const uint32_t pulsos = lectura.pulsos_aceptados - calibracion->pulsos_referencia_rpm;
        calibracion->rpm_registro = 60000000.0 * pulsos / PULSOS_POR_VUELTA / intervalo_us;
        calibracion->referencia_rpm_us = lectura.tiempo_lectura_us;
        calibracion->pulsos_referencia_rpm = lectura.pulsos_aceptados;
    } else if (lectura.estado == VELOCIDAD_SIN_PULSOS) {
        calibracion->rpm_registro = 0.0;
    }
    emitir_muestra(calibracion, ahora_us);
}

static void iniciar_registro(calibracion_t *calibracion, int64_t ahora_us)
{
    const lectura_velocidad_t lectura = sensor_optico_leer();
    calibracion->inicio_registro_us = ahora_us;
    calibracion->proxima_muestra_us = ahora_us + PERIODO_REGISTRO_US;
    calibracion->referencia_rpm_us = lectura.tiempo_lectura_us;
    calibracion->pulsos_referencia_rpm = lectura.pulsos_aceptados;
    calibracion->rpm_registro = !lectura.pulsos_aceptados || lectura.estado == VELOCIDAD_SIN_PULSOS ? 0.0 : NAN;
    protocolo_emitir("tiempo_s,rpm,servo_deg");
    emitir_muestra(calibracion, ahora_us);
}

static void terminar_registro(calibracion_t *calibracion, int64_t ahora_us)
{
    if (!calibracion->proxima_muestra_us) return;
    if (ahora_us > calibracion->inicio_registro_us) registrar_muestra(calibracion, ahora_us);
    calibracion->proxima_muestra_us = 0;
    protocolo_emitir("# Fin de la tabla.");
}

static void informar_estado(const calibracion_t *calibracion)
{
    char angulo[16] = "pendiente";
    if (calibracion->pulso_us) {
        snprintf(angulo, sizeof(angulo), "%.1f",
            grados_de_intervalo(calibracion->pulso_us - PULSO_REFERENCIA_CERO_US));
    }
    protocolo_emitir("PWM=%s ultimo_pulso_us=%d angulo_nominal_deg=%s paso_nominal_deg=%.1f liberado_us=%d contacto_us=%d modo=%s",
        calibracion->pwm_activo ? "activo" : "apagado", calibracion->pulso_us,
        angulo, grados_de_intervalo(calibracion->paso_us),
        calibracion->liberado_us, calibracion->contacto_us,
        calibracion->prueba_manual ? "prueba_manual" : "calibracion");
    if (calibracion->contacto_us) {
        protocolo_emitir("liberado_nominal_deg=%.1f contacto_nominal_deg=%.1f",
            grados_de_intervalo(calibracion->liberado_us - PULSO_REFERENCIA_CERO_US),
            grados_de_intervalo(calibracion->contacto_us - PULSO_REFERENCIA_CERO_US));
    }
}

static int convertir_paso_us(double grados)
{
    return (int)(grados * RANGO_REFERENCIA_US / RANGO_REFERENCIA_DEG + 0.5);
}

static void configurar_paso(calibracion_t *calibracion, const char *argumentos)
{
    char *fin;
    double grados = strtod(argumentos, &fin);
    if (fin == argumentos || !(grados >= 0.5 && grados <= 10) || fin[strspn(fin, " \t")]) {
        protocolo_emitir("Uso: PASO grados (0.5 a 10; usa punto decimal).");
        return;
    }
    calibracion->paso_us = convertir_paso_us(grados);
    informar_estado(calibracion);
}

static void cortar_pwm(calibracion_t *calibracion)
{
    if (ledc_stop(LEDC_LOW_SPEED_MODE, LEDC_CHANNEL_0, 0) == ESP_OK) {
        calibracion->pwm_activo = false;
        calibracion->prueba_manual = false;
        calibracion->fin_frenado_us = 0;
    } else {
        protocolo_emitir("Fallo al cortar PWM. Desconecta la alimentacion del servo.");
    }
}

static bool aplicar_pulso(calibracion_t *calibracion, int pulso_us, int64_t ahora_us)
{
    uint32_t duty = ((uint32_t)pulso_us * ESCALA_PWM + PERIODO_PWM_US / 2) / PERIODO_PWM_US;
    esp_err_t resultado = ledc_set_duty(LEDC_LOW_SPEED_MODE, LEDC_CHANNEL_0, duty);
    if (resultado == ESP_OK) resultado = ledc_update_duty(LEDC_LOW_SPEED_MODE, LEDC_CHANNEL_0);
    if (resultado != ESP_OK) {
        cortar_pwm(calibracion);
        protocolo_emitir("Fallo PWM: %s", esp_err_to_name(resultado));
        return false;
    }
    calibracion->pwm_activo = true;
    calibracion->pulso_us = pulso_us;
    calibracion->ultimo_movimiento_us = ahora_us;
    calibracion->ultima_orden_us = ahora_us;
    return true;
}

static void iniciar_prueba(calibracion_t *calibracion, int64_t ahora_us)
{
    if (calibracion->prueba_manual && !calibracion->proxima_muestra_us) {
        iniciar_registro(calibracion, ahora_us);
        return;
    }
    if (calibracion->pwm_activo) {
        protocolo_emitir("Envia STOP antes de iniciar PRUEBA.");
        return;
    }
    if (aplicar_pulso(calibracion, PRUEBA_LIBERADO_US, ahora_us)) {
        calibracion->prueba_manual = true;
        protocolo_emitir("Prueba lista. Corta la alimentacion del motor antes de enviar FRENAR.");
        informar_estado(calibracion);
        iniciar_registro(calibracion, ahora_us);
    }
}

static void liberar_prueba(calibracion_t *calibracion, int64_t ahora_us)
{
    if (aplicar_pulso(calibracion, PRUEBA_LIBERADO_US, ahora_us)) {
        calibracion->fin_frenado_us = 0;
        protocolo_emitir("Freno liberado.");
        informar_estado(calibracion);
    }
    terminar_registro(calibracion, ahora_us);
}

static bool es_comando_frenar(const char *linea)
{
    return !strcmp(linea, "FRENAR") || !strncmp(linea, "FRENAR ", sizeof("FRENAR ") - 1);
}

static void frenar_prueba(calibracion_t *calibracion, const char *argumentos, int64_t ahora_us)
{
    int duracion_s = DURACION_FRENADO_INICIAL_S;
    argumentos += strspn(argumentos, " \t");
    if (*argumentos) {
        char *fin;
        long valor = strtol(argumentos, &fin, 10);
        if (fin == argumentos || valor < 1 || valor > DURACION_FRENADO_MAXIMA_S ||
            fin[strspn(fin, " \t")]) {
            protocolo_emitir("Uso: FRENAR [segundos] (entero de 1 a %d).", DURACION_FRENADO_MAXIMA_S);
            return;
        }
        duracion_s = (int)valor;
    }

    if (calibracion->fin_frenado_us) {
        protocolo_emitir("Freno ya aplicado. Usa LIBERAR para soltarlo antes.");
    } else if (ahora_us - calibracion->ultimo_movimiento_us < PAUSA_ENTRE_PASOS_US) {
        protocolo_emitir("Espera a que el servo termine de liberar y vuelve a enviar FRENAR.");
    } else if (aplicar_pulso(calibracion, PRUEBA_FRENO_US, ahora_us)) {
        calibracion->fin_frenado_us = ahora_us + (int64_t)duracion_s * 1000000;
        protocolo_emitir("Freno aplicado por %d s.", duracion_s);
        informar_estado(calibracion);
        if (!calibracion->proxima_muestra_us) iniciar_registro(calibracion, ahora_us);
    } else {
        terminar_registro(calibracion, ahora_us);
    }
}

static void ejecutar_prueba(calibracion_t *calibracion, const char *linea, int64_t ahora_us)
{
    if (!strcmp(linea, "LIBERAR")) {
        liberar_prueba(calibracion, ahora_us);
    } else if (es_comando_frenar(linea)) {
        frenar_prueba(calibracion, linea + sizeof("FRENAR") - 1, ahora_us);
    } else {
        protocolo_emitir("En modo prueba usa FRENAR, LIBERAR, ESTADO o STOP.");
    }
}

static void armar(calibracion_t *calibracion, const char *argumentos, int64_t ahora_us)
{
    if (calibracion->pwm_activo || calibracion->contacto_us) {
        protocolo_emitir("ARMAR requiere PWM apagado y calibracion sin cerrar.");
        return;
    }

    int pulsos[3];
    for (size_t indice = 0; indice < sizeof(pulsos) / sizeof(pulsos[0]); ++indice) {
        char *fin;
        long valor = strtol(argumentos, &fin, 10);
        if (fin == argumentos || valor < PULSO_MINIMO_US || valor > PULSO_MAXIMO_US ||
            (*fin && *fin != ' ' && *fin != '\t')) {
            protocolo_emitir("Uso: ARMAR pulso_us minimo_us maximo_us (%d a %d us).",
                PULSO_MINIMO_US, PULSO_MAXIMO_US);
            return;
        }
        pulsos[indice] = (int)valor;
        argumentos = fin;
    }
    const int inicial_us = pulsos[0];
    const int minimo_us = pulsos[1];
    const int maximo_us = pulsos[2];
    if (argumentos[strspn(argumentos, " \t")] || minimo_us >= maximo_us ||
        inicial_us < minimo_us || inicial_us > maximo_us) {
        protocolo_emitir("El pulso inicial debe quedar dentro del intervalo elegido.");
        return;
    }
    if (calibracion->liberado_us && inicial_us != calibracion->liberado_us) {
        protocolo_emitir("Rearma en la posicion liberada registrada: %d us.", calibracion->liberado_us);
        return;
    }
    if (aplicar_pulso(calibracion, inicial_us, ahora_us)) {
        calibracion->minimo_us = minimo_us;
        calibracion->maximo_us = maximo_us;
        informar_estado(calibracion);
    }
}

static void ejecutar(calibracion_t *calibracion, const char *linea, int64_t ahora_us)
{
    if (!strcmp(linea, "AYUDA")) {
        protocolo_emitir("ARMAR pulso_us minimo_us maximo_us | PASO grados | + | - | LIBERADO | CONTACTO | ESTADO | STOP");
        protocolo_emitir("PASO admite 0.5 a 10 grados nominales. En calibracion el PWM se corta por inactividad a los 15 s.");
        protocolo_emitir("Frenado con motor externo: PRUEBA | FRENAR [segundos] | LIBERAR | STOP.");
        protocolo_emitir("FRENAR dura %d s por defecto. Puedes pedir de 1 a %d s.",
            DURACION_FRENADO_INICIAL_S, DURACION_FRENADO_MAXIMA_S);
        protocolo_emitir("PRUEBA inicia el CSV de tiempo, RPM y angulo nominal; termina al liberar o con STOP.");
    } else if (!strcmp(linea, "ESTADO")) {
        informar_estado(calibracion);
    } else if (!strcmp(linea, "STOP")) {
        cortar_pwm(calibracion);
        terminar_registro(calibracion, ahora_us);
        informar_estado(calibracion);
    } else if (!strcmp(linea, "PRUEBA")) {
        iniciar_prueba(calibracion, ahora_us);
    } else if (calibracion->prueba_manual) {
        ejecutar_prueba(calibracion, linea, ahora_us);
    } else if (es_comando_frenar(linea) || !strcmp(linea, "LIBERAR")) {
        protocolo_emitir("Envia PRUEBA para preparar el freno.");
    } else if (!strncmp(linea, "ARMAR ", 6)) {
        armar(calibracion, linea + 6, ahora_us);
    } else if (!strncmp(linea, "PASO ", 5)) {
        configurar_paso(calibracion, linea + 5);
    } else if (!calibracion->pwm_activo) {
        protocolo_emitir("PWM apagado. Usa AYUDA para consultar los comandos.");
    } else if (!strcmp(linea, "LIBERADO")) {
        calibracion->liberado_us = calibracion->pulso_us;
        calibracion->ultima_orden_us = ahora_us;
        informar_estado(calibracion);
    } else if (!strcmp(linea, "CONTACTO")) {
        if (!calibracion->liberado_us || calibracion->liberado_us == calibracion->pulso_us) {
            protocolo_emitir("Marca primero LIBERADO en una posicion distinta.");
            return;
        }
        calibracion->contacto_us = calibracion->pulso_us;
        cortar_pwm(calibracion);
        informar_estado(calibracion);
    } else if (!strcmp(linea, "+") || !strcmp(linea, "-")) {
        const int nuevo_us = calibracion->pulso_us + (linea[0] == '+' ? calibracion->paso_us : -calibracion->paso_us);
        if (nuevo_us < calibracion->minimo_us || nuevo_us > calibracion->maximo_us) {
            protocolo_emitir("Limite de recorrido. Pulso actual: %d us.", calibracion->pulso_us);
            return;
        }
        if (ahora_us - calibracion->ultimo_movimiento_us < PAUSA_ENTRE_PASOS_US) {
            protocolo_emitir("Espera a que el servo se asiente y vuelve a enviar el paso.");
            return;
        }
        if (aplicar_pulso(calibracion, nuevo_us, ahora_us)) informar_estado(calibracion);
    } else {
        protocolo_emitir("Comando invalido. Usa AYUDA.");
    }
}

void app_main(void)
{
    const ledc_timer_config_t temporizador = {
        .speed_mode = LEDC_LOW_SPEED_MODE,
        .duty_resolution = LEDC_TIMER_16_BIT,
        .timer_num = LEDC_TIMER_0,
        .freq_hz = FRECUENCIA_PWM_HZ,
        .clk_cfg = LEDC_USE_APB_CLK,
    };
    const ledc_channel_config_t canal = {
        .gpio_num = GPIO_SERVO,
        .speed_mode = LEDC_LOW_SPEED_MODE,
        .channel = LEDC_CHANNEL_0,
        .timer_sel = LEDC_TIMER_0,
        .duty = 0,
    };
    ESP_ERROR_CHECK(ledc_timer_config(&temporizador));
    ESP_ERROR_CHECK(ledc_channel_config(&canal));
    ESP_ERROR_CHECK(ledc_stop(LEDC_LOW_SPEED_MODE, LEDC_CHANNEL_0, 0));
    const configuracion_hardware_t sensor = {
        .sensor_gpio = GPIO_SENSOR,
        .flanco_bajada = true,
        .pulsos_por_vuelta = PULSOS_POR_VUELTA,
        .intervalo_minimo_pulso_us = INTERVALO_MINIMO_ENTRE_FLANCOS_US,
    };
    ESP_ERROR_CHECK(sensor_optico_iniciar(&sensor));
    sensor_optico_configurar_timeout(SIN_PULSOS_US);
    ESP_ERROR_CHECK(protocolo_iniciar());
    protocolo_emitir("Servo GPIO18 y sensor GPIO27, 20 pulsos/vuelta. PWM apagado. Escribe AYUDA.");

    calibracion_t calibracion = {.paso_us = convertir_paso_us(PASO_INICIAL_DEG)};
    for (;;) {
        const int64_t ahora_us = esp_timer_get_time();
        const bool fallo_serial = protocolo_fallo();
        const bool inactividad_calibracion = !calibracion.prueba_manual &&
            ahora_us - calibracion.ultima_orden_us >= INACTIVIDAD_US;
        if (calibracion.pwm_activo &&
            (inactividad_calibracion || fallo_serial)) {
            cortar_pwm(&calibracion);
            terminar_registro(&calibracion, ahora_us);
            informar_estado(&calibracion);
        } else if (calibracion.fin_frenado_us && ahora_us >= calibracion.fin_frenado_us) {
            liberar_prueba(&calibracion, ahora_us);
        }
        if (!fallo_serial) {
            char linea[COMANDO_LONGITUD_MAXIMA];
            int recibido = protocolo_recibir(linea, sizeof(linea));
            if (recibido == 1) ejecutar(&calibracion, linea, ahora_us);
            if (recibido < 0) protocolo_emitir("Linea descartada. Usa AYUDA.");
        }
        if (calibracion.proxima_muestra_us && ahora_us >= calibracion.proxima_muestra_us) {
            registrar_muestra(&calibracion, ahora_us);
            const int64_t atraso_us = ahora_us - calibracion.proxima_muestra_us;
            calibracion.proxima_muestra_us += (atraso_us / PERIODO_REGISTRO_US + 1) * PERIODO_REGISTRO_US;
        }
        vTaskDelay(1);
    }
}
