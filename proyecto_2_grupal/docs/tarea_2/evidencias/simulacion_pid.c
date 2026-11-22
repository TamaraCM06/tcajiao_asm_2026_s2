/* Evidencia de la pregunta 3 (Tarea 2). SIMULACION, no medicion del banco.
 * Ejecuta el mismo pid_controller.c del firmware contra una planta ilustrativa
 * del disco con freno unilateral y escribe CSV + macros LaTeX en generado/.
 *
 * Casos:
 *   aw_si / aw_no : referencia con un tramo inicial imposible (satura el freno),
 *                   con y sin anti-windup.
 *   timer / delay : rampa alcanzable; el periodo lo fija un temporizador o un
 *                   bucle delay(20) + tiempo de ejecucion variable.
 *
 * Los parametros de planta son supuestos razonables, no identificados; la
 * identificacion real corresponde a la pregunta 7 y al proyecto (seccion 2.3). */
#include <math.h>
#include <stdio.h>
#include <stdlib.h>

#include "pid_controller.h"

/* Planta ilustrativa: J*dw/dt = -b*w - Tc - Tfreno(b_servo), dividido entre J. */
#define TAU_NATURAL 8.0     /* s, J/b */
#define DECEL_COULOMB 1.5   /* rad/s^2, Tc/J */
#define DECEL_FRENO 100.0   /* rad/s^2 con u = 1 */
#define TAU_SERVO 0.05      /* s, respuesta del brazo del servo */
#define RETARDO_PWM 0.020   /* s, el servo toma el mando en la siguiente trama */
#define OMEGA_0 150.0

#define TS 0.020
#define DT 1e-4
#define T_FINAL 5.0

#define KP 0.04f
#define KI 0.08f
#define KD 0.0005f
#define TF 0.04f

typedef double (*referencia_fn)(double t);

static double ref_imposible(double t)
{
    /* 140 rad/s^2 supera el frenado maximo (~120 rad/s^2 con friccion). */
    const double t1 = 0.5, w1 = OMEGA_0 - 140.0 * t1;
    const double w = (t < t1) ? OMEGA_0 - 140.0 * t : w1 - 25.0 * (t - t1);
    return w > 0.0 ? w : 0.0;
}

static double ref_rampa(double t)
{
    const double w = OMEGA_0 - 40.0 * t;
    return w > 0.0 ? w : 0.0;
}

static unsigned semilla = 12345u;
static double aleatorio(void) /* LCG determinista en [0, 1) */
{
    semilla = semilla * 1103515245u + 12345u;
    return (double)((semilla >> 8) & 0xFFFFFF) / 16777216.0;
}

typedef struct {
    double iae, rmse, frac_saturado, periodo_medio_ms, periodo_max_ms, desfase_final_ms;
} metricas_t;

/* modo_delay = 0: instantes k*TS. 1: t_(k+1) = t_k + ejecucion + delay(TS).
 * La referencia del firmware se calcula con k*TS (contador de muestras), que
 * es lo que hace un bucle con delay que asume periodo fijo. */
static metricas_t simular(const char *ruta, referencia_fn ref, int anti_windup,
                          int modo_delay, const char *ruta_periodos)
{
    pid_controlador_t pid;
    pid_iniciar(&pid, KP, KI, KD, (float)TS, TF, 0.0f, 1.0f, anti_windup != 0);

    FILE *f = fopen(ruta, "w");
    FILE *fp = ruta_periodos ? fopen(ruta_periodos, "w") : NULL;
    if (!f || (ruta_periodos && !fp)) {
        perror("fopen");
        exit(1);
    }
    fprintf(f, "t,ref,omega,u\n");
    if (fp) fprintf(fp, "k,periodo_ms\n");

    double t = 0.0, w = OMEGA_0, b = 0.0, u_aplicado = 0.0;
    double pend_t[8], pend_u[8];
    int n_pend = 0;
    double t_muestra = 0.0, t_anterior = 0.0, suma_periodo = 0.0, periodo_max = 0.0;
    unsigned k = 0, saturadas = 0;
    double iae = 0.0, ise = 0.0, e_prev = 0.0, t_eval_prev = 0.0;

    while (t < T_FINAL) {
        if (t >= t_muestra - 1e-12) {
            const double ref_firmware = ref(k * TS);
            const float u = pid_paso(&pid, (float)ref_firmware, (float)w);
            saturadas += pid.saturado;
            if (n_pend < 8) {
                pend_t[n_pend] = t + RETARDO_PWM;
                pend_u[n_pend++] = u;
            }
            fprintf(f, "%.4f,%.3f,%.3f,%.4f\n", t, ref(t), w, u);

            /* Error contra la curva en tiempo real: es la que importa fisicamente. */
            const double e = w - ref(t);
            if (k > 0 && ref(t_eval_prev) > 0.0) {
                const double h = t - t_eval_prev;
                iae += 0.5 * (fabs(e) + fabs(e_prev)) * h;
                ise += 0.5 * (e * e + e_prev * e_prev) * h;
            }
            e_prev = e;
            t_eval_prev = t;

            if (k > 0) {
                const double h = (t - t_anterior) * 1e3;
                suma_periodo += h;
                if (h > periodo_max) periodo_max = h;
                if (fp) fprintf(fp, "%u,%.3f\n", k, h);
            }
            t_anterior = t;
            k++;
            if (modo_delay) {
                /* Calculo ~0.3 ms + printf de una linea CSV por UART a 115200 baud
                 * (~40 caracteres * 87 us) con variacion por la longitud del texto. */
                const double ejecucion = 0.0003 + 0.0025 + 0.0020 * aleatorio();
                t_muestra = t + ejecucion + TS;
            } else {
                t_muestra = k * TS;
            }
        }
        if (n_pend > 0 && t >= pend_t[0]) {
            u_aplicado = pend_u[0];
            for (int i = 1; i < n_pend; ++i) {
                pend_t[i - 1] = pend_t[i];
                pend_u[i - 1] = pend_u[i];
            }
            n_pend--;
        }
        b += DT * (u_aplicado - b) / TAU_SERVO;
        if (w > 0.0) {
            w += DT * (-w / TAU_NATURAL - DECEL_COULOMB - DECEL_FRENO * b);
            if (w < 0.0) w = 0.0; /* El freno no invierte el giro */
        }
        t += DT;
    }
    fclose(f);
    if (fp) fclose(fp);

    metricas_t m = {
        .iae = iae,
        .rmse = sqrt(ise / (t_eval_prev > 0 ? t_eval_prev : 1.0)),
        .frac_saturado = 100.0 * saturadas / (k ? k : 1),
        .periodo_medio_ms = suma_periodo / (k > 1 ? k - 1 : 1),
        .periodo_max_ms = periodo_max,
        /* Atraso del reloj real frente a lo que el firmware cree, k*TS */
        .desfase_final_ms = (t_anterior - (k - 1) * TS) * 1e3,
    };
    return m;
}

