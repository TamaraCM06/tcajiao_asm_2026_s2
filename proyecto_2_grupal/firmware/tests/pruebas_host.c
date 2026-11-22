/* Ejecuta codigo de produccion con fronteras SDK simuladas; no acredita hardware. */
#include <assert.h>
#include <stdarg.h>
#include <stdlib.h>
#include <string.h>
#include "conversion_freno.h"
#include "../src/aplicacion.c"

static int64_t tiempo_virtual_us;
static double angulo_virtual;
static double motor_virtual;
static bool falla_motor;
static unsigned ordenes_motor;
static unsigned ordenes_servo;
static unsigned cantidad_mensajes;
static unsigned limite_mensajes;
static char mensajes[256][512];
static lectura_velocidad_t velocidad_virtual;

/* Devuelve tiempo virtual controlado por cada escenario. */
int64_t esp_timer_get_time(void) { return tiempo_virtual_us; }
/* Simula parada del temporizador sin planificar tareas. */
esp_err_t esp_timer_stop(esp_timer_handle_t identificador) { (void)identificador; return ESP_OK; }
/* Simula temporizador correcto sin producir muestras por si mismo. */
esp_err_t esp_timer_start_periodic(esp_timer_handle_t identificador, uint64_t periodo)
{ (void)identificador; assert(periodo > 0); return ESP_OK; }
/* Permite enlazar el punto de entrada sin ejecutarlo en los escenarios. */
esp_err_t esp_timer_create(const esp_timer_create_args_t *argumentos, esp_timer_handle_t *identificador)
{ (void)argumentos; *identificador = NULL; return ESP_OK; }
/* Etiqueta explicitamente la trama como simulada. */
const esp_app_desc_t *esp_app_get_description(void)
{ static const esp_app_desc_t descriptor = {.version = "simulacion_host"}; return &descriptor; }
/* Sustituye notificaciones; los escenarios llaman la adquisicion explicitamente. */
void xTaskNotifyGive(TaskHandle_t tarea) { (void)tarea; }
/* Sustituye notificaciones para poder enlazar el coordinador original. */
uint32_t ulTaskNotifyTake(int limpiar, uint32_t espera) { (void)limpiar; (void)espera; return 0; }
/* Sustituye identificacion de tareas. */
TaskHandle_t xTaskGetCurrentTaskHandle(void) { return NULL; }
/* Sustituye prioridades del RTOS. */
void vTaskPrioritySet(TaskHandle_t tarea, unsigned prioridad) { (void)tarea; (void)prioridad; }
/* Sustituye esperas del RTOS. */
void vTaskDelay(unsigned tiempo) { (void)tiempo; }
/* Sustituye instalacion serial. */
esp_err_t protocolo_iniciar(void) { return ESP_OK; }
/* Captura las mismas lineas que formatea la aplicacion de produccion. */
bool protocolo_emitir(const char *formato, ...)
{
    if (cantidad_mensajes >= limite_mensajes) return false;
    va_list argumentos;
    va_start(argumentos, formato);
    int longitud = vsnprintf(mensajes[cantidad_mensajes], 512, formato, argumentos);
    va_end(argumentos);
    assert(longitud > 0 && longitud < 511);
    ++cantidad_mensajes;
    return true;
}
/* Los escenarios inyectan comandos completos, sin emular bytes UART. */
int protocolo_recibir(char *linea, size_t capacidad) { (void)linea; (void)capacidad; return 0; }
/* Mantiene reserva suficiente para inicio; el fallo se inyecta al emitir. */
unsigned protocolo_espacios(void) { return 64; }
/* No simula errores electricos UART. */
bool protocolo_fallo(void) { return false; }
/* Sustituye inicializacion de sensor. */
esp_err_t sensor_optico_iniciar(const configuracion_hardware_t *parametros) { (void)parametros; return ESP_OK; }
/* Sustituye configuracion temporal del sensor. */
void sensor_optico_configurar_timeout(int64_t timeout_us) { assert(timeout_us > 0); }
/* Entrega la observacion elegida por cada escenario. */
lectura_velocidad_t sensor_optico_leer(void)
{ velocidad_virtual.tiempo_lectura_us = tiempo_virtual_us; return velocidad_virtual; }
/* Sustituye instalacion PWM del servo. */
esp_err_t servo_freno_iniciar(const configuracion_hardware_t *parametros) { (void)parametros; return ESP_OK; }
/* Usa la conversion real y cuenta ordenes para comprobar los bloqueos del coordinador. */
esp_err_t servo_freno_ordenar(double angulo_deg)
{
    ++ordenes_servo;
    uint32_t pulso;
    if (!freno_convertir_pulso(&montaje, angulo_deg, &pulso)) return ESP_ERR_INVALID_ARG;
    angulo_virtual = angulo_deg;
    return ESP_OK;
}
/* Expone la orden simulada del servo. */
double servo_freno_angulo(void) { return angulo_virtual; }
/* Comprueba la liberacion comandada en el montaje simulado. */
bool servo_freno_liberado(void) { return angulo_virtual == montaje.servo_liberado_deg; }
/* Sustituye instalacion del puente. */
esp_err_t motor_iniciar(const configuracion_hardware_t *parametros) { (void)parametros; return ESP_OK; }
/* Cuenta ordenes para detectar una reactivacion indebida durante captura. */
esp_err_t motor_ordenar(double porcentaje, int64_t tiempo_us)
{
    (void)tiempo_us;
    ++ordenes_motor;
    if (falla_motor) return ESP_FAIL;
    if (porcentaje < 0 || porcentaje > montaje.motor_maximo_porcentaje) return ESP_ERR_INVALID_ARG;
    motor_virtual = porcentaje;
    return ESP_OK;
}
/* La vigilancia PWM real requiere comprobacion posterior en placa. */
bool motor_vigilar(int64_t tiempo_us) { (void)tiempo_us; return false; }
/* Expone el mando simulado. */
double motor_porcentaje(void) { return motor_virtual; }

