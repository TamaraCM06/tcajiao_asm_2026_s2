# Manual de operación y defensa — por completar

Este documento es una plantilla. Completar con el hardware y software reales antes
de operar el banco. No constituye todavía un procedimiento validado.

1. Identificar componentes, conexiones, alimentación y versión del firmware.
2. Documentar fijación, protección del disco y velocidad máxima validada.
3. Explicar compilación y carga, dependencias y configuración de adquisición.
4. Definir arranque, calibración/verificación del sensor y velocidad inicial repetible.
5. Explicar selección de acción fija o PID y referencia decreciente.
6. Definir parada normal, liberación del freno y respuesta ante fallos.
7. Indicar cómo guardar un ensayo y reproducir métricas y gráficas.
8. Preparar una defensa de 15 minutos que muestre giro/medición, freno, registro,
   PID real, seguimiento y comparación, y explique modelo, Ts y ganancias.

## Registro y protocolos experimentales

El flujo de casos y datos está en [experimentos](../experimentos/README.md); el formato
de cada captura se define abajo.
En `experimentos/datos/registro_ensayos.csv`, guardar la fase, repetición,
velocidad medida, versión Git y observaciones. La celda
`configuracion_efectiva_json` conservará una copia completa de los parámetros
resueltos, calibraciones y versiones utilizadas, aunque luego cambie `casos.json`.
Separar ajuste y validación por ensayos completos usando el campo `fase`.
Conservar intentos fallidos con su motivo de exclusión y etiquetar simulaciones.

## Formato de muestras propuesto

Cada captura usa coma como separador, punto decimal y UTF-8, con una fila por
instante adquirido y el siguiente encabezado:

```csv
t_s,referencia_rad_s,velocidad_rad_s,error_rad_s,u_solicitada_norm,u_aplicada_norm,saturado,motor_habilitado,estado,ejecucion_us
```

| Campo | Significado |
|---|---|
| `t_s` | Tiempo monotónico desde el inicio, segundos |
| `referencia_rad_s` | Referencia, rad/s; vacío si no aplica |
| `velocidad_rad_s` | Velocidad medida, rad/s |
| `error_rad_s` | Velocidad menos referencia; vacío si no aplica |
| `u_solicitada_norm` | Mando del freno antes de limitar |
| `u_aplicada_norm` | Mando limitado entre 0 (liberado) y 1 (máximo calibrado) |
| `saturado` | 1 si el límite modificó el mando; 0 si no |
| `motor_habilitado` | 1 si se permite accionar el motor; 0 si está cortado |
| `estado` | Estado de la máquina del firmware (`IMPULSO`, `FRENADO`) |
| `ejecucion_us` | Duración del paso de control en esa muestra, µs |

La conversión a PWM/posición depende de la calibración; no asumir una relación
lineal entre mando y par. Esta organización y el protocolo serial son decisiones
del proyecto, no formatos prescritos por el enunciado.

# Protocolos experimentales

Antes de cada ensayo: comprobar fijación y protección del disco, calibración,
registro activo, límites de velocidad y forma de detener el banco. Estas
comprobaciones deben concretarse para el montaje real en el manual.

## Identificación y validación — etapa 3

1. Calibrar sensor y freno; registrar pulsos/vuelta, zona muerta, límites y retardo.
2. Definir velocidades iniciales y entradas conocidas, incluyendo acción fija
   o escalones de frenado. Registrar cómo se corta/reduce el motor.
3. Arrancar de manera repetible y registrar u(t), velocidad y tiempos reales.
4. Separar ensayos completos para ajuste y validación; no repartir muestras de
   una misma corrida entre ambos grupos como sustituto de validación independiente.
5. Ajustar un modelo local de velocidad o desaceleración y validarlo sobre datos
   no usados en el ajuste. Documentar región de validez, fricción y no linealidades.
6. Justificar Ts con la dinámica y los límites del sensor; registrar polos y ceros
   cuando el modelo lo permita.

## Diseño y sintonización — etapas 4 y 5

Definir referencia decreciente realizable y convención de error. Documentar ecuación
PID, discretización, derivada filtrada, anti-windup y saturación. Conservar cada
configuración de Kp, Ki y Kd, las gráficas y el efecto observado. Estudiar los tres
términos aunque la configuración final deje alguno en cero con justificación.

## Comparación final — etapa 6

Mínimo **12 ensayos**: 2 condiciones × 2 velocidades iniciales × 3 repeticiones.
La tabla usa etiquetas; elegir los valores físicos después de calibrar el banco.

| Condición | Velocidad inicial | Repeticiones mínimas |
|---|---|---|
| Lazo abierto, acción fija | Baja | 3 |
| Lazo abierto, acción fija | Alta | 3 |
| PID, referencia temporal | Baja | 3 |
| PID, referencia temporal | Alta | 3 |

Fijar antes de medir: tolerancia de velocidad inicial, referencia por velocidad,
mando de lazo abierto, ganancias finales, Ts, duración, umbral de parada e intervalo
de evaluación. Usar la misma referencia de evaluación al comparar ambos controles
para cada velocidad, aunque en lazo abierto no se realimente esa referencia.
Alternar el orden de pruebas y registrar temperatura/desgaste si afectan al freno.

Registrar referencia, velocidad, error y acción de control. Reportar IAE o RMSE,
tiempo de frenado, oscilaciones, saturación y variabilidad entre ensayos. Definir el
umbral y tiempo de permanencia que se usarán para declarar la parada. Documentar
exclusiones y repetir para conservar el mínimo de ensayos válidos.

Una menor duración de frenado por sí sola no demuestra un mejor ABS: el banco no
mide deslizamiento rueda–vehículo. Las mejoras opcionales requieren datos y análisis
adicionales y solo se evalúan cuando funciona el alcance básico.