/* Escribe \newcommand{\nombre}{valor} con coma decimal, como el resto del informe. */
static void macro(FILE *tex, const char *nombre, double valor, int decimales)
{
    char texto[64];
    snprintf(texto, sizeof texto, "%.*f", decimales, valor);
    fprintf(tex, "\\newcommand{\\%s}{", nombre);
    for (const char *c = texto; *c; ++c) {
        if (*c == '.') fputs("{,}", tex);
        else fputc(*c, tex);
    }
    fputs("}\n", tex);
}

int main(int argc, char **argv)
{
    const char *dir = argc > 1 ? argv[1] : "generado";
    char ruta[512], ruta2[512];

#define RUTA(nombre) (snprintf(ruta, sizeof ruta, "%s/%s", dir, nombre), ruta)
    const metricas_t aw_si = simular(RUTA("aw_si.csv"), ref_imposible, 1, 0, NULL);
    const metricas_t aw_no = simular(RUTA("aw_no.csv"), ref_imposible, 0, 0, NULL);
    const metricas_t timer = simular(RUTA("timer.csv"), ref_rampa, 1, 0, NULL);
    snprintf(ruta2, sizeof ruta2, "%s/periodos_delay.csv", dir);
    const metricas_t delay = simular(RUTA("delay.csv"), ref_rampa, 1, 1, ruta2);

    FILE *tex = fopen(RUTA("metricas.tex"), "w");
    if (!tex) {
        perror("fopen");
        return 1;
    }
    fprintf(tex, "%% Generado por evidencias/simulacion_pid.c; no editar a mano.\n");
    macro(tex, "iaeAwSi", aw_si.iae, 1);
    macro(tex, "iaeAwNo", aw_no.iae, 1);
    macro(tex, "rmseAwSi", aw_si.rmse, 2);
    macro(tex, "rmseAwNo", aw_no.rmse, 2);
    macro(tex, "satAwSi", aw_si.frac_saturado, 0);
    macro(tex, "satAwNo", aw_no.frac_saturado, 0);
    macro(tex, "iaeTimer", timer.iae, 1);
    macro(tex, "iaeDelay", delay.iae, 1);
    macro(tex, "rmseTimer", timer.rmse, 2);
    macro(tex, "rmseDelay", delay.rmse, 2);
    macro(tex, "periodoTimer", timer.periodo_medio_ms, 2);
    macro(tex, "periodoDelay", delay.periodo_medio_ms, 2);
    macro(tex, "periodoMaxDelay", delay.periodo_max_ms, 2);
    macro(tex, "desfaseDelay", delay.desfase_final_ms, 0);
    macro(tex, "decelEfectivaDelay", 40.0 * TS * 1e3 / delay.periodo_medio_ms, 1);
    fclose(tex);

    printf("aw_si: IAE=%.1f RMSE=%.2f sat=%.0f%%\n", aw_si.iae, aw_si.rmse, aw_si.frac_saturado);
    printf("aw_no: IAE=%.1f RMSE=%.2f sat=%.0f%%\n", aw_no.iae, aw_no.rmse, aw_no.frac_saturado);
    printf("timer: IAE=%.1f RMSE=%.2f T=%.2f ms\n", timer.iae, timer.rmse, timer.periodo_medio_ms);
    printf("delay: IAE=%.1f RMSE=%.2f T=%.2f ms (max %.2f) desfase=%.0f ms\n", delay.iae,
           delay.rmse, delay.periodo_medio_ms, delay.periodo_max_ms, delay.desfase_final_ms);
    return 0;
}
