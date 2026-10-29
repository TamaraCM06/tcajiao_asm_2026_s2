# 1. Emisor ESP32

## 1.1. Estado y alcance

| Campo | Valor |
|---|---|
| Responsable | Persona 3, Santiago |
| Proyecto | Reducción adaptativa de ruido, CE 1110 |
| Entrega inmediata | Taller asincrónico de semana 12 |
| Avance | Bloque 1: base ESP-IDF y generador configurable |
| Lenguaje y entorno | C estándar para el cálculo; ESP-IDF 5.5.5 para la aplicación |
| Destino de compilación | esp32, correspondiente al ESP32 clásico |
| Implementado | Configuración, validación, síntesis numérica y primer buffer |
| Estado de revisión | Lectura de código, documentación y diff |
| Pendiente de verificar | Compilación, ejecución y salida física |
| Siguiente bloque | Conversión de muestras y reproducción DAC/DMA |

La aplicación prepara 256 muestras y termina. El estado y el buffer permanecen
reservados para conectarlos al DAC en el siguiente bloque. Este avance todavía
no emite una señal física.

## 1.2. Módulos y responsabilidades

| Archivo | Responsabilidad |
|---|---|
| [emisor_config.h](components/emisor/include/emisor_config.h) | Tipos, parámetros y operaciones de configuración. |
| [emisor_config.c](components/emisor/emisor_config.c) | Valores iniciales y validaciones de tonos e interferencia. |
| [generador_senales.h](components/emisor/include/generador_senales.h) | Estado e interfaz pública del generador. |
| [generador_senales.c](components/emisor/generador_senales.c) | Preparación de amplitudes, fases y generación continua. |
| [app_main.c](main/app_main.c) | Selección del modo, inicialización y primer buffer. |
| [CMakeLists.txt](CMakeLists.txt) | Proyecto ESP-IDF y destino esp32. |
| [sdkconfig.defaults](sdkconfig.defaults) | Opciones iniciales de ESP-IDF compartidas por el equipo. |

El componente emisor usa C estándar y la biblioteca matemática. Sus archivos C
no dependen de FreeRTOS, UART ni DAC. La aplicación es responsable de conectarlo
con el hardware. Las funciones auxiliares permanecen en el módulo de su dominio;
una utilidad compartida se extraerá cuando exista una función repetida que lo justifique.

## 1.3. Modos y parámetros

| Parámetro | Valor inicial | Unidad o significado |
|---|---|---|
| Modo | EMISOR_MULTITONO_CON_INTERFERENCIA | Suma de señal útil e interferencia tonal. |
| frecuencia_muestreo_hz | 16000 | Muestras por segundo. |
| EMISOR_MUESTRAS_POR_BLOQUE | 256 | Cantidad de muestras del buffer de aplicación. |
| Tono individual | Frecuencia 440; amplitud 1; fase 0 | Hz; peso relativo; grados. |
| Multitono | Frecuencias 440, 880, 1320 | Hz. |
| Amplitudes del multitono | 1, 0.55, 0.3 | Pesos relativos antes de la ganancia común. |
| Fases del multitono | 0, 35, -50 | Grados. |
| frecuencia_interferencia_hz | 4000 | Hz. |
| fase_interferencia_grados | 0 | Grados. |
| snr_db | 10 | Relación señal a ruido (SNR), en decibelios. |
| limite_amplitud | 0.8 | Cota de magnitud de salida normalizada. |
| Salida | float centrado en cero | Todavía no son códigos del DAC. |

| Modo disponible | Señal generada |
|---|---|
| EMISOR_TONO | Un tono útil. |
| EMISOR_MULTITONO | Dos o tres tonos útiles; tres en la configuración inicial. |
| EMISOR_MULTITONO_CON_INTERFERENCIA | Multitono más interferencia de amplitud derivada de la SNR. |

