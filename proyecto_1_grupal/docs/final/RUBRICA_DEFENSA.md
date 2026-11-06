# 1. Criterios de defensa y cobertura del sistema

## 1.1. Fuentes y forma de evaluar

| Fuente | Uso |
|---|---|
| [Enunciado del proyecto, version 7](../references/ASM_Proyecto_Grupal1_v7.pdf) | Requisitos del sistema, P1--P6, restricciones y entregables |
| Rúbrica del curso | Nueve categorias funcionales; niveles 0 insuficiente, 1 basico, 2 bueno y 3 excelente |
| [Manual](MANUAL_USUARIO.md) | Procedimientos ejecutables y obtencion de resultados |

Los pesos siguientes suman 100 % dentro de la rubrica funcional. El enunciado
asigna 65 % a la presentacion funcional y 35 % a documentacion, dividida en
articulo 30 % y herramientas 5 %. No confundir ambas escalas.

Compilar, aprobar pruebas host o disponer de un comando no acredita una categoria
en nivel excelente. Se necesitan comportamiento observado y explicacion tecnica.
Esta matriz no asigna una nota ni presupone aprobacion del profesor.

## 1.2. Matriz de la rubrica funcional

| Categoria | Peso | Que exige el nivel excelente | Soporte actual |
|---|---|---|---|
| Adquisicion y manejo de la senal | 10 % | Captura sin perdidas, saturacion ni alteraciones; explicar muestreo, escalamiento, cuantizacion y prevencion de saturacion | Pico ADC/DMA, DC, contadores y transporte con CRC. Consola de la Pico (manual 1.4): observar Sat y diferencias de Perd/Err/Rein en la Pico durante capturas; no usar recortes PCM como sustituto de saturacion ADC |
| Analisis espectral y diagnostico del ruido | 15 % | Identificar ruido y bandas; justificar mediante espectro, frecuencia, amplitud, energia y resolucion | FFT de Pico y espectros de las sesiones. Mostrar P1--P5 y diferenciar componentes utiles de interferencia. El pico dominante de la mezcla no identifica por si solo el ruido; la candidata Pico sobre 1600 Hz tampoco cubre toda la superposicion de P5 |
| Filtrado temporal FIR o IIR | 15 % | Reducir ruido y permanecer estable; justificar seleccion, orden, coeficientes, respuesta y polos/ceros | FIR de 75 coeficientes, orden 74 y retardo 37 muestras; modelo, respuesta calculada y contraste digital disponibles. Ejecutar, escuchar y explicar H(z), fase lineal, estabilidad y limites de medida |
| Filtrado espectral FFT/IFFT | 15 % | FFT, modificacion e IFFT correctas; explicar resolucion, simetria, umbrales, componentes eliminadas y reconstruccion | Hann, FFT 1024, salto 512, ganancias adaptativas y OLA normalizada. Resultados P1–P5 en placa (Tabla II del artículo); demostrar el sonido en la defensa y justificar ajustes por caso |
| Seleccion y configuracion del metodo | 10 % | Elegir el metodo apropiado y fundamentarlo comparando ventajas, limitaciones y efectos | Ambas rutas y ajustes sin recompilar. Comparar FIR y espectral sobre la misma entrada, justificar minimo/ancho/factor/umbral y explicar el compromiso de P5. La rubrica no exige inventar un selector automatico de metodos |
| Calidad de la senal recuperada | 15 % | Mejora objetiva y perceptible con poca distorsion; explicar ruido eliminado frente a senal conservada | CSV con referencia para metricas y captura acustica para escucha. 14 evaluaciones en placa (Tabla II); escuchar a igual ganancia en la defensa. Concordancia C/Python no equivale a calidad ni porcentaje de ruido eliminado |
| Metricas funcionales | 10 % | Todas las metricas correctas; explicar significado, procedimiento y relacion con lo observado | MSE, SNR, energia util, atenuacion regional, costos y latencia digital medidos en placa. Explicar intervalos, referencia, region y unidades; no llamar latencia analogica al tramo recepcion ESP32--UART |
| Integracion de los tres nodos | 5 % | Completar automaticamente la cadena; explicar flujo, sincronizacion, responsabilidades y fallos | Pico separada; rutas temporal y espectral independientes en ESP32, permitidas por el PDF. capturar ejecuta adquisicion, filtros y guardado; la escucha requiere orden posterior. Cálculo medio 9 ms por bloque de 16 ms y captura de 6 s sin pérdidas |
| Prueba desconocida durante defensa | 5 % | Diagnosticar y procesar sin asistencia; responder y adaptar parametros justificadamente | Carga de CSV o captura, ajustes sin recompilar y ambas salidas. Ensayar fuente nueva, cambios de ruido y ausencia de referencia; P6 real depende del profesor. Comunicar antes los limites de bloque y muestreo |

