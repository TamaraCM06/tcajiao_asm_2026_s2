# 1. Emisor ESP32 con señales del notebook

## 1.1. Propósito y estado

| Campo | Valor |
|---|---|
| Responsable | Persona 3, Santiago |
| Rama | sb-emisor-esp32 |
| Entorno | C, ESP-IDF 5.5.5, destino esp32 |
| Fuente de señales | CSV exportados por el notebook de Tarea 1; Python es el único generador matemático |
| Funcionamiento | Elegir un caso en app_main, compilar y reproducirlo una vez al arrancar |
| Almacenamiento | Tres registros constantes incluidos en la memoria flash del firmware |
| Implementado | Exportación de los tres casos, catálogo, selección y reproducción finita DAC/DMA |
| Realizado en este avance | Exportación de datos y revisión estática de código, documentación e interfaces |
| Pendiente por acuerdo | Compilación, carga en placa, memoria real y pruebas funcionales/físicas |
| Alcance | Emisor del banco del taller; filtros y enlace Pico → ESP32 del proyecto final quedan fuera |

Flujo de preparación: CSV del notebook → exportador Python → arreglos C → firmware en flash.

Flujo de reproducción: flash ESP32 → buffer pequeño en RAM → DAC/DMA GPIO25 → ADC acondicionado de Pico.

El computador se utiliza para preparar y programar el firmware. Una vez programado,
el emisor puede reproducir el caso al arrancar sin una aplicación de envío conectada.
Esta función de banco se distingue de la arquitectura final: Pico adquiere y
ESP32 filtra.

## 1.2. Archivos y responsabilidades

| Archivo | Responsabilidad |
|---|---|
| [archivos.py](../../tarea1_grupo1/src/datos/archivos.py) | Lectura compartida del CSV; conserva la interfaz de cargar_caso |
| [preparacion.py](../../herramientas/exportacion_senales/preparacion.py) | Validación de las muestras y conversión a códigos DAC |
| [escritura_c.py](../../herramientas/exportacion_senales/escritura_c.py) | Escritura de arreglos C constantes y metadatos JSON |
| [exportar_senales.py](../../herramientas/exportar_senales.py) | Consola para exportar los tres casos o actualizar uno |
| [senales_embebidas.h](components/senales_embebidas/include/senales_embebidas.h) | Identificadores y descriptor de lectura de las señales |
| [senales_embebidas.c](components/senales_embebidas/senales_embebidas.c) | Catálogo que devuelve el registro seleccionado |
| [caso_1.c](components/senales_embebidas/datos/caso_1.c), [caso_2.c](components/senales_embebidas/datos/caso_2.c) y [caso_3.c](components/senales_embebidas/datos/caso_3.c) | Muestras exportadas automáticamente; contienen datos, sin algoritmos |
| [caso_1.json](components/senales_embebidas/datos/caso_1.json), [caso_2.json](components/senales_embebidas/datos/caso_2.json) y [caso_3.json](components/senales_embebidas/datos/caso_3.json) | Origen, longitud, duración, conversión, recortes y CRC de cada registro |
| [salida_dac.c](components/salida_dac/salida_dac.c) | Controlador, DMA, contadores, espera de fin y cierre |
| [reproduccion_senal.c](main/reproduccion_senal.c) | Copia por bloques desde flash y coordinación de una reproducción |
| [app_main.c](main/app_main.c) | Único lugar de selección del caso e inicio de la reproducción |
| [CMakeLists.txt](CMakeLists.txt) y [sdkconfig.defaults](sdkconfig.defaults) | Construcción para esp32 y alineación automática para DMA |

Los archivos C de datos son extensos porque contienen muestras, no lógica.
Se mantienen separados por caso y se regeneran con Python. Incluirlos en el commit
permite compilar sin ejecutar el exportador ni abrir el notebook.

## 1.3. Casos y conversión

