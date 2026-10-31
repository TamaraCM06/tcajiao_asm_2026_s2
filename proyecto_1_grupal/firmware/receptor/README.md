# Nodo 1: Pico RP2040

ADC0/GPIO26, 10 kHz, bloques de 256; eliminación de DC por media flotante,
Hann + FFT radix-2 sobre una copia y estadísticas USB cada segundo.
`main.c` coordina hardware; `nodo1_metodos.c/.h` contienen DSP y tramas.
`receiver.c` es un archivo vacío previo, no participa en la compilación.

## Contrato actual: entrada analógica

Se conserva el [emisor ESP32](../esp32/README.md): CSV `contaminada` del notebook,
DAC GPIO25 a **16 kHz**, 96000 muestras/6 s, una emisión por arranque. No se
modifican exportador, casos ni firmware ESP32. Preparar Pico antes de reiniciar
el emisor; los identificadores Pico no representan índices del CSV.

Conectar GPIO25 → acondicionamiento/antialias → GPIO26 y GND común; rango ADC
0–3,3 V. Alternativamente usar OUT del MAX4466 alimentado a 3,3 V, sin unir
ambas salidas. Limitar la banda antes de 5 kHz; 16 kHz de reproducción y 10 kHz
de adquisición son relojes distintos. Las muestras Pico se expresan en voltios
con Vref nominal 3,3 V, sin normalización al rango del CSV.

## Contrato SPI v1: preparado, integración pendiente

El ESP32 actual **no recibe SPI ni ejecuta filtros**. Este acuerdo define su
futura interfaz; SPI permanece OFF para las pruebas autónomas de Pico.

| Elemento | Acuerdo |
|---|---|
| Roles | Pico maestro transmite; ESP32 esclavo recibe y distribuye a nodos 2/3 |
| Bus | SPI0, 2 MHz solicitados, **modo 1**, 8 bits, MSB primero; CS activo bajo |
| Cableado futuro | Pico GP18→ESP32 GP18 SCK; GP19→GP23 MOSI; GP17→GP5 CS; GP20←GP21 READY; GND común, 3,3 V |
| MISO | Sin uso; no se recibe ACK remoto |
| Transacción | 1032 bytes bajo un único CS: trama de 1031 + relleno `00` |
| Trama | `[0:1] AA BB`, `[2:5] id uint32 LE`, `[6:1029] 256 float32 IEEE-754 LE`, `[1030] CRC8`, `[1031] 00` |
| Muestras | Voltios sin DC, **sin Hann**, orden temporal, Fs=10000 Hz |
| CRC | CRC-8/SMBUS: poly=07, init=00, sin reflexión, xorout=00; cubre bytes 0–1029; relleno excluido |
| Secuencia | ID inicia en 0, avanza por bloque capturado, módulo 2³²; descartes producen huecos |
| READY | Alto solo cuando el esclavo tiene buffer armado; bajar al consumir cada transacción, antes de volver a armar y subir |
| Espera | Pico espera READY hasta 2 ms; tras envío espera su flanco descendente hasta 2 ms; cuenta fallos y no retransmite |

