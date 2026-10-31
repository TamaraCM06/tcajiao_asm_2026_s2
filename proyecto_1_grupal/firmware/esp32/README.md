# 1. Emisor y evaluación digital en ESP32

## 1.1. Propósito

Este firmware es el programa de la ESP32 para el taller de semana 12. Reproduce
las tres señales del notebook de Tarea 1 mediante el convertidor digital a
analógico (DAC) de GPIO25. Después evalúa un filtro temporal de respuesta finita
al impulso (FIR) y uno espectral en la propia ESP32, y muestra sus resultados
en la consola.

La computadora prepara los datos, compila, programa la placa y muestra la
consola. Durante la demostración, los filtros se calculan en la ESP32.

## 1.2. Funcionamiento

Al arrancar, la ESP32 recorre caso_1, caso_2 y caso_3. Para cada caso realiza
estos pasos en orden:

| Paso | Qué hace | Resultado esperado |
|---|---|---|
| 1. Emitir | Lee los códigos de 8 bits guardados en flash y los envía al DAC | Una reproducción de 6 segundos por GPIO25 |
| 2. Evaluar FIR | Filtra la mezcla digital y evalúa el resultado con la referencia limpia | Métricas y tiempos del filtro temporal |
| 3. Evaluar espectral | Procesa la misma mezcla con el filtro espectral | Métricas y tiempos del filtro espectral |
| 4. Continuar | Termina el caso y pasa al siguiente | Al finalizar los tres: RESUMEN FINAL con seis resultados y DEMOSTRACION COMPLETADA |

Las etapas se ejecutan una después de otra. El DAC emite la mezcla original;
las salidas filtradas se evalúan digitalmente y no se envían al DAC.
La referencia limpia se usa para medir el resultado, sin decidir qué ruido quitar.

Las métricas digitales describen los filtros aplicados a los datos guardados en
flash. Los mensajes de consola registran la ejecución del programa y son distintos
de una medición eléctrica de la salida DAC.

### 1.2.1. Qué hacen los filtros

| Filtro | Explicación |
|---|---|
| FIR, de respuesta finita al impulso | Combina la muestra actual con las 74 anteriores. Conserva esa historia entre bloques y usa los coeficientes del notebook para reducir frecuencias altas. |
| Espectral | Divide la señal en ventanas, analiza sus frecuencias y reduce las componentes seleccionadas por su energía. Después reconstruye la señal. |

El filtro espectral usa la transformada rápida de Fourier (FFT) para pasar de
muestras a frecuencias, y su inversa (IFFT) para regresar. La ventana Hann suaviza
los bordes de cada bloque. Los bloques se superponen y se dividen por la suma de
los pesos Hann al cuadrado para compensar la reconstrucción.

En cada ventana, el umbral es el mayor entre 0.05 veces el pico de energía de la
región analizada y 0.001 veces el pico global. Si hay silencio o la región tiene
muy poca energía, se mantienen las ganancias en uno. Las frecuencias por debajo
de 1600 Hz quedan protegidas. La atenuación conserva la simetría del espectro y
no modifica directamente la fase. Se usan ceros virtuales en los extremos para
reconstruir toda la señal sin guardar un registro extendido.

Para medir cuánto afecta el filtro a la señal útil, la referencia pasa por el
mismo FIR o por las ganancias que el filtro espectral calculó desde la mezcla.

## 1.3. Señales y parámetros

Las señales proceden del [notebook de Tarea 1](../../tarea1_grupo1/notebook.ipynb)
y de sus [configuraciones](../../tarea1_grupo1/metadatos/configuraciones.json).
SNR significa relación señal a ruido y se expresa en decibelios (dB).

| Parámetro común | Valor |
|---|---|
| Plataforma | ESP32 clásico; lenguaje C; entorno de desarrollo ESP-IDF 5.5.5 |
| Muestreo | 16000 Hz, es decir, 16000 muestras por segundo |
| Duración | 6 segundos; 96000 muestras por caso |
| Señal útil | Tonos de 440, 880 y 1320 Hz |
| Amplitudes de los tonos | 1, 0.55 y 0.3 antes del escalado común del notebook |
| Fases de los tonos | 0°, 35° y -50°, respectivamente |
| Escala | Se conserva el escalado de los CSV; no se normaliza de nuevo por bloque |

| Caso | Ruido añadido | SNR configurada | Semilla |
|---|---|---|---|
| caso_1 | Tono de 4000 Hz | 10 dB | 1000 |
| caso_2 | Ruido de banda entre 2500 y 3800 Hz | 5 dB | 2000 |
| caso_3 | Ruido entre 600 y 1500 Hz, superpuesto a la señal útil | 0 dB | 3000 |