Seleccionar MODO_EMISION_INICIAL en la aplicación. Obtener la configuración
predeterminada y editar sus campos antes de inicializar. Editar esa estructura
después no cambia el estado ya preparado; para aplicar otra configuración se
debe volver a inicializar. Los comandos de selección durante ejecución se incorporarán después.

## 1.4. Interfaz y contrato de errores

| Orden de uso | Operación | Entrada | Resultado |
|---|---|---|---|
| 1 | emisor_config_predeterminada | Modo y destino de configuración. | Llena los parámetros de emisión. |
| Opcional | emisor_validar_configuracion | Configuración. | Comprueba parámetros sin generar muestras. |
| 2 | emisor_inicializar | Estado y configuración. | Valida, copia parámetros y prepara amplitudes/fases. |
| 3 | emisor_generar | Estado, buffer y cantidad_muestras. | Escribe muestras y avanza las fases. |
| Opcional | emisor_reiniciar | Estado inicializado. | Restaura las fases, conservando amplitudes y ganancia. |

| Regla del contrato | Comportamiento |
|---|---|
| Operación correcta | Devuelve NULL. |
| Error | Devuelve un mensaje estático; el llamador debe mostrarlo o gestionarlo y no liberarlo. |
| Inicialización fallida | El generador queda deshabilitado. |
| Vida de la configuración | No necesita seguir viva después de una inicialización correcta. |
| Buffer de salida | El llamador reserva espacio para la cantidad solicitada. |
| Cero muestras | Válido; permite buffer NULL y no cambia el estado. |
| Memoria por bloque | No hay reservas dinámicas ni normalización individual del bloque. |
| Concurrencia | Cada instancia tiene estado propio; no modificar una instancia desde tareas simultáneas. |

## 1.5. Validaciones

| Parámetro o condición | Criterio |
|---|---|
| Modo | Uno de los tres modos definidos. |
| Muestreo | Entero positivo representado por frecuencia_muestreo_hz. |
| Frecuencias | Finitas y dentro de 0 < frecuencia < muestreo/2. |
| Cantidad de tonos | Uno para tono individual; dos o tres para multitono. |
| Amplitudes útiles | Finitas, no negativas y al menos una positiva. |
| Fases y SNR | Finitas. |
| Límite de amplitud | Mayor que cero y no mayor que uno. |
| Mezcla con interferencia | Tonos útiles distintos entre sí y de la interferencia. |
| SNR extrema | Error al inicializar si produce una amplitud de ruido o ganancia no representable. |

Los tonos inactivos no se evalúan. La frecuencia y fase de interferencia y la SNR
deben ser válidas incluso en los modos sin ruido, aunque solo se utilizan para
sintetizar interferencia en el modo de mezcla.

## 1.6. Fundamento de la generación

### 1.6.1. Potencia y ganancia común

| Cálculo | Expresión | Propósito |
|---|---|---|
| Potencia útil estable | (A1^2 + A2^2 + A3^2) / 2 | Sumar la potencia media de tonos distintos. |
| Amplitud de interferencia | sqrt(A1^2 + A2^2 + A3^2) * 10^(-SNR_dB/20) | Ajustar la relación señal a ruido solicitada. |
| Ganancia común | limite_amplitud / (A1 + A2 + A3 + A_interferencia) | Acotar la mezcla sin alterar la relación útil/ruido. |
| Muestra emitible | ganancia_comun * (senal_util + interferencia) | Producir una amplitud numérica normalizada. |

Los modos sin ruido omiten su amplitud del denominador. La cota utiliza que la
magnitud de un seno no supera uno; el pico real puede quedar por debajo de 0.8.
El límite está sujeto al redondeo de punto flotante. La misma ganancia para útil
y ruido conserva su relación de potencia.

La SNR configurada describe potencia estable. Un fragmento corto que no contiene
ciclos completos puede tener otra SNR medida.

### 1.6.2. Continuidad y precisión

