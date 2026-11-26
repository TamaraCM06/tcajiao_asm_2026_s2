#include "comandos.h"
#include "conversion_freno.h"
#include "hardware.h"
#include "motor.h"
#include "protocolo_serial.h"
#include "reloj_registro.h"
#include "sensor_optico.h"
#include "servo_freno.h"
#include "esp_app_desc.h"
#include "driver/ledc.h"
#include "esp_timer.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include <inttypes.h>
#include <math.h>
#include <stdio.h>

static configuracion_hardware_t montaje;
static configuracion_ensayo_t ensayo;
static reloj_registro_t reloj;
static esp_timer_handle_t temporizador;
static TaskHandle_t tarea_aplicacion;
static bool hardware_listo;
static const char *motivo_hardware = "no_inicializado";
static bool registrando;
static bool cerrando;
static bool cierre_correcto;
static const char *motivo_cierre;
static uint32_t muestras_enviadas;
static uint32_t numero_ensayo;
static uint32_t pulsos_rechazados_iniciales;
static uint32_t pulsos_rechazados_finales;
static int64_t tiempo_fin_us;
static estado_velocidad_t estado_sensor_anterior;

/* ENSAYO automatico: exige una banda estable de RPM, corta el motor,
 * empieza a registrar y aplica el freno tras la espera pedida. */
#define ESTABILIDAD_TOLERANCIA_RELATIVA 0.07
#define ESTABILIDAD_LECTURAS_REQUERIDAS 5
#define ESTABILIDAD_PERIODO_LECTURA_US 500000
#define ENSAYO_ESPERA_MAXIMA_MS 10000
static bool acelerando;
static bool freno_pendiente;
static double freno_automatico_deg;
static uint32_t espera_freno_ms;
static double velocidad_referencia_estabilidad_rpm = NAN;
static uint32_t lecturas_estables;
static int64_t ultima_lectura_estabilidad_us = -1;
static int64_t ultimo_pulso_estabilidad_us = -1;
static int64_t inicio_aceleracion_us;
static int64_t ultimo_diagnostico_estabilidad_us = -1;

/* Exige una referencia nueva tras iniciar un ensayo o perder una lectura valida. */
static void reiniciar_estabilidad(void)
{
    velocidad_referencia_estabilidad_rpm = NAN;
    lecturas_estables = 0;
    ultima_lectura_estabilidad_us = -1;
    ultimo_pulso_estabilidad_us = -1;
}

/* Solicita una lectura a la tarea coordinadora, sin transmitir desde el callback. */
static void solicitar_muestra(void *argumento)
{
    (void)argumento;
    xTaskNotifyGive(tarea_aplicacion);
}

/* Devuelve errores estructurados que el receptor separa del CSV. */
static void informar_error(const char *motivo)
{
    if (!protocolo_emitir("# {\"tipo\":\"error\",\"motivo\":\"%s\",\"parametros\":{"
        "\"motor_maximo_porcentaje\":%d,\"motor_maximo_impulso_ms\":%d,"
        "\"servo_minimo_deg\":%d,\"servo_maximo_deg\":%d,\"servo_liberado_deg\":%d,"
        "\"estabilidad_tolerancia_porcentaje\":%.1f,\"estabilidad_lecturas\":%d,"
        "\"estabilidad_periodo_ms\":%d,\"espera_maxima_ms\":%d}}", motivo,
        montaje.motor_maximo_porcentaje, montaje.motor_maximo_impulso_ms,
        montaje.servo_minimo_deg, montaje.servo_maximo_deg, montaje.servo_liberado_deg,
        ESTABILIDAD_TOLERANCIA_RELATIVA * 100, ESTABILIDAD_LECTURAS_REQUERIDAS,
        ESTABILIDAD_PERIODO_LECTURA_US / 1000, ENSAYO_ESPERA_MAXIMA_MS) && registrando)
        cierre_correcto = false;
}