| Parámetro de procesamiento | Valor |
|---|---|
| FIR | 75 coeficientes; bloques de 256 muestras; retardo de 37 muestras |
| Intervalo fijo de evaluación del taller | 95963 muestras por caso y filtro: índices de referencia 0 a 95962 |
| Ventana espectral | 1024 muestras; avance de 512 muestras; Hann simétrica en análisis y reconstrucción |
| Selección espectral | Frecuencia mínima 1600 Hz; ancho total 100 Hz; factor de amplitud 0.1; umbral relativo 0.05 |
| Datos para filtros | Pares intercalados de mezcla y referencia, en punto flotante de 32 bits (float32), con el byte menos significativo primero (little-endian) |
| Datos para DAC | Códigos enteros de 0 a 255, con resolución de 8 bits |
| Conversión a DAC | floor(127.5 × (clip(muestra, -1, 1) + 1) + 0.5): limitar a [-1, 1], convertir a [0, 255] y redondear |
| Flash necesaria | Al menos 4 MB físicos; 2304000 bytes float32 y 288000 códigos DAC, además de coeficientes y programa |
| Organización de flash | Una partición de aplicación |
| Memoria de trabajo (RAM) | Bloques pequeños y estado fijo; no se cargan las señales completas ni se reserva memoria en cada bloque |

Los archivos CSV son tablas de muestras en texto; los JSON guardan sus metadatos.
Los archivos binarios .f32 y los códigos DAC están incluidos en Git. El exportador
permite reproducirlos desde los CSV existentes sin generar de nuevo los ruidos.
Los archivos JSON registran el origen y la longitud; para los datos de evaluación
incluyen la huella SHA-256 y el código de comprobación CRC-32 del registro DAC.
Cambiar las señales exige exportar, compilar y programar otra vez.
La demostración exige registros de 96000 muestras y rechaza otras longitudes
antes de emitir el caso correspondiente. Así mantiene 95963 muestras evaluadas
al compensar el retardo FIR. El banco de filtros conserva su soporte de otras
longitudes para las pruebas numéricas.

## 1.4. Preparación y ejecución

### 1.4.1. Requisitos y conexión

| Recurso | Uso o condición |
|---|---|
| Python del proyecto | Preparar el entorno según el [README general](../../README.md#14-entorno-python) |
| ESP-IDF | El script usa por defecto la versión 5.5.5 instalada en C:/Espressif |
| ESP32 y cable USB | ESP32 clásico con al menos 4 MB de flash; conexión USB para programar y ver la consola |
| GPIO25 y GND | GPIO25 entrega la señal DAC; GND proporciona la referencia eléctrica común |

Para observar las métricas basta la conexión USB y la consola. La reproducción
puede ejecutarse sin conectar nada a GPIO25. El cero de la señal numérica se
convierte aproximadamente en media alimentación: la salida DAC no es bipolar.

### 1.4.2. Comandos

Ejecutar desde la raíz del repositorio en PowerShell. Sustituir COM5 por el puerto
real de la placa. Los datos ya están incluidos; exportarlos solo es necesario
para regenerarlos o cambiar las señales.

| Paso | Comando o acción |
|---|---|
| Exportar los tres casos | & proyecto_1_grupal/.venv/Scripts/python.exe -m proyecto_1_grupal.herramientas.exportar_senales |
| Compilar | powershell -NoProfile -ExecutionPolicy Bypass -File proyecto_1_grupal/firmware/esp32/ejecutar_idf.ps1 -Accion build |
| Programar la placa | powershell -NoProfile -ExecutionPolicy Bypass -File proyecto_1_grupal/firmware/esp32/ejecutar_idf.ps1 -Accion flash -Puerto COM5 |
| Abrir la consola | powershell -NoProfile -ExecutionPolicy Bypass -File proyecto_1_grupal/firmware/esp32/ejecutar_idf.ps1 -Accion monitor -Puerto COM5 |
| Repetir desde el inicio | Pulsar EN/RESET con el monitor abierto |
| Cerrar el monitor | Ctrl+] |

El [script ejecutar_idf.ps1](ejecutar_idf.ps1) compila una copia temporal de las
fuentes en una ruta sin tildes ni espacios, por incompatibilidades de las
herramientas con la ruta del repositorio. El directorio temporal TEMP también
debe cumplir esa condición. El script conserva el repositorio en su ubicación.

La ruta de la última compilación correcta se guarda en build/ruta_compilacion.txt,
ignorado por Git. Las acciones flash y monitor usan esa copia. Si se cambian las
fuentes o se borra la copia temporal, hay que compilar de nuevo antes de programar.
Los parámetros RutaSdk, RutaHerramientas y PythonSdk permiten indicar otras rutas
de instalación. ExecutionPolicy Bypass solo afecta al proceso del comando.

