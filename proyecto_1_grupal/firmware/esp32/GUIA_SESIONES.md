# 1. Captura en PC y reproducción diferida

## 1.1. Alcance y estado

| Campo | Valor |
|---|---|
| Responsable | Persona 3, aplicación ESP32; adquisición Pico de Persona 1 |
| Modo predeterminado | Sesiones PC; al arrancar espera comandos, no reproduce automáticamente |
| Flujo físico | Pico → SPI → FIR y espectral en ESP32 → USB → archivos en PC |
| Flujo de escucha | Archivo seleccionado → USB → ESP32 DAC → filtro analógico → GF1002 → parlante |
| Evaluación controlada | CSV del notebook → mezcla/referencia PCM16 → filtros y métricas en ESP32 |
| Bloques | Entrada 256; FFT 1024; salto 512; 16000 Hz |
| Duración inicial | 6 segundos, 96000 muestras; configurable entre 256 y 960000 muestras |
| Memoria | Estado y colas acotados; ningún registro completo se almacena en RAM de la placa |
| Pendiente físico | Velocidad USB real, continuidad ADC/SPI/DAC, niveles, escucha y respuesta analógica |

La aplicación completa dos filtros durante la captura y guarda sus resultados en la
computadora. El programa Python no aplica filtros para sustituir a la ESP32.
La escucha se realiza después y no modifica los archivos. El banco de archivos
no demuestra por sí mismo la adquisición física ni cubre toda la matriz P1–P6.

## 1.2. Conexiones

Desconectar la alimentación antes de modificar cables. Las etiquetas GPIO de ESP32
son números de señal, no números de posición física del conector.

| Origen | Destino | Función |
|---|---|---|
| Pico GP18, pin físico 24 | ESP32 GPIO18 | Reloj SPI |
| Pico GP19, pin físico 25 | ESP32 GPIO23 | Datos MOSI |
| Pico GP17, pin físico 22 | ESP32 GPIO27 | Selección CS; respeta el último cambio de la rama |
| ESP32 GPIO21 | Pico GP20, pin físico 26 | READY |
| GND Pico | GND ESP32 | Tierra común; señales SPI de 3.3 V |
| MAX4466 OUT acondicionado | Pico GP26/ADC0, pin físico 31 | Entrada analógica; entre GND y 3.3 V |
| MAX4466 VCC/GND | Pico 3V3 OUT/GND | Alimentación del micrófono |
| ESP32 GPIO25 | Entrada del filtro analógico acordado | Salida DAC |
| LM358 pin 7, salida del filtro | GF1002 Input L | Entrada de audio del módulo con acoplamiento integrado |
| GND común | GF1002 Input G y Power − | Referencia de señal y alimentación |
| Fuente regulada de 5 V | GF1002 Power + y LM358 pin 8 | Alimentación; LM358 pin 4 a GND |
| GF1002 Lout+ y Lout− | Los dos cables del parlante | No conectar Lout− a GND ni unir canales |

El filtro acordado usa divisor 10 kΩ/10 kΩ, primer operacional como seguidor,
Sallen-Key con R1=R2=4.7 kΩ, capacitor a tierra de 10 nF y realimentación de
20 nF, segundo operacional como seguidor, desacoplo de alimentación de 100 nF.
Su corte teórico es 2394 Hz y el divisor reduce amplitud a la mitad. Documentar
la medición real; no representa una respuesta analógica ya verificada.
El capacitor de alimentación del GF1002 marcado 10 V no autoriza alimentarlo a 10 V.

## 1.3. Preparación de software

Comandos PowerShell desde la raíz del repositorio. Cambiar COMx por el puerto
real que aparezca al conectar la placa. Los puertos Bluetooth no son la ESP32.

| Paso | Comando |
|---|---|
| Dependencias Python | & proyecto_1_grupal/.venv/Scripts/python.exe -m pip install -r proyecto_1_grupal/requirements.txt |
| Compilar ESP32 | powershell -ExecutionPolicy Bypass -File proyecto_1_grupal/firmware/esp32/ejecutar_idf.ps1 -Accion build |
| Programar ESP32 | powershell -ExecutionPolicy Bypass -File proyecto_1_grupal/firmware/esp32/ejecutar_idf.ps1 -Accion flash -Puerto COMx |
| Listar puertos | & proyecto_1_grupal/.venv/Scripts/python.exe proyecto_1_grupal/firmware/esp32/tools/sesiones.py --listar |
| Abrir herramienta | & proyecto_1_grupal/.venv/Scripts/python.exe proyecto_1_grupal/firmware/esp32/tools/sesiones.py --puerto COMx |

