#include "hardware.h"
#include "driver/gpio.h"
#include "sdkconfig.h"
#include <stddef.h>

/* Identifica GPIO reservados para UART0, flash o arranque del ESP32 clasico. */
static bool gpio_reservado(int numero_gpio)
{
    return numero_gpio == 0 || numero_gpio == 1 || numero_gpio == 2 ||
        numero_gpio == 3 || numero_gpio == 5 || numero_gpio == 12 ||
        numero_gpio == 15 || (numero_gpio >= 6 && numero_gpio <= 11) ||
        numero_gpio == 16 || numero_gpio == 17;
}

/* Carga los valores de menuconfig sin iniciar el hardware. */
configuracion_hardware_t hardware_cargar(void)
{
    configuracion_hardware_t parametros = {
        .sensor_gpio = CONFIG_ASM_SENSOR_GPIO,
        .pulsos_por_vuelta = CONFIG_ASM_PULSOS_POR_VUELTA,
        .intervalo_minimo_pulso_us = CONFIG_ASM_INTERVALO_MINIMO_PULSO_US,
        .servo_gpio = CONFIG_ASM_SERVO_GPIO,
        .servo_frecuencia_hz = CONFIG_ASM_SERVO_FRECUENCIA_HZ,
        .servo_minimo_deg = CONFIG_ASM_SERVO_MINIMO_DEG,
        .servo_maximo_deg = CONFIG_ASM_SERVO_MAXIMO_DEG,
        .servo_liberado_deg = CONFIG_ASM_SERVO_LIBERADO_DEG,
        .servo_pulso_minimo_us = CONFIG_ASM_SERVO_PULSO_MINIMO_US,
        .servo_pulso_maximo_us = CONFIG_ASM_SERVO_PULSO_MAXIMO_US,
        .motor_enable_gpio = CONFIG_ASM_MOTOR_ENABLE_GPIO,
        .motor_entrada1_gpio = CONFIG_ASM_MOTOR_ENTRADA1_GPIO,
        .motor_entrada2_gpio = CONFIG_ASM_MOTOR_ENTRADA2_GPIO,
        .motor_frecuencia_hz = CONFIG_ASM_MOTOR_FRECUENCIA_HZ,
        .motor_maximo_porcentaje = CONFIG_ASM_MOTOR_MAXIMO_PORCENTAJE,
        .motor_maximo_impulso_ms = CONFIG_ASM_MOTOR_MAXIMO_IMPULSO_MS
    };
#ifdef CONFIG_ASM_CONEXIONES_VERIFICADAS
    parametros.conexiones_verificadas = true;
#endif
#ifdef CONFIG_ASM_SENSOR_FLANCO_BAJADA
    parametros.flanco_bajada = true;
#endif
    return parametros;
}

/* Valida el montaje completo antes de permitir inicializar sus perifericos. */
const char *hardware_validar(const configuracion_hardware_t *parametros)
{
    if (!parametros->conexiones_verificadas) return "conexiones_no_verificadas";
    const int pines[] = {parametros->sensor_gpio, parametros->servo_gpio,
        parametros->motor_enable_gpio, parametros->motor_entrada1_gpio,
        parametros->motor_entrada2_gpio};
    for (unsigned indice_pin = 0; indice_pin < sizeof(pines) / sizeof(pines[0]); ++indice_pin) {
        int numero_gpio = pines[indice_pin];
        if (!GPIO_IS_VALID_GPIO(numero_gpio) || gpio_reservado(numero_gpio)) return "gpio_no_admitido";
        if (indice_pin > 0 && !GPIO_IS_VALID_OUTPUT_GPIO(numero_gpio)) return "gpio_sin_salida";
        for (unsigned indice_anterior = 0; indice_anterior < indice_pin; ++indice_anterior) {
            if (pines[indice_anterior] == numero_gpio) return "gpio_repetido";
        }
    }
    if (parametros->servo_frecuencia_hz <= 0 || parametros->servo_minimo_deg < 0 ||
        parametros->servo_maximo_deg <= parametros->servo_minimo_deg ||
        parametros->servo_liberado_deg < parametros->servo_minimo_deg ||
        parametros->servo_liberado_deg > parametros->servo_maximo_deg ||
        parametros->servo_pulso_minimo_us <= 0 || parametros->servo_pulso_maximo_us <= 0 ||
        parametros->servo_pulso_minimo_us == parametros->servo_pulso_maximo_us ||
        (int64_t)parametros->servo_pulso_minimo_us * parametros->servo_frecuencia_hz >= 1000000 ||
        (int64_t)parametros->servo_pulso_maximo_us * parametros->servo_frecuencia_hz >= 1000000)
        return "calibracion_servo_incompleta";
    if (parametros->motor_maximo_porcentaje <= 0 || parametros->motor_maximo_impulso_ms <= 0)
        return "limites_motor_incompletos";
    return NULL;
}
