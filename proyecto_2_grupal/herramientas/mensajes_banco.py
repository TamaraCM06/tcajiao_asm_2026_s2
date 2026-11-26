"""Traduce errores usando parametros efectivos enviados por la placa, sin inventar limites."""
import math

MOTIVOS = {
    "falta_CONFIG": "La placa no recibio CONFIG; vuelve a conectar la consola",
    "ordenar_freno_liberado": "Primero ordena liberar el freno",
    "velocidad_no_disponible": "El sensor no entrega velocidad valida; revisa giro y ranuras",
    "ensayo_activo": "Hay un ensayo en curso; usa parar antes de iniciar otro",
    "cierre_pendiente": "El firmware aun esta cerrando la captura anterior",
    "motor_requiere_reposo_CONFIG_y_liberacion": "El motor requiere registro detenido, CONFIG valido y freno liberado",
    "cortar_motor_antes_de_frenar": "Corta el motor antes de cambiar el freno",
    "mando_rechazado": "La placa rechazo la orden del actuador",
    "parametros_ENSAYO_invalidos": "La placa rechazo el angulo o la espera del ENSAYO",
    "velocidad_maxima_no_alcanzada": "El motor se corto antes de completar la estabilidad",
    "CONFIG_requiere_reposo": "CONFIG solo se aplica con motor detenido y sin captura",
    "tiempos_CONFIG_invalidos": "CONFIG rechazado; requiere tiempos enteros positivos y duracion no menor al periodo",
    "comando_invalido": "Comando no reconocido; escribe ayuda",
    "linea_descartada": "Linea demasiado larga o con caracteres no admitidos",
    "transmision_ocupada": "No hay espacio suficiente en la cola serial para iniciar; espera y reintenta",
    "fallo_uart_reiniciar": "El firmware detecto un fallo UART; reinicia la placa",
    "fallo_corte_motor": "No se pudo aplicar la orden de cortar el motor; no se inicio el registro",
    "fallo_temporizador": "No se pudo iniciar el temporizador de registro",
    "fallo_actuador": "El controlador del motor o servo devolvio un error; revisa el montaje",
    "fallo_inicializacion": "No se pudo inicializar el hardware",
    "gpio_no_admitido": "Hay un GPIO reservado o no valido en la configuracion",
    "gpio_sin_salida": "Se asigno un GPIO sin salida a un actuador",
    "gpio_repetido": "La configuracion asigna el mismo GPIO a dos funciones",
    "ventana_sensor_invalida": "Pulsos por vuelta o ventana del sensor no validos",
    "calibracion_servo_incompleta": "La calibracion del servo no es valida",
    "limites_motor_incompletos": "Faltan limites positivos de porcentaje o duracion del motor",
    "no_inicializado": "El hardware aun no esta inicializado",
    "cola_llena": "La cola serial se lleno; revisa la integridad del CSV",
}


# Mezcla parametros del error y configuracion recibida; los valores del propio error tienen prioridad.
def parametros_reportados(mensaje, configuracion):
    motor, servo, ensayo = (configuracion.get(grupo, {}) for grupo in ("motor", "servo", "ensayo"))
    valores = {"motor_maximo_porcentaje": motor.get("maximo_porcentaje"),
               "motor_maximo_impulso_ms": motor.get("maximo_impulso_ms"),
               "servo_minimo_deg": servo.get("minimo_deg"), "servo_maximo_deg": servo.get("maximo_deg"),
               "servo_liberado_deg": servo.get("liberado_deg"),
               "estabilidad_tolerancia_porcentaje": ensayo.get("estabilidad_tolerancia_porcentaje"),
               "estabilidad_lecturas": ensayo.get("estabilidad_lecturas"),
               "estabilidad_periodo_ms": ensayo.get("estabilidad_periodo_ms"), "espera_maxima_ms": None}
    valores.update(mensaje.get("parametros") or {})
    return valores


# Presenta numeros conocidos y senala los parametros que la placa todavia no ha informado.
def valor_real(valor):
    return f"{valor:g}" if isinstance(valor, (int, float)) and math.isfinite(valor) else "no informado"


# Describe el motivo sin confundir un corte externo con el vencimiento del limite del motor.
def describir_error(mensaje, configuracion):
    motivo = mensaje.get("motivo", "error_sin_motivo")
    texto = MOTIVOS.get(motivo, f"Error informado por la placa: {motivo}")
    valores = parametros_reportados(mensaje, configuracion)
    if motivo in ("mando_rechazado", "parametros_ENSAYO_invalidos", "calibracion_servo_incompleta"):
        texto += (f". Motor: 0 a {valor_real(valores['motor_maximo_porcentaje'])} %; "
                  f"servo: {valor_real(valores['servo_minimo_deg'])} a {valor_real(valores['servo_maximo_deg'])} grados")
        if motivo == "parametros_ENSAYO_invalidos":
            texto += f"; espera: entero de 0 a {valor_real(valores['espera_maxima_ms'])} ms"
    if motivo in ("ordenar_freno_liberado", "motor_requiere_reposo_CONFIG_y_liberacion"):
        texto += f". Angulo de liberacion informado: {valor_real(valores['servo_liberado_deg'])} grados"
    if motivo == "velocidad_maxima_no_alcanzada":
        texto += (f". Criterio: {valor_real(valores['estabilidad_lecturas'])} lecturas en "
                  f"+/-{valor_real(valores['estabilidad_tolerancia_porcentaje'])} %, "
                  f"cada {valor_real(valores['estabilidad_periodo_ms'])} ms")
    if motivo == "limites_motor_incompletos":
        texto += (f". Reportado: {valor_real(valores['motor_maximo_porcentaje'])} % y "
                  f"{valor_real(valores['motor_maximo_impulso_ms'])} ms")
    return texto
