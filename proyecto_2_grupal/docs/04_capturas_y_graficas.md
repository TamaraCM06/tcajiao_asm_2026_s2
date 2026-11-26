# 1. Capturas, resumen y gráficas de frenado

## 1.1. Instalación (una vez por computadora)

Todo se corre desde proyecto_2_grupal con banco.py, igual en Linux y Windows: en Linux
`python banco.py <acción>` (en Debian/Ubuntu `python3`), en Windows (PowerShell) `py banco.py <acción>`.
banco.py encuentra ESP-IDF solo y detecta el puerto si hay una sola placa; no hace falta abrir la
"ESP-IDF PowerShell" ni ejecutar `export`.

**Linux**

~~~bash
# Arch/CachyOS
sudo pacman -S --needed gcc git make flex bison gperf python cmake ninja ccache dfu-util libusb
sudo usermod -aG uucp $USER
# Debian/Ubuntu
sudo apt install git wget flex bison gperf python3 python3-pip python3-venv cmake ninja-build \
    ccache libffi-dev libssl-dev dfu-util libusb-1.0-0 gcc
sudo usermod -aG dialout $USER
# ESP-IDF 5.5.5 (cualquier distribución)
git clone --depth 1 --branch v5.5.5 --recursive --shallow-submodules \
    https://github.com/espressif/esp-idf.git ~/esp/esp-idf
~/esp/esp-idf/install.sh esp32
~~~

Cerrar sesión y volver a entrar para que valga el permiso del puerto; después `python banco.py preparar`.

**Windows**

