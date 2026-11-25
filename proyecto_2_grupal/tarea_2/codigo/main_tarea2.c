/* Tarea 2, pregunta 3: lazo PID del banco de frenado sin delay().
 * ESP32 con ESP-IDF 5.5. El periodo Ts lo fija un esp_timer periodico; el sensor
 * TCRT5000 se lee por interrupcion con el estimador del registrador y una tarea
 * aparte imprime la telemetria. Pines y calibracion son provisionales y deben
 * coincidir con los del registrador (docs/decisiones.md). Las tres primeras
 * columnas siguen el contrato tiempo_ms,freno_deg,velocidad_rpm. */
#include <math.h>
#include <stdio.h>

#include "conversion_freno.h"
#include "driver/gpio.h"
#include "driver/ledc.h"
#include "esp_timer.h"
#include "estimador_velocidad.h"
#include "freertos/FreeRTOS.h"
#include "freertos/queue.h"
#include "freertos/task.h"
#include "pid_controller.h"

#define GPIO_SENSOR 27
#define GPIO_SERVO 18
#define GPIO_MOTOR_ENA 25
#define GPIO_MOTOR_IN1 26
#define GPIO_MOTOR_IN2 33

#define TS_US 20000              /* Ts = 20 ms (50 Hz), ver pregunta 2 */
#define PULSOS_POR_VUELTA 10     /* 10 marcas, un flanco por marca */
#define TIMEOUT_SENSOR_US 100000
#define REBOTE_MINIMO_US 500     /* Rechaza flancos dobles del comparador */
#define FRENO_LIBRE_DEG 120.0    /* Goma sin contacto */
#define FRENO_MAXIMO_DEG 180.0   /* Frenado maximo */

#define RPM_A_RAD_S (2.0f * (float)M_PI / 60.0f)
/* Valores del banco medidos en la pregunta 7 (escalon_02): ~300 RPM al cortar el motor,
 * caida libre de 8 rad/s^2 y frenado maximo de 15 rad/s^2. */
#define OMEGA_INICIAL 28.0f      /* rad/s (~270 RPM) */
#define DESACELERACION 11.0f     /* rad/s^2, entre la caida libre y el frenado maximo */
#define OMEGA_FIN 5.0f
#define IMPULSO_MAXIMO_US 5000000 /* Corta el motor si no alcanza OMEGA_INICIAL */

typedef enum { REPOSO, IMPULSO, FRENADO } estado_t;
static const char *const NOMBRE_ESTADO[] = {"REPOSO", "IMPULSO", "FRENADO"};

typedef struct {
    float tiempo_ms, freno_deg, velocidad_rpm, referencia_rpm; /* NAN si no aplica */
    float u_norm;
    uint16_t ejecucion_us;
    uint8_t estado;
    bool saturado;
} muestra_t;

/* Calibracion del MG90S en el formato del registrador: grados -> microsegundos. */
static const configuracion_hardware_t SERVO = {
    .servo_frecuencia_hz = 50, .servo_minimo_deg = 0, .servo_maximo_deg = 180,
    .servo_pulso_minimo_us = 500, .servo_pulso_maximo_us = 2500};

static portMUX_TYPE proteccion = portMUX_INITIALIZER_UNLOCKED;
static estimador_velocidad_t estimador;
static QueueHandle_t cola;
static volatile uint32_t descartadas;
static volatile estado_t estado = REPOSO;
static pid_controlador_t pid;
static uint32_t k_frenado;
static int64_t t_inicio_us;

/* ISR del sensor: solo fecha el flanco; no se pierde ninguna marca. */
static void al_flanco(void *argumento)
{
    (void)argumento;
    const int64_t tiempo_us = esp_timer_get_time();
    portENTER_CRITICAL_ISR(&proteccion);
    estimador_registrar(&estimador, tiempo_us, REBOTE_MINIMO_US, TIMEOUT_SENSOR_US);
    portEXIT_CRITICAL_ISR(&proteccion);
}

