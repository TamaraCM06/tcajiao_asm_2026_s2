**Instituto Tecnológico de Costa Rica**  
Escuela de Ingeniería en Computadores  
CE 1110 — Análisis de Señales Mixtas

---

# Tarea 2

## Modelado de sistemas

---

| | | | |
|---:|:---|---:|:---|
| **Fecha de asignación:** | 11 noviembre 2026 | **Fecha de entrega:** | 22 noviembre 2026 |
| **Grupo:** | 3-4 personas | **Profesor:** | Luis Chavarría Zamora |

## 1. Descripción

Esta tarea tiene como objetivo que los estudiantes experimenten los puntos más importantes de diseño de un controlador.

1. ¿Por qué es importante la respuesta al impulso y al escalón para modelar sistemas? Ejemplifique cada una en su proyecto (20 %).
2. ¿Cómo determinar la frecuencia de muestreo de un sistema de control continuo? Proponga una frecuencia razonable para el proyecto suyo (15 %).
3. ¿Cómo se implementa un sistema PID en un microcontrolador? ¿Por qué no se debe usar la función `delay` como en Arduino? Muestre el código en un microcontrolador sin la función `delay` (15 %).
4. Realice un diagrama de bloques del sistema completo, de una descripción en prosa de todos los componentes tanto continuos como discreto (25 %).
5. De una representación matemática del sistema según la teoría. Explique cómo debería quedar la respuesta final de la planta (sin controlador) y algunos posibles valores que se puedan extraer teóricamente (25 %).
6. Construya la planta del proyecto (solo no tiene controlador pero si el resto de componentes)[^1] (40 % **extra**). Adjunte fotos y video de la construcción final. Se tendrá todo el puntaje si se ensambla completamente y se muestra un vídeo de su funcionamiento a lazo abierto.
7. Caracterice el sistema mediante la respuesta al escalón (40 % **extra**). Adjunte un vídeo de la respuesta al escalón (ejecutando la planta en físico con ustedes explicando y su funcionamiento en computadora, debe ser un solo vídeo). Debe usar la respuesta al impulso de Matlab (en el Laimi se encuentra). El proceso es muy similar al realizado en este [enlace](https://www.youtube.com/watch?v=HRaZLCBFVDE) para un motor DC (note que probablemente su proyecto sea más complejo que este).

[^1]: solo haría falta conectarlo a un microcontrolador para tener el sistema completo

## 2. Entregable

Se debe de subir en la sección de Evaluaciones los siguientes archivos en un archivo `*.pdf` con lo siguientes apartados a grandes rasgos:

1. Preguntas contestadas y los ejemplos de implementación interpretadas robustamente y basado en la teoría, así como fotografías de funcionamiento. Debe ser referenciado todo.
2. Programas del microcontrolador (puede ser un `listing`).
3. Para los vídeos coloque un enlace (o enlaces) a [YouTube](http://www.youtube.com/) como un enlace a un vídeo no listado o bien una lista de reproducción no listada.

Los `PDF` pueden ser realizados en Word o LaTeX en formato libre, lo mostrado debe ser legible y referenciado.

Si tienen dudas puede escribir al profesor al [correo electrónico](mailto:lachavarria@itcr.ac.cr). **Los documentos serán sometidos a control de plagios.** La entrega se debe realizar por medio del TEC-Digital en la pestaña de evaluación. Cualquier entrega después de las 11:59 pm recibiría una penalidad de un punto por minuto en la nota final.

---

*Tarea 2 — Modelado de sistemas — 2 páginas*
