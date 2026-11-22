# 1. Proyecto Grupal 2: banco de frenado

CE 1110, II semestre de 2026. Entrega y defensa: 2 de diciembre de 2026;
archivos hasta las 23:50. Fuente: [enunciado v7](docs/referencias/Proyectos_ASM_Proyecto_Grupal2_v7.pdf).

## 1.1. Estado y responsabilidades

| Elemento | Estado |
|---|---|
| Responsable de este bloque | Santiago, Persona 3 |
| Plataforma confirmada | ESP32 clasico, ESP-IDF 5.5.5 |
| Bloque actual | Registrador de frenado a lazo abierto para MATLAB |
| Hardware | TCRT5000, MG90S y puente tipo L298N; conexiones y calibraciones pendientes |
| Implementado | Firmware de captura y receptor MATLAB minimo |
| Modelo identificado, PID y extra 2 | Pendientes; el registro no acredita esos requisitos |
| Verificacion | Compilacion ESP-IDF y 19 pruebas C host; analizador MATLAB sin observaciones |
| Pendientes | Ejecucion de pruebas MATLAB por licencia; comprobaciones fisicas |

## 1.2. Organizacion

| Ubicacion | Responsabilidad |
|---|---|
| [Firmware](firmware/README.md) | Sensor, actuadores, temporizacion y serial |
| [Experimentos](experimentos/README.md) | Recepcion y CSV originales |
| [Modelado MATLAB](matlab_modelado/README.md) | Analisis e identificacion del equipo |
| [Decisiones](docs/decisiones.md) | Montaje, GPIO y calibraciones |
| [Requisitos](docs/requisitos.md) | Evidencias necesarias para las entregas |
| [Manual](docs/manual_operacion.md) | Operacion y comprobaciones pendientes |
| [Resultados](resultados/README.md) | Modelos, figuras y metricas derivados |

## 1.3. Entregas y continuidad

La [Tarea 2](docs/referencias/Tareas_ASM_Tarea2_v5.pdf), del 22 de noviembre,
incluye teoria, muestreo, codigo PID sin delay, diagrama y modelo teorico.
Construccion y caracterizacion fisica son extras de esa tarea. El proyecto final
exige planta real, identificacion validada con otros ensayos, PID y comparacion
de lazo abierto/cerrado con dos velocidades y tres repeticiones por condicion.

Este bloque conserva tiempo_ms, freno_deg y velocidad_rpm para el analisis del
companero. Despues se integraran referencia, error y PID. Permitir configurar el
registro no demuestra la comparacion experimental del extra 2.

## 1.4. Colaboracion

Trabajo incremental en sb/features/samplings. Conservar datos crudos y
configuracion efectiva por ensayo; separar simulacion de medicion. El PDF
presenta discrepancias development/develop y s1/s2: confirmar con el profesor
antes de cambiar nombres. Se conserva el historico de proyectos anteriores.

La [auditoria del bloque](docs/verificacion_registrador.md) registra cambios,
compatibilidad, comprobaciones y limites. No se ha medido el funcionamiento fisico.
