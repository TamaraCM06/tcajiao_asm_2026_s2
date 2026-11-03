# Pico → ESP32: filtros en vivo y pantalla IPS 80×160

Proyecto **nuevo** ESP-IDF 5.5.5 para el ESP32 clásico (ESP-32S/WROOM).
Los nodos 2 (FIR) y 3 (espectral) corren en una misma ESP32, sobre la misma
entrada, en paralelo lógico. Conserva el proyecto `../esp32` de demostración/DAC.
No programar los dos proyectos a la vez en la misma ESP32: este reemplaza su aplicación.

## Cableado corregido

Desconectar alimentación al cambiar cables. Todas las señales son de 3,3 V.
Conectar GND común aunque las placas se alimenten por USB separado.

| Pico SPI0 maestra | ESP32 VSPI esclava | Función |
|---|---|---|
| GP18 | GPIO18 | SCK |
| GP19 | GPIO23 | MOSI: bloques de audio |
| GP16 | GPIO19 | MISO: ceros; NO es ACK ni confirma CRC |
| GP17 | GPIO5 | CS, activo bajo |
| GP20 | GPIO21 | READY: ESP32 permite un envío cuando el DMA ya está preparado |
| GND | GND | Referencia común |

**READY es necesario.** El esclavo sube READY en `post_setup_cb`, lo baja en
`post_trans_cb` y lo mantiene bajo durante validación/procesamiento. Las
interrupciones solo cambian READY: filtros y dibujos se ejecutan en tareas.
La Pico espera READY, baja CS, transmite la trama completa, espera fin de SPI y
sube CS. Observa el descenso de READY antes de considerar otro envío.
El timeout de READY es 2 ms; si el ESP32 aún no puede recibir, se omite ese bloque
sin detener ADC. El próximo ID tendrá un hueco, que fuerza reinicio del DSP.
READY confirma fin de transferencia, **no** integridad CRC ni filtrado exitoso.

| Pantalla ST7735S, perfil supuesto 80×160 | ESP32 HSPI maestra |
|---|---|
| VCC | 3V3 |
| GND | GND |
| SCL/SCK | GPIO14 |
| SDA/MOSI | GPIO13 |
| RES/RST | **GPIO27**, reemplaza GPIO9 |
| DC/RS | **GPIO26**, reemplaza GPIO10 |
| CS | GPIO15 |

**No conectar RST/DC a GPIO9/10:** el ESP32 clásico los reserva a flash.
GPIO5 y GPIO15 son pines de strapping: los periféricos no deben forzar niveles
incompatibles durante reset. CS debe permanecer inactivo alto; usar un pull-up
externo (por ejemplo 10 kΩ) si el cableado lo requiere. Si el módulo expone BL/LED,
consultar su especificación y conectar la retroiluminación según corresponda;
este controlador no maneja un pin BL. No asumir que un LED sin resistencia admite 3,3 V directo.

La descripción “0.96 IPS 80×160 RGB” no identifica de forma unívoca el controlador.
Se implementa **ST7735S**, habitual en ese formato; confirmar el IC del módulo.
Es LCD IPS, no OLED SSD1306. En `idf.py menuconfig` → Audio Pico / filtros / pantalla
se pueden cambiar MADCTL (orientación/RGB-BGR), inversión y offsets. Perfil inicial
horizontal 160×80, MADCTL A8, offsets X=1/Y=26. Un panel con otro controlador
requiere su inicialización, no solo cambiar offsets.

## SPI: verificar antes de subir a 10 MHz

Se implementa **modo 0 solicitado** (CPOL=0/CPHA=0), MSB primero, 8 bits y DMA
`SPI_DMA_CH_AUTO`. El modo del esclavo está en `CONFIG_AUDIO_SPI_MODO`; el de la
Pico en `NODO1_SPI_MODO`. Ambos deben coincidir.