| Decisión | Efecto |
|---|---|
| Fases e incrementos en double | Mantener el estado angular con mayor precisión. |
| Fases acotadas a un ciclo | Evitar un contador de tiempo que crezca indefinidamente. |
| Seno evaluado con sinf y salida float | Producir las muestras que consumirá el siguiente bloque. |
| Estado conservado entre llamadas | Continuar la onda sin reiniciarla al comenzar cada buffer. |
| Reinicio explícito | Volver a las fases configuradas cuando se solicite. |

El periodo común de las frecuencias iniciales es 25 ms, equivalente a 400 muestras.
El buffer de 256 representa 16 ms: se deben generar muestras nuevas conservando
las fases, no repetir ese primer buffer. La duración del buffer no es una medida
de latencia del sistema.

## 1.7. Relación con Python

| Referencia | Información reutilizada |
|---|---|
| [configuraciones.json](../../tarea1_grupo1/metadatos/configuraciones.json) | Frecuencias, amplitudes relativas y fases útiles. |
| [generacion.py](../../tarea1_grupo1/src/senales/generacion.py) | Definición de senoides y relación señal a ruido. |

| Aspecto | Emisor continuo | Registros históricos Python |
|---|---|---|
| Fase de interferencia | Explícita; 0 grados por defecto. | Determinada por una semilla. |
| Ganancia | Cota basada en suma de amplitudes. | Máximo observado en seis segundos. |
| SNR | Potencia estable de tonos. | RMS del registro finito. |
| Extremos | Sin envolvente de inicio/final todavía. | Suavizado en los extremos del registro. |
| Tipo de ruido del bloque 1 | Interferencia tonal. | También existen otros tipos de ruido. |

El emisor no reproduce exactamente los CSV anteriores. En la verificación final,
comparar con una señal Python construida con los mismos parámetros y sobre
intervalos equivalentes. El arranque suave del audio físico, si se añade, debe
aplicar la misma ganancia a señal útil y ruido.

## 1.8. Entorno y verificación final

| Paso | Directorio o condición | Comando o dato |
|---|---|---|
| Activar entorno | Terminal ESP-IDF 5.5.5; idf.py disponible. | Instalación local: C:/Espressif/frameworks/esp-idf-v5.5.5. |
| Entrar al proyecto | Desde la raíz del repositorio. | Set-Location proyecto_1_grupal/firmware/esp32 |
| Compilar al cerrar la implementación | Desde la carpeta del proyecto. | idf.py build |
| Cargar y observar después de integrar DAC | Sustituir COM_REEMPLAZAR por el puerto real. | idf.py -p COM_REEMPLAZAR flash monitor |

| Archivo o carpeta | Gestión |
|---|---|
| [sdkconfig.defaults](sdkconfig.defaults) | Valores compartidos. |
| sdkconfig y sdkconfig.old | Generados localmente; ignorados por Git. |
| build/ | Artefactos locales; ignorados por Git. |
| CMake del proyecto | No contiene rutas absolutas al SDK instalado. |

Por acuerdo del equipo, los bloques permiten commits incrementales y no incluyen
etapas de pruebas intermedias. La verificación final abarcará tonos, mezcla,
continuidad, amplitud, SNR, reinicio, parámetros inválidos y frecuencia física de salida.

## 1.9. Auditoría de organización del bloque

| Zona | Ajuste de legibilidad | Finalidad |
|---|---|---|
| Configuración | Validación separada en comprobaciones generales, tonos e interferencia. | Localizar cada criterio sin concentrar todas las comprobaciones en una función. |
| Generación | Preparación de amplitudes separada de la inicialización de fases. | Distinguir nivel/SNR de continuidad angular. |
| Código e interfaz | Nombres descriptivos, unidades en las fases y comentario por función. | Reducir ambigüedad al leer el estado y los parámetros. |
| Documentación | Apartados numerados, tablas de parámetros/contratos y enlaces a archivos. | Facilitar lectura humana y extracción automática del contexto. |

La reorganización conserva las fórmulas y valores iniciales. La compilación,
las pruebas funcionales y la validación física siguen pendientes. El siguiente
bloque implementará la conversión y reproducción DAC mediante DMA.
