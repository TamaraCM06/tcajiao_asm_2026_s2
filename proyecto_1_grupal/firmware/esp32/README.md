# 1. ESP32: captura en PC y reproducción diferida

## 1.1. Aplicación vigente

| Campo | Valor |
|---|---|
| Responsable | Persona 3; integra adquisición Pico de Persona 1 y filtros del equipo |
| Entrada física | Pico a 16 kHz por SPI, bloques de 256 muestras |
| Procesamiento | FIR y espectral con estados independientes en ESP32 |
| Salidas | Entrada, FIR y espectral guardadas en PC como WAV PCM16 |
| Escucha | La PC envía una ruta seleccionada al DAC GPIO25 después de capturar |
| Evaluación controlada | CSV del notebook con mezcla y referencia; los filtros se ejecutan en ESP32 |
| Interfaz | Terminal sesiones.py, protocolo ASM2/1 a 1 Mbaud |
| Límites | Entrada 256, FFT 1024, salto 512; CSV de 256 a 960000 muestras, múltiplo de 256 |
| Firmware | Única aplicación de sesiones PC; sin selector de modos ni registros de señales en flash |
| Hardware actual | ESP32 clásico, DAC de 8 bits; configuración de placa de 4 MB conservada |

El [manual de usuario](../../docs/final/MANUAL_USUARIO.md) describe las pruebas de
entrega. La [guía técnica](GUIA_SESIONES.md) contiene conexiones, protocolo,
escalas, archivos y diagnóstico. El [TODO](../../docs/final/TODO.md) enumera
las comprobaciones y funciones que todavía faltan.

## 1.2. Compilación y operación

Comandos desde la raíz del repositorio, con el entorno ESP-IDF existente.

| Acción | Comando |
|---|---|
| Compilar | powershell.exe -NoProfile -ExecutionPolicy Bypass -File proyecto_1_grupal/firmware/esp32/ejecutar_idf.ps1 -Accion build |
| Programar | Mismo script con -Accion flash -Puerto COMx |
| Ver tamaño | Mismo script con -Accion size |
| Listar puertos | & 'proyecto_1_grupal/.venv/Scripts/python.exe' proyecto_1_grupal/firmware/esp32/tools/sesiones.py --listar |
| Abrir terminal | & 'proyecto_1_grupal/.venv/Scripts/python.exe' proyecto_1_grupal/firmware/esp32/tools/sesiones.py --puerto COMx --puerto-pico COMy |

El script compila una copia temporal ASCII para evitar fallos de ESP-IDF con las
tildes de la ruta. Programar utiliza la última compilación correcta registrada
en build/ruta_compilacion.txt. Repetir build después de cambiar código.
El nombre del binario emisor_esp32.bin se conserva por compatibilidad con el script.

No abrir monitor y sesiones.py sobre el mismo puerto. El firmware inicia
esperando órdenes; capturar no reproduce audio y reproducir no vuelve a filtrar.

## 1.3. Casos y coeficientes

| Identificador | Señal y ruido |
|---|---|
| P1 | Tono de 440 Hz e interferencia de 4000 Hz |
| P2 | Tres tonos y ruido de banda alta 2500–3800 Hz |
| P3 | Barrido sintético del notebook con ruido blanco |
| P4 | Transitorio e impulsos |
| P5 | Tres tonos y ruido superpuesto 600–1500 Hz |
| P2_tonal | Multitono histórico con interferencia de 4000 Hz, útil para el diagnóstico analógico |

Los [parámetros y semillas](../../tarea1_grupo1/metadatos/configuraciones.json)
se mantienen. Los alias caso_1/caso_2/caso_3 siguen admitidos al abrir casos
anteriores. Los CSV se preparan automáticamente cuando falta su copia local y
se transfieren desde PC; no se incorporan señales completas al firmware.

| Preparación desde proyecto_1_grupal | Comando y alcance |
|---|---|
| Casos | python -m herramientas.preparar_casos; genera las entradas ausentes sin reescribir el JSON fuente |
| Actualizar copias locales | Mismo comando con --regenerar; conserva los archivos históricos caso_N |
| Coeficientes FIR | python -m herramientas.exportar_coeficientes; ejecutar cuando cambie el diseño fuente |
| Diseño fuente | tarea1_grupo1/resultados/filtro_temporal/coeficientes_fir.csv |
| Constante C | [coeficientes_fir.c](components/filtros_digitales/coeficientes_fir.c), 75 valores float32 y símbolo COEFICIENTES_FIR |

