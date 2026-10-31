CE 1110 - ANÁLISIS DE SEÑALES MIXTAS
Sesión asincrónica semana 12 - FFT y sistemas de modulación - Grupo 1
GUÍA GENERAL DE EJECUCIÓN

======================================================================
1. CONTENIDO DEL PAQUETE
======================================================================

ASM_Semana12_Grupo1.pdf
    Informe: diseño, criterios, resultados y discusión.

proyecto_1_grupal/prototipo.py y proyecto_1_grupal/metadatos/
    Punto 1 del taller: sistema completo en alto nivel (Python).
    Genera las señales, analiza con FFT, aplica el filtro FIR y el
    espectral y exporta figuras, WAV y métricas.

proyecto_1_grupal/firmware/esp32/
    Punto 2 del taller: emisor en ESP32 (C, ESP-IDF 5.5.5). Reproduce
    los tres casos por el DAC (GPIO25) y evalúa los filtros en la placa.

proyecto_1_grupal/firmware/receptor/
    Punto 3 del taller: receptor en Raspberry Pi Pico (C, Pico SDK).
    Adquiere por el ADC a 10 kHz, analiza bloques de 256 con Hann y FFT
    y reporta su diagnóstico por USB cada segundo.

proyecto_1_grupal/docs/avance2/
    El informe (informe.pdf), esta guía, las fuentes de los diagramas
    (Mermaid y PNG) y empaquetar_entrega.py, que arma este paquete a
    partir del repositorio. La estrategia de validación del receptor
    está en la Sección 3.4 del informe (Figuras 3.5 y 3.6).

proyecto_1_grupal/tarea1_grupo1/ y proyecto_1_grupal/herramientas/
    Módulos de procesamiento, configuraciones y semillas de los casos,
    pruebas automáticas y el exportador de señales hacia el firmware.

Todos los comandos se ejecutan desde la carpeta indicada en cada
sección. "RAÍZ" es la carpeta donde se descomprimió este paquete.

======================================================================
2. REQUISITOS
======================================================================

- Python 3.10 o posterior (probado con 3.13).
- Para las pruebas del núcleo C: gcc en el PATH (MinGW en Windows,
  GCC en Linux o el gcc de las Command Line Tools en macOS).
- Para el ESP32: Windows con PowerShell, ESP-IDF 5.5.5 instalado en
  C:/Espressif, una placa ESP32 clásica con al menos 4 MB de flash y
  un cable USB de datos.
- Para el receptor: una Raspberry Pi Pico, CMake, el compilador
  arm-none-eabi-gcc y el Pico SDK con TinyUSB. Sus pruebas en
  computadora solo necesitan gcc y Python 3.

======================================================================
3. PROTOTIPO PYTHON (punto 1)
======================================================================

Desde RAÍZ/proyecto_1_grupal:

  macOS / Linux:
    python3 -m venv .venv
    .venv/bin/python -m pip install -r requirements.txt
    .venv/bin/python prototipo.py --caso todos

  Windows:
    py -m venv .venv
    .venv\Scripts\python.exe -m pip install -r requirements.txt
    .venv\Scripts\python.exe prototipo.py --caso todos

Tarda menos de un minuto. Los resultados quedan en
proyecto_1_grupal/resultados/simulacion/todos/: figuras/, pruebas/
(WAV de referencia, ruido y mezcla), muestras/, salidas filtradas,
metricas.csv y la configuración efectiva (configuracion_ejecutada.json
y configuracion.csv).

Opciones: --caso caso_1|caso_2|caso_3, --salida <carpeta> y
--config <json>. Los ajustes están en metadatos/prototipo.json y los
casos en tarea1_grupo1/metadatos/configuraciones.json.

Resultado esperado en consola (SNR de salida en dB):
  caso_1: sin filtrar 10.002 | FIR 69.049 | espectral 29.976
  caso_2: sin filtrar  5.002 | FIR 65.140 | espectral 23.349
  caso_3: sin filtrar  0.000 | FIR  0.003 | espectral  0.003

======================================================================
4. PRUEBAS AUTOMÁTICAS
======================================================================

Desde RAÍZ, con el entorno creado en la sección 3:

  macOS / Linux:
    proyecto_1_grupal/.venv/bin/python -m pytest proyecto_1_grupal/firmware/esp32/tests proyecto_1_grupal/tarea1_grupo1/tests -q

  Windows:
    proyecto_1_grupal\.venv\Scripts\python.exe -m pytest proyecto_1_grupal/firmware/esp32/tests proyecto_1_grupal/tarea1_grupo1/tests -q

Resultado esperado: 117 passed (94 del modelo Python, 16 del núcleo C
de los filtros y 7 del cierre del DAC). Estas pruebas no programan la
placa.

======================================================================
5. EMISOR ESP32 (punto 2)
======================================================================

Los datos de los tres casos ya están incluidos en el firmware. Solo
hay que exportarlos de nuevo si se cambian las señales. En ese caso,
desde RAÍZ (Windows, con el entorno de la sección 3):

  proyecto_1_grupal\.venv\Scripts\python.exe -m proyecto_1_grupal.herramientas.exportar_senales

Compilar, programar y abrir la consola (PowerShell, desde RAÍZ;
cambiar COM5 por el puerto real de la placa):

  powershell -NoProfile -ExecutionPolicy Bypass -File proyecto_1_grupal/firmware/esp32/ejecutar_idf.ps1 -Accion build
  powershell -NoProfile -ExecutionPolicy Bypass -File proyecto_1_grupal/firmware/esp32/ejecutar_idf.ps1 -Accion flash -Puerto COM5
  powershell -NoProfile -ExecutionPolicy Bypass -File proyecto_1_grupal/firmware/esp32/ejecutar_idf.ps1 -Accion monitor -Puerto COM5