| Contrato | Valor |
|---|---|
| Fuente | [Notebook](../../tarea1_grupo1/notebook.ipynb), [configuraciones](../../tarea1_grupo1/metadatos/configuraciones.json) y resultados/muestras de Tarea 1 |
| CSV | Encabezado tiempo_s,limpia,ruido,contaminada |
| Señal reproducida | Columna contaminada |
| Muestreo admitido | 16000 Hz; tiempo positivo entre muestras y uniforme |
| Longitud admitida | 256 a 96000 muestras, múltiplo de 256 |
| Casos actuales | 96000 muestras por caso; duración nominal de 6 s |
| Validación | Columnas, finitud, limpia + ruido = contaminada, tiempo y longitud; presets contrastados con su JSON |
| Conversión | piso(127.5 × (clip(muestra, -1, 1) + 1) + 0.5) |
| Escala | Sin normalización adicional; contar valores fuera de [-1,+1] y limitarlos |
| Correspondencia | -1 → 0, 0 → 128, +1 → 255 |
| Identificación | CRC-32 de los códigos exportados; se registra como metadato, sin protocolo ni cálculo en la placa |

| Caso | Señal útil | Ruido activo | SNR del modelo | Semilla | CRC-32 exportado |
|---|---|---|---|---|---|
| caso_1 | 440, 880 y 1320 Hz | Tonal de 4000 Hz | 10 dB | 1000 | 8B1F9B59 |
| caso_2 | 440, 880 y 1320 Hz | Banda de 2500 a 3800 Hz | 5 dB | 2000 | 6140EEE7 |
| caso_3 | 440, 880 y 1320 Hz | Banda de 600 a 1500 Hz | 0 dB | 3000 | C29233A4 |

La señal útil utiliza amplitudes relativas 1, 0.55 y 0.3, con fases 0°, 35° y -50°.
El CSV conserva el ruido, suavizado y escala del notebook. La exportación actual
reportó cero recortes en los tres casos. La cuantización a 8 bits y el circuito
introducen diferencias frente a los valores ideales y su SNR.

## 1.4. Preparación y selección

Los arreglos de los tres casos ya están exportados. Solo ejecutar el exportador
cuando cambien los CSV o se quiera incluir otra señal compatible. No genera
nuevos ruidos ni altera las semillas o los resultados de Tarea 1.

| Acción desde la raíz del repositorio | Comando o cambio |
|---|---|
| Exportar los tres casos originales | & 'proyecto_1_grupal/.venv/Scripts/python.exe' -m proyecto_1_grupal.herramientas.exportar_senales |
| Actualizar un caso original | & 'proyecto_1_grupal/.venv/Scripts/python.exe' -m proyecto_1_grupal.herramientas.exportar_senales --caso caso_2 |
| Incluir CSV manual en el lugar del caso 2 | & 'proyecto_1_grupal/.venv/Scripts/python.exe' -m proyecto_1_grupal.herramientas.exportar_senales --caso caso_2 --archivo 'proyecto_1_grupal/tarea1_grupo1/tonos_defensa/muestras_referencia.csv' |
| Caso inicial | En app_main.c, CASO_EMISION_INICIAL = SENAL_CASO_1 |
| Elegir otro caso | Cambiar esa constante a SENAL_CASO_2 o SENAL_CASO_3 |
| Entrar al firmware | Set-Location proyecto_1_grupal/firmware/esp32 |
| Compilar/programar al cierre | Desde terminal ESP-IDF 5.5.5: idf.py -p COM5 build flash monitor |
| Repetir la señal | Reiniciar con EN/RESET; preparar antes el receptor o instrumento de medida |

| Condición | Comportamiento |
|---|---|
| Cambiar selección o muestras | Requiere recompilar y programar nuevamente |
| CSV manual | Reemplaza solo el registro seleccionado del firmware; conserva los CSV originales del notebook |
| Restaurar casos originales | Ejecutar el exportador sin argumentos y volver a compilar |
| Archivos específicos | Se sobrescriben el C y JSON del caso actualizado; no se borran carpetas |
| Reinicio | Conserva los datos en flash y reproduce de nuevo el caso seleccionado |
| Consola | UART0 a 115200 solo muestra registros de inicio, fin o error |
| Puerto COM | COM5 es un ejemplo para la programación; usar el puerto real |
| USB | Se retiraron cliente de envío, comandos ASM1, carga en RAM y dependencia PySerial |