/* Prepara valores exclusivamente simulados, nunca usados como calibracion del firmware. */
static void preparar_escenario(void)
{
    montaje = (configuracion_hardware_t){.conexiones_verificadas = true, .sensor_gpio = 27,
        .pulsos_por_vuelta = 24, .servo_gpio = 18, .servo_frecuencia_hz = 50,
        .servo_minimo_deg = 10, .servo_maximo_deg = 90, .servo_liberado_deg = 10,
        .servo_pulso_minimo_us = 1000, .servo_pulso_maximo_us = 1800,
        .motor_enable_gpio = 19, .motor_entrada1_gpio = 21, .motor_entrada2_gpio = 22,
        .motor_frecuencia_hz = 1000, .motor_maximo_porcentaje = 30, .motor_maximo_impulso_ms = 2000};
    ensayo = (configuracion_ensayo_t){20, 1000, 300};
    hardware_listo = true;
    motivo_hardware = "simulacion";
    registrando = cerrando = false;
    angulo_virtual = NAN;
    motor_virtual = 0;
    falla_motor = false;
    ordenes_motor = ordenes_servo = cantidad_mensajes = 0;
    limite_mensajes = 256;
    tiempo_virtual_us = 5000000000LL;
    velocidad_virtual = (lectura_velocidad_t){.estado = VELOCIDAD_VALIDA, .velocidad_rpm = 1000};
}

/* Recorre impulso, corte, cambio de freno y cierre usando el coordinador original. */
static void recorrido_completo(void)
{
    ejecutar_comando("FRENO 10");
    ejecutar_comando("MOTOR 20");
    assert(motor_virtual == 20);
    ejecutar_comando("START");
    assert(registrando && motor_virtual == 0 && muestras_enviadas == 1);
    tiempo_virtual_us += 20000;
    ejecutar_comando("FRENO 40");
    adquirir_muestra();
    tiempo_virtual_us += 20000;
    adquirir_muestra();
    ejecutar_comando("STOP");
    assert(!registrando && cerrando && angulo_virtual == 10);
    intentar_cierre();
    assert(!cerrando && strstr(mensajes[cantidad_mensajes - 1], "\"completo\":true"));
}