Compilar Pico con NODO1_HABILITAR_SPI=ON según su [README](../receptor/README.md).
La aplicación PC utiliza 2 000 000 baudios; el arranque ROM puede emitir a 115200.
La herramienta ignora solamente ese ruido inicial durante HELLO. No utilizar
idf.py monitor simultáneamente. Al iniciar mide 393216 bytes con CRC e índices:
exige al menos 120000 bytes/s, frente a los 96000 bytes/s de las tres señales.
Ese control del enlace no sustituye la prueba física completa de 60 segundos.

La compilación usa una copia temporal ASCII para evitar problemas de rutas con
tildes. El comando flash utiliza la última compilación correcta registrada; hay
que repetir build después de modificar código. El modo anterior con datos en
flash se conserva mediante APLICACION_DEMOSTRACION; la configuración predeterminada
del ayudante es APLICACION_PC. Quien use idf.py directamente debe seleccionar ese
modo en menuconfig si conserva un sdkconfig antiguo.

## 1.4. Uso de la terminal

| Comando | Resultado |
|---|---|
| ayuda | Lista de operaciones |
| estado | Configuración y sesión seleccionada; durante una operación indica OCUPADO |
| configurar segundos=6 | Duración redondeada hacia arriba a bloques de 256; muestra duración efectiva |
| configurar minimo_hz=1600 ancho_hz=100 factor=0.1 umbral=0.05 ganancia=1 | Parámetros iniciales; ganancia solo cambia la escucha |
| capturar | Guarda la entrada Pico y los dos resultados sin reproducirlos |
| evaluar caso_1 | Procesa el primer CSV existente del notebook; también caso_2 y caso_3 |
| evaluar "C:/ruta/prueba.csv" | CSV de cuatro columnas del notebook, o tiempo_s,contaminada sin referencia |
| reproducir entrada | Reproduce la entrada guardada por el DAC |
| reproducir fir | Reproduce el resultado FIR guardado |
| reproducir espectral | Reproduce el resultado espectral guardado |
| abrir "C:/ruta/sesion" | Selecciona una sesión completa anterior después de verificar integridad |
| detener | Cancela una operación; una captura parcial permanece incompleta |
| salir | Cancela si hace falta y cierra el puerto |

No se permite cambiar parámetros durante una operación. La Pico continúa
adquiriendo en reposo, pero esos bloques se descartan: capturar abre un intervalo
nuevo. Si aparece pérdida SPI, CRC incorrecto, cola llena, falta de datos o fallo
de transferencia, se aborta y se conserva evidencia de sesión incompleta.
Durante capturas físicas la PC envía un latido cada 0.5 s; dos segundos sin
latido cancelan la operación. Para registros de al menos un segundo se exige
cadencia estimada entre 15200 y 16800 muestras/s, para detectar una Pico antigua
a 10 kHz. Es una comprobación de compatibilidad, no calibración de frecuencia.

## 1.5. Archivos y escalas

| Archivo | Contenido |
|---|---|
| entrada.wav, fir.wav, espectral.wav | Mono, PCM16, 16000 Hz, misma longitud declarada |
| referencia.wav | Solo en evaluación con referencia; exactamente la referencia enviada |
| sesion.json | Estado, origen, escala, parámetros, versiones, hashes y resultados ESP32 |
| metricas.csv | Dos filas, una por método; celdas vacías para medidas no disponibles |
| eventos.log | Inicio, final o causa del fallo |

Las carpetas se crean bajo proyecto_1_grupal/resultados/sesiones, con identificador
único; no se sobrescriben sesiones anteriores. Guardar aparte las evidencias
seleccionadas para la entrega, porque resultados está ignorado por Git.

| Aspecto | Contrato |
|---|---|
| Transporte | q=limitar(floor(x/escala×32768+0.5), −32768, 32767); x=q×escala/32768 |
| Captura física | Escala fija 3.3 V; la entrada se cuantiza antes de procesar para que el WAV identifique exactamente la entrada DSP |
| CSV | Escala común calculada una vez sobre mezcla y referencia, con margen de un código; almacenada como float32 |
| Salidas | Misma escala que entrada, sin normalización por bloque; recortes contabilizados |
| Escucha física | Código DAC aproximado 128 + x×ganancia×255/3.3 |
| Escucha de archivos normalizados | Código DAC aproximado 128 + x×ganancia×127.5 |
| Formato de cálculo | float32; acumuladores de energía en double |
| Retardo | FIR causal y espectral retrasado 37 muestras; primeras 37 muestras no se usan para métricas |
| Intervalo de evaluación | Salidas [37,L), referencia/mezcla [0,L−37); no optimizar retardos distintos por método |
| Métricas | Calculadas antes de cuantizar las salidas WAV y antes del DAC/filtro analógico |