## 1.5. Lectura de resultados

La consola muestra el detalle de cada caso y filtro durante la ejecución.
Al terminar los tres casos, RESUMEN FINAL reúne las seis evaluaciones en dos
tablas: calidad digital y tiempos. Ambas usan el mismo orden: FIR y ESPECTRAL
de caso_1, después caso_2 y caso_3.

MSE significa error cuadrático medio. El detalle usa microsegundos (us); las
tablas finales usan milisegundos por bloque (ms) y segundos acumulados (s).
Los nombres siguientes corresponden a los mensajes y columnas de consola.

| Campo de consola | Cómo interpretarlo |
|---|---|
| SNR entrada / salida / mejora | Compara la energía de referencia con la del error; la mejora es la diferencia entre salida y entrada |
| MSE | Error medio al cuadrado entre salida alineada y referencia; menor indica menos error |
| Energia util | Porcentaje de energía de la referencia que permanece después del filtro |
| Atenuacion ruido total | Reducción de la energía del ruido residual, expresada en dB |
| SNR distorsion | Compara la referencia con su versión filtrada; mayor indica menos distorsión |
| evaluadas | 95963 muestras para ambos métodos: 96000 menos el retardo FIR de 37 |
| producidas | FIR: 95963 muestras alineadas; espectral: 96000 muestras reconstruidas |
| Calculo+referencia+metricas / media / max | Tiempo acumulado, promedio y máximo por bloque; incluye lectura, filtros y métricas |
| tiempo transcurrido | Incluye preparación y pausas para ceder el procesador al sistema FreeRTOS; excluye emisión DAC |
| Espacio estatico compartido | Memoria fija del banco; excluye pila, entorno ESP-IDF y acceso directo a memoria (DMA) del DAC |
| presupuesto / max compatible | Compara el bloque más lento con 16000 us para FIR o 32000 us para espectral |

| Tabla final | Columnas |
|---|---|
| CALIDAD DIGITAL | Caso, método, SNR de entrada y salida, mejora, MSE, energía útil, atenuación del ruido y SNR de distorsión |
| TIEMPOS | Caso, método, evaluadas, tiempo medio y máximo por bloque, presupuesto, cumplimiento, cálculo acumulado y tiempo total |

La columna Evaluadas muestra siempre 95963 en las seis filas. El firmware valida
esa cantidad antes de publicar cada evaluación. Para construir el resumen solo
guarda seis estructuras pequeñas de resultados; no almacena las señales filtradas
completas. La RAM informada corresponde al banco compartido y excluye esas
estructuras de presentación, además de pila, SDK y DMA.

Los filtros se comparan sobre el mismo intervalo. Se compensa el retardo conocido
del FIR de 37 muestras, sin buscar un desplazamiento que mejore las métricas.
Las salidas se consumen por bloques y las energías se acumulan en doble precisión.

Una energía útil cercana al 100 % no garantiza poca distorsión: también se revisan
MSE y SNR de distorsión. Los casos 1 y 2 permiten estudiar ruido separado en
frecuencia; el caso 3 muestra la dificultad de separar ruido y señal útil cuando
comparten frecuencias. No se presupone que todos los casos mejoren.

Los tiempos por bloque incluyen la evaluación de la referencia y excluyen las
pausas voluntarias para FreeRTOS. El indicador max compatible compara tiempos
por bloque y es distinto de la latencia de extremo a extremo.
Los tiempos obtenidos en computadora tampoco representan los de la ESP32.
Con silencio, algunas relaciones de energía pueden resultar indefinidas (NaN)
o infinitas.

Si la reproducción falla, la consola identifica la etapa: inicializacion,
escritura, espera_fin o cierre. El diagnóstico de inicialización, escritura o
espera incluye los códigos previstos, aceptados y reproducidos, las paradas
inesperadas y las muestras notificadas por bloque DMA.

| Contador DAC | Significado |
|---|---|
| aceptadas | Códigos copiados al controlador; por sí solos no confirman reproducción |
| reproducidas | Códigos cuya conversión confirma el evento de fin total on_stop del controlador |
| notificadas_dma | Suma de los avisos parciales on_convert_done; se conserva como diagnóstico independiente |
| paradas | Eventos de fin antes de completar la carga, o con contadores inconsistentes |

El cierre correcto exige cargar el registro completo y recibir on_stop sin
paradas prematuras. En ESP32, la suma de avisos parciales puede omitir el último
buffer; esa suma no se usa como condición de cierre. El evento de fin confirma
la ejecución del controlador y no mide la forma de onda analógica.