El futuro ESP32 debe usar RX DMA alineado a 4 bytes, capacidad >=1032 y comprobar
longitud **8256 bits**, cabecera, CRC, relleno, finitud y secuencia antes de
distribuir el bloque. Modo 1 y relleno atienden las [restricciones DMA del ESP32
clásico](https://docs.espressif.com/projects/esp-idf/en/v5.5/esp32/api-reference/peripherals/spi_slave.html#restrictions-and-known-issues).
El diagnóstico FFT permanece local: esta trama transporta solo muestras.
Un envío registrado no confirma validación remota. GP5 y demás pines propuestos
deben verificarse con la placa elegida y su configuración de arranque.
Si READY queda alto después de una transacción, no se vuelve a enviar hasta
observar su descenso; los bloques intermedios se omiten y sus IDs dejan huecos.

## Métricas, parámetros y conceptos

La consola imprime una tabla con una fila por segundo y repite los encabezados
cada 20 reportes y al reconectar. Cada fila resume todos los bloques procesados
en ese intervalo, para no ocultar sonidos breves entre impresiones. Los contadores
de errores acumulan desde el arranque; desconectar la consola no detiene la captura.

| Columna | Interpretación |
|---|---|
| `#` | Número de reporte enviado a la consola; empieza en 1 y continúa al reconectar. No es el ID de bloque ADC. |
| `t(s)` | Segundos desde el arranque de la Pico. |
| `Nivel` | `ACTIVIDAD` si el RMS máximo supera o iguala 5 mV; `BAJO` en caso contrario. Es un umbral eléctrico orientativo, no una detección de voz ni identificación de la fuente. Ajustable con la definición de compilación `NODO1_UMBRAL_ACTIVIDAD_MV`. |
| `RMS mV` | Nivel AC eficaz del intervalo: raíz de la media de los RMS al cuadrado de sus bloques, después de quitar la media de cada bloque. |
| `Max mV` | Mayor RMS de un bloque del intervalo; ayuda a ver golpes, palmadas o sonidos cortos. |
| `Pico Hz` | Frecuencia dominante del bloque con mayor RMS. Se oculta con `--` en nivel bajo. Resolución 39,0625 Hz; no identifica voz ni confirma que sea la señal deseada. |
| `DC V` | Promedio de las medias de los bloques. En MAX4466 suele rondar 1,65 V. |
| `Vpp V` | Diferencia entre máximo y mínimo ADC de todo el intervalo, convertida a voltios. |
| `Sat` | Total de muestras exactamente en 0 o 4095 durante el intervalo. Puede indicar recorte; con la entrada a GND también aumenta. |
| `Fs Hz` | Tasa de muestras entregadas por DMA. `!` indica intervalo inválido por reinicio de captura. |
| `Perd/Err/Rein` | Contadores acumulados de bloques descartados de cola, bloques con error ADC y reinicios de captura. Idealmente `0/0/0`. |

Cada 20 reportes se muestran además bloques capturados/procesados y tiempos
máximos DSP/ciclo del último intervalo. Con SPI habilitado se informa cada segundo
el total de envíos, esperas sin READY y esperas sin consumo; un envío no confirma
validación remota. La energía y la candidata de banda continúan calculándose
internamente, pero no aparecen en la tabla para facilitar la lectura.

Para comprobar el micrófono: observar el nivel en silencio, producir un sonido y
comprobar que suben `RMS mV`, `Max mV` y `Vpp V`. Con un tono sostenido conocido,
`Pico Hz` debe aproximarse a su frecuencia. `ACTIVIDAD` por sí sola no demuestra
que el micrófono esté conectado: una entrada flotante o ruido también puede activarla.

| Parámetro o concepto | Significado en este receptor |
|---|---|
| ADC / DAC | Conversión analógica a códigos digitales / conversión digital a voltaje. |
| GPIO26 / ADC0 | Pin de entrada analógica y canal ADC utilizado en la Pico. |
| Fs / N | 10000 muestras/s y 256 muestras por bloque: 25,6 ms de señal. |
| Vref | Referencia nominal de 3,3 V usada para convertir códigos a voltios; ajustar a la referencia medida para calibrar. |
| Antialias / Nyquist | Filtrar antes del ADC para evitar que frecuencias altas aparezcan como bajas; con Fs=10 kHz, Nyquist es 5 kHz. |
| Hann | Ventana que suaviza los extremos para reducir fuga espectral; se aplica solo a la copia de análisis. |
| FFT / bin / radix-2 | Transformada rápida a frecuencia; cada bin es una posición del espectro. Radix-2 divide el cálculo en etapas de dos entradas. Separación: Fs/N=39,0625 Hz. |
| DMA / buffer / FIFO | DMA mueve datos sin copiar cada muestra con CPU; los buffers guardan bloques y FIFO es la cola pequeña del ADC. |
| IRQ / ISR / cola | Interrupción, rutina que la atiende y almacenamiento temporal; aquí la ISR publica bloques y el bucle principal los procesa. |
| SPI / SCK / MOSI / MISO | Enlace síncrono, reloj, datos maestro→esclavo y datos esclavo→maestro; MISO no se usa aquí. |
| CS / READY / timeout | Selección de una transacción, permiso de recepción y tiempo máximo de espera. |
| Modo 1 / MSB primero | Reloj inactivo bajo y muestreo en flanco descendente; dentro de cada byte se transmite primero el bit más significativo. |
| Trama / CRC8 / relleno | Bloque de bytes con cabecera e ID; CRC8 detecta errores y el byte final adapta la longitud a DMA del ESP32. |
| float32 / little-endian | Muestra flotante IEEE-754 de 32 bits; los bytes de cada campo multibyte se envían del menos al más significativo. |
| USB CDC / DSP | Puerto serie virtual USB para consola / procesamiento digital de señales. |
| MSE / SNR | Error cuadrático medio y relación señal a ruido; requieren referencia limpia alineada y no se calculan aquí. |

La resta de media por bloque también modifica componentes de baja frecuencia.
La banda candidata comienza en 1600 Hz y su umbral relativo es 0,001 respecto
a la energía del pico dominante; una componente útil también puede cumplirlo.

## Por qué CMake

`CMakeLists.txt` describe cómo construir el firmware: importa Pico SDK, selecciona
los archivos C, enlaza ADC/DMA/SPI y matemáticas, habilita consola USB y genera
el archivo `.uf2`. CMake configura la compilación; el compilador ARM traduce el
código para RP2040. La opción `NODO1_HABILITAR_SPI` permite preparar ambas
variantes sin editar el código. Este proyecto no descarga el SDK automáticamente.

## Cómo probar el receptor

### 1. Comprobar los métodos en la computadora

Desde `proyecto_1_grupal/firmware/receptor/`, con GCC instalado y sin Pico SDK:

```bash
gcc -std=c11 -Wall -Wextra -Werror -I. nodo1_metodos.c tests/test_metodos.c -lm -o /tmp/test_nodo1
/tmp/test_nodo1
```

Debe imprimir `OK`. Comprueba DC/RMS, Hann, FFT contra DFT, estimación, formato
de trama y CRC8. No prueba ADC, USB, DMA ni SPI físicos.

### 2. Compilar y cargar la Pico

Requiere CMake, compilador ARM, herramienta de construcción Make o Ninja y
Pico SDK con su submódulo TinyUSB inicializado. Desde la misma carpeta:

```bash
cmake -S . -B build -DPICO_SDK_PATH=/ruta/pico-sdk -DPICO_BOARD=pico -DNODO1_HABILITAR_SPI=OFF
cmake --build build
```

1. Mantener BOOTSEL presionado al conectar la Pico por USB; soltar al aparecer la unidad `RPI-RP2`.
2. Copiar `build/nodo1_receptor.uf2` a esa unidad; la Pico reinicia automáticamente.
3. Abrir su puerto USB CDC con una terminal serie. En Linux suele ser `/dev/ttyACM0`; en Windows, un puerto COM. Se puede seleccionar 115200 en la terminal: no fija el muestreo ni la velocidad SPI.
4. Verificar el banner y los reportes aproximadamente cada segundo. La captura inicia aunque la consola no esté conectada.

### 3. Verificar la entrada sin integrar el ESP32

Con SPI en OFF, conectar MAX4466: VCC a 3V3, GND común y OUT a GPIO26 mediante
el acondicionamiento previsto. En silencio observar el offset y ruido de fondo;
al reproducir un tono cercano al micrófono, RMS y espectro deben responder.
No evaluar con GPIO26 flotante. Para una comprobación de cero, desconectar la
fuente y conectar GPIO26 a GND: ADC/DC/RMS deberían acercarse a cero, aunque
`sat` puede aumentar porque el código 0 también se cuenta como extremo.

Con un tono eléctrico conocido, usar una entrada acondicionada entre 0 y 3,3 V
y GND común. El pico debe aproximarse al tono con la limitación de resolución
FFT; revisar que no haya recorte y que los tres contadores `Perd/Err/Rein`
permanezcan en cero. Con SPI apagado sus contadores también quedan en cero.

Para un ensayo posterior con los casos del notebook, usar el contrato analógico
anterior: preparar Pico y consola, luego reiniciar el emisor. El caso 1 contiene
440/880/1320 Hz y una interferencia de 4000 Hz; la tabla muestra la frecuencia dominante del bloque más intenso de cada
intervalo, no una lista de todos los tonos.

### 4. Ver la forma de onda del micrófono

Compilar y cargar **el nuevo** `build/nodo1_receptor.uf2` siguiendo el paso 2.
Cerrar `cat` con Ctrl+C y cualquier otra terminal serie antes de abrir la gráfica.
Desde `proyecto_1_grupal/firmware/receptor/`:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r tools/requirements.txt
.venv/bin/python tools/graficar_microfono.py --puerto /dev/ttyACM0
```

Ejecutar en una sesión de escritorio Linux: se abre una ventana de Matplotlib.
Si falta el soporte de ventanas de Python, instalar el paquete Tk correspondiente
a Python de la distribución (`python3-tk` en Debian/Ubuntu, `tk` en Arch).
En este equipo Arch Linux falta la biblioteca nativa de Tk; instalarla con:

```bash
sudo pacman -S --needed tk
```

El visualizador selecciona TkAgg cuando Matplotlib utiliza Agg (sin ventana),
y avisa si falta Tk. Ejecutarlo sin sudo desde la sesión de escritorio.
Sin `--puerto`, el programa busca automáticamente una única Pico USB.

Si aparece `Permission denied`, este equipo usa el grupo `uucp` para el puerto:

```bash
sudo usermod -aG uucp "$USER"
```

Cerrar sesión e iniciarla nuevamente para aplicar el grupo y ejecutar el
visualizador **sin sudo**. En otra distribución verificar el grupo con
`ls -l /dev/ttyACM0` (puede ser `dialout`) y usar ese grupo en el comando.

La ventana muestra:

- Arriba: voltaje de entrada ADC, incluido el offset DC, con escala de 0 a Vref.
- Abajo: las mismas muestras después de restar su media, en mV; equivalentes a
  la señal preparada para SPI. La escala vertical se ajusta automáticamente:
  comparar RMS y Vpp para evaluar cambios de intensidad.
- Encabezado: número de captura visualizada, bloque ADC, DC, RMS y amplitud Vpp.
- Pie: saturaciones del bloque y contadores acumulados de pérdida/error/reinicio.

Cada captura contiene 256 muestras consecutivas a 10 kHz: **25,6 ms**. Se piden
unas cinco capturas por segundo. Hay huecos entre capturas y no se unen como si
fueran una grabación continua. La adquisición ADC y el DSP continúan trabajando
sobre todos los bloques. Vigilar los contadores para detectar problemas de captura.
El voltaje se estima a partir del ADC con Vref nominal de 3,3 V; no es una medida
calibrada ni permite reconstruir frecuencias superiores a Nyquist.

Conectar OUT del micrófono a GPIO26 con el acondicionamiento previsto y GND común;
mantener la entrada entre 0 y 3,3 V. En un MAX4466 el offset suele rondar 1,65 V.
Hablar o reproducir un tono y observar los cambios de amplitud y forma de onda.
Una entrada flotante también puede oscilar: no confirma recepción del micrófono.

Al cerrar la ventana se vuelve a la tabla, que puede abrirse de nuevo con los
comandos `stty`/`cat`. Si el programa se interrumpe abruptamente, la tabla retorna
tras dos segundos sin peticiones; no hace falta recargar firmware.

Protocolo USB de diagnóstico: el carácter `g` solicita un bloque y silencia la
tabla por dos segundos; `t` recupera la tabla. La respuesta es una línea ASCII
`ADC1,id,Fs,Vref,perdidos,errores,reinicios,N,codigo0,...,codigo255`.
Los códigos son los valores ADC crudos (0–4095), **antes** de eliminar DC.
No se modifica el contrato SPI ni se habilita SPI para esta visualización.
El lector descarta líneas incompletas o inválidas y muestra aviso si deja de
recibir capturas. Este protocolo USB no tiene CRC; el CRC del contrato SPI se conserva.

Pruebas del lector y conversión, sin Pico ni dependencias gráficas:

```bash
python3 -m unittest discover -s tests -p 'test_*.py'
```

### 5. Ensayo SPI posterior

Reconfigurar con `-DNODO1_HABILITAR_SPI=ON`, recompilar y cargar cuando exista
un esclavo compatible. Sin él, `sin_READY` aumentará y la adquisición continuará.
Esta etapa exige implementar recepción en el ESP32 conforme al contrato anterior.

Pendientes físicos: compilación ARM, tasa ADC real, continuidad/latencia,
acondicionamiento, recepción y CRC remoto SPI. Ante FIFO lleno o plazo DMA
perdido se reinicia captura y se informa; el rendimiento se debe medir en placa.
