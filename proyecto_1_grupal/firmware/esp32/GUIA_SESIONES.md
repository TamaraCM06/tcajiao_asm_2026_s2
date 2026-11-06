# 1. Captura en PC y reproducción diferida

## 1.1. Alcance y estado

| Campo | Valor |
|---|---|
| Responsable | Persona 3, aplicación ESP32; adquisición Pico de Persona 1 |
| Aplicación | Sesiones PC; al arrancar espera comandos, no reproduce automáticamente |
| Flujo físico | Pico → SPI → FIR y espectral en ESP32 → USB → archivos en PC |
| Flujo de escucha | Archivo seleccionado → USB → ESP32 DAC → filtro analógico → GF1002 → parlante |
| Evaluación controlada | CSV del notebook → mezcla/referencia PCM16 → filtros y métricas en ESP32 |
| Bloques | Entrada 256; FFT 1024; salto 512; 16000 Hz |
| Duración inicial | 6 segundos, 96000 muestras; configurable entre 256 y 960000 muestras |
| Memoria | Estado y colas acotados; ningún registro completo se almacena en RAM de la placa |
| Ejecución | Optimización de rendimiento, CPU 240 MHz; sesiones/DSP en núcleo distinto de las ISR SPI/UART |
| Verificación física parcial | Captura Pico de 6 s y evaluación de P2_tonal comprobadas; respuesta analógica válida en tres tonos útiles, 4 kHz inválido por inestabilidad; escucha y estabilidad prolongada pendientes |

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
22 nF, segundo operacional como seguidor, desacoplo de alimentación de 100 nF.
Su corte teórico es 2283 Hz (Q ≈ 0.74; 22 nF por disponibilidad en lugar de 20 nF)
y el divisor reduce amplitud a la mitad. Documentar
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
La aplicación PC utiliza 1 000 000 baudios; el arranque ROM puede emitir a 115200.
La herramienta ignora solamente ese ruido inicial durante HELLO. No utilizar
idf.py monitor simultáneamente. Al iniciar mide 393216 bytes con CRC e índices:
exige al menos 98000 bytes/s de contenido, frente a los 96000 bytes/s de las tres señales.
Las tres rutas viajan agrupadas en un paquete por salto y la transmisión UART
usa una cola para avanzar mientras se calcula el siguiente bloque. La ocupación
máxima estimada del enlace se acerca al 97.4 %: comprobar la captura completa,
porque el ensayo inicial de velocidad por sí solo no garantiza continuidad.
El puente de la placa conectada falló a 2 Mbaud y respondió a 1 Mbaud en la
comprobación directa con esptool; no aumentar la velocidad sin validarla.
Ese control del enlace no sustituye una captura física completa. Un ensayo de
60 segundos es un diagnóstico interno recomendado, no una duración exigida por el PDF.

La compilación usa una copia temporal ASCII para evitar problemas de rutas con
tildes. El comando flash utiliza la última compilación correcta registrada; hay
que repetir build después de modificar código. La aplicación inicia únicamente
sesiones PC, también si se compila directamente con idf.py; no hay selección de modos.

## 1.4. Uso de la terminal

