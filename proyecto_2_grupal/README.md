# Proyecto Grupal 2: banco de frenado con PID digital

CE 1110 — Análisis de Señales Mixtas, II semestre de 2026.
Entrega y defensa: **2 de diciembre de 2026**; archivos hasta las **23:50**.
Fuente: [enunciado v7](docs/referencias/Proyectos_ASM_Proyecto_Grupal2_v7.pdf),
secciones 1–6. Es un banco didáctico de frenado; el antibloqueo simplificado es opcional.

Estado: estructura inicial, protocolos propuestos y plantillas. No hay firmware,
scripts MATLAB, modelo identificado ni resultados experimentales implementados todavía.
Raspberry Pi Pico/Pico SDK y MATLAB son elecciones de la propuesta del grupo,
no plataformas impuestas por el enunciado del proyecto. La Tarea 2 sí menciona
MATLAB en su apartado de caracterización extra.

## Organización

```text
proyecto_2_grupal/
├── firmware/
│   ├── include/                 # Interfaces y configuración de hardware
│   └── src/                     # Adquisición, actuadores, PID y máquina de estados
├── matlab_modelado/             # Adquisición, identificación, simulación y métricas
├── experimentos/
│   ├── casos.json              # Parámetros comunes y casos de todos los ensayos
│   ├── datos/                  # Capturas y registro_ensayos.csv
│   └── README.md               # Flujo de configuración y envío
├── resultados/
│   ├── modelos/                 # Parámetros identificados y condiciones de validez
│   ├── figuras/                 # Gráficas de datos reales y simulaciones identificadas
│   └── metricas/                # Resultados por ensayo y estadísticas por condición
└── docs/
    ├── referencias/             # Enunciado y bibliografía de apoyo
    ├── requisitos.md            # Correspondencia entre requisitos y evidencias
    ├── decisiones.md            # Pines, montaje, calibraciones y decisiones
    └── manual_operacion.md      # Guion de operación y defensa por completar
```

Los datos crudos tienen una sola ubicación en `experimentos/datos/`; MATLAB los
lee desde ahí. Los resultados derivados se guardan en `resultados/`. La fase de cada ensayo se registra en `experimentos/datos/registro_ensayos.csv`.
Los pines, materiales, esquema y calibraciones se documentan en `docs/decisiones.md`.

## Ruta de trabajo

1. Completar [decisiones](docs/decisiones.md), materiales, conexiones y calibraciones.
2. Implementar los módulos descritos en [firmware](firmware/README.md) y validar
   adquisición, arranque repetible y frenado variable.
3. Ejecutar los [protocolos](docs/manual_operacion.md#registro-y-protocolos-experimentales), identificar y
   validar el modelo con ensayos distintos; justificar el periodo de muestreo.
4. Diseñar, simular e implementar PID discreto con saturación, anti-windup y
   tratamiento del ruido; registrar el estudio de los tres términos.
5. Ejecutar la comparación final y generar métricas, figuras y artículo.
6. Verificar [requisitos](docs/requisitos.md) y completar el manual para la defensa.

## Reproducibilidad y colaboración

Cada ensayo debe relacionar su CSV, configuración efectiva, calibración, versión
Git del firmware, condiciones iniciales y observaciones. Conservar datos crudos;
los procesados deben poder regenerarse mediante scripts y parámetros versionados.
No mezclar señales simuladas con mediciones sin etiquetarlas.

El enunciado solicita `master` y `development`, ramas de trabajo, integración
incremental y una etiqueta de entrega. En el punto 5.6 también escribe `develop`:
confirmar con el profesor el nombre a utilizar. Registrar avances reales de todos
los integrantes; no concentrar el trabajo en un único commit final.

El repositorio actual se llama `tcajiao_asm_2026_s2`; el PDF indica el sufijo `s1`.
Confirmar esa discrepancia con el profesor antes de cambiar el nombre. Se conserva
la organización histórica `proyecto_1/`, `proyecto_1_grupal/` y `proyecto_2_grupal/`.

## Papel de MATLAB

MATLAB sirve para modelar la planta, simular el PID y analizar datos del banco
real; también podrá configurar casos y registrar por serial. El controlador final
se ejecutará en la Pico. Ver [modelado](matlab_modelado/README.md) para distinguir
lo solicitado en Tarea 2 de la identificación y validación del proyecto final.

## Entrada para ejecutar ensayos

Se prevé `experimentos/ejecutar_caso.m` como único punto de entrada en la
computadora: leerá `casos.json`, enviará el caso a la Pico por USB/UART y guardará
las mediciones en `experimentos/datos/`. Este programa y la recepción en el
firmware todavía están pendientes de implementar.
