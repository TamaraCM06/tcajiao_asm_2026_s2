# Experimentos: configurar, enviar y registrar

```text
experimentos/
├── casos.json       # Aquí se editan los parámetros
├── datos/           # Aquí se guardan capturas y registro_ensayos.csv
└── README.md
```

## Desde dónde se enviarán los parámetros

La entrada prevista será `experimentos/ejecutar_caso.m`, ejecutada en MATLAB en
la computadora. Este archivo todavía no existe: el envío serial y la recepción
en el firmware están pendientes de implementar. Se ubicará aquí para mantener
juntos los casos y su ejecución. `matlab_modelado/` conservará los scripts de
identificación, simulación y análisis.

Flujo previsto:

```text
casos.json → ejecutar_caso.m (PC) → USB/UART → firmware en la Pico
                        ↑                         │
                        └──── mediciones ─────────┘
                        │
                        └→ datos/<ensayo_id>.csv
```

1. Editar [casos.json](casos.json): parámetros comunes y casos individuales.
2. Ejecutar `ejecutar_caso` indicando el identificador del caso y el puerto serial.
   La interfaz exacta se definirá al implementar el programa.
3. El programa combinará `comunes` con el caso elegido (prioridad del caso),
   validará parámetros y enviará la configuración al firmware.
4. La Pico ejecutará el ensayo y devolverá mediciones; el programa guardará cada
   repetición en un CSV y añadirá una fila a
   [datos/registro_ensayos.csv](datos/registro_ensayos.csv).

Los cuatro casos actuales son plantillas deshabilitadas para acción fija/PID y
velocidad baja/alta, con tres repeticiones cada uno. Completar los valores `null`
y validar la configuración antes de habilitarlos. Se pueden añadir casos de
identificación, validación y sintonización en el mismo JSON.

Los GPIO y las conversiones a PWM se implementan en `firmware/` y se documentan
en [decisiones.md](../docs/decisiones.md). El firmware recibe los parámetros del
ensayo; el JSON se lee en la computadora.