/* Publica todos los parametros efectivos sin truncar una unica linea demasiado grande. */
static bool informar_configuracion(void)
{
    bool correcto = protocolo_emitir("# {\"tipo\":\"configuracion\",\"grupo\":\"ensayo\","
        "\"periodo_ms\":%" PRIu32 ",\"duracion_ms\":%" PRIu32 ",\"timeout_ms\":%" PRIu32 ","
        "\"estabilidad_tolerancia_porcentaje\":%.1f,\"estabilidad_lecturas\":%d,"
        "\"estabilidad_periodo_ms\":%d}", ensayo.periodo_ms, ensayo.duracion_ms, ensayo.timeout_ms,
        ESTABILIDAD_TOLERANCIA_RELATIVA * 100, ESTABILIDAD_LECTURAS_REQUERIDAS,
        ESTABILIDAD_PERIODO_LECTURA_US / 1000);
    correcto &= protocolo_emitir("# {\"tipo\":\"configuracion\",\"grupo\":\"sensor\","
        "\"gpio\":%d,\"flanco_bajada\":%s,\"pulsos_por_vuelta\":%" PRIu32 ",\"ventana_pulsos\":%" PRIu32 ","
        "\"minimo_pulso_us\":%" PRIu32 "}", montaje.sensor_gpio, montaje.flanco_bajada ? "true" : "false",
        montaje.pulsos_por_vuelta, montaje.ventana_pulsos, montaje.intervalo_minimo_pulso_us);
    correcto &= protocolo_emitir("# {\"tipo\":\"configuracion\",\"grupo\":\"servo\","
        "\"gpio\":%d,\"frecuencia_hz\":%d,\"minimo_deg\":%d,\"maximo_deg\":%d,\"liberado_deg\":%d,"
        "\"pulso_minimo_us\":%d,\"pulso_maximo_us\":%d}", montaje.servo_gpio,
        montaje.servo_frecuencia_hz, montaje.servo_minimo_deg, montaje.servo_maximo_deg,
        montaje.servo_liberado_deg, montaje.servo_pulso_minimo_us, montaje.servo_pulso_maximo_us);
    correcto &= protocolo_emitir("# {\"tipo\":\"configuracion\",\"grupo\":\"motor\","
        "\"enable_gpio\":%d,\"entrada1_gpio\":%d,\"entrada2_gpio\":%d,\"frecuencia_hz\":%d,"
        "\"maximo_porcentaje\":%d,\"maximo_impulso_ms\":%d}", montaje.motor_enable_gpio,
        montaje.motor_entrada1_gpio, montaje.motor_entrada2_gpio, montaje.motor_frecuencia_hz,
        montaje.motor_maximo_porcentaje, montaje.motor_maximo_impulso_ms);
    return correcto;
}

/* Guarda cambios aplicados con su tiempo ESP32, fuera de las tres columnas numericas. */
static bool informar_evento(const char *evento, double valor, int64_t tiempo_us)
{
    double tiempo_ms = registrando || cerrando ? (tiempo_us - reloj.inicio_us) / 1000.0 : -1.0;
    return protocolo_emitir("# {\"tipo\":\"evento\",\"evento\":\"%s\",\"tiempo_ms\":%.3f,\"valor\":%.3f}",
        evento, tiempo_ms, valor);
}