**Modo 0 + DMA es experimental para ESP32 clásico.** Espressif documenta restricciones
de DMA en modos 0/2 y timing especial de MISO; recomienda modos 1/3 si el maestro no
cumple esas restricciones. Este enlace no usa datos MISO para decisiones, pero eso
no acredita integridad del enlace ni elimina la necesidad de pruebas eléctricas.
Si aparecen CRC/longitud incorrectos, probar primero **modo 1 en ambos extremos**.
No presentar modo 0 a 10 MHz como validado solo porque compile.

Arrancar a **2 MHz**, con cables cortos y GND próximo a SCK. La Pico admite configurar
1–10 MHz. Una trama de 1032 bytes toma 4,128 ms a 2 MHz y 0,8256 ms a 10 MHz
(solo reloj; excluye CS, READY, latencia y procesamiento). El plazo de captura es
25,6 ms. No es necesario empezar en el límite para sostener 10 kHz.
La LCD usa otro bus a 20 MHz; dibuja desde una tarea separada y una cola de una
vista. Una cola adicional lleva estadísticas a una tarea de monitor: ni dibujos
ni impresión UART bloquean la ruta RX/DSP al publicar.

Contrato, sin cambios: 1032 bytes por CS; `AA BB`, ID uint32 little-endian,
256 float32 IEEE754 little-endian en voltios sin DC, CRC-8/SMBUS (poly07, init00,
sin reflexión, xorout00) sobre bytes 0–1029, y relleno00 en byte1031.
RX/TX están en memoria DMA interna alineada con capacidad de 1036 bytes: los 4 bytes
extra permiten detectar envíos demasiado largos sin confundir longitud truncada
con una trama válida de1032 bytes. Se comprueban **8256 bits exactos**,
cabecera, relleno, CRC, finitud y rango físico antes de usar las muestras.
No se transportan referencia limpia, Fs negociada, ACK ni resultados FFT.
Fs=10000 Hz y N=256 son un contrato fijo: recompilar ambos si cambia.

## Compilar y programar

Requiere una instalación **Linux** de ESP-IDF 5.5.5 y sus herramientas para ESP32.
Activar su entorno, por ejemplo `source /ruta/esp-idf/export.sh`.
Desde este directorio:

```bash
idf.py set-target esp32
idf.py menuconfig
idf.py build
idf.py -p /dev/ttyUSB0 flash monitor
```

En menuconfig, dejar **Autoprueba desactivada** para recibir la Pico.
Cambiar `/dev/ttyUSB0` al puerto de la ESP32 (no confundir con USB de la Pico).
Salir del monitor con Ctrl+]. El archivo de aplicación es `build/esp32_filtros_en_vivo.bin`;
`idf.py flash` también programa bootloader y tabla de particiones en sus direcciones.
No copiar ese binario a la unidad BOOTSEL de la Pico.

Pico, desde la raíz del repositorio:

```bash
cmake -S proyecto_1_grupal/firmware/receptor \
  -B proyecto_1_grupal/firmware/receptor/build \
  -DPICO_SDK_PATH="$HOME/.pico-sdk/sdk/2.3.1" \
  -DPICO_BOARD=pico -DNODO1_HABILITAR_SPI=ON \
  -DNODO1_SPI_MODO=0 -DNODO1_SPI_HZ=2000000
cmake --build proyecto_1_grupal/firmware/receptor/build -j2
```

Copiar `receptor/build/nodo1_receptor.uf2` a BOOTSEL. Encender primero la ESP32,
abrir su monitor y luego iniciar la Pico. La recepción permanece esperando con
READY armado aunque todavía no haya maestro. La pantalla muestra SIN DATOS SPI.
Si se cambia a modo 1: menuconfig ESP32 → modo 1, recompilar/programar; Pico →
`-DNODO1_SPI_MODO=1`, recompilar/cargar. Reiniciar ambas al cambiar el modo.

## Filtros y lectura de la pantalla