## 1.4. Organización vigente

| Módulo | Responsabilidad |
|---|---|
| [app_main.c](main/app_main.c) | Iniciar únicamente el servicio de sesiones |
| [sesiones_pc](components/sesiones_pc/) | Comandos, adquisición desacoplada, reproducción e informes |
| [procesamiento_registro](components/procesamiento_registro/) | Procesamiento finito por bloques, alineación y cierre |
| [filtros_digitales](components/filtros_digitales/) | FIR, FFT/IFFT, selección espectral, reconstrucción y coeficientes |
| [evaluacion_digital](components/evaluacion_digital/) | Acumulación de métricas, sin banco secuencial de señales |
| [recepcion_spi](components/recepcion_spi/) | Tramas Pico, CRC y continuidad |
| [enlace_pc](components/enlace_pc/) | UART, CRC32, COBS y paquetes ASM2 |
| [salida_dac](components/salida_dac/) | Controlador DAC utilizado por la reproducción de archivos |
| [tools/pc](tools/pc/) | Cliente, archivos, terminal, concordancia e instrumentación |

La reubicación conserva los algoritmos, coeficientes, escalas y retardo causal de
37 muestras. El FIR conserva su historial; el espectral usa Hann simétrica,
FFT 1024, salto 512, umbral regional con piso global y suma solapada normalizada
por suma de Hann al cuadrado. La limpia solo evalúa: las ganancias espectrales se
estiman desde la mezcla.

## 1.5. Verificación y límites

| Comprobación | Interpretación |
|---|---|
| Python y ejecutor C de registro | Compara la aplicación vigente con los modelos sobre el mismo PCM16 |
| Silencio, reconstrucción unitaria y cierre | Verifica memoria e índices de arranque/finalización |
| Parámetros inválidos | Deben rechazarse antes de procesar |
| Controlador DAC | Sus pruebas con dobles de ESP-IDF se conservan porque lo utiliza la reproducción PC |
| Sesiones y protocolo | Verifican integridad, longitudes, cancelación y reapertura |
| Hardware | Las pruebas host no acreditan adquisición, antialiasing, sonido ni latencia física |
| Micrófono sin referencia | MSE, SNR y energía útil no disponibles; no se sustituyen por referencia de archivo |
| Tiempo | El máximo conjunto de cálculo no equivale a latencia física entrada/salida |
| Medidas nuevas | version_mediciones=2: costos individuales, espera en cola, evaluacion, publicacion y latencia digital con arranque/cierre separados |
| Region de interferencia | Se calcula en ESP32 con los residuos de mezcla y util filtrada; FFT 1024/Hann sobre bloques reales completos, region y longitud explicitas |
| Fuente fisica acordada | Audios del notebook por parlante hacia microfono; antialiasing de entrada y retardo analogico permanecen sin medir |

La latencia digital comienza al recibir la trama completa en ESP32 y termina
cuando UART acepta el paquete de salida; no incluye ADC, viaje UART, computadora
ni DAC. Los costos FIR y espectral incluyen calculo de referencia y se expresan
por 256 y 512 muestras nuevas respectivamente. Ver comandos, regiones y estados
no disponibles en el [manual, apartado 1.6](../../docs/final/MANUAL_USUARIO.md#16-qué-guarda-cada-corrida).

| Desde proyecto_1_grupal | Comando |
|---|---|
| Verificación conjunta | python -m pytest tarea1_grupo1/tests firmware/esp32/tests -q |
| Métodos Pico en PC | gcc -std=c11 -Wall -Wextra -Werror -I firmware/receptor firmware/receptor/nodo1_metodos.c firmware/receptor/tests/test_metodos.c -lm -o firmware/receptor/build/test_metodos.exe |

## 1.6. Continuidad y referencias

Las entregas previas permanecen en sus carpetas históricas. Las tablas anteriores
del artículo describen mediciones de sus versiones, no modos disponibles en esta
aplicación. No se programan placas, reproducen sonidos ni hacen commits al ejecutar
las herramientas de revisión.

Documentación de controladores: [ESP-IDF 5.5, DAC](https://docs.espressif.com/projects/esp-idf/en/v5.5/esp32/api-reference/peripherals/dac.html)
y [UART](https://docs.espressif.com/projects/esp-idf/en/v5.5/esp32/api-reference/peripherals/uart.html).