/* Expone la lectura y banda usadas en la decision, incluida la nueva referencia tras reiniciar. */
static void informar_estabilidad(const lectura_velocidad_t *lectura, double referencia_evaluada_rpm,
    const char *decision, int64_t tiempo_us)
{
    char velocidad[32] = "null", referencia[32] = "null", minimo[32] = "null", maximo[32] = "null";
    char referencia_siguiente[32] = "null";
    if (isfinite(lectura->velocidad_rpm))
        snprintf(velocidad, sizeof(velocidad), "%.3f", lectura->velocidad_rpm);
    if (isfinite(referencia_evaluada_rpm)) {
        snprintf(referencia, sizeof(referencia), "%.3f", referencia_evaluada_rpm);
        snprintf(minimo, sizeof(minimo), "%.3f", referencia_evaluada_rpm * (1 - ESTABILIDAD_TOLERANCIA_RELATIVA));
        snprintf(maximo, sizeof(maximo), "%.3f", referencia_evaluada_rpm * (1 + ESTABILIDAD_TOLERANCIA_RELATIVA));
    }
    if (isfinite(velocidad_referencia_estabilidad_rpm))
        snprintf(referencia_siguiente, sizeof(referencia_siguiente), "%.3f", velocidad_referencia_estabilidad_rpm);
    protocolo_emitir("# {\"tipo\":\"estabilidad\",\"tiempo_ms\":%.3f,\"velocidad_rpm\":%s,"
        "\"referencia_rpm\":%s,\"minimo_rpm\":%s,\"maximo_rpm\":%s,"
        "\"referencia_siguiente_rpm\":%s,\"lecturas\":%" PRIu32 ",\"requeridas\":%d,\"decision\":\"%s\"}",
        (tiempo_us - inicio_aceleracion_us) / 1000.0, velocidad, referencia, minimo, maximo,
        referencia_siguiente, lecturas_estables, ESTABILIDAD_LECTURAS_REQUERIDAS, decision);
    ultimo_diagnostico_estabilidad_us = tiempo_us;
}

/* Finaliza adquisicion antes de liberar; el cierre FIFO se reintenta si la cola estaba llena. */
static void terminar_registro(const char *motivo, bool correcto)
{
    if (!registrando) return;
    esp_timer_stop(temporizador);
    registrando = false;
    cerrando = true;
    tiempo_fin_us = esp_timer_get_time();
    int64_t limite_us = reloj.inicio_us + (int64_t)ensayo.duracion_ms * 1000;
    reloj_registro_cerrar(&reloj, tiempo_fin_us < limite_us ? tiempo_fin_us : limite_us, ensayo.periodo_ms);
    pulsos_rechazados_finales = sensor_optico_leer().pulsos_rechazados;
    motivo_cierre = motivo;
    cierre_correcto &= correcto;
    esp_err_t resultado_motor = motor_ordenar(0, tiempo_fin_us);
    esp_err_t resultado_servo = servo_freno_ordenar(montaje.servo_liberado_deg);
    if (resultado_motor != ESP_OK || resultado_servo != ESP_OK) {
        cierre_correcto = false;
        motivo_cierre = "fallo_actuador";
    }
}

/* Cierra solo despues de los mensajes pendientes y declara transporte incompleto ante huecos. */
static void intentar_cierre(void)
{
    if (!cerrando) return;
    bool completo = cierre_correcto && !protocolo_fallo() &&
        muestras_enviadas == reloj.muestras_producidas && reloj.vencimientos_perdidos == 0;
    if (protocolo_emitir("# {\"tipo\":\"fin\",\"ensayo\":%" PRIu32 ",\"motivo\":\"%s\",\"completo\":%s,"
        "\"producidas\":%" PRIu32 ",\"enviadas\":%" PRIu32 ",\"vencimientos_perdidos\":%" PRIu32 ","
        "\"pulsos_rechazados\":%" PRIu32 ",\"dt_min_us\":%" PRId64 ",\"dt_max_us\":%" PRId64 ","
        "\"tiempo_fin_ms\":%.3f,\"liberado_deg\":%d}", numero_ensayo, motivo_cierre,
        completo ? "true" : "false", reloj.muestras_producidas, muestras_enviadas,
        reloj.vencimientos_perdidos, pulsos_rechazados_finales - pulsos_rechazados_iniciales,
        reloj.intervalo_minimo_us, reloj.intervalo_maximo_us,
        (tiempo_fin_us - reloj.inicio_us) / 1000.0, montaje.servo_liberado_deg)) cerrando = false;
}

