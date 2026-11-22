# Decisiones y pendientes

| Tema | Estado / decisión |
|---|---|
| Ubicación | `proyecto_2_grupal/`, consistente con el proyecto grupal anterior |
| Microcontrolador | Pico/Pico SDK propuesto; confirmar modelo exacto y versión SDK |
| Análisis | MATLAB propuesto; registrar versión y toolboxes al implementar |
| Sensor | Pendiente: tecnología, pulsos/vuelta, límites, filtrado y calibración |
| Motor y potencia | Pendiente: driver, alimentación, arranque repetible y corte |
| Freno | Servo propuesto; pendientes mecánica, PWM, zona muerta y saturación |
| GPIO | Pendiente de esquema eléctrico |
| Muestreo | Ts pendiente de identificación y capacidad del sensor |
| Control | Pendientes signo definitivo, discretización, derivada, anti-windup y ganancias |
| Referencias | Pendientes trayectorias físicamente realizables y velocidades iniciales |
| Registro | USB/UART pendiente; contrato CSV inicial en `experimentos/README.md` |
| Parada y fallos | Pendientes límites seguros, umbral de parada y respuesta a pérdida de sensor |
| Repositorio | Confirmar sufijo `s1` del PDF frente al actual `s2` |
| Ramas | Confirmar discrepancia `development` / `develop` del PDF |
| Tarea 2 | Enunciado v5 recibido: modelado, muestreo, PID sin delay y diagrama del sistema; entrega 22 de noviembre de 2026 |

Registrar cada resolución con fecha, responsable, evidencia y motivo. Los requisitos
del documento orientan las entregas; no autorizan cambios de repositorio remoto,
invitaciones, fusiones ni publicaciones automáticas.

## Montaje físico y conexiones

La documentación física se centraliza aquí; no se utiliza una carpeta `hardware/`.
El programa que controla los pines pertenece a `firmware/`. Completar las tablas
con valores reales y mantenerlas coherentes con la configuración del firmware.

| Señal / componente | GPIO Pico | Conexión / alimentación | Observaciones |
|---|---|---|---|
| Sensor de velocidad | Pendiente | Pendiente | Tipo, pulsos/vuelta y niveles eléctricos |
| Puente H / etapa del motor | Pendiente | Pendiente | PWM, dirección, habilitación y corte |
| Servomotor de freno | Pendiente | Pendiente | PWM, alimentación y límites |
| Registro USB/UART | Pendiente | Pendiente | Puerto y protocolo |

### Materiales y esquema

Pendiente: lista de componentes, cantidades, especificaciones y costos; diagrama
completo de conexiones, fuentes y masas. El esquema eléctrico sigue siendo un
entregable del proyecto aunque se documente aquí. Puede incorporarse como diagrama
editable o enlazar su exportación desde este documento cuando se diseñe.

### Mecánica, calibraciones y evidencias

Pendiente: dimensiones y fijación del disco, acople, zapata, protecciones y
velocidad máxima validada. Registrar calibración del sensor y correspondencia
PWM/posición del servo, contacto, zona muerta, saturación y retardo. Cada calibración
tendrá identificador, fecha y resultados para relacionarla con los ensayos.
Las fotos y enlaces a videos del montaje se incorporarán a la documentación de
la entrega que corresponda. No son código ejecutable para la Pico.