/* Copia el estimador bajo seccion critica y calcula las RPM fuera de ella. */
static lectura_velocidad_t leer_velocidad(int64_t ahora_us)
{
    portENTER_CRITICAL(&proteccion);
    const estimador_velocidad_t copia = estimador;
    portEXIT_CRITICAL(&proteccion);
    return estimador_leer(&copia, ahora_us, PULSOS_POR_VUELTA, TIMEOUT_SENSOR_US);
}

/* u en [0, 1] -> angulo calibrado -> pulso PWM. Devuelve el angulo ordenado. */
static float aplicar_freno(float u)
{
    const double grados = FRENO_LIBRE_DEG + u * (FRENO_MAXIMO_DEG - FRENO_LIBRE_DEG);
    uint32_t pulso_us;
    if (freno_convertir_pulso(&SERVO, grados, &pulso_us)) {
        const uint32_t duty = (uint32_t)llround(pulso_us * SERVO.servo_frecuencia_hz * 65536.0 / 1e6);
        ledc_set_duty(LEDC_LOW_SPEED_MODE, LEDC_CHANNEL_0, duty);
        ledc_update_duty(LEDC_LOW_SPEED_MODE, LEDC_CHANNEL_0);
    }
    return (float)grados;
}

/* ENA en bajo deja el motor en marcha libre (L298N). */
static void motor(bool encendido)
{
    gpio_set_level(GPIO_MOTOR_IN1, encendido);
    gpio_set_level(GPIO_MOTOR_IN2, 0);
    gpio_set_level(GPIO_MOTOR_ENA, encendido);
}

/* Se ejecuta cada Ts: esp_timer programa cada disparo sobre el anterior, de modo
 * que el tiempo de ejecucion no se suma al periodo. */
static void al_periodo(void *argumento)
{
    (void)argumento;
    if (estado == REPOSO) return;
    const int64_t inicio = esp_timer_get_time();
    const lectura_velocidad_t lectura = leer_velocidad(inicio);
    const float rpm = isfinite(lectura.velocidad_rpm) ? (float)lectura.velocidad_rpm : 0.0f;
    const float omega = rpm * RPM_A_RAD_S;

    if (estado == IMPULSO && inicio - t_inicio_us > IMPULSO_MAXIMO_US) {
        motor(false); /* Seguridad: no alcanzo la velocidad inicial */
        estado = REPOSO;
        return;
    }
    if (estado == IMPULSO && omega >= OMEGA_INICIAL) {
        motor(false); /* Se corta el motor y empieza la referencia */
        pid_reiniciar(&pid);
        k_frenado = 0;
        estado = FRENADO;
    }

    muestra_t m = {.tiempo_ms = (float)(inicio - t_inicio_us) / 1000.0f,
                   .freno_deg = (float)FRENO_LIBRE_DEG,
                   .velocidad_rpm = (float)lectura.velocidad_rpm,
                   .referencia_rpm = NAN, .u_norm = NAN, .estado = (uint8_t)estado};
    if (estado == FRENADO) {
        const float t_ref = k_frenado * (TS_US * 1e-6f);
        const float ref = fmaxf(OMEGA_INICIAL - DESACELERACION * t_ref, 0.0f);
        m.u_norm = pid_paso(&pid, ref, omega);
        m.freno_deg = aplicar_freno(m.u_norm);
        m.referencia_rpm = ref / RPM_A_RAD_S;
        m.saturado = pid.saturado;
        k_frenado++;
        if (omega < OMEGA_FIN && ref <= 0.0f) {
            aplicar_freno(0.0f);
            estado = REPOSO;
        }
    }
    m.ejecucion_us = (uint16_t)(esp_timer_get_time() - inicio);
    if (xQueueSend(cola, &m, 0) != pdTRUE) descartadas++; /* Nunca se espera aqui */
}

/* Tarea sin requisitos de tiempo: imprime muestras y atiende la consola. Se
 * bloquea esperando la cola (eventos), no con una espera fija. */