/* Selecciona escenarios independientes con aserciones sobre comportamiento observable. */
int main(int cantidad_argumentos, char **argumentos)
{
    assert(cantidad_argumentos == 2);
    const char *escenario = argumentos[1];
    preparar_escenario();
    estimador_velocidad_t estimador;
    estimador_reiniciar(&estimador);
    if (!strcmp(escenario, "velocidad")) {
        assert(isnan(estimador_leer(&estimador, 0, 24, 10000).velocidad_rpm));
        estimador_registrar(&estimador, 0, 0, 10000);
        assert(estimador_leer(&estimador, 0, 24, 10000).estado == VELOCIDAD_ESPERANDO);
        estimador_registrar(&estimador, 2500, 0, 10000);
        assert(fabs(estimador_leer(&estimador, 2500, 24, 10000).velocidad_rpm - 1000) < 1e-10);
    } else if (!strcmp(escenario, "rechazo_pulsos")) {
        estimador_registrar(&estimador, 10000, 100, 10000);
        estimador_registrar(&estimador, 10000, 100, 10000);
        estimador_registrar(&estimador, 10001, 100, 10000);
        estimador_registrar(&estimador, 9900, 100, 10000);
        estimador_registrar(&estimador, 12500, 100, 10000);
        assert(estimador.pulsos_rechazados == 3 && estimador.pulsos_aceptados == 2);
        assert(estimador.intervalo_us == 2500);
    } else if (!strcmp(escenario, "timeout")) {
        estimador_registrar(&estimador, 0, 0, 10000);
        estimador_registrar(&estimador, 2500, 0, 10000);
        assert(estimador_leer(&estimador, 12499, 24, 10000).estado == VELOCIDAD_VALIDA);
        assert(estimador_leer(&estimador, 12500, 24, 10000).velocidad_rpm == 0);
        estimador_registrar(&estimador, 20000, 0, 10000);
        assert(estimador_leer(&estimador, 20000, 24, 10000).estado == VELOCIDAD_ESPERANDO);
        estimador_registrar(&estimador, 25000, 0, 10000);
        assert(estimador_leer(&estimador, 25000, 24, 10000).velocidad_rpm == 500);
    } else if (!strcmp(escenario, "reloj_64bits")) {
        estimador_registrar(&estimador, 5000000000LL, 0, 10000);
        estimador_registrar(&estimador, 5000002500LL, 0, 10000);
        assert(estimador_leer(&estimador, 5000002500LL, 24, 10000).velocidad_rpm == 1000);
        estimador_reiniciar(&estimador);
        assert(!estimador.tiene_intervalo && estimador.pulsos_aceptados == 0);
    } else if (!strcmp(escenario, "conversion")) {
        uint32_t pulso;
        assert(freno_convertir_pulso(&montaje, 50, &pulso) && pulso == 1400);
        montaje.servo_pulso_minimo_us = 1800; montaje.servo_pulso_maximo_us = 1000;
        assert(freno_convertir_pulso(&montaje, 10, &pulso) && pulso == 1800);
        assert(!freno_convertir_pulso(&montaje, NAN, &pulso));
        assert(!freno_convertir_pulso(&montaje, 91, &pulso));
    } else if (!strcmp(escenario, "comandos")) {
        const char *invalidos[] = {"", "START ahora", "MOTOR nan", "FRENO inf", "CONFIG 20 100 20 extra", "MOTOR 10abc", "MOTOR 1e999"};
        for (unsigned indice = 0; indice < sizeof(invalidos) / sizeof(invalidos[0]); ++indice)
            assert(comando_interpretar(invalidos[indice]).tipo == COMANDO_INVALIDO);
        assert(comando_interpretar("  FRENO 40.5 ").valores[0] == 40.5);
        assert(comando_interpretar("CONFIG").tipo == COMANDO_CONFIG_CONSULTA);
    } else if (!strcmp(escenario, "configuracion")) {
        configuracion_ensayo_t resultado;
        comando_t comando = comando_interpretar("CONFIG 20 1000 300");
        assert(comando_configuracion(&comando, 0, &resultado));
        const char *invalidos[] = {"CONFIG 1 1000 300", "CONFIG 20.5 1000 300", "CONFIG 20 10 300", "CONFIG 20 4000000 300", "CONFIG 20 1000 0"};
        for (unsigned indice = 0; indice < sizeof(invalidos) / sizeof(invalidos[0]); ++indice) {
            comando = comando_interpretar(invalidos[indice]); assert(!comando_configuracion(&comando, 0, &resultado));
        }
    } else if (!strcmp(escenario, "temporizacion")) {
        reloj_registro_iniciar(&reloj, 5000000000LL);
        assert(reloj_registro_muestrear(&reloj, 5000000000LL, 20));
        assert(!reloj_registro_muestrear(&reloj, 5000000001LL, 20));
        assert(reloj_registro_muestrear(&reloj, 5000061000LL, 20));
        assert(reloj.muestras_producidas == 2 && reloj.vencimientos_perdidos == 2);
        assert(reloj.intervalo_maximo_us == 61000);
        reloj_registro_cerrar(&reloj, 5000100000LL, 20);
        assert(reloj.vencimientos_perdidos == 3);
    } else if (!strcmp(escenario, "hardware")) {
        assert(hardware_validar(&montaje) == NULL);
        montaje.conexiones_verificadas = false; assert(hardware_validar(&montaje));
        montaje.conexiones_verificadas = true; montaje.servo_gpio = 27; assert(hardware_validar(&montaje));
        montaje.servo_gpio = 34; assert(hardware_validar(&montaje));
        montaje.servo_gpio = 18; montaje.sensor_gpio = 6; assert(hardware_validar(&montaje));
        montaje.sensor_gpio = 27; montaje.servo_liberado_deg = 100; assert(hardware_validar(&montaje));
        montaje.servo_liberado_deg = 10; montaje.motor_maximo_porcentaje = 0; assert(hardware_validar(&montaje));
    } else if (!strcmp(escenario, "inicio_bloqueado")) {
        ejecutar_comando("START"); assert(!registrando && ordenes_motor == 0);
        angulo_virtual = 10; hardware_listo = false;
        ejecutar_comando("START"); assert(!registrando && ordenes_motor == 0);
        hardware_listo = true; velocidad_virtual.estado = VELOCIDAD_ESPERANDO;
        ejecutar_comando("START"); assert(!registrando && ordenes_motor == 0);
    } else if (!strcmp(escenario, "recorrido") || !strcmp(escenario, "trama")) {
        recorrido_completo();
        if (!strcmp(escenario, "trama"))
            for (unsigned indice = 0; indice < cantidad_mensajes; ++indice) puts(mensajes[indice]);
    } else if (!strcmp(escenario, "bloqueos")) {
        angulo_virtual = 10; iniciar_registro();
        unsigned anteriores = ordenes_motor;
        ejecutar_comando("MOTOR 20"); assert(ordenes_motor == anteriores && motor_virtual == 0);
        ejecutar_comando("CONFIG 30 1000 300"); assert(ensayo.periodo_ms == 20);
        ejecutar_comando("FRENO 200"); assert(registrando && angulo_virtual == 10);
    } else if (!strcmp(escenario, "cola_llena")) {
        angulo_virtual = 10; iniciar_registro();
        limite_mensajes = cantidad_mensajes;
        tiempo_virtual_us += 20000; adquirir_muestra();
        assert(!registrando && cerrando && motor_virtual == 0 && angulo_virtual == 10);
        intentar_cierre(); assert(cerrando);
        limite_mensajes = 256; intentar_cierre();
        assert(!cerrando && strstr(mensajes[cantidad_mensajes-1], "\"completo\":false"));
    } else if (!strcmp(escenario, "fallo_corte")) {
        angulo_virtual = 10; iniciar_registro();
        unsigned anteriores = ordenes_servo;
        falla_motor = true; terminar_registro("STOP", true);
        assert(ordenes_servo == anteriores + 1);
        intentar_cierre(); assert(strstr(mensajes[cantidad_mensajes-1], "fallo_actuador"));
    } else return 2;
    return 0;
}