## 1.3. Que mostrar y explicar en las pruebas

| Momento | Demostracion y fundamento |
|---|---|
| Antes de filtrar | Fuente y niveles; ADC 12 bits, PCM16 de transporte y DAC 8 bits; explicar por que el formato no aumenta la resolucion fisica |
| Diagnostico | Identificar frecuencias/bandas en la entrada y distinguirlas de la senal util conocida. Explicar amplitud y energia; sin referencia no se separa ruido y util de forma unica en P5 |
| Resolucion | Pico: 16000/256 = 62.5 Hz; filtro espectral: 16000/1024 = 15.625 Hz. La figura de un WAV completo de 6 s usa 1/6 Hz entre bins y no cambia la resolucion del filtro embebido; Hann afecta la separacion efectiva |
| Comparacion | Misma entrada, escala y ganancia de escucha; observar ruido residual, distorsion y transitorios; mostrar ambas rutas |
| P5 | Explicar por que eliminar energia en la zona compartida tambien puede eliminar senal util. No prometer la misma mejora que P1/P2 |
| Metricas | Mostrar valores, referencia, alineacion fija, region evaluada, cantidad de muestras y tiempos reales de la misma version |
| Repeticiones | P1--P5: al menos tres ejecuciones independientes por condicion, parametros, media, variabilidad y escucha; no copiar registros para producir repeticiones |
| P6 | Diagnosticar antes de cambiar parametros; justificar cada ajuste y comunicar que se puede medir sin referencia |
| Preguntas de codigo | Todos explican sus modulos y cualquier linea seleccionada por el profesor; evitar utilidades sin una funcion defendible |

## 1.4. Límites declarados y cómo se responden

| Punto | Estado al 6/11 | Respuesta en la defensa |
|---|---|---|
| Prevención de aliasing | Justificada: los estímulos se generan a 16 kHz y no tienen contenido sobre 8 kHz. No hay filtro antialias de entrada | Mostrar el argumento de Nyquist y declarar el filtro antialias como recomendación |
| Funcionamiento cuasi real | Cada bloque se filtra al llegar; captura de 6 s sin pérdidas a 16 000.26 muestras/s; cálculo medio 9 ms por bloque de 16 ms | La escucha es posterior a la captura, lo que además evita realimentación |
| Cadena automática | `capturar` ejecuta adquisición, filtros y guardado; la reproducción requiere `reproducir` | Explicar que el audio vuelve al DAC de la ESP32 porque la placa no guarda la captura |
| Referencia física | Capturas acústicas sin limpia sincronizada no generan MSE/SNR; las métricas salen de los CSV evaluados en la ESP32 | Separar "calidad del filtro" (CSV) de "cadena física" (micrófono, sonido) |
| Retardo analógico | No medido. Se reportan latencia algorítmica y latencia digital | No atribuir la latencia digital al trayecto ADC/DAC |
| Resultados | P1–P5 evaluadas en placa el 6/11: 14 corridas completas, P4 con dos | Tabla II del artículo y [evidencias](evidencias/README.md) |