- FIR: 75 coeficientes sinc/Hamming, corte de 1800 Hz, diseñados para **10 kHz**.
  Historia persistente y retardo de 37 muestras (3,7 ms). Para superponer curvas y
  medir, se retrasa la entrada/referencia 37 muestras. Se excluye del primer cálculo
  el prefijo de calentamiento. No se reutilizan coeficientes del banco de 16 kHz.
- Espectral: FFT de 1024, salto de 512 (51,2 ms), Hann y overlap-add. Banda protegida
  <1600 Hz, ancho de 100 Hz y atenuación de 0,1; decisión basada solo en la mezcla.
  Se precarga medio bloque con ceros y se descarta esa primera salida virtual.
  La primera salida real requiere 4 paquetes de 256; después produce 512 cada 2.
  Entrada, referencia y salida comparadas pertenecen al mismo segmento temporal.
- Ambos reciben el mismo audio; **no** están en cascada. Al perder paquetes se
  reinician historias y calentamiento. Se rechazan duplicados y secuencias atrasadas;
  ID 0 permite reinicio del maestro; el desbordamiento uint32 es válido.

La pantalla alterna FIR/FFT cada 4 segundos; etiqueta MIC o SIM y bloque de la
vista (en FFT, ID inicial del segmento reconstruido; en FIR, bloque de salida,
con entrada/referencia retrasadas 37 muestras).
Zona superior: rojo=entrada contaminada, verde=salida **filtrada** (no necesariamente
limpia), misma escala vertical. Muestra 160 muestras consecutivas (16 ms), no una
forma de onda continua entre refrescos. La escala es automática y compartida;
comparar también RMS/E en el monitor. Refresco máximo 5 Hz. Tras 1 s sin vistas
válidas muestra SIN DATOS, evitando una imagen congelada que parezca recepción.
Un error histórico/discontinuidad enciende ERROR hasta reiniciar; el monitor
explica los contadores. CALENTANDO FFT no es un fallo.

### Métricas: micrófono vs referencia conocida

**MIC:** SNR y MSE muestran `N/D SIN REF`: no se conoce la señal útil original.
`E TOTAL = 100·sum(y²)/sum(x_alineada²)` describe energía total transmitida, no
energía útil conservada ni calidad. Puede superar 100% por transitorios o por el
filtro, y es indefinida con entrada cero. Una salida pequeña no prueba mejora.

**SIM:** activar Autoprueba en menuconfig y volver a programar. No requiere Pico;
genera 440 Hz útil (0,3 V de amplitud) + 3000 Hz de ruido (0,15 V) a 10 kHz.
La etiqueta SIM permanece visible: **no es una prueba de transporte SPI ni micrófono**.
También se puede compilar una variante separada, sin cambiar el modo MIC:

```bash
idf.py -B build_sim -D SDKCONFIG=build_sim/sdkconfig \
  -D 'SDKCONFIG_DEFAULTS=sdkconfig.defaults;sdkconfig.sim.defaults' build
idf.py -B build_sim -D SDKCONFIG=build_sim/sdkconfig -p /dev/ttyUSB0 flash monitor
```

Los filtros deciden usando la mezcla; la referencia conocida solo mide:

- SNR salida =10·log10(sum(ref_alineada²)/sum((y−ref_alineada)²)).
- MSE =mean((y−ref_alineada)²), en V².
- E UTIL =100·sum(util_filtrada²)/sum(ref_alineada²). La referencia pasa por el
  mismo FIR o ganancias FFT elegidas desde la mezcla; se conserva la alineación.

Las métricas corresponden al último bloque de cada filtro, no a todo un ensayo.
Sin energía de referencia la relación se marca no disponible; error cero puede
producir SNR infinita. El modo SIM usa la misma ruta DSP que MIC.
Para defender métricas de calidad del micrófono real haría falta capturar una
referencia limpia sincronizada y calibrada; el protocolo actual no la incluye.
La demostración anterior `../esp32` permite evaluar los 3 casos reales del notebook
con referencia, pero sigue siendo otro firmware y usa 16 kHz.

## Pruebas y defensa