## 1.5. Memoria y reproducción

| Elemento | Implementación |
|---|---|
| Datos de los tres casos | 3 × 96000 = 288000 bytes de muestras constantes; presupuesto de flash adicional al programa |
| Flash disponible | Comprobar tamaño final de imagen y partición al compilar; no asumir capacidad física por la etiqueta ESP-32S |
| RAM de trabajo | Un buffer de 1536 códigos; no se copia un registro completo a RAM |
| DMA | Seis buffers de 512 bytes = 3072 bytes, más estructuras del controlador |
| Reservas adicionales | Tarea, estado, semáforo y recursos de ESP-IDF |
| Salida | Un canal, GPIO25, 16000 muestras/s solicitadas, reloj APLL |
| Arranque | Una entrega de hasta 1536 muestras del registro |
| Continuación | Bloques de 256, sin repetir fragmentos ni añadir esperas artificiales |
| Copia | Desde el arreglo constante en flash al buffer RAM, después al formato DMA interno |
| Alineación | Códigos de 8 bits; ESP-IDF los adapta a contenedores internos de 16 bits |
| Escritura | Síncrona; timeout de 1000 ms y comprobación de cantidad aceptada |
| Consumo | Eventos on_convert_done acumulan write_bytes / 2 |
| Final | on_stop compara contra la longitud total; fin normal exige previsto = aceptado = consumido |
| Cierre | Esperar hasta 1000 ms tras enviar el último bloque y después liberar el DAC |
| Errores | Detener y cerrar; informar la causa mediante el registro de ESP-IDF |

Aceptar bytes significa que el controlador ya los copió. Esperar el evento final
permite que termine de consumirlos antes de deshabilitar el DAC. Los contadores
describen el avance reportado por DMA; la señal física se valida con medición.

## 1.6. Conexión y verificación pendiente

| Elemento | Acuerdo |
|---|---|
| Señal | GPIO25 hacia entrada ADC acondicionada de Pico |
| Referencia eléctrica | GND común |
| Componente DC | El cero numérico corresponde aproximadamente a media alimentación |
| Coordinación con Persona 1 | Confirmar pin ADC, niveles, acondicionamiento y filtrado analógico |
| Referencia limpia | Este único DAC reproduce la mezcla; no entrega un segundo canal limpio |

| Verificación al cierre | Criterio |
|---|---|
| Compilación | ESP-IDF 5.5.5; revisar imagen, partición y RAM |
| Tres casos | Seleccionar, programar y medir cada registro de 96000 muestras |
| Datos | Comprobar conversión y correspondencia con los CSV de origen |
| Duración | Una emisión de 6 s nominales por arranque; sin repetición automática |
| Continuidad | Frecuencias, amplitud, tasa efectiva y ausencia de interrupciones medidas |
| Final DMA | Número exacto de muestras, sin paradas prematuras ni cierre anticipado |
| Reinicio | Nueva reproducción del mismo registro conservado en flash |
| Modelo Python | Pruebas finales sin regresiones y cargar_caso compatible |

## 1.7. Fuentes

| Fuente | Uso |
|---|---|
| [DAC de ESP-IDF v5.5](https://docs.espressif.com/projects/esp-idf/en/v5.5/esp32/api-reference/peripherals/dac.html) | APLL, DMA, alineación y eventos |
| [Tipos de memoria de ESP-IDF v5.5](https://docs.espressif.com/projects/esp-idf/en/v5.5/esp32/api-guides/memory-types.html) | Datos constantes en flash y memoria de trabajo |
| [Configuración Python](../../tarea1_grupo1/metadatos/configuraciones.json) | Parámetros y semillas de los casos |
| SDK local ESP-IDF 5.5.5 | Semántica del controlador DAC y enlace de datos constantes |