1. Instalar [Python 3](https://www.python.org/downloads/) (deja el comando `py`).
2. Instalar ESP-IDF **5.5.5** con el *ESP-IDF Tools Installer* en la ruta que propone (`C:\Espressif`).
   Si se instala en otra ruta, definir `IDF_PATH` (carpeta de esp-idf) e `IDF_TOOLS_PATH` (herramientas).
3. Instalar el driver USB de la placa (CP210x o CH340) y, en PowerShell, `py banco.py preparar`.
4. Para `banco.py pruebas` hace falta gcc: [MSYS2](https://www.msys2.org/), `pacman -S mingw-w64-ucrt-x86_64-gcc`
   y agregar `C:\msys64\ucrt64\bin` al PATH.

Para `banco.py modelo` hace falta MATLAB (R2019a o posterior) o GNU Octave en esa computadora.

La ventana de Matplotlib utiliza Qt mediante PySide6-Essentials. Después de actualizar el
repositorio, ejecutar otra vez `python banco.py preparar` para instalar esta dependencia en
el mismo Python que usa banco.py. La exportación del PNG sigue disponible sin abrir ventanas.

## 1.2. Ejecución

Ejecutar desde proyecto_2_grupal. El banco utiliza Python y el entorno ESP-IDF 5.5.5
ya configurado para programar la ESP32. La generación de una gráfica desde CSV también
funciona sin placa y sin ESP-IDF si Python tiene las dependencias instaladas.

| Acción | Comando | Resultado |
|---|---|---|
| Instalar dependencias de PC | python banco.py preparar | Instala PySerial, pytest, prompt_toolkit y Matplotlib |
| Compilar firmware | python banco.py compilar | Genera el firmware sin programar la placa |
| Programar ESP32 | python banco.py flashear | Detecta el puerto; se puede indicar -p COM5 o -p /dev/ttyUSB0 |
| Abrir consola | python banco.py consola --nombre Demo | Prepara el registro y libera el freno |
| Ejecutar ensayo en la consola | ensayo 40 152 | Acelera al 40 %, espera estabilidad, corta, registra y ordena el freno |
| Guardar figuras sin abrir el visor | python banco.py consola --nombre Demo --sin-abrir-grafica | Conserva CSV, JSON y PNG al finalizar |
| Regenerar una figura existente | python banco.py graficar --archivo datos/Demo_m40_f152_10.csv | Lee el archivo y abre el PNG generado |
| Regenerar sin abrir el visor | python banco.py graficar --archivo datos/Demo_m40_f152_10.csv --sin-abrir-grafica | Genera únicamente el PNG |
| Campaña de identificación | python banco.py pid | Barrido de velocidad, elige alta y baja, y corre los ensayos del plan uno por Enter ([ensayos y modelo](05_ensayos_y_modelo.md)) |
| Modelo de la planta | python banco.py modelo | MATLAB (u Octave) sobre datos/identificacion; deja modelo.json, tablas y figuras |
| Ejecutar verificación en PC | python banco.py pruebas | Pruebas del núcleo C y herramientas Python; no mueve el hardware |

## 1.3. Datos y frecuencias

| Proceso o parámetro | Valor inicial | Fuente efectiva |
|---|---|---|
| Período del CSV | 20 ms, 50 filas/s | Respuesta CONFIG y JSON de la captura |
| Muestras mostradas durante la captura | Separación mínima de 100 ms, aproximadamente 10/s | Reloj de pantalla de PC; conserva las filas originales del CSV |
| Diagnóstico de estabilidad | Cinco lecturas nuevas en ±7 %, separadas al menos 500 ms | Firmware y configuración de ensayo recibida |
| Duración máxima del registro | 30000 ms | Respuesta CONFIG; distinta del tiempo de motor encendido |
| Impulso máximo continuo del motor | 30000 ms | Configuración de motor enviada por la ESP32 |
| Timeout del sensor | 100 ms | Respuesta CONFIG; cero RPM es una inferencia por ausencia de pulsos |
| Cierre automático tras cero RPM | 1000 ms continuos | Consola; envía STOP y espera el cierre del firmware |

La consola presenta más filas durante la captura, pero no imprime las 50 filas por segundo.
Al cerrar muestra una tabla con 20 posiciones distribuidas y añade las filas del máximo,
el cambio de freno, el primer cero y sus antecedentes cuando existan. La tabla muestra
el número de fila, tiempo_ms, freno_deg y velocidad_rpm con tres decimales; el CSV conserva todas.

| Parte del resumen | Cálculo y significado |
|---|---|
| Cantidad y tiempos | Filas recibidas y tiempos de primera y última muestra |
| RPM inicial, final, mínima y media | Valores del CSV; las velocidades no finitas se declaran ausentes |
| Máximo | Valor, instante y fila del pico, aunque no haya aparecido durante el refresco de pantalla |
| Muestreo observado | Media, mínimo y máximo de las diferencias de tiempo entre filas y frecuencia media correspondiente |
| Cambio de freno | Primera fila con la nueva orden; no mide el ángulo físico del servo |
| Pendientes RPM/s | Ajustes por mínimos cuadrados en los 300 ms anteriores y posteriores al único cambio de orden |
| Primer cero | Tiempo del primer 0 RPM posterior al cambio; se informa tanto desde el corte como desde el freno |
| Transporte | Producidas, enviadas, vencimientos perdidos y pulsos rechazados del mensaje de cierre |

## 1.4. Gráfica automática

Al llegar el cierre, la consola cierra CSV y JSON y entrega el análisis a un trabajador
independiente. La recepción serial queda libre para otra captura. El trabajador lee el CSV
cerrado, imprime el resumen, guarda un PNG con el mismo nombre y abre una ventana nativa de Matplotlib,
salvo que se haya indicado la opción para no abrirlo. Al salir se espera el trabajo pendiente.

| Elemento de la figura | Fuente |
|---|---|
| Curva superior | Todas las RPM originales contra tiempo, sin suavizado, interpolación ni cambio de escala |
| Curva inferior | Orden angular del servo como escalones |
| Marca de freno | Cambio de orden encontrado en el CSV |
| Marca de máximo | Pico de RPM con su instante |
| Marca de cero | Primera lectura cero posterior al freno, inferida por el sensor |
| Estado de integridad | JSON asociado: completa, incompleta o sin verificación disponible |

Las lecturas RPM no válidas dejan huecos. Una captura incompleta se rotula como tal;
dibujar sus datos no la convierte en válida. La generación no modifica los bytes del CSV ni del JSON.
Si falta una dependencia o falla la salida del PNG, se conserva el CSV y se muestra el error.

La exportación usa un backend sin interfaz gráfica y acceso serializado a Matplotlib,
siguiendo sus [indicaciones sobre hilos](https://matplotlib.org/stable/faq/howto_faq.html#work-with-threads).
La ventana utiliza [QtAgg con PySide6](https://matplotlib.org/stable/api/backend_qt_api),
lee el mismo CSV y conserva los ejes de velocidad y orden del servo, con las herramientas
de zoom, desplazamiento y guardado de Matplotlib. Se ejecuta en el hilo principal de un
proceso independiente, de modo que la consola continúa recibiendo datos mientras permanece abierta.
Los errores del proceso visor quedan en salidas/visores/<captura>.log. La opción
--sin-abrir-grafica conserva la exportación del PNG sin iniciar la ventana.

## 1.5. Errores y valores efectivos

Los mensajes de error nuevos incluyen los parámetros efectivos de motor, servo y estabilidad.
La consola prioriza los valores del propio error sobre la configuración que tuviera almacenada.
Si no existe un valor informado, lo indica en vez de sustituirlo por un límite supuesto.

| Mensaje o validación | Comportamiento |
|---|---|
| Orden rechazada | Explica el rango de motor y servo informado por la placa |
| ENSAYO inválido | Informa recorrido de servo y espera máxima efectiva |
| Freno no liberado | Indica el ángulo de liberación informado |
| Estabilidad no alcanzada | Indica lecturas, tolerancia y cadencia; no atribuye todo corte al límite de tiempo |
| Límite de impulso | Muestra maximo_impulso_ms del motor; la configuración vigente equivale a 30 s |
| CONFIG aceptado | La respuesta de firmware contiene período, duración y timeout realmente aplicados |
| Tiempos fraccionarios o no finitos | Se rechazan sin convertirlos silenciosamente en otro valor |
| Firmware anterior | Se usa la configuración recibida cuando exista; los datos ausentes se declaran no informados |

## 1.6. Tres capturas conservadas

Por solicitud del usuario, datos contiene las tres capturas más recientes del 25 de noviembre
de 2026, cada una con CSV, JSON y PNG. Se eligieron por fecha del CSV, no por fecha de regeneración
de la figura. La consola sigue guardando cada captura nueva; esta selección fue una limpieza puntual.

| Captura | CSV original | JSON original | Gráfica |
|---|---|---|---|
| 08 | [CSV 08](../datos/Demo_m40_f152_08.csv) | [JSON 08](../datos/Demo_m40_f152_08.json) | [PNG 08](../datos/Demo_m40_f152_08.png) |
| 09 | [CSV 09](../datos/Demo_m40_f152_09.csv) | [JSON 09](../datos/Demo_m40_f152_09.json) | [PNG 09](../datos/Demo_m40_f152_09.png) |
| 10 | [CSV 10](../datos/Demo_m40_f152_10.csv) | [JSON 10](../datos/Demo_m40_f152_10.json) | [PNG 10](../datos/Demo_m40_f152_10.png) |

Las demos anteriores se archivaron localmente en salidas/archivo_capturas_20261125 con
un manifiesto SHA-256. El [escalón histórico de la Tarea 2](../tarea_2/evidencias/banco_anterior/escalon_02.csv),
su JSON y su registro se conservan en las evidencias del banco anterior.

## 1.7. Estado y verificación

| Campo | Estado |
|---|---|
| Responsable | Santiago; integración de consola y evidencia del banco |
| Implementado | Más muestras, resumen completo, PNG automático y ventana nativa de Matplotlib, errores con parámetros efectivos y tres capturas seleccionadas |
| Revisión | Código, documentación, diff, enlaces y figura generada desde la captura 10 |
| Verificación en PC | 60 pruebas aprobadas con python banco.py pruebas, incluido el renderizado Qt en otro proceso sin mostrar ventanas; PNG de capturas 08, 09 y 10 conservado |
| Evidencia preservada | CSV y JSON originales; gráficos derivados y estado de integridad explícito |
| Pendiente físico | Cargar el firmware actualizado y comprobar mensajes y apertura automática del visor durante una sesión real |
| Continuidad | Comparar los ensayos y avanzar a la identificación de la planta con evidencia repetible |