1. Revisar visualmente GND y retirar GPIO9/10. Confirmar controlador LCD y CS.
2. Ejecutar SIM: ver FIR/FFT, curvas y métricas con referencia conocida. Anotar
   que es autoprueba; no atribuirla al micrófono.
3. Volver a MIC: modo igual en ambos lados; 2 MHz. Inicialmente conectar fuente
   desconectada de GP26 y GP26 a GND para prueba de cero. SNR/MSE=N/D es correcto.
4. Conectar micrófono acondicionado, 0–3,3 V y antialias <5 kHz; un tono conocido
   debe verse. Para probar rechazo, inyectar mezcla conocida con componentes
   fuera/dentro de banda; voz o palmadas no acreditan SNR/MSE.
5. Registrar monitor ESP32 (`OK`, rechazados, CRC, longitud, secuencia,
   discontinuidades, DSPmax) y consola Pico (`Perd/Err/Rein`, `sin_READY`,
   `sin_consumo`). Esperar CRC/errores en cero y DSPmax<25600 us durante el ensayo.
6. Desconectar enlace/reiniciar una placa: no usar datos inválidos, mostrar SIN
   DATOS y recuperar; el reinicio del DSP debe ser visible en discontinuidades.
7. Probar 1/2/5/10 MHz con analizador lógico: CPOL/CPHA, CS sobre toda la trama,
   8256 clocks, READY antes de CS y descenso al terminar. Registrar errores por
   duración y carga de LCD. Si modo 0 falla, usar modo 1 y documentar la razón.
8. Medir latencia extremo a extremo en placa. DSPmax solo mide ambos filtros;
   no incluye envío, cola, espera FFT ni actualización de pantalla.

Pruebas portables (GCC, sin IDF ni placas):

```bash
bash tests/probar_host.sh
```

Comprueban productor Pico contra decodificador ESP32, CRC/cabecera/longitud,
NaN, filtros a 10 kHz con referencia, métricas alineadas, huecos/duplicados/reinicio,
wrap de ID y silencio. No reemplazan compilación ESP-IDF ni validación eléctrica.

## Referencias técnicas

- [Espressif SPI slave: DMA, modos, timing, READY y alineación](https://docs.espressif.com/projects/esp-idf/en/v5.5.5/esp32/api-reference/peripherals/spi_slave.html).
- [ESP32-WROOM-32: GPIO reservados y strapping](https://documentation.espressif.com/esp32-wroom-32_datasheet_en.html).
- [Perfil de pantalla de referencia ST7735S 0.96 160×80](https://docs.waveshare.net/0.96inch_LCD_Module/).

## Verificación en este cambio

- Pico: compilación ARM con SPI habilitado, modos 0 y 1 a 2 MHz.
- ESP32: compilaciones completas ESP-IDF 5.5.5 para MIC y SIM, incluida pantalla.
- Banco anterior de 16 kHz: 16 pruebas numéricas aprobadas tras agregar Fs configurable.
- Contrato y DSP en vivo: prueba host y sanitizadores de memoria/comportamiento indefinido.
  En la mezcla sintética de prueba, último bloque: FIR SNR≈63,90 dB, MSE≈1,83e-8 V²,
  E útil≈99,96%; espectral SNR≈26,02 dB, MSE≈1,13e-4 V², E útil≈100%.
  Son resultados calculados en computadora; no son mediciones del micrófono,
  del transporte SPI, de latencia ESP32 ni evidencia de funcionamiento físico de la LCD.

El SDK y herramientas Linux usados para esta revisión se descargaron temporalmente
sin modificar la instalación del usuario. En esta sesión pueden activarse con:

```bash
export IDF_TOOLS_PATH=/tmp/audio-idf-tools
source /tmp/audio-esp-idf-5.5.5/export.sh
```

`/tmp` puede desaparecer al reiniciar. Para uso duradero instalar ESP-IDF en una
ubicación persistente y activar ese entorno antes de los comandos anteriores.