/* Toma una instantanea real; si hubo un retraso no repite muestras para cubrirlo. */
static void adquirir_muestra(void)
{
    lectura_velocidad_t lectura = sensor_optico_leer();
    if (!reloj_registro_muestrear(&reloj, lectura.tiempo_lectura_us, ensayo.periodo_ms)) return;
    if (lectura.estado != estado_sensor_anterior) {
        if (!informar_evento("estado_sensor", lectura.estado, lectura.tiempo_lectura_us)) {
            terminar_registro("cola_llena", false);
            return;
        }
        estado_sensor_anterior = lectura.estado;
    }
    if (!protocolo_emitir("%.3f,%.3f,%.3f", (lectura.tiempo_lectura_us - reloj.inicio_us) / 1000.0,
        servo_freno_angulo(), lectura.velocidad_rpm)) {
        terminar_registro("cola_llena", false);
        return;
    }
    ++muestras_enviadas;
}

/* Exige calibracion, parametros y velocidad recientes antes de cortar el motor. */
static void iniciar_registro(void)
{
    if (!hardware_listo) { informar_error(motivo_hardware); return; }
    if (registrando || cerrando) { informar_error("ensayo_activo"); return; }
    if (!ensayo.periodo_ms) { informar_error("falta_CONFIG"); return; }
    if (protocolo_fallo()) { informar_error("fallo_uart_reiniciar"); return; }
    if (!servo_freno_liberado()) { informar_error("ordenar_freno_liberado"); return; }
    lectura_velocidad_t lectura = sensor_optico_leer();
    if (lectura.estado != VELOCIDAD_VALIDA) { informar_error("velocidad_no_disponible"); return; }
    if (protocolo_espacios() < 10) { informar_error("transmision_ocupada"); return; }
    if (motor_ordenar(0, esp_timer_get_time()) != ESP_OK) { informar_error("fallo_corte_motor"); return; }
    reloj_registro_iniciar(&reloj, esp_timer_get_time());
    registrando = true;
    cierre_correcto = true;
    muestras_enviadas = 0;
    ++numero_ensayo;
    pulsos_rechazados_iniciales = lectura.pulsos_rechazados;
    estado_sensor_anterior = lectura.estado;
    ulTaskNotifyTake(pdTRUE, 0);
    protocolo_emitir("# {\"tipo\":\"inicio\",\"protocolo\":1,\"ensayo\":%" PRIu32 ","
        "\"firmware\":\"%s\",\"corte_motor_us\":%" PRId64 "}", numero_ensayo,
        esp_app_get_description()->version, reloj.inicio_us);
    if (!informar_configuracion() || !protocolo_emitir("tiempo_ms,freno_deg,velocidad_rpm")) {
        terminar_registro("cola_llena", false);
        return;
    }
    if (esp_timer_start_periodic(temporizador, (uint64_t)ensayo.periodo_ms * 1000) != ESP_OK) {
        terminar_registro("fallo_temporizador", false);
        return;
    }
    adquirir_muestra();
}

/* Valida ENSAYO completo antes de mover nada y arranca la aceleracion vigilada. */
static void iniciar_ensayo_automatico(const comando_t *comando)
{
    double porcentaje = comando->valores[0], angulo = comando->valores[1], espera = comando->valores[2];
    uint32_t pulso_us;
    if (!hardware_listo) { informar_error(motivo_hardware); return; }
    if (registrando || acelerando) { informar_error("ensayo_activo"); return; }
    if (!ensayo.periodo_ms) { informar_error("falta_CONFIG"); return; }
    if (!servo_freno_liberado()) { informar_error("ordenar_freno_liberado"); return; }
    if (espera < 0 || espera > ENSAYO_ESPERA_MAXIMA_MS || floor(espera) != espera ||
        !freno_convertir_pulso(&montaje, angulo, &pulso_us)) {
        informar_error("parametros_ENSAYO_invalidos"); return;
    }
    int64_t ahora = esp_timer_get_time();
    if (porcentaje <= 0 || motor_ordenar(porcentaje, ahora) != ESP_OK) { informar_error("mando_rechazado"); return; }
    acelerando = true;
    freno_pendiente = false;
    freno_automatico_deg = angulo;
    espera_freno_ms = (uint32_t)espera;
    reiniciar_estabilidad();
    inicio_aceleracion_us = ahora;
    ultimo_diagnostico_estabilidad_us = -1;
    informar_evento("motor", porcentaje, ahora);
}