Por ello los WAV PCM16 y una medición analógica pueden diferir ligeramente de las
métricas calculadas sobre las salidas float32. Abrir los WAV directamente en otro
reproductor tampoco garantiza el mismo volumen eléctrico que el DAC.

## 1.6. Métricas y límites

| Modalidad | Disponible |
|---|---|
| Pico sin referencia | Energía total, recortes, tiempos, memoria y cadencia estimada. MSE/SNR/energía útil: no disponibles |
| Archivo con referencia | MSE, SNR entrada/salida/mejora, energía útil conservada, distorsión y atenuación de ruido total |
| Referencia espectral | Se filtra con las ganancias estimadas desde la mezcla; nunca decide la detección |
| Tiempo de cálculo | Suma, media y máximo del procesamiento conjunto, incluido el cierre; excluye envío serial |
| Tiempo de sesión | Incluye esperas y transferencia; no es latencia analógica extremo a extremo |
| Memoria | Tamaño del estado DSP y heap libre/mínimo; no implica disponer de toda la RAM del chip |

La atenuación reportada corresponde al ruido total, no a una medida independiente
de la interferencia principal. Los valores matemáticamente indefinidos se escriben
como null; no se sustituyen por cero. La referencia física sincronizada, las
repeticiones P1–P5, P6 y la caracterización analógica siguen requiriendo trabajo
experimental. La aceptación de escucha diferida debe contrastarse con la defensa.

## 1.7. Verificación final

| Comprobación | Criterio |
|---|---|
| Codec C/Python | Mismos bytes, CRC, COBS y detección de tramas corruptas |
| DSP finito | Coincidencia con Python dentro de 3e−6 en muestras float32; cierre de longitudes múltiplo de 256 |
| Archivos | 96000 muestras por ruta para 6 s; hashes consistentes; no sobrescritura |
| Reproducción | No refiltrar ni cambiar WAV; FIN solo después del consumo DMA |
| Cancelación/desconexión | Sesión incompleta, error explícito y posibilidad de reconectar |
| Placas | Verificar adquisición, enlace y sonido sin pérdidas; no confundir simulación con evidencia física |

| Comando desde la raíz | Alcance |
|---|---|
| & proyecto_1_grupal/.venv/Scripts/python.exe -m pytest proyecto_1_grupal/tarea1_grupo1/tests proyecto_1_grupal/firmware/esp32/tests -q | Modelo Python y núcleos C, protocolo y cliente |
| Desde firmware/receptor: & ../../.venv/Scripts/python.exe -m unittest discover -s tests -p test_graficar.py | Visualizador ADC1 de la Pico |

## 1.8. Protocolo y responsabilidades de módulos

| Elemento | Descripción |
|---|---|
| Cabecera | ASM2:4 bytes, versión:u8=1, tipo:u8, canal:u16, sesión:u32, secuencia:u32, índice:u32, longitud:u32; little-endian |
| Integridad | CRC-32/ISO-HDLC sobre cabecera y payload, anexado como u32; COBS sobre todo, delimitador 0 |
| Tamaño | Payload máximo 4096 bytes; muestras PCM16 little-endian |
| Tipos | 1 comando, 2 ACK, 3 entrada, 4 salida, 5 resultado JSON, 6 error, 7 audio, 8 sonda, 9 fin |
| Canales de salida | 1 entrada, 2 FIR, 3 espectral |
| Evaluación | Un paquete de 256 muestras, mezcla/referencia intercaladas si existe referencia; esperar ACK antes del siguiente |
| Audio | Paquetes de hasta 1536 muestras, ventana de dos paquetes pendientes; ACK libera capacidad |
| enlace_pc | UART, cola RX y codec portable |
| procesamiento_registro | FIR/FFT, historia corta, alineación, métricas y vaciado finito |
| sesiones_pc | Coordinación, adquisición desacoplada, reproducción e informe |
| tools/pc | Codec Python, cliente, almacenamiento y terminal separados |

Documentación de controladores: [UART ESP-IDF 5.5](https://docs.espressif.com/projects/esp-idf/en/v5.5/esp32/api-reference/peripherals/uart.html),
[DAC ESP-IDF 5.5](https://docs.espressif.com/projects/esp-idf/en/v5.5/esp32/api-reference/peripherals/dac.html),
[PySerial](https://pyserial.readthedocs.io/en/latest/pyserial_api.html).
