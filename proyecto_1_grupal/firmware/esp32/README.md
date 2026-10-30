# 1. Emisor y comparaci?n digital en ESP32

## 1.1. Prop?sito y alcance

La ESP32 reproduce las se?ales del notebook por GPIO25 y despu?s ejecuta en su
propio procesador un FIR y un filtro espectral independientes. La computadora
prepara los datos, programa la placa y muestra la consola; no calcula los filtros
durante la demostraci?n.

| Etapa | Entrada | Salida |
|---|---|---|
| Preparaci?n Python | CSV y coeficientes de Tarea 1 | C?digos DAC y pares mezcla/referencia en flash |
| Emisi?n | Mezcla cuantizada a 8 bits | GPIO25, 16000 muestras/s, una reproducci?n |
| Evaluaci?n FIR | Mezcla y referencia float32 | M?tricas y tiempos de la ESP32 |
| Evaluaci?n espectral | La misma mezcla y referencia float32 | M?tricas y tiempos de la ESP32 |
| Final | Tres casos completos | Mensaje DEMOSTRACION COMPLETADA |

Cada caso se emite y luego se eval?a; las etapas son secuenciales. No hay captura
ADC, transferencia de muestras por USB, gr?ficas ni filtros alimentados por Pico.
Las m?tricas digitales no demuestran la calidad de la tensi?n emitida por el DAC.
La referencia limpia sirve ?nicamente para evaluar: no decide qu? ruido eliminar.

## 1.2. Par?metros y datos

| Par?metro | Valor |
|---|---|
| Plataforma | ESP32 cl?sico, C, ESP-IDF 5.5.5 |
| Casos | caso_1, caso_2 y caso_3; autom?ticos en ese orden |
| Muestreo y longitud | 16000 Hz; 96000 muestras por caso; 6 segundos de emisi?n |
| Se?al ?til | 440, 880 y 1320 Hz; amplitudes 1, 0.55 y 0.3; fases 0?, 35? y ?50? |
| Caso 1 | Interferencia tonal 4000 Hz, SNR configurada 10 dB |
| Caso 2 | Ruido 2500?3800 Hz, SNR configurada 5 dB |
| Caso 3 | Ruido superpuesto 600?1500 Hz, SNR configurada 0 dB |
| FIR | 75 coeficientes exportados del notebook, historia persistente, bloques de 256 |
| Alineaci?n FIR | Retardo de 37 muestras, sin buscar un retardo que mejore la m?trica |
| Espectral | FFT 1024, salto 512, Hann sim?trica de an?lisis y s?ntesis |
| Detecci?n | M?nimo 1600 Hz, ancho total 100 Hz, factor 0.1, umbral relativo 0.05 |
| Datos digitales | Pares mezcla/referencia float32 little-endian, sin nueva normalizaci?n |
| Conversi?n DAC | Redondear 127.5 ? (clip(muestra, ?1, 1) + 1); no se usa para evaluar filtros |
| Flash de datos | 2304000 bytes float32 + 288000 c?digos DAC + coeficientes y programa |
| Partici?n | Una aplicaci?n sin OTA; requiere flash f?sica de al menos 4 MB |
| RAM | Buffers por bloque; no se cargan las se?ales completas ni se asigna memoria por bloque |

Los archivos binarios .f32 evitan a?adir cientos de miles de l?neas de constantes.
Son datos generados, incluidos en Git y reproducibles con el exportador. Cada JSON
registra formato, longitud, SHA-256 y CRC del registro DAC correspondiente.
Los coeficientes y los CSV originales, sus semillas y el notebook se conservan.
Cambiar se?ales requiere exportar, compilar y programar otra vez.

## 1.3. Organizaci?n del c?digo

| Ubicaci?n | Responsabilidad |
|---|---|
| [app_main.c](main/app_main.c) | Entrada y reporte de fallo |
| [demostracion.c](main/demostracion.c) | Secuencia de casos, reloj y coordinaci?n |
| [informe_consola.c](main/informe_consola.c) | Res?menes legibles por caso y m?todo |
| [reproduccion_senal.c](main/reproduccion_senal.c) | Env?o finito de flash al DAC |
| components/salida_dac | Controlador, DMA y confirmaci?n de fin |
| components/senales_embebidas | Cat?logo, lectura float32, datos y coeficientes |
| components/filtros_digitales | FIR con estado, FFT radix 2 y filtrado espectral |
| components/evaluacion_digital | Alineaci?n, banco secuencial y m?tricas acumuladas |
| [exportar_senales.py](../../herramientas/exportar_senales.py) | Exportaci?n com?n de c?digos y datos digitales |
| [tests](tests/test_filtros_c.py) | Comparaci?n del n?cleo C con Python mediante GCC |