| Comando | Resultado |
|---|---|
| ayuda | Lista de operaciones |
| estado | Configuración y sesión seleccionada; durante una operación indica OCUPADO |
| configurar segundos=6 | Duración redondeada hacia arriba a bloques de 256; muestra duración efectiva |
| configurar minimo_hz=1600 ancho_hz=100 factor=0.1 umbral=0.05 ganancia=1 | Parámetros iniciales; ganancia solo cambia la escucha |
| capturar | Guarda la entrada Pico y los dos resultados sin reproducirlos |
| evaluar P1 | Procesa el CSV del notebook; admite P1, P2, P3, P4, P5 y la variante histórica P2_tonal |
| evaluar "C:/ruta/prueba.csv" | CSV de cuatro columnas del notebook, o tiempo_s,contaminada sin referencia |
| reproducir entrada | Reproduce la entrada guardada por el DAC |
| reproducir fir | Reproduce el resultado FIR guardado |
| reproducir espectral | Reproduce el resultado espectral guardado |
| abrir "C:/ruta/sesion" | Selecciona una sesión completa anterior después de verificar integridad |
| metricas | Tablas FIR/espectral, tiempos y recursos de la sesion seleccionada; usa resultados ESP32 y validacion guardada sin recalcular ni cambiar archivos |
| Presentacion | Omite filas sin valores y tablas vacias; conserva ceros, negativos, incumplimientos y observaciones de mediciones invalidas. Los JSON/CSV mantienen la informacion original |
| detener | Cancela una operación; una captura parcial permanece incompleta |
| validar | Compara la sesión seleccionada con el modelo Python sobre la misma entrada PCM16 |
| demo analogico | Guía la comparación de GPIO25 y pin 7 del LM358 usando la Pico por USB |
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
| Version de medidas | version_mediciones=2 agrega tiempos por ruta, cola, publicacion y latencia digital con arranque/cierre separados |
| Costos individuales | ruta_cantidad/medio_us/max_us en cada metodo; FIR por 256 y espectral por salto de 512; incluyen calculo de referencia |
| Latencia digital | latencia_bloque_medio_us/max_us: trama completa recibida en ESP32 hasta aceptacion UART de sus indices de salida; excluye ADC, viaje serial, escritura PC y DAC |
| Evaluacion adicional | evaluacion_cantidad/medio_us/max_us incluye metricas y medida regional; publicacion incluye cuantizacion y entrega UART |
| Region | atenuacion_interferencia_db por metodo, region_minima_hz/maxima_hz y region_muestras; FFT 1024 con Hann, sin solapamiento, bloques completos del intervalo valido |
| Memoria | Tamaño del estado DSP y heap libre/mínimo; no implica disponer de toda la RAM del chip |

atenuacion_ruido_total_db se conserva como energia total del residuo. La nueva
atenuacion_interferencia_db usa una region explicita del mismo residuo real de
placa: entrada menos limpia y salida menos util filtrada. Las ganancias utiles
espectrales se obtienen de la mezcla. Si no existe referencia, region o energia
resoluble, estado_atenuacion_regional explica el null; no se sustituye por cero.
El final parcial de la medida regional se excluye y region_muestras lo identifica.
Sin osciloscopio ni generador, los ensayos fisicos elegidos son parlante hacia
microfono; antialiasing de entrada y retardo analogico no quedan comprobados.

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
| Canales de salida | 0: entrada/FIR/espectral PCM16 intercalados por muestra; el lector también acepta los canales individuales 1/2/3 |
| Evaluación | Un paquete de 256 muestras, mezcla/referencia intercaladas si existe referencia; esperar ACK antes del siguiente |
| Comando EVALUATE | EVALUATE longitud referencia escala minimo ancho factor umbral; admite dos limites regionales opcionales al final, minimo_hz maximo_hz. La forma anterior sigue valida, sin region |
| Region en terminal | configurar interferencia_min_hz=2500 interferencia_max_hz=3800; configurar interferencia_min_hz=auto restablece regiones por caso. No modifica los parametros del filtro |
| Notas | nota texto agrega notas.txt fechado a la sesion seleccionada; no modifica metadatos, WAV ni metricas |
| Audio | Paquetes de hasta 1536 muestras, ventana de dos paquetes pendientes; ACK libera capacidad |
| enlace_pc | UART, cola RX y codec portable |
| procesamiento_registro | FIR/FFT, historia corta, alineación, métricas y vaciado finito |
| sesiones_pc | Coordinación, adquisición desacoplada, reproducción e informe |
| tools/pc | Codec Python, cliente, almacenamiento y terminal separados |

