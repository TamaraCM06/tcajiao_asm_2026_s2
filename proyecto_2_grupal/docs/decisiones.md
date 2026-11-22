# 1. Decisiones del banco de frenado

## 1.1. Acuerdos del 21 de noviembre de 2026

Responsable del firmware: Santiago. Fuente: instrucciones del usuario y revision
del repositorio. Los acuerdos no acreditan compra, montaje ni medicion.

| Elemento | Acuerdo | Pendiente |
|---|---|---|
| Microcontrolador | ESP32 clasico; ESP-IDF 5.5.5 disponible | Confirmar placa fisica |
| Sensor | Modulo TCRT5000 frente a anillo reflectivo | Salida digital, nivel y polaridad |
| Disco | MDF cafe de aproximadamente 120 mm por 3 mm | Montaje y velocidad admitida |
| Marcas | 10 negras equidistantes, fondo blanco recomendado; un flanco por marca (PULSOS_POR_VUELTA = 10) | Rechazo de rebotes de 500 us |
| Distancia | Inicio propuesto 2 a 3 mm | Ajuste experimental con cinta real |
| Freno | MG90S y goma | Posicion liberada, limites, pulsos y sentido |
| Motor | Motor DC para impulso inicial | Modelo, corriente, fuente y acople |
| Puente | Fotografia compatible con modulo tipo L298N | Confirmar integrado, jumpers y alimentacion |
| Mando | Manual desde ESP32; START corta motor y registra | Comprobacion fisica |
| Transmision | Tres columnas CSV y receptor MATLAB minimo implementados | Verificacion final y captura fisica |
| Muestreo del PID | Ts = 20 ms propuesto en Tarea 2, pregunta 2 (coincide con la trama del servo) | Confirmar con la identificacion |
| PID y referencia | e = omega - omega_ref (e > 0 aprieta), Euler hacia atras, derivativo filtrado y anti-windup en `firmware/src/pid_controller.c`; rampa omega_ref = omega0 - a t | Integrar al firmware ESP32, identificar y sintonizar |
| Eje y transmision | Eje 8 mm, dos 608ZZ y rueda de goma propuestos | Compatibilidad y desacoplamiento |

## 1.2. Conexiones y calibracion

No hay GPIO elegidos. La configuracion queda inhabilitada hasta completar y
verificar el montaje. Se excluyen pines de flash, arranque, UART0 y 16/17 por
posible PSRAM. GPIO 34 a 39 solo admiten entrada y no tienen pull-up interno.

| Senal | GPIO ESP32 | Dato requerido |
|---|---|---|
| Salida digital TCRT5000 | Pendiente | Alimentacion, tension medida y flanco |
| MG90S | Pendiente | Fuente externa, frecuencia, pulsos, grados y liberacion |
| ENA, IN1, IN2 | Pendientes | Retirar jumper ENA para mando por GPIO; confirmar modulo |
| Tierra comun | No aplica | ESP32, sensor, servo y driver |
| Registro | UART0 por USB de la placa | 115200 baudios, 8N1 |

No alimentar el MG90S desde 3,3 V ni conectar una salida de 5 V al GPIO.
Verificar el modulo concreto: la ficha del TCRT5000 no garantiza niveles de
una placa con comparador. El corte electrico no implica desacople mecanico.
Documentar el acople real porque cambia la inercia y las perdidas.

## 1.3. Fundamento y fuentes

| Concepto | Criterio | Fuente |
|---|---|---|
| Optica | Respuesta maxima nominal cerca de 2,5 mm; verificar contraste infrarrojo | [Vishay TCRT5000](https://www.vishay.com/docs/83760/tcrt5000.pdf) |
| RPM | 60000000 / (pulsos_por_vuelta por intervalo_us) | Tiempo de una vuelta con marcas equidistantes |
| Corte del motor | ENA deshabilitado corresponde a marcha libre | [ST L298, tabla 5](https://www.st.com/resource/en/datasheet/l298.pdf) |
| Servo | Angulo solicitado no equivale a fuerza ni par | [Tower Pro MG90S](https://towerpro.com.tw/product/mg90s-3/) |
| Tiempo | Reloj monotono y callbacks breves | [ESP Timer 5.5.5](https://docs.espressif.com/projects/esp-idf/en/v5.5.5/esp32/api-reference/system/esp_timer.html) |

## 1.4. Continuidad

Registrar cada calibracion con identificador, fecha, responsable, evidencia y
limites admitidos. Los documentos academicos no autorizan por si solos
publicaciones, invitaciones, fusiones ni cambios del repositorio remoto.