## 1.6. Organización del código

| Ubicación | Responsabilidad |
|---|---|
| [app_main.c](main/app_main.c) | Iniciar la aplicación y reportar fallos |
| [demostracion.c](main/demostracion.c) | Coordinar los tres casos y los servicios de reloj y pausas |
| [informe_consola.c](main/informe_consola.c) | Mostrar el detalle por caso y las tablas comparativas finales |
| [reproduccion_senal.c](main/reproduccion_senal.c) | Reproducir un registro completo desde flash |
| [salida_dac](components/salida_dac/) | Controlar el DAC, transferir datos por DMA y confirmar el fin |
| [senales_embebidas](components/senales_embebidas/) | Leer señales, datos float32 y coeficientes desde flash |
| [filtros_digitales](components/filtros_digitales/) | Implementar FIR, FFT e IFFT radix 2 y filtro espectral en C estándar |
| [evaluacion_digital](components/evaluacion_digital/) | Alinear salidas, ejecutar filtros y acumular métricas |
| [exportar_senales.py](../../herramientas/exportar_senales.py) | Preparar códigos DAC, datos digitales y coeficientes desde los CSV |
| [test_filtros_c.py](tests/test_filtros_c.py) | Comparar el mismo núcleo C con Python mediante el compilador GCC |
| [test_salida_dac.py](tests/test_salida_dac.py) | Comprobar el cierre del controlador C con eventos del SDK controlados en computadora |

Los filtros están separados del DAC, la consola y FreeRTOS. El banco recibe
funciones para consultar el reloj, ceder el procesador y observar salidas durante
las pruebas. Comparte su memoria fija entre métodos, por lo que debe ejecutarse
un filtro a la vez y no puede llamarse desde dos tareas simultáneamente.

## 1.7. Verificación numérica

La verificación registrada compara el modelo Python con el mismo núcleo C que
usa el firmware. Las pruebas del núcleo C se ejecutan en computadora mediante GCC.
Las pruebas de cierre DAC usan dobles de las API de ESP-IDF para reproducir el
último aviso parcial omitido, una parada prematura, una escritura parcial,
contadores inconsistentes y el cierre voluntario. También comprueban que cargar
todo el registro no acredita su reproducción sin recibir el evento de fin total.

| Comprobación | Antecedente documentado |
|---|---|
| Pruebas numéricas | 110 aprobadas: 94 del modelo Python y 16 del núcleo C ejecutado en computadora |
| Cierre DAC con eventos controlados | 7 aprobadas con el controlador C real y dobles de las funciones del SDK; no acreditan salida física |
| Comparación C/Python | Error absoluto de muestras ≤ 3e-6; diferencias de métricas en dB ≤ 0.03 dB; MSE con tolerancia absoluta 1e-7 |
| Distorsión casi nula | Si Python supera 100 dB, se exige C > 100 dB; la precisión float32 limita la comparación |
| Reconstrucción espectral | Ganancia unitaria, silencio y longitudes de 256, 768 y 96000 muestras |
| Compilación | Compilación completa con ESP-IDF 5.5.5, registrada previamente |

Para ejecutar las pruebas se requiere el entorno Python y GCC disponible en PATH.
El comando comprueba los cálculos digitales y no programa la placa.

| Directorio de ejecución | Comando |
|---|---|
| Raíz del repositorio | & proyecto_1_grupal/.venv/Scripts/python.exe -m pytest proyecto_1_grupal/firmware/esp32/tests proyecto_1_grupal/tarea1_grupo1/tests -q |

Estos resultados corresponden a la verificación numérica y la compilación;
no representan mediciones analógicas de la salida DAC.

## 1.8. Referencias

| Fuente | Contenido relacionado |
|---|---|
| [Modelo espectral Python](../../tarea1_grupo1/src/filtros/filtrado_espectral.py) | Selección espectral y parámetros |
| [Métricas Python](../../tarea1_grupo1/src/mediciones/metricas.py) | Convenciones de energía, SNR y MSE |
| [DAC de ESP-IDF 5.5](https://docs.espressif.com/projects/esp-idf/en/v5.5/esp32/api-reference/peripherals/dac.html) | Transferencia por DMA y conversión de 8 bits |
| [Reloj de ESP-IDF 5.5](https://docs.espressif.com/projects/esp-idf/en/v5.5/esp32/api-reference/system/esp_timer.html) | Medición de tiempo en microsegundos |
| [Particiones de ESP-IDF 5.5](https://docs.espressif.com/projects/esp-idf/en/v5.5/esp32/api-guides/partition-tables.html) | Organización de aplicación y datos en flash |
