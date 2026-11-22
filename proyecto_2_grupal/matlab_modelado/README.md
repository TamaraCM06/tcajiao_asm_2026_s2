# 1. Modelado y analisis MATLAB

## 1.1. Responsabilidad y estado

`visualizar_ensayo.m` recibe el CSV de un escalon del servo, grafica el ensayo,
ajusta K y tau y calcula h(t) con `impulse` (Tarea 2, pregunta 7). La
[recepcion serial](../experimentos/README.md) guarda ese mismo CSV; no es un
segundo identificador.

| Entrada | Estado |
|---|---|
| tiempo_ms,freno_deg,velocidad_rpm | Contrato vigente del registrador abierto |
| Modelo experimental validado | Pendiente de datos reales y analisis del equipo |
| Diseno y simulacion PID | Pendiente |
| Metricas de comparacion final | Pendientes |

## 1.2. Unidades y condiciones

Convertir milisegundos a segundos si el analisis lo requiere. RPM significa
vueltas por minuto; rad/s = RPM por 2 pi / 60. La entrada freno_deg es una
orden de posicion, no par medido. Revisar NaN y eventos de ausencia de pulsos;
un cero por timeout no prueba que el sensor este conectado. Conservar el CSV
original y documentar cualquier filtrado o remuestreo.

Ajustar y validar con ensayos distintos. Registrar condiciones iniciales,
retardo, friccion, zona muerta, saturacion y acople del motor. Guardar modelos,
figuras y metricas derivados en resultados, sin duplicar capturas.

## 1.3. Relacion con las entregas

La [Tarea 2](../docs/referencias/ENUNCIADO_TAREA_2.md) usa un modelo teorico
para explicar impulso, escalon, muestreo y planta sin controlador; la
caracterizacion fisica es extra. El proyecto final exige identificacion real,
validacion y justificacion del controlador y muestreo. El PID final se
ejecutara en ESP32. MATLAB configura y analiza; no sustituye la demostracion
fisica del control.