/* Cuenta cinco lecturas nuevas, separadas 500 ms, dentro de una banda fija de +/-7 %. */
static void vigilar_ensayo_automatico(int64_t tiempo_us)
{
    if (acelerando) {
        if (motor_porcentaje() <= 0) {  /* limite de impulso, STOP o MOTOR 0 */
            acelerando = false;
            informar_error("velocidad_maxima_no_alcanzada");
            return;
        }
        lectura_velocidad_t lectura = sensor_optico_leer();
        if (lectura.estado != VELOCIDAD_VALIDA || !isfinite(lectura.velocidad_rpm) ||
            lectura.velocidad_rpm <= 0) {
            double referencia_anterior_rpm = velocidad_referencia_estabilidad_rpm;
            bool reinicia_conteo = lecturas_estables > 0;
            velocidad_referencia_estabilidad_rpm = NAN;
            lecturas_estables = 0;
            /* Conserva la cadencia aun si alternan lecturas validas e invalidas. */
            if (reinicia_conteo || ultimo_diagnostico_estabilidad_us < 0 ||
                tiempo_us - ultimo_diagnostico_estabilidad_us >= ESTABILIDAD_PERIODO_LECTURA_US)
                informar_estabilidad(&lectura, referencia_anterior_rpm, "invalida", tiempo_us);
            return;
        }
        if (lectura.ultimo_pulso_us <= ultimo_pulso_estabilidad_us ||
            (ultima_lectura_estabilidad_us >= 0 &&
             tiempo_us - ultima_lectura_estabilidad_us < ESTABILIDAD_PERIODO_LECTURA_US)) return;
        ultima_lectura_estabilidad_us = tiempo_us;
        ultimo_pulso_estabilidad_us = lectura.ultimo_pulso_us;
        double referencia_evaluada_rpm = velocidad_referencia_estabilidad_rpm;
        const char *decision;
        if (!isfinite(velocidad_referencia_estabilidad_rpm) ||
            fabs(lectura.velocidad_rpm - velocidad_referencia_estabilidad_rpm) >
                velocidad_referencia_estabilidad_rpm * ESTABILIDAD_TOLERANCIA_RELATIVA) {
            decision = isfinite(velocidad_referencia_estabilidad_rpm) ? "fuera" : "referencia";
            if (!isfinite(referencia_evaluada_rpm)) referencia_evaluada_rpm = lectura.velocidad_rpm;
            velocidad_referencia_estabilidad_rpm = lectura.velocidad_rpm;
            lecturas_estables = 1;
        } else {
            ++lecturas_estables;
            decision = lecturas_estables >= ESTABILIDAD_LECTURAS_REQUERIDAS ? "aceptada" : "dentro";
        }
        informar_estabilidad(&lectura, referencia_evaluada_rpm, decision, tiempo_us);
        if (lecturas_estables >= ESTABILIDAD_LECTURAS_REQUERIDAS) {
            acelerando = false;
            informar_evento("velocidad_maxima", velocidad_referencia_estabilidad_rpm, tiempo_us);
            iniciar_registro();
            freno_pendiente = registrando;
        }
        return;
    }
    if (freno_pendiente && !registrando) freno_pendiente = false;
    if (freno_pendiente && tiempo_us - reloj.inicio_us >= (int64_t)espera_freno_ms * 1000) {
        freno_pendiente = false;
        if (servo_freno_ordenar(freno_automatico_deg) != ESP_OK) {
            informar_error("mando_rechazado");
            terminar_registro("fallo_actuador", false);
            return;
        }
        if (!informar_evento("freno", freno_automatico_deg, tiempo_us)) terminar_registro("cola_llena", false);
    }
}