static void tarea_telemetria(void *argumento)
{
    (void)argumento;
    printf("tiempo_ms,freno_deg,velocidad_rpm,referencia_rpm,error_rpm,u_norm,"
           "saturado,estado,ejecucion_us\n");
    muestra_t m;
    for (;;) {
        if (xQueueReceive(cola, &m, pdMS_TO_TICKS(50)) == pdTRUE) {
            if (isnan(m.referencia_rpm)) { /* Impulso: sin referencia ni mando */
                printf("%.3f,%.1f,%.2f,,,,0,%s,%u\n", m.tiempo_ms, m.freno_deg,
                       m.velocidad_rpm, NOMBRE_ESTADO[m.estado], m.ejecucion_us);
            } else {
                printf("%.3f,%.1f,%.2f,%.2f,%.2f,%.4f,%d,%s,%u\n", m.tiempo_ms, m.freno_deg,
                       m.velocidad_rpm, m.referencia_rpm, m.velocidad_rpm - m.referencia_rpm,
                       m.u_norm, m.saturado, NOMBRE_ESTADO[m.estado], m.ejecucion_us);
            }
        }
        const int c = getchar(); /* stdin por UART0 no bloquea: EOF sin datos */
        if (c == 's' && estado == REPOSO) {
            t_inicio_us = esp_timer_get_time();
            motor(true);
            estado = IMPULSO;
        }
    }
}

void app_main(void)
{
    const gpio_config_t salidas = {
        .pin_bit_mask = (1ULL << GPIO_MOTOR_ENA) | (1ULL << GPIO_MOTOR_IN1) | (1ULL << GPIO_MOTOR_IN2),
        .mode = GPIO_MODE_OUTPUT};
    gpio_config(&salidas);
    motor(false);

    const ledc_timer_config_t pwm = {.speed_mode = LEDC_LOW_SPEED_MODE, .timer_num = LEDC_TIMER_0,
        .duty_resolution = LEDC_TIMER_16_BIT, .freq_hz = 50, .clk_cfg = LEDC_USE_APB_CLK};
    ledc_timer_config(&pwm);
    const ledc_channel_config_t canal = {.gpio_num = GPIO_SERVO, .speed_mode = LEDC_LOW_SPEED_MODE,
        .channel = LEDC_CHANNEL_0, .timer_sel = LEDC_TIMER_0, .duty = 0, .hpoint = 0};
    ledc_channel_config(&canal);
    aplicar_freno(0.0f);

    estimador_reiniciar(&estimador);
    const gpio_config_t entrada = {.pin_bit_mask = 1ULL << GPIO_SENSOR, .mode = GPIO_MODE_INPUT,
        .intr_type = GPIO_INTR_NEGEDGE};
    gpio_config(&entrada);
    gpio_install_isr_service(0);
    gpio_isr_handler_add(GPIO_SENSOR, al_flanco, NULL);

    /* Ganancias desde el modelo de la pregunta 7: con u en [0, 1] (60 grados de freno),
     * a_max = |K| * 60 = 155 RPM/s = 16 rad/s^2 y polo del freno en 1/tau = 3,6 rad/s.
     * Cruce en 2 rad/s (Kp = 2/16) y cero del PI en 0,5 rad/s: margen de fase ~45 grados. */
    pid_iniciar(&pid, 0.125f, 0.0625f, 0.005f, TS_US * 1e-6f, 0.04f, 0.0f, 1.0f, true);

    cola = xQueueCreate(64, sizeof(muestra_t));
    xTaskCreate(tarea_telemetria, "telemetria", 4096, NULL, 3, NULL);

    esp_timer_handle_t temporizador;
    const esp_timer_create_args_t argumentos = {.callback = al_periodo, .name = "pid"};
    esp_timer_create(&argumentos, &temporizador);
    esp_timer_start_periodic(temporizador, TS_US);
}
