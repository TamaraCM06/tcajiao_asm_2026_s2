# 1. Criterios de defensa y cobertura del sistema

## 1.1. Fuentes y forma de evaluar

| Fuente | Uso |
|---|---|
| [Enunciado del proyecto, version 7](../references/ASM_Proyecto_Grupal1_v7.pdf) | Requisitos del sistema, P1--P6, restricciones y entregables. Copia identica al PDF indicado por el usuario |
| Rubrica proporcionada por el usuario en esta conversacion | Nueve categorias funcionales; niveles 0 insuficiente, 1 basico, 2 bueno y 3 excelente |
| [Manual](MANUAL_USUARIO.md) | Procedimientos ejecutables y obtencion de resultados |
| [TODO](TODO.md) | Ensayos, documentos y cobertura aun pendientes |

Los pesos siguientes suman 100 % dentro de la rubrica funcional. El enunciado
asigna 65 % a la presentacion funcional y 35 % a documentacion, dividida en
articulo 30 % y herramientas 5 %. No confundir ambas escalas.

Compilar, aprobar pruebas host o disponer de un comando no acredita una categoria
en nivel excelente. Se necesitan comportamiento observado y explicacion tecnica.
Esta matriz no asigna una nota ni presupone aprobacion del profesor.

## 1.2. Matriz de la rubrica funcional

| Categoria | Peso | Que exige el nivel excelente | Soporte actual y comprobacion pendiente |
|---|---|---|---|
| Adquisicion y manejo de la senal | 10 % | Captura sin perdidas, saturacion ni alteraciones; explicar muestreo, escalamiento, cuantizacion y prevencion de saturacion | Pico ADC/DMA, DC, contadores y transporte con CRC. Manual 1.12: observar Sat y diferencias de Perd/Err/Rein en la Pico durante capturas; no usar recortes PCM como sustituto de saturacion ADC |
| Analisis espectral y diagnostico del ruido | 15 % | Identificar ruido y bandas; justificar mediante espectro, frecuencia, amplitud, energia y resolucion | FFT de Pico y espectros de las sesiones. Mostrar P1--P5 y diferenciar componentes utiles de interferencia. El pico dominante de la mezcla no identifica por si solo el ruido; la candidata Pico sobre 1600 Hz tampoco cubre toda la superposicion de P5 |
| Filtrado temporal FIR o IIR | 15 % | Reducir ruido y permanecer estable; justificar seleccion, orden, coeficientes, respuesta y polos/ceros | FIR de 75 coeficientes, orden 74 y retardo 37 muestras; modelo, respuesta calculada y contraste digital disponibles. Ejecutar, escuchar y explicar H(z), fase lineal, estabilidad y limites de medida |
| Filtrado espectral FFT/IFFT | 15 % | FFT, modificacion e IFFT correctas; explicar resolucion, simetria, umbrales, componentes eliminadas y reconstruccion | Hann, FFT 1024, salto 512, ganancias adaptativas y OLA normalizada. Pruebas host disponibles; falta demostrar sonido sin artefactos y justificar ajustes por caso |
| Seleccion y configuracion del metodo | 10 % | Elegir el metodo apropiado y fundamentarlo comparando ventajas, limitaciones y efectos | Ambas rutas y ajustes sin recompilar. Comparar FIR y espectral sobre la misma entrada, justificar minimo/ancho/factor/umbral y explicar el compromiso de P5. La rubrica no exige inventar un selector automatico de metodos |
| Calidad de la senal recuperada | 15 % | Mejora objetiva y perceptible con poca distorsion; explicar ruido eliminado frente a senal conservada | CSV con referencia para metricas y captura acustica para escucha. Ejecutar repeticiones, mantener ganancia comparable y registrar notas. Concordancia C/Python no equivale a calidad ni porcentaje de ruido eliminado |
| Metricas funcionales | 10 % | Todas las metricas correctas; explicar significado, procedimiento y relacion con lo observado | MSE, SNR, energia util, atenuacion regional, costos y latencia digital preparados. Ejecutar y explicar intervalos, referencia, region y unidades; no llamar latencia analogica al tramo recepcion ESP32--UART |
| Integracion de los tres nodos | 5 % | Completar automaticamente la cadena; explicar flujo, sincronizacion, responsabilidades y fallos | Pico separada; rutas temporal y espectral independientes en ESP32, permitidas por el PDF. capturar ejecuta adquisicion, filtros y guardado; la escucha requiere orden posterior. La integracion automatica completa y adecuacion cuasi real no se consideran acreditadas por esa secuencia |
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

## 1.4. Cobertura que no se debe dar por cumplida

| Punto | Estado y consecuencia |
|---|---|
| Prevencion de aliasing | El PDF 2 exige demostrarla bajo condiciones previstas. Audio por parlante--microfono, ausencia de picos y filtro despues del DAC no bastan. Declarar la limitacion no cumple ese requisito |
| Funcionamiento cuasi real | PDF 1 exige resultados en tiempo real o cuasi real. Medir procesamiento por bloques ayuda, pero los WAV y escucha diferida no acreditan por si solos la adecuacion del sistema completo |
| Cadena automatica | La rubrica reserva excelente a la cadena completa automatica. El flujo actual requiere ordenar reproduccion; no se interpreta que el profesor ya acepto esa intervencion |
| Referencia fisica | Capturas acusticas sin limpia sincronizada no generan MSE/SNR fisicos. El PDF condiciona esas metricas a disponer de referencia; reportar por separado los CSV procesados en placa |
| Retardo analogico | No medido; el enunciado exige latencia por bloque, pero no fija expresamente una medida con osciloscopio. Delimitar la latencia digital y no atribuirle el trayecto ADC/DAC |
| Resultados nuevos | Instrumentacion version 2 compilada y probada en PC; aun sin corridas fisicas de esa version. Los resultados anteriores mantienen sus fechas y alcance |
| Entrega | Articulo hasta cuatro paginas con referencias y herramientas hasta dos; defensa hasta 15 minutos. Revisar tambien ramas, integracion y tag segun PDF 7 |

Se conserva la decision del usuario de trabajar con audios, sin incorporar
osciloscopio ni generador y sin recuperar modos retirados. Esa decision delimita
el procedimiento actual, pero no elimina requisitos ni garantiza nivel excelente.
