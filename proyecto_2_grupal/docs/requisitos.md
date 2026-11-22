# Requisitos y evidencias

Fuente: [enunciado v7](referencias/ENUNCIADO_PROYECTO_2.md).
Todo está pendiente de ejecución; esta tabla asigna destinos, no acredita cumplimiento.

| Requisito | Sección del PDF | Evidencia prevista |
|---|---|---|
| Revisión de control, rotación, fricción, identificación y PID; límites del modelo lineal, máximo una página sin referencias | 2.1 | Marco teórico del artículo y bibliografía citada |
| Banco funcional, arranque repetible, frenado variable, materiales y esquema | 2.2 | `docs/decisiones.md` (montaje, materiales y esquema), registro de velocidad y demostración |
| Entradas conocidas, u(t), velocidad, retardo, fricción, zona muerta y saturación | 2.3 | Datos de identificación y calibraciones |
| Modelo local, validación con datos nuevos, polos/ceros cuando aplique y muestreo justificado | 2.3 | Datos de validación, scripts y modelos |
| PID digital, referencia decreciente, ecuación, discretización, ruido y anti-windup | 2.4 | Firmware, simulación y explicación de diseño |
| Análisis de polos y ceros del controlador y lazo cerrado según modelo | 2.4 | Modelos, figuras y artículo |
| Estudio de Kp, Ki y Kd, modificaciones, criterios y ganancias finales | 2.5 | Configuraciones, datos y figuras de sintonización |
| Acción fija vs. PID, dos velocidades y al menos tres repeticiones por condición | 2.6 | ≥12 ensayos finales y configuración efectiva |
| Referencia, velocidad, error, control, error de seguimiento, tiempo, oscilaciones, saturación y variabilidad | 2.6 | CSV, métricas y gráficas comparativas |
| Explicar por qué frenar más rápido no demuestra mejor ABS | 2.6 | Discusión y defensa |
| Giro, sensor, freno, registro, PID real, seguimiento y comparación en vivo; fijación y protección | 3 | Manual, fotos y demostración |
| Colaboración Git incremental, ramas e integración; etiqueta de entrega | 5 | Historial real del repositorio |
| Defensa de 15 minutos y entrega de todos los fuentes | 6 | Manual y revisión final |
| Artículo LaTeX ≤4 páginas incluidas referencias; abstract en inglés de 150–250 palabras; ≤6 palabras clave | 6 | Fuentes y PDF en `paper_ieee/` |
| Introducción, marco teórico, resultados de etapas 2–6, conclusiones y recomendaciones en prosa, bibliografía IEEE citada | 6 | Artículo final |
| Sin código fuente en documentos; referencias confiables citadas en texto | 6 | Revisión editorial del artículo |

La parte funcional vale 65 %. El PDF asigna 35 % a documentación y menciona 30 %
para el artículo sin desglosar el 5 % restante; consultar el criterio con el profesor.
Las bonificaciones de la sección 4 son opcionales y no sustituyen estos requisitos.

## Relación con Tarea 2

El [enunciado de Tarea 2 v5](referencias/ENUNCIADO_TAREA_2.md) corresponde a
una entrega separada, el 22 de noviembre de 2026. Pide teoría de impulso/escalón,
muestreo propuesto, código PID en microcontrolador sin `delay`, diagrama completo
y representación matemática de la planta. Construcción y caracterización física
son puntos extra de esa tarea; en el proyecto final la planta real, identificación,
PID y comparación experimental sí forman parte del alcance obligatorio.

Tarea 2 permite incluir el programa como listing en su PDF; la prohibición de
código fuente en documentos indicada arriba corresponde al artículo del proyecto.
El punto 1.7 menciona respuesta al escalón y también respuesta al impulso de MATLAB;
conservar esa distinción y consultar al profesor si requiere aclaración.
