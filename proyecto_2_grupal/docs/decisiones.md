# Decisiones y pendientes

| Tema | Estado / decisión |
|---|---|
| Ubicación | `proyecto_2_grupal/`, consistente con el proyecto grupal anterior |
| Microcontrolador | Pico/Pico SDK propuesto; confirmar modelo exacto y versión SDK |
| Análisis | MATLAB propuesto; registrar versión y toolboxes al implementar |
| Sensor | Propuesta: encoder óptico de 12 marcas, 24 flancos/vuelta, ω por tiempo entre flancos con timeout de 100 ms (Tarea 2, pregunta 2). Pendientes montaje y calibración |
| Motor y potencia | Pendiente: driver, alimentación, arranque repetible y corte |
| Freno | Servo MG90S que presiona una goma contra el disco; PWM de 50 Hz, pulso de 1000 a 2000 µs provisional. Pendientes mecánica, zona muerta y saturación |
| GPIO | Pendiente de esquema eléctrico |
| Muestreo | Ts = 20 ms propuesto (Tarea 2, pregunta 2); confirmar con la identificación |
| Control | `e = ω − ω_ref` (e > 0 aprieta), Euler hacia atrás, derivativo filtrado sobre la medición y anti-windup por clamping, en `firmware/src/pid_controller.c`. Ganancias provisionales; pendiente diseñarlas con el modelo |
| Referencias | Propuesta: rampa ω_ref = ω₀ − a·t con a entre la desaceleración natural y la máxima. Pendientes valores medidos |
| Registro | USB; formato de muestras en [manual_operacion.md](manual_operacion.md#formato-de-muestras-propuesto), ya usado por `docs/tarea_2/codigo/main_tarea2.c` |
| Parada y fallos | Pendientes límites seguros, umbral de parada y respuesta a pérdida de sensor |
| Repositorio | Confirmar sufijo `s1` del PDF frente al actual `s2` |
| Ramas | Confirmar discrepancia `development` / `develop` del PDF |
| Tarea 2 | Informe en `docs/tarea_2/` (entrega 22 de noviembre de 2026); pendientes los extras 6 y 7 con la planta física |

Registrar cada resolución con fecha, responsable, evidencia y motivo. Los requisitos
del documento orientan las entregas; no autorizan cambios de repositorio remoto,
invitaciones, fusiones ni publicaciones automáticas.

## Montaje físico y conexiones

La documentación física se centraliza aquí; no se utiliza una carpeta `hardware/`.
El programa que controla los pines pertenece a `firmware/`. Completar las tablas
con valores reales y mantenerlas coherentes con la configuración del firmware.

| Señal / componente | GPIO Pico | Conexión / alimentación | Observaciones |
|---|---|---|---|
| Sensor de velocidad | GPIO2 (provisional) | Pull-up interno, 3,3 V | Interrupción en ambos flancos |
| Puente H / etapa del motor | GPIO16 (provisional) | Pendiente | Encendido/apagado para el impulso inicial |
| Servomotor de freno | GPIO15 (provisional) | Pendiente | PWM 50 Hz, pulso 1000–2000 µs por calibrar |
| Registro USB | USB de la Pico | — | CSV según el formato de muestras del manual |

### Materiales y esquema

Pendiente: lista de componentes, cantidades, especificaciones y costos; diagrama
completo de conexiones, fuentes y masas. El esquema eléctrico sigue siendo un
entregable del proyecto aunque se documente aquí. Puede incorporarse como diagrama
editable o enlazar su exportación desde este documento cuando se diseñe.

### Mecánica, calibraciones y evidencias

Pendiente: dimensiones y fijación del disco, acople, goma, protecciones y
velocidad máxima validada. Registrar calibración del sensor y correspondencia
PWM/posición del servo, contacto, zona muerta, saturación y retardo. Cada calibración
tendrá identificador, fecha y resultados para relacionarla con los ensayos.
Las fotos y enlaces a videos del montaje se incorporarán a la documentación de
la entrega que corresponda. No son código ejecutable para la Pico.