- El script compila una copia en una ruta sin tildes ni espacios. Si
  ESP-IDF está en otra ubicación, usar -RutaSdk, -RutaHerramientas y
  -PythonSdk.
- Al arrancar, la placa recorre caso_1, caso_2 y caso_3. En cada uno
  emite 6 s por el DAC y luego evalúa el FIR y el espectral. Al final
  imprime RESUMEN FINAL y DEMOSTRACION COMPLETADA.
- EN/RESET repite la secuencia. Ctrl+] cierra el monitor.
- Detalle del firmware: proyecto_1_grupal/firmware/esp32/README.md.

======================================================================
6. RECEPTOR RASPBERRY PI PICO (punto 3)
======================================================================

Pruebas en computadora, sin Pico, desde
RAÍZ/proyecto_1_grupal/firmware/receptor:

  gcc -std=c11 -Wall -Wextra -Werror -I. nodo1_metodos.c tests/test_metodos.c -lm -o test_nodo1
  ./test_nodo1                                      (Windows: test_nodo1.exe)
  python3 -m unittest discover -s tests -p "test_*.py"

La primera debe imprimir OK (DC, RMS, Hann, FFT frente a DFT, pico,
CRC-8 y trama) y la segunda, 4 pruebas OK.

Compilar y cargar (desde la misma carpeta):

  cmake -S . -B build -DPICO_SDK_PATH=/ruta/pico-sdk -DPICO_BOARD=pico -DNODO1_HABILITAR_SPI=OFF
  cmake --build build

- Mantener BOOTSEL presionado al conectar la Pico por USB y copiar
  build/nodo1_receptor.uf2 a la unidad RPI-RP2.
- Abrir el puerto USB de la Pico con una terminal serie (la velocidad
  no importa). Cada segundo imprime una fila con Nivel, RMS, Max,
  Pico Hz, DC, Vpp, Sat, Fs y Perd/Err/Rein.

Prueba con el emisor:
  1. Conectar las placas como indica la sección 7.
  2. Cargar la Pico y abrir su consola.
  3. Pulsar EN/RESET en el ESP32 para que emita los tres casos.
  4. Revisar las filas de cada emisión de 6 s con la Figura 3.6 del
     informe y los valores de la sección 8.

Visualizador opcional de la forma de onda (Linux o macOS), con la
consola serie cerrada:

  python3 -m venv .venv
  .venv/bin/python -m pip install -r tools/requirements.txt
  .venv/bin/python tools/graficar_microfono.py

Detalle del receptor: proyecto_1_grupal/firmware/receptor/README.md.

======================================================================
7. CONEXIÓN FÍSICA
======================================================================

Emisor:
  ESP32 GPIO25 (DAC)  -> entrada del receptor
  ESP32 GND           -> GND del receptor
  La señal es unipolar: media cerca de 1.65 V, mezcla entre 0.32 y
  2.98 V aproximadamente. No necesita fuente externa. Entre un caso y
  otro el DAC se deshabilita.

Receptor Raspberry Pi Pico:
  GPIO25 -> R serie 1 kOhm -> nodo -> GPIO26 / ADC0 de la Pico
                               nodo -> C 33 nF -> GND
  GND ESP32 <-> GND / AGND de la Pico
  El filtro RC (fc = 4.8 kHz aprox.) limita la banda antes del
  Nyquist de la Pico (5 kHz). No aplicar más de
  3.3 V a la entrada del ADC. Ver las Figuras 3.5 y 3.6 del informe.

======================================================================
8. VALORES DE REFERENCIA
======================================================================

Emisor ESP32, ejecución del 30/10/2026 (Figura 4.1 del informe),
95 963 muestras por evaluación:

  caso    filtro     SNR sal (dB)  mejora (dB)  máx. por bloque
  caso_1  FIR          69.0489      59.0472      8.828 ms / 16 ms
  caso_1  espectral    29.9760      19.9743     18.863 ms / 32 ms
  caso_2  FIR          65.1396      60.1379      8.828 ms / 16 ms
  caso_2  espectral    23.3486      18.3468     18.945 ms / 32 ms
  caso_3  FIR           0.0034       0.0029      8.803 ms / 16 ms
  caso_3  espectral     0.0027       0.0022     18.838 ms / 32 ms

Los tiempos pueden variar ligeramente entre ejecuciones. Las métricas
deben coincidir con las de Python en al menos 0.03 dB.

Receptor Pico, valores esperados durante cada emisión de 6 s (Tabla
3.10 del informe, calculados con los códigos DAC, sin el filtro RC):

  caso    Fs (Hz)   DC (V)  Vpp (V)  RMS (mV)  Pico (Hz)  Sat  Perd/Err/Rein
  caso_1  ~10000    1.65    <=2.45   470-635   429.7      0    0/0/0
  caso_2  ~10000    1.65    <=2.64   330-455   429.7      0    0/0/0
  caso_3  ~10000    1.65    <=2.60   295-440   429.7 *    0    0/0/0

Aceptación: DC entre 1.48 y 1.82 V, Nivel ACTIVIDAD y pico entre
390.6 y 468.8 Hz (bin 11 +-1). * En el caso 3 algunas filas pueden
mostrar la zona de 880 Hz por el ruido superpuesto. Las filas de las
pausas entre casos no se evalúan.