Los filtros usan C est?ndar y no conocen FreeRTOS, consola ni DAC. El banco recibe
funciones para leer el reloj, ceder procesador y observar salidas durante pruebas.
Su espacio de trabajo est?tico se comparte entre m?todos: no es reentrante ni se
puede llamar simult?neamente desde dos tareas. La FFT radix 2 portable evita a?adir
una dependencia externa; se puede sustituir por una implementaci?n optimizada en
el proyecto final, verificando antes equivalencia num?rica.

## 1.4. Qu? hacen los filtros

El FIR combina la muestra actual con las 74 anteriores. Conserva esa historia
entre bloques y reduce las frecuencias altas con los coeficientes ya dise?ados.

El espectral aplica Hann ? FFT ? ganancias ? IFFT ? Hann ? solapamiento y
normalizaci?n. El umbral se calcula desde la energ?a de la mezcla en cada ventana;
se descarta silencio o energ?a regional inferior a 0.001 del pico global.
La ganancia se aplica a ambas mitades conjugadas del espectro: no se modifica
intencionalmente la fase de los coeficientes. Los pesos acumulados de Hann al
cuadrado compensan la reconstrucci?n. Se a?aden ceros virtuales al principio y
al final, evitando reservar un registro extendido completo.

Para evaluar da?o ?til, la referencia pasa por el mismo FIR o por las mismas
ganancias espectrales de la mezcla. Nunca se vuelve a estimar ruido desde ella.

## 1.5. Lectura de resultados

| Campo de consola | Significado |
|---|---|
| SNR entrada / salida / mejora | Relaci?n entre energ?a de referencia y error; mayor suele ser mejor |
| MSE | Error cuadr?tico medio entre salida alineada y referencia; menor es mejor |
| Energ?a ?til | Energ?a de la referencia despu?s del filtro respecto a su energ?a original |
| Atenuaci?n ruido total | Reducci?n de la energ?a del ruido residual, no solo de su pico dominante |
| SNR distorsi?n | Da?o que el filtro introduce en la referencia limpia |
| Evaluadas | 95963 muestras comunes para los registros actuales: longitud menos 37 |
| Producidas | FIR: 95963 alineadas; espectral: las 96000 muestras originales |
| C?lculo / media / m?ximo | Lectura de datos, filtrado de mezcla y referencia, y acumulaci?n de m?tricas |
| Tiempo transcurrido | Incluye preparaci?n y cesiones a FreeRTOS; no incluye emisi?n DAC |
| Espacio est?tico | Buffers compartidos reservados por el banco; excluye pila, SDK y DMA |
| M?ximo compatible | Comparaci?n orientativa con 16 ms FIR o 32 ms espectral |

Ambos m?todos usan el mismo intervalo y cada salida se compara con la referencia
correctamente alineada. La salida completa no se guarda: se consume por bloques
y se acumulan energ?as en doble precisi?n. Una energ?a ?til cercana al 100 % no
implica ausencia de distorsi?n; tambi?n se revisan MSE y SNR de distorsi?n.
Los casos 1 y 2 deben mejorar; el caso 3 evidencia el l?mite de conservar la banda
?til cuando el ruido cae dentro de ella. No se obliga a que todos los casos mejoren.

Los tiempos se miden con el reloj de la ESP32 e incluyen la evaluaci?n adicional
de la referencia. Las cesiones al sistema quedan fuera del tiempo por bloque.
El indicador de presupuesto no demuestra operaci?n simult?nea en tiempo real,
ni equivale a latencia de extremo a extremo. Resultados en el PC son validaci?n
num?rica, no tiempos de la placa. Con silencio pueden aparecer NaN o infinito,
porque algunas relaciones de energ?a no est?n definidas.

## 1.6. Preparar, compilar y ejecutar

Ejecutar desde la ra?z del repositorio en PowerShell. Sustituir COM5 por el puerto
real de la placa. No se programa hardware autom?ticamente desde las pruebas.