/* Consulta estado sin enviar NaN como un numero JSON invalido. */
static void informar_estado(void)
{
    char angulo[32] = "null", velocidad[32] = "null";
    if (isfinite(servo_freno_angulo())) snprintf(angulo, sizeof(angulo), "%.3f", servo_freno_angulo());
    lectura_velocidad_t lectura = sensor_optico_leer();
    if (hardware_listo && isfinite(lectura.velocidad_rpm))
        snprintf(velocidad, sizeof(velocidad), "%.1f", lectura.velocidad_rpm);
    protocolo_emitir("# {\"tipo\":\"estado\",\"hardware_listo\":%s,\"motivo\":\"%s\","
        "\"registrando\":%s,\"acelerando\":%s,\"motor_porcentaje\":%.3f,\"freno_deg\":%s,"
        "\"velocidad_rpm\":%s}", hardware_listo ? "true" : "false", motivo_hardware,
        registrando ? "true" : "false", acelerando ? "true" : "false", motor_porcentaje(), angulo, velocidad);
}

/* Procesa ordenes completas; CONFIG y reactivacion de motor quedan bloqueados en captura. */
static void ejecutar_comando(const char *linea)
{
    comando_t comando = comando_interpretar(linea);
    if (comando.tipo == COMANDO_STATUS) { informar_estado(); return; }
    if (comando.tipo == COMANDO_STOP) {
        acelerando = freno_pendiente = false;
        if (registrando) terminar_registro("STOP", true);
        else if (!cerrando) {
            if (hardware_listo) {
                esp_err_t resultado_motor = motor_ordenar(0, esp_timer_get_time());
                esp_err_t resultado_servo = servo_freno_ordenar(montaje.servo_liberado_deg);
                if (resultado_motor != ESP_OK || resultado_servo != ESP_OK) {
                    informar_error("fallo_actuador"); return;
                }
            }
            protocolo_emitir("# {\"tipo\":\"ok\",\"comando\":\"STOP\"}");
        }
        return;
    }
    if (cerrando) { informar_error("cierre_pendiente"); return; }
    if (comando.tipo == COMANDO_CONFIG_CONSULTA) {
        if (!registrando) informar_configuracion();
        else informar_error("ensayo_activo");
        return;
    }
    if (comando.tipo == COMANDO_CONFIG) {
        configuracion_ensayo_t nueva_configuracion;
        if (registrando || motor_porcentaje() > 0) { informar_error("CONFIG_requiere_reposo"); return; }
        if (!comando_configuracion(&comando, montaje.intervalo_minimo_pulso_us, &nueva_configuracion)) {
            informar_error("tiempos_CONFIG_invalidos"); return;
        }
        ensayo = nueva_configuracion;
        sensor_optico_configurar_timeout((int64_t)ensayo.timeout_ms * 1000);
        protocolo_emitir("# {\"tipo\":\"ok\",\"comando\":\"CONFIG\",\"periodo_ms\":%" PRIu32
            ",\"duracion_ms\":%" PRIu32 ",\"timeout_ms\":%" PRIu32 "}",
            ensayo.periodo_ms, ensayo.duracion_ms, ensayo.timeout_ms);
        return;
    }
    if (comando.tipo == COMANDO_ENSAYO) { iniciar_ensayo_automatico(&comando); return; }
    if (comando.tipo != COMANDO_MOTOR && comando.tipo != COMANDO_FRENO) {
        informar_error("comando_invalido"); return;
    }
    if (!hardware_listo) { informar_error(motivo_hardware); return; }
    esp_err_t resultado;
    if (comando.tipo == COMANDO_MOTOR) {
        if (comando.valores[0] > 0 && (registrando || !ensayo.periodo_ms || !servo_freno_liberado())) {
            informar_error("motor_requiere_reposo_CONFIG_y_liberacion"); return;
        }
        resultado = motor_ordenar(comando.valores[0], esp_timer_get_time());
    } else {
        if (motor_porcentaje() > 0) { informar_error("cortar_motor_antes_de_frenar"); return; }
        resultado = servo_freno_ordenar(comando.valores[0]);
    }
    if (resultado != ESP_OK) {
        informar_error("mando_rechazado");
        if (registrando && resultado != ESP_ERR_INVALID_ARG) terminar_registro("fallo_actuador", false);
        return;
    }
    if (!informar_evento(comando.tipo == COMANDO_MOTOR ? "motor" : "freno",
        comando.valores[0], esp_timer_get_time()) && registrando) terminar_registro("cola_llena", false);
}

