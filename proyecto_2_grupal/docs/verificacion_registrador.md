# 1. Cierre del bloque de captura ESP32

## 1.1. Estado y alcance

| Campo | Resultado |
|---|---|
| Fecha local | 21 de noviembre de 2026 |
| Responsable | Santiago, Persona 3 |
| Rama | sb/features/samplings |
| Alcance implementado | Captura abierta, mando manual de motor y freno, serial y receptor MATLAB minimo |
| Datos | tiempo_ms,freno_deg,velocidad_rpm; metadatos separados |
| Hardware accionado | Ninguno durante este bloque |
| Excluido por acuerdo | PID, referencia decreciente y secuencia automatica |

## 1.2. Cambios y fundamento

| Cambio | Ubicacion | Motivo |
|---|---|---|
| ESP32 e inhabilitacion sin calibracion | [Firmware](../firmware/README.md) | Sustituir la propuesta Pico y evitar parametros fisicos inventados |
| Medicion por intervalo de un flanco | [Estimador](../firmware/src/estimador_velocidad.c) | Calcular vueltas por minuto con 24 marcas propuestas |
| Mando manual y corte en START | [Coordinador](../firmware/src/aplicacion.c) | Registrar una entrada de freno conocida desde el corte de impulso |
| Cola y cierre con contadores | [Serial](../firmware/src/protocolo_serial.c) | Separar transmision de lectura y detectar capturas incompletas |
| Receptor con CSV inalterado | [MATLAB](../experimentos/README.md) | Entregar datos al analisis h(t) existente sin duplicarlo |

El tiempo entre marcas equidistantes representa una fraccion de vuelta. Las RPM
se obtienen como 60000000 dividido entre pulsos por vuelta e intervalo en us.
El angulo de servo es una orden; la fuerza y la dinamica dependen del montaje.
El muestreo conserva tiempos reales y contabiliza vencimientos sin inventar filas.

## 1.3. Comprobaciones

| Comprobacion | Resultado y limite |
|---|---|
| Codigo, documentacion y diff | Revisados por bloque; no es prueba funcional |
| ESP-IDF 5.5.5, target esp32 | Compilacion del registrador completada; configuracion fisica inhabilitada |
| Pruebas C host | 19 aprobadas; fuentes de produccion con fronteras SDK simuladas |
| Analizador MATLAB mlint | Sin observaciones en receptor, clase de registro y archivo de pruebas |
| Pruebas de ejecucion MATLAB | 10 preparadas; no ejecutadas: MATLAB R2025b solicita inicio de sesion para licencia |
| Sensor, PWM, USB/UART y mecanica | Sin comprobacion fisica |

Las pruebas incluyen bloqueo de motor durante captura, GPIO repetidos o
reservados, conversion invertida del servo, ausencia de pulsos, perdida de
periodos incluso al cerrar, saturacion de cola y un fallo PWM simulado.
El cierre completo solo comprueba coherencia de captura; no valida cada byte
como lo haria un CRC, ni confirma calibracion o integridad fisica del sensor.

## 1.4. Compatibilidad y reproduccion

El esquema anterior de nueve columnas era una propuesta sin consumidores
implementados en esta rama. Este bloque fija las tres columnas acordadas y
explica sus unidades en [experimentos](../experimentos/README.md). Se conserva
casos.json como plantilla deshabilitada del futuro PID; el receptor manual
recibe una estructura MATLAB y no ejecuta esas plantillas.

| Accion desde la raiz | Comando |
|---|---|
| Host | & proyecto_1_grupal/.venv/Scripts/python.exe -m pytest proyecto_2_grupal/firmware/tests -q |
| Compilacion | powershell.exe -NoProfile -ExecutionPolicy Bypass -File proyecto_2_grupal/firmware/ejecutar_idf.ps1 -Accion build |
| Pruebas MATLAB, licencia activa | resultados = runtests('proyecto_2_grupal/experimentos/tests'); assertSuccess(resultados); |

El ejecutor usa copia temporal ASCII y conserva sdkconfig local ignorado.
El binario inicial no configura GPIO ni acciona el banco. Una nueva configuracion
debe compilarse antes de programar; flash usa la ultima copia compilada.

## 1.5. Siguiente bloque

Confirmar modelo de puente, motor y fuente, completar esquema y calibraciones,
activar la licencia MATLAB y ejecutar sus pruebas. Despues adquirir un ensayo
abierto con evidencia real y entregarlo al companero para identificar y validar
el modelo. La configuracion de periodos de registro no acredita el extra 2 del PID.