| Paso | Comando |
|---|---|
| Exportar los tres casos | & proyecto_1_grupal/.venv/Scripts/python.exe -m proyecto_1_grupal.herramientas.exportar_senales |
| Compilar ESP32 | powershell -NoProfile -ExecutionPolicy Bypass -File proyecto_1_grupal/firmware/esp32/ejecutar_idf.ps1 -Accion build |
| Programar | powershell -NoProfile -ExecutionPolicy Bypass -File proyecto_1_grupal/firmware/esp32/ejecutar_idf.ps1 -Accion flash -Puerto COM5 |
| Ver resultados | powershell -NoProfile -ExecutionPolicy Bypass -File proyecto_1_grupal/firmware/esp32/ejecutar_idf.ps1 -Accion monitor -Puerto COM5 |
| Repetir | Pulsar EN/RESET con el monitor abierto |
| Salir del monitor | Ctrl+] |
| Pruebas num?ricas y regresi?n | & proyecto_1_grupal/.venv/Scripts/python.exe -m pytest proyecto_1_grupal/firmware/esp32/tests proyecto_1_grupal/tarea1_grupo1/tests -q |

El script usa el SDK y Python instalados en C:/Espressif; permite reemplazar sus
rutas mediante par?metros. Debido a incompatibilidades de las herramientas con
la ruta acentuada del repositorio, build copia exclusivamente las fuentes del
firmware a una carpeta temporal ASCII. No mueve ni borra el repositorio.
Guarda la ubicaci?n exitosa en build/ruta_compilacion.txt, ignorado por Git.
Flash y monitor usan esa compilaci?n. Despu?s de editar fuentes, ejecutar build
otra vez antes de flash. Si se borra la carpeta temporal, volver a compilar.
ExecutionPolicy Bypass afecta solo ese proceso; no cambia la pol?tica persistente.

Para ver los c?lculos basta USB y consola. La emisi?n DAC puede ejecutarse sin
conectar nada a GPIO25. Para recepci?n el?ctrica se usar?n GPIO25 y GND com?n,
con niveles y acondicionamiento acordados con Persona 1. Cero num?rico en el DAC
corresponde aproximadamente a media alimentaci?n: no es una se?al bipolar.
No se necesita el divisor GPIO25 ? GPIO34 de la alternativa descartada.

## 1.7. Verificaci?n y pendientes

| Verificaci?n | Estado |
|---|---|
| Pruebas Python originales y n?cleo C | 110 aprobadas: 94 existentes + 16 nuevas |
| Comparaci?n C/Python | Error absoluto de muestras ? 3e-6; m?tricas relevantes ? 0.03 dB |
| Distorsi?n casi nula | Si Python supera 100 dB, exigir C > 100 dB; float32 impone otro piso num?rico |
| Reconstrucci?n | Ganancia unitaria, silencio y longitudes 256, 768 y 96000 verificadas |
| Compilaci?n ESP-IDF | Compilaci?n completa ESP-IDF 5.5.5; no equivale a una prueba f?sica |
| Hardware | Pendientes programaci?n, comprobaci?n de flash f?sica, emisi?n y tiempos reales |
| Cierre esperado | Tres emisiones completas, seis evaluaciones y DEMOSTRACION COMPLETADA |

Se retiraron captura ADC, protocolo CAP1, cliente de adquisici?n, gr?ficas y
PySerial de esta propuesta. Se conservaron la salida DAC, sus controles de error,
los datos del notebook y el exportador. El sistema continuo con Pico, adquisici?n,
interfaz y salidas filtradas corresponde al siguiente avance del proyecto.

## 1.8. Fuentes

| Fuente | Aplicaci?n |
|---|---|
| [Modelo del proyecto](../../tarea1_grupo1/src/filtros/filtrado_espectral.py) | Selecci?n espectral y par?metros |
| [M?tricas Python](../../tarea1_grupo1/src/mediciones/metricas.py) | Convenciones de energ?a y SNR |
| [DAC ESP-IDF 5.5](https://docs.espressif.com/projects/esp-idf/en/v5.5/esp32/api-reference/peripherals/dac.html) | DMA y conversi?n de 8 bits |
| [Reloj ESP-IDF 5.5](https://docs.espressif.com/projects/esp-idf/en/v5.5/esp32/api-reference/system/esp_timer.html) | Medici?n en microsegundos |
| [Particiones ESP-IDF 5.5](https://docs.espressif.com/projects/esp-idf/en/v5.5/esp32/api-guides/partition-tables.html) | Aplicaci?n y datos en flash |