/* Inicializa hardware solo tras validar todos los GPIO y parametros fisicos. */
static void preparar_hardware(void)
{
    montaje = hardware_cargar();
    motivo_hardware = hardware_validar(&montaje);
    if (motivo_hardware) return;
    esp_err_t resultado = motor_iniciar(&montaje);
    if (resultado == ESP_OK) resultado = servo_freno_iniciar(&montaje);
    /* ledc_set_duty_and_update (servo y motor) exige el servicio de fades, y su
     * instalacion requiere LEDC ya configurado: va despues de ambos iniciar. */
    if (resultado == ESP_OK) resultado = ledc_fade_func_install(0);
    if (resultado == ESP_OK) resultado = sensor_optico_iniciar(&montaje);
    hardware_listo = resultado == ESP_OK;
    motivo_hardware = hardware_listo ? "listo" : "fallo_inicializacion";
}

/* Coordina serial y muestras notificadas; mantiene el motor vigilado aun sin PC. */
void app_main(void)
{
    if (protocolo_iniciar() != ESP_OK) return;
    tarea_aplicacion = xTaskGetCurrentTaskHandle();
    vTaskPrioritySet(NULL, 4);
    preparar_hardware();
    esp_timer_create_args_t argumentos = {.callback = solicitar_muestra, .name = "asm2_registro"};
    if (esp_timer_create(&argumentos, &temporizador) != ESP_OK) {
        hardware_listo = false;
        motivo_hardware = "fallo_temporizador";
    }
    protocolo_emitir("# {\"tipo\":\"listo\",\"protocolo\":1,\"firmware\":\"%s\"}",
        esp_app_get_description()->version);
    informar_estado();
    for (;;) {
        int64_t tiempo_us = esp_timer_get_time();
        if (motor_vigilar(tiempo_us)) informar_evento("limite_impulso_motor", 0, tiempo_us);
        vigilar_ensayo_automatico(tiempo_us);
        if (protocolo_fallo() && motor_porcentaje() > 0) motor_ordenar(0, tiempo_us);
        if (registrando && protocolo_fallo()) terminar_registro("fallo_uart", false);
        if (registrando && tiempo_us - reloj.inicio_us >= (int64_t)ensayo.duracion_ms * 1000)
            terminar_registro("duracion", true);
        if (ulTaskNotifyTake(pdTRUE, 0) && registrando) adquirir_muestra();
        intentar_cierre();
        char linea[COMANDO_LONGITUD_MAXIMA];
        int recibida = protocolo_recibir(linea, sizeof(linea));
        if (recibida == 1) ejecutar_comando(linea);
        else if (recibida < 0) informar_error("linea_descartada");
        vTaskDelay(pdMS_TO_TICKS(1));
    }
}
