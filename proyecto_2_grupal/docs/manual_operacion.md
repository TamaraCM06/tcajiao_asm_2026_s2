# 1. Operacion del registrador y continuidad del proyecto

## 1.1. Estado

Responsable del bloque: Santiago. Guia del software implementado; el montaje
fisico y sus valores siguen pendientes. No constituye evidencia de ensayo real.

## 1.2. Preparacion del banco

1. Completar [decisiones](decisiones.md), fijar disco y soportes y definir velocidad admitida.
2. Verificar fuente, tierra comun y salida digital del modulo optico compatible con 3,3 V.
3. Confirmar puente tipo L298N, conexiones y jumpers; retirar ENA para controlarlo.
4. Calibrar MG90S sin aplicar limites supuestos: grados, pulsos, liberacion y contacto.
5. Elegir GPIO admitidos en menuconfig y completar limites de motor y servo.
6. Confirmar conexiones verificadas, compilar y programar segun [firmware](../firmware/README.md).
7. Comprobar un flanco por marca y contar pulsos reales en una vuelta lenta.
8. Medir rango de RPM y elegir periodo de registro y timeout compatibles.

## 1.3. Ensayo manual

Seguir [captura MATLAB](../experimentos/README.md): abrir una sesion con nombre
nuevo, ordenar liberacion, impulsar y enviar START cuando la velocidad inicial
sea adecuada. START deshabilita el motor y fija el origen temporal. Conservar un
tramo previo al cambio de freno; aplicar el angulo elegido mediante FRENO.
El firmware registra el instante del cambio. STOP o la duracion maxima terminan
la captura y ordenan liberacion. Documentar si el motor siguio acoplado.

Al cerrar, revisar completo en el JSON, cantidades, muestras invalidas, perdidas,
tiempos y estado optico. Una captura completa puede contener cero inferido o
lecturas NaN: revisar los eventos antes de identificar la planta. Registrar
calibracion, repeticion, velocidad inicial medida, commit y observaciones en
el inventario del equipo. Conservar intentos fallidos con su motivo de exclusion.

## 1.4. Identificacion y validacion posteriores

Aplicar acciones conocidas desde condiciones iniciales controladas. Separar
ensayos completos de ajuste y validacion; no repartir una misma corrida como
sustituto de datos nuevos. Considerar friccion, zona muerta, retardo y saturacion.
Definir region de validez del modelo y justificar el muestreo. El receptor no
reemplaza el analisis MATLAB existente del companero.

## 1.5. PID y comparacion final pendientes

Disenar una referencia decreciente realizable, discretizacion, derivada filtrada,
saturacion y anti-windup. Estudiar Kp, Ki y Kd, aunque alguno termine en cero.
Conservar modificaciones y graficas de sintonizacion.

| Condicion final | Velocidad inicial | Repeticiones minimas |
|---|---|---|
| Lazo abierto, accion fija | Baja | 3 |
| Lazo abierto, accion fija | Alta | 3 |
| PID, referencia temporal | Baja | 3 |
| PID, referencia temporal | Alta | 3 |

Los 12 ensayos finales son posteriores a este bloque. Definir tolerancias de
inicio, referencia, umbral de parada e intervalo comun antes de medir. Comparar
IAE/RMSE, tiempo, oscilaciones, saturacion y variabilidad. Menor tiempo de
frenado por si solo no demuestra mejor ABS; no se mide deslizamiento vehicular.
Preparar defensa de 15 minutos con evidencia real. El extra 2 requiere dos
configuraciones del control y resultados experimentales, ademas de lo basico.
