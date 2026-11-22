/* Tarea 2, pregunta 3: lazo PID del banco de frenado sin delay().
 * Raspberry Pi Pico (Pico SDK). El periodo Ts lo fija un temporizador por
 * hardware; el encoder se lee por interrupcion y el bucle principal solo
 * atiende la consola y vacia la telemetria. Pines y limites son provisionales
 * hasta cerrar el esquema electrico (docs/decisiones.md). */
#include <math.h>
#include <stdio.h>

#include "hardware/clocks.h"
#include "hardware/gpio.h"
#include "hardware/pwm.h"
#include "hardware/sync.h"
#include "pico/stdlib.h"
#include "pid_controller.h"

#define PIN_ENCODER 2
#define PIN_SERVO 15
#define PIN_MOTOR 16

#define TS_US 20000            /* Ts = 20 ms (50 Hz), ver pregunta 2 */
#define FLANCOS_POR_VUELTA 24  /* 12 marcas, ambos flancos */
#define TIMEOUT_ENCODER_US 100000
#define SERVO_US_LIBRE 1000    /* Goma sin contacto: calibrar */
#define SERVO_US_MAXIMO 2000   /* Frenado maximo seguro: calibrar */

#define OMEGA_INICIAL 150.0f   /* rad/s */
#define DESACELERACION 40.0f   /* rad/s^2, entre decel. natural y maxima */
#define OMEGA_FIN 5.0f

typedef enum { REPOSO, IMPULSO, FRENADO } estado_t;

typedef struct {
    uint32_t k;
    float ref, omega, u;
    uint16_t ejecucion_us;
    bool saturado;
} muestra_t;

enum { CAPACIDAD_COLA = 64 };
static muestra_t cola[CAPACIDAD_COLA];
static volatile uint32_t escritura, lectura, descartadas;

static volatile uint64_t flancos_us[3];
static volatile uint32_t n_flancos;

static volatile estado_t estado = REPOSO;
static pid_controlador_t pid;
static uint32_t k_frenado;
static uint slice_servo;

/* ISR del encoder: solo guarda la marca de tiempo; no se pierde ningun flanco. */
static void al_flanco(uint gpio, uint32_t eventos)
{
    (void)gpio;
    (void)eventos;
    flancos_us[n_flancos % 3] = time_us_64();
    n_flancos++;
}

/* omega por tiempo entre flancos. Se toma t_k - t_(k-2), un periodo completo
 * marca negra + espacio cafe, para que la asimetria del ancho de las marcas
 * no aparezca como ruido. */
static float medir_omega(uint64_t ahora)
{
    const uint32_t guardado = save_and_disable_interrupts();
    const uint32_t n = n_flancos;
    const uint64_t t_ultimo = flancos_us[(n + 2) % 3];  /* flanco n - 1 */
    const uint64_t t_anterior = flancos_us[n % 3];      /* flanco n - 3 */
    restore_interrupts(guardado);

    if (n < 3 || ahora - t_ultimo > TIMEOUT_ENCODER_US) return 0.0f;
    const float dt = (float)(t_ultimo - t_anterior) * 1e-6f;
    return (2.0f * (float)M_PI * 2.0f / FLANCOS_POR_VUELTA) / dt;
}

static void aplicar_freno(float u)
{
    const float pulso = SERVO_US_LIBRE + u * (SERVO_US_MAXIMO - SERVO_US_LIBRE);
    pwm_set_gpio_level(PIN_SERVO, (uint16_t)pulso); /* 1 cuenta = 1 us */
}

/* Se ejecuta cada Ts exactos: el SDK reprograma la alarma desde el inicio
 * del llamado anterior (retardo negativo), no desde que termina. */
static bool al_periodo(repeating_timer_t *t)
{
    (void)t;
    const uint64_t inicio = time_us_64();
    const float omega = medir_omega(inicio);

    if (estado == IMPULSO && omega >= OMEGA_INICIAL) {
        gpio_put(PIN_MOTOR, 0); /* Se corta el motor y empieza la referencia */
        pid_reiniciar(&pid);
        k_frenado = 0;
        estado = FRENADO;
    }
    if (estado != FRENADO) return true;

    const float t = k_frenado * (TS_US * 1e-6f);
    const float ref = fmaxf(OMEGA_INICIAL - DESACELERACION * t, 0.0f);
    const float u = pid_paso(&pid, ref, omega);
    aplicar_freno(u);

    if (omega < OMEGA_FIN && ref <= 0.0f) {
        aplicar_freno(0.0f);
        estado = REPOSO;
    }

    const uint32_t siguiente = (escritura + 1) % CAPACIDAD_COLA;
    if (siguiente == lectura) {
        descartadas++; /* Se pierde telemetria, nunca el periodo de control */
    } else {
        cola[escritura] = (muestra_t){k_frenado, ref, omega, u,
                                      (uint16_t)(time_us_64() - inicio), pid.saturado};
        escritura = siguiente;
    }
    k_frenado++;
    return true;
}

static void iniciar_servo(void)
{
    gpio_set_function(PIN_SERVO, GPIO_FUNC_PWM);
    slice_servo = pwm_gpio_to_slice_num(PIN_SERVO);
    pwm_config cfg = pwm_get_default_config();
    pwm_config_set_clkdiv(&cfg, (float)clock_get_hz(clk_sys) / 1e6f); /* 1 MHz */
    pwm_config_set_wrap(&cfg, 20000 - 1);                             /* 20 ms */
    pwm_init(slice_servo, &cfg, true);
    aplicar_freno(0.0f);
}

int main(void)
{
    stdio_init_all();
    gpio_init(PIN_MOTOR);
    gpio_set_dir(PIN_MOTOR, GPIO_OUT);
    gpio_put(PIN_MOTOR, 0);
    iniciar_servo();

    gpio_init(PIN_ENCODER);
    gpio_pull_up(PIN_ENCODER);
    gpio_set_irq_enabled_with_callback(PIN_ENCODER,
                                       GPIO_IRQ_EDGE_RISE | GPIO_IRQ_EDGE_FALL,
                                       true, &al_flanco);

    /* Ganancias provisionales (pregunta 3); se redisenan con el modelo. */
    pid_iniciar(&pid, 0.04f, 0.08f, 0.0005f, TS_US * 1e-6f, 0.04f, 0.0f, 1.0f, true);

    repeating_timer_t temporizador;
    add_repeating_timer_us(-TS_US, al_periodo, NULL, &temporizador);

    printf("k,ref_rad_s,omega_rad_s,u_norm,saturado,ejecucion_us\n");
    while (true) {
        /* Consola no bloqueante: 's' inicia un ensayo. */
        const int c = getchar_timeout_us(0);
        if (c == 's' && estado == REPOSO) {
            gpio_put(PIN_MOTOR, 1);
            estado = IMPULSO;
        }
        if (lectura != escritura) {
            const muestra_t m = cola[lectura];
            lectura = (lectura + 1) % CAPACIDAD_COLA;
            printf("%lu,%.3f,%.3f,%.4f,%d,%u\n", (unsigned long)m.k, m.ref, m.omega,
                   m.u, m.saturado, m.ejecucion_us);
        } else {
            tight_loop_contents();
        }
    }
}
