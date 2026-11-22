# Adquisición, modelado y análisis MATLAB

Estado: scripts pendientes de implementación. Ejecutarlos en el futuro resolviendo
rutas desde su propio archivo, sin depender del directorio de trabajo de MATLAB.
Registrar versión de MATLAB y toolboxes efectivamente usados.

| Script previsto | Entradas y salidas |
|---|---|
| `identificacion_planta.m` | Datos de identificación → modelo local; validación con ensayos independientes |
| `simulacion_pid.m` | Modelo, Ts y trayectoria → diseño discreto y simulaciones etiquetadas |
| `analisis_metricas.m` | Comparación final → IAE/RMSE, tiempo de frenado, oscilaciones, saturación y variabilidad |

Leer datos desde `../experimentos/datos/` y guardar salidas en `../resultados/`.
No duplicar capturas en esta carpeta. Registrar el método de identificación,
condiciones de validez, zona muerta, retardo y saturación; analizar polos y ceros
cuando corresponda. El ajuste y la validación deben usar ensayos diferentes.

Definir el intervalo común de evaluación, tratamiento de muestras perdidas y
umbral de parada antes de comparar ensayos. Usar el tiempo medido para integrar
el error y documentar cualquier remuestreo o filtrado. Conservar los datos crudos.

## Relación con la tarea y el proyecto final

En [Tarea 2](../docs/referencias/Tareas_ASM_Tarea2_v5.pdf), el modelo teórico ayuda
a explicar impulso, escalón, muestreo y comportamiento esperado sin controlador;
la caracterización física con MATLAB aparece en el apartado de puntos extra.

En el proyecto final, el modelo se obtiene de mediciones de la planta real y se
valida con otros ensayos. Sirve para diseñar y justificar el controlador y el
muestreo. La simulación permite estudiar ganancias antes de probarlas; el análisis
posterior compara los ensayos físicos de acción fija y PID.

MATLAB se ejecuta en la computadora. El PID final se ejecutará en la Pico mediante
`firmware/`; MATLAB podrá configurar casos y registrar datos, pero no sustituye
la demostración del controlador digital real. El proyecto exige modelado y análisis,
sin imponer MATLAB como única herramienta. La comunicación y los scripts aún no
están implementados.

La ejecución y adquisición tendrán una única entrada en
`../experimentos/ejecutar_caso.m` (pendiente). Esta carpeta se dedicará al
modelado, simulación y análisis; no mantendrá un segundo programa de envío de casos.