Documentación de controladores: [UART ESP-IDF 5.5](https://docs.espressif.com/projects/esp-idf/en/v5.5/esp32/api-reference/peripherals/uart.html),
[DAC ESP-IDF 5.5](https://docs.espressif.com/projects/esp-idf/en/v5.5/esp32/api-reference/peripherals/dac.html),
[PySerial](https://pyserial.readthedocs.io/en/latest/pyserial_api.html).

## 1.9. Diagnóstico y comprobación del 5 de noviembre de 2026

| Elemento | Evidencia observada |
|---|---|
| Placas | ESP32-D0WD-V3, revisión 3.1, COM12; Pico USB CDC, COM13 |
| Fallo inicial | Sin saludo a 2 Mbaud; esptool tampoco recibió respuesta al cambiar a esa velocidad |
| Velocidad utilizada | 1 Mbaud; ensayo ASM2 con contenido verificado de aproximadamente 98970 bytes/s |
| Ajustes | Rutas agrupadas, TX acotado, margen FIFO RX de 64 bytes y timeout de 10 símbolos; CPU 240 MHz, optimización de rendimiento y DSP en núcleo separado |
| Captura física | 96000 muestras por archivo; 0 pérdidas y 0 recortes; cadencia estimada 16000.26 muestras/s |
| Cálculo durante captura | Máximo conjunto de 16323 us, inferior al salto de 32000 us; no es latencia analógica |
| Sesión física | proyecto_1_grupal/resultados/sesiones/20261105T164053Z_77315ebc |
| Evaluación controlada en placa | Caso 1 del CSV original, con referencia PCM16; 96000 muestras guardadas, 95963 evaluadas |
| Resultado espectral del caso 1 | SNR entrada 10.0017 dB; salida 29.9764 dB; mejora 19.9747 dB |
| Sesión de evaluación | proyecto_1_grupal/resultados/sesiones/20261105T164327Z_614a343d |
| Límite de esta evidencia | Una captura y un caso; no acredita 60 s de estabilidad, P1–P6 completos ni calidad analógica del DAC/parlante |

Las sesiones previas que fallaron se conservaron como incompletas para diagnóstico.
Las carpetas de resultados están ignoradas por Git; conservar una copia de las
evidencias seleccionadas para el informe. La reproducción no se ejecutó durante
este diagnóstico: comprobarla manualmente con el volumen inicialmente bajo.

## 1.10. Demo de comparación analógica y concordancia porcentual

| Campo | Decisión |
|---|---|
| Inicio | Salir de la terminal anterior y volver a abrir sesiones.py para cargar el código Python actualizado |
| Comando PowerShell desde raíz | & proyecto_1_grupal/.venv/Scripts/python.exe proyecto_1_grupal/firmware/esp32/tools/sesiones.py --puerto COM12 --puerto-pico COM13 |
| Comando dentro de asm | demo analogico |
| Firmware | Usa PLAY existente de ESP32 y ADC1 existente de Pico; no requiere recompilar por esta demo |
| Estímulo | Entrada histórica P2_tonal del notebook, antes caso 1; verificada contra su CSV, reutiliza una sesión compatible o la evalúa en ESP32 |
| Frecuencias | Se leen de configuraciones.json: 440, 880, 1320 y 4000 Hz actualmente |
| Ganancia de reproducción | Fija en 1 para ambos puntos, independiente de la ganancia de escucha configurada |
| Pico instrumento | GP26/ADC0, pin físico 31; desconectar el micrófono antes de usar la sonda |
| Medición antes | GP26 de Pico a GPIO25 de ESP32, antes del divisor; GND común |
| Medición después | Mover solamente la sonda de GP26 al pin 7 del LM358; esperar a la instrucción de la terminal |
| Rango | Verificar voltajes de entrada entre 0 y 3.3 V; nunca conectar 5 V ni salidas Lout/Rout al ADC |
| Amplificador | Volumen al mínimo durante la prueba; conservar el circuito de reconstrucción conectado y alimentado |
| Muestreo | 12 bloques solicitados por punto, 256 muestras por bloque, 16 kHz; hay huecos entre bloques |
| Estabilización | Esperar 0.5 s desde el primer bloque aceptado por DAC antes de medir |
| Cierre | Restablecer micrófono en GP26 antes de volver a usar capturar |

La demo espera que el usuario cambie la sonda y confirme con Enter antes de cada
reproducción. Abre el puerto de la Pico después de esa confirmación y lo cierra
al terminar cada punto, de modo que desconectar USB durante el cambio no deje
una conexión antigua abierta. Comprueba una respuesta ADC1 antes de iniciar el
DAC. No ejecutarla con otra consola leyendo el puerto de la Pico. Es
una comparación de amplitud por frecuencia: no compara la fase entre las dos
capturas ni demuestra las imágenes de reconstrucción alrededor de 16 kHz.

### 1.10.1. Uso del multímetro

| Prueba | Procedimiento e interpretación |
|---|---|
| Alimentación | Modo voltaje DC, punta negra a GND y roja al pin 8 del LM358: aproximadamente 5 V; pin 4 a GND |
| Centro de señal | Durante la reproducción estable de entrada de P2_tonal, medir GPIO25 respecto de GND: aproximadamente 1.65 V DC |
| Salida del filtro | Durante la misma señal, medir pin 7 respecto de GND: aproximadamente 0.825 V DC por el divisor 1/2 |
| Polaridad y tomas | Usar COM y V del multímetro, sin seleccionar corriente ni continuidad con el circuito alimentado |
| Límite de la medida | Esas lecturas comprueban alimentación y centrado, no frecuencia de corte ni reducción de imágenes |
| Voltaje AC | Solo interpretar amplitudes si el manual del multímetro especifica precisión y ancho de banda suficientes para las frecuencias medidas |

Los valores DC son aproximados, dependen de la alimentación real y se miden
durante la reproducción, no suponiendo un voltaje concreto con el DAC apagado.

### 1.10.2. Qué se guarda

| Ubicación/archivo | Contenido |
|---|---|
| resultados/sesiones/analogicas/identificador_unico | Carpeta nueva para cada intento; no sobrescribe medidas anteriores |
| medicion_antes.csv | Códigos ADC crudos, voltios, ID de bloque, índice y tiempo local dentro del bloque, escala y contadores |
| medicion_despues.csv | Lo mismo para la salida del filtro |
| comparacion_analogica.csv | Amplitud antes/después por tono, ganancia medida, ganancia teórica, error y concordancia porcentual |
| medicion.json | Componentes del modelo, fuente reproducida, resúmenes, dispersión, criterios, estado y causa si falla |
| diagnostico_error.txt | Si falla, traza del error y su origen; medicion.json conserva la etapa de la prueba |
| respuesta_analogica.png | Curva del modelo y puntos medidos, lista para el informe |
| metadatos/filtro_analogico.json | Componentes y criterios editables; revisar que coincidan con el circuito real antes de medir |

No se crea un WAV continuo con los bloques ADC separados. Se estiman juntas las
amplitudes de los cuatro tonos y el nivel DC mediante ajuste de senos/cosenos en
cada bloque; después se calcula su media y dispersión. Las fases iniciales pueden
ser distintas y no se alinean artificialmente los bloques.

### 1.10.3. Significado de accuracy o concordancia

| Prueba | Porcentaje y referencia |
|---|---|
| Circuito analógico | Concordancia = max(0, 100 − error relativo de ganancia en %), por frecuencia; divisor × Sallen-Key × abs(sinc(f/16000)) para la fundamental |
| Criterio analógico inicial | Error relativo <=15 % por tono; equivale a concordancia >=85 %, con medida válida. Es un criterio del equipo, no un valor impuesto por el profesor |
| Validez analógica | Rechazar saturación, cambios en contadores de adquisición, amplitudes bajo el límite de detección o variabilidad mayor al 10 % |
| Implementación digital | Concordancia = 100×max(0,1−RMSE/RMS del modelo Python), sobre las salidas PCM16 con la misma escala y retardo causal |
| Criterio digital | ≥90 % en FIR y espectral, ratificado por el usuario el 5/11; validar escribe umbral y cumplimiento por método, con no disponible si el porcentaje no está definido |
| Silencio digital | Modelo y salida exactamente cero: 100 %. Modelo cero y salida distinta: porcentaje no disponible; se conserva el error RMS |
| Fuente digital | La misma entrada PCM16 guardada se pasa por los modelos originales de FIR y espectral; también funciona en capturas sin referencia limpia |
| Archivos digitales | validacion_python.json, validacion_python.csv y columnas adicionales en metricas.csv; resultado_esp32 permanece identificado como medida de placa |

Un 100 % significa coincidencia con el modelo elegido; no significa eliminar
el 100 % del ruido, conservar toda la señal útil ni conocer la incertidumbre
absoluta del instrumento. MSE/SNR siguen requiriendo referencia limpia. La
validación Python es independiente y se realiza después de la captura, sin
sustituir el procesamiento de los microcontroladores. Se ejecuta automáticamente
en capturar/evaluar y puede repetirse con validar sobre una sesión anterior.

Fundamento del circuito: [Análisis de la arquitectura Sallen-Key, Texas Instruments](https://www.ti.com/lit/an/sloa024b/sloa024b.pdf).

### 1.10.4. Retención DAC, imágenes y evidencia archivada

| Aspecto | Modelo y límite |
|---|---|
| Retención de orden cero | Cada código permanece un periodo; la fundamental se atenúa por abs(sinc(f/16000)), donde sinc(x)=sin(pi×x)/(pi×x) |
| Comparación | La sonda directa muestrea los escalones; después del filtro observa la fundamental reconstruida. Se modela esta diferencia, sin ajustar componentes a las medidas |
| Atenuación DAC a 440/880/1320/4000 Hz | Aproximadamente 0.99876 / 0.99503 / 0.98884 / 0.90032 |
| Imagen de 4 kHz | La imagen en 12 kHz se pliega sobre 4 kHz al adquirir a 16 kHz; contribución nominal aproximada de 4 % respecto a la fundamental filtrada, dependiente de fase |
| Límite | El modelo de fundamental no incluye imágenes aliasadas ni demuestra sincronización exacta de relojes ADC/DAC; la corrección no elimina toda incertidumbre |
| Criterios previos | Error ≤15 % y variabilidad ≤10 %, conservados desde antes de medir; la corrección sinc se identifica como reanálisis posterior |
| Medición 20261105T185714Z_80cf289c | Tres tonos útiles cumplen con errores 2.52 / 0.59 / 9.95 %; 4 kHz tiene variabilidad de 19.3 % y no permite validar ese punto |
| Archivo | [Resultados seleccionados](../../docs/final/evidencias/README.md); registros completos y reanálisis siguen locales |
| Alcance del PDF | Documentar reconstrucción DAC, §5.6. Esta demo es complementaria y no demuestra antialias antes del ADC |

Fundamento de retención: [DAC Output Response, Texas Instruments](https://www.ti.com/content/dam/videos/external-videos/en-us/2/3816841626001/5577272810001.mp4/subassets/TIPL4705-DAC-Output-Response.pdf).

## 1.11. Casos de defensa y repetición

| Identificador | Señal y ruido | Semilla |
|---|---|---|
| P1 | Tono 440 Hz e interferencia 4000 Hz, 10 dB | 4100 |
| P2 | Multitono histórico y banda 2500–3800 Hz, 5 dB | 2000 |
| P2_tonal | Multitono e interferencia 4000 Hz, 10 dB; antiguo caso 1 | 1000 |
| P3 | Audio sintético: barrido 220–1320 Hz y ruido blanco, 5 dB | 4300 |
| P4 | Transitorio 440 Hz e impulsos, 5 dB | 4400 |
| P5 | Multitono y banda superpuesta 600–1500 Hz, 0 dB | 3000 |

Todas duran 6 s a 16 kHz y usan el generador del notebook. Desde proyecto_1_grupal,
python -m herramientas.preparar_casos prepara los CSV; cargar un caso también
prepara automáticamente la copia faltante sin reescribir el JSON fuente.
Abrir sesiones.py con --salidas resultados/pruebas_finales y ejecutar evaluar Pn
tres veces de forma independiente. Luego, python -m herramientas.resumen_pruebas
resultados/pruebas_finales --salida resultados/entrega genera estadísticas.
No hace falta copiar WAV ni JSON a docs para resumir. Los resultados digitales
CSV no sustituyen la adquisición física. El [manual de pruebas](../../docs/final/MANUAL_USUARIO.md)
describe P1–P6, origen de las métricas, antialias y selección mínima para la entrega.
P2_tonal es una variante adicional y no se contabiliza como P1. Los nombres
históricos se admiten por compatibilidad. El banco flash conserva tres registros;
los cinco casos de defensa se transfieren por PC, sin ampliar la flash necesaria.

## 1.12. Compilación de la única aplicación

| Desde la raíz del repositorio | Alcance |
|---|---|
| powershell.exe -NoProfile -ExecutionPolicy Bypass -File proyecto_1_grupal/firmware/esp32/ejecutar_idf.ps1 -Accion build | Compilar sesiones PC desde una copia temporal ASCII |
| Mismo script con -Accion flash -Puerto COMx | Programar la última compilación correcta |
| Mismo script con -Accion size | Consultar tamaño |
| proyecto_1_grupal/firmware/esp32/tools/sesiones.py --puerto COMx | Abrir la terminal ASM2 con el Python del entorno |

No hay selector de modos ni banco de señales flash. El procesador finito está en
[procesamiento_registro](components/procesamiento_registro/), conserva los estados
de los dos filtros y entrega sus resultados al servicio de sesiones.
