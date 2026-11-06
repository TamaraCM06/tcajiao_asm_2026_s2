# 1. Manual de operación, pruebas y preparación de entrega

| Campo | Valor |
|---|---|
| Fuente de verdad | [PDF del proyecto](../references/ASM_Proyecto_Grupal1_v7.pdf) |
| Criterios de evaluacion | [Rubrica de defensa y cobertura](RUBRICA_DEFENSA.md); funcionamiento observado y justificacion, ademas de pruebas de software |
| Alcance | Operar lo implementado, obtener resultados y reconocer lo que todavía falta |
| Responsable | P1: Pico/entrada; P2: temporal; P3: ESP32/espectral/audio; P4: medidas/documentos |
| Punto de partida de los comandos | PowerShell abierto en proyecto_1_grupal, salvo indicación contraria |
| Archivos fuente | Código, configuraciones y documentos versionados |
| Salidas locales | resultados y las copias sintéticas Pn; se regeneran o conservan como registros, no se publican todos |
| Pendientes | [TODO de entrega](TODO.md) |

## 1.1. Preparar el entorno sin placas

Desde la raíz del repositorio, entrar con Set-Location proyecto_1_grupal.
Los nombres COM12/COM13 son ejemplos del diagnóstico anterior: comprobar los actuales.

| Paso | Comando o acción | Resultado esperado |
|---|---|---|
| Crear entorno si falta | py -m venv .venv | Entorno Python local |
| Instalar dependencias | & '.venv/Scripts/python.exe' -m pip install -r requirements.txt | NumPy, SciPy, Matplotlib, pytest y PySerial |
| Preparar los seis CSV | & '.venv/Scripts/python.exe' -m herramientas.preparar_casos | CSV P1–P5 y P2_tonal en tarea1_grupo1/resultados/muestras; el JSON fuente no cambia |
| Cambié parámetros del JSON | & '.venv/Scripts/python.exe' -m herramientas.preparar_casos --regenerar | Actualiza solamente las copias Pn locales; preserva los archivos históricos caso_N |
| Audios para ensayos acusticos | & '.venv/Scripts/python.exe' -m herramientas.preparar_casos --audio | WAV sin recortes en resultados/estimulos/Pn; ganancia comun para limpia, ruido y mezcla; no son salidas de la placa |
| Ejecutar simulación reproducible | & '.venv/Scripts/python.exe' prototipo.py --caso todos --salida resultados/simulacion_final | Figuras y tablas de los seis registros, en una carpeta separada de los históricos |
| Pruebas de software | & '.venv/Scripts/python.exe' -m pytest tarea1_grupo1/tests firmware/esp32/tests -q | Todas pasan; no acredita ADC, SPI o audio físicos |

La carga de un caso prepara automáticamente su CSV si falta, incluso en otra
computadora. La preparación utiliza el generador del notebook, no un modelo nuevo.
Los JSON de metadatos/configuraciones son entradas del experimento y se mantienen
en Git; los JSON de cada ejecución son registros locales.

| Comprobación C opcional desde proyecto_1_grupal | Comando |
|---|---|
| Crear carpeta de salida | New-Item -ItemType Directory -Force firmware/receptor/build |
| Compilar métodos de Pico en PC | gcc -std=c11 -Wall -Wextra -Werror -I firmware/receptor firmware/receptor/nodo1_metodos.c firmware/receptor/tests/test_metodos.c -lm -o firmware/receptor/build/test_metodos.exe |
| Ejecutar | & 'firmware/receptor/build/test_metodos.exe' |

## 1.2. Comprobar conexiones y programar

El cableado completo está en la [guía técnica de sesiones, §1.2](../../firmware/esp32/GUIA_SESIONES.md#12-conexiones).

| Señal | Pico | ESP32 o destino |
|---|---|---|
| SCK | GP18 | GPIO18 |
| MOSI | GP19 | GPIO23 |
| CS | GP17 | GPIO27; no GPIO5 |
| READY | GP20 | GPIO21 |
| Tierra | GND | GND común |
| ADC de entrada | GP26/ADC0, pin físico 31 | MAX4466 u otra fuente acondicionada entre 0 y 3.3 V |
| Audio de salida | No conectar al ADC durante escucha con micrófono | GPIO25 → divisor/seguidor/Sallen-Key de 22 nF → GF1002/PAM8403 → parlante |

El LM358 y el amplificador usan los 5 V acordados; eso no autoriza aplicar 5 V
al ADC. El parlante se conecta entre Lout+ y Lout−, sin unir una de esas salidas a
GND. Desenergizar antes de cambiar cableado y empezar con volumen bajo.

Para compilar Pico se requieren Pico SDK, compilador ARM, CMake y Ninja. Si
PICO_SDK_PATH no está configurado, agregar -DPICO_SDK_PATH=C:/ruta/pico-sdk
al comando de configuración siguiente.

| Placa | Programación | Comprobación |
|---|---|---|
| Pico, configurar | cmake -S firmware/receptor -B firmware/receptor/build -G Ninja -DPICO_BOARD=pico -DNODO1_HABILITAR_SPI=ON | Preparación del firmware de adquisición |
| Pico, compilar | cmake --build firmware/receptor/build | Copiar nodo1_receptor.uf2 con BOOTSEL según [README Pico](../../firmware/receptor/README.md#13-compilar-y-cargar). Debe indicar 16000 Hz y SPI habilitado |
| ESP32 | powershell.exe -NoProfile -ExecutionPolicy Bypass -File firmware/esp32/ejecutar_idf.ps1 -Accion build | Compila la única aplicación de sesiones PC desde una copia ASCII |
| Cargar última compilación | powershell.exe -NoProfile -ExecutionPolicy Bypass -File firmware/esp32/ejecutar_idf.ps1 -Accion flash -Puerto COM12 | Programa la copia compilada más recientemente; verificar la versión antes de cargar |
| Listar puertos | & '.venv/Scripts/python.exe' firmware/esp32/tools/sesiones.py --listar | Identificar ESP32 y Pico |

La opción de ejecución de PowerShell anterior aplica a ese proceso, para poder
ejecutar el script local; no cambia la política global del sistema.

## 1.3. Primera captura y reproducción en modo PC

Cerrar el monitor ESP-IDF y cualquier otra aplicación que use el mismo puerto.

| Lugar | Acción | Qué observar |
|---|---|---|
| PowerShell | & '.venv/Scripts/python.exe' firmware/esp32/tools/sesiones.py --puerto COM12 --puerto-pico COM13 --salidas resultados/pruebas_finales | Saludo y enlace a 1 Mbaud; terminal asm |
| asm | estado | Firmware, parámetros y estado |
| asm | configurar segundos=6 minimo_hz=1600 ancho_hz=100 factor=0.1 umbral=0.05 ganancia=0.1 | Configuración aceptada estando detenido |
| asm | capturar | Entrada Pico y dos salidas DSP guardadas; esperar SESION COMPLETA y anotar la ruta |
| asm | reproducir entrada | Escuchar entrada de esa sesión |
| asm | reproducir fir | Escuchar FIR, esperando fin de cada reproducción |
| asm | reproducir espectral | Escuchar espectral sobre la misma entrada |
| asm | validar | Concordancia con Python; es comprobación complementaria, no porcentaje de ruido eliminado |
| asm | nota Entrada audible; FIR ...; espectral ...; volumen ... | Guarda notas.txt fechado, sin modificar medidas |
| asm | detener / salir | Cancelar operación o cerrar puerto, respectivamente |

Cada captura de 6 s debe tener 96000 muestras en las tres rutas y estado completo.
Los mensajes de cola, pérdida, CRC o transferencia fallida no se ocultan: conservar
la sesión incompleta y resolver la causa antes de repetir. Anotar recortes,
contadores, versiones, ganancia y qué se escuchó. No escribir comandos nuevos
mientras una operación esté activa, salvo detener.

Sin referencia limpia sincronizada, MSE, SNR y energía útil aparecen no disponibles;
la energía total y una voz grabada no sirven para deducirlas. La validación Python
puede comparar implementaciones sin esa referencia, pero no crea una señal limpia.

## 1.4. Comparar las dos rutas con reproducción diferida

| Paso en asm | Qué hacer | Qué comprobar |
|---|---|---|
| Captura o evaluación completa | Mantener seleccionada la misma sesión para ambos métodos | Entrada común, misma longitud y configuración |
| reproducir fir | Escuchar el WAV FIR por GPIO25 | Final de reproducción, recortes y ruido residual |
| reproducir espectral | Escuchar el WAV espectral sin cambiar la ganancia | Comparar distorsión y ruido sobre el mismo registro |
| estado | Consultar configuración y sesión seleccionada | No confundir una sesión anterior con la condición actual |
| configurar | Cambiar parámetros solo cuando no haya una operación activa | La siguiente evaluación usa la configuración nueva y una carpeta distinta |

La adquisición, el cálculo y la escucha son etapas del flujo PC vigente. La
reproducción empieza por una orden posterior; no se presenta como salida
analógica continua durante la adquisición. No existe selector de modos de
firmware ni una segunda consola de audio continuo. Las métricas con referencia
se obtienen al evaluar CSV; una captura de micrófono sigue sin referencia limpia.

## 1.5. Ejecutar P1–P5 y obtener estadísticas

El PDF §4 exige tres repeticiones por condición y revisar sonido en cada prueba.
Las siguientes entradas verifican los filtros en la ESP32. Además debe aplicarse
una fuente física controlada a la Pico para verificar ADC/enlace/audio: evaluar
un CSV evita el ADC y no basta para declarar completo el sistema distribuido.

### 1.5.1. Corridas controladas con referencia

Usar modo PC y la terminal abierta con salidas bajo resultados/pruebas_finales.
Cada evaluar se ejecuta tres veces, esperando fin y anotando tres identificadores
distintos. No se obtienen repeticiones copiando una carpeta.

| Prueba | Señal preparada y condición | Comando asm y parámetros | Qué revisar/mostrar |
|---|---|---|---|
| P1 | Tono 440 Hz e interferencia 4000 Hz, SNR 10 dB | Configuración inicial 1600/100/0.1/0.05; evaluar P1, tres veces | Espectros y atenuación del tono de 4 kHz; escuchar entrada/FIR/espectral |
| P2 | Tres tonos y ruido 2500–3800 Hz, SNR 5 dB | Misma configuración; evaluar P2, tres veces | Reconstrucción, ΔSNR, energía útil y sonido |
| P3 | Audio sintético del notebook: barrido 220–1320 Hz con ruido blanco, SNR 5 dB | Misma configuración; evaluar P3, tres veces | MSE, energía y prueba auditiva |
| P4 | Transitorio de 440 Hz e impulsos, SNR 5 dB | Misma configuración; evaluar P4, tres veces | Forma temporal, respuesta y latencia; el tiempo de cálculo solo no cierra la latencia |
| P5 | Tres tonos y ruido superpuesto 600–1500 Hz, SNR 0 dB | configurar minimo_hz=600 factor=0.1; evaluar P5, tres veces | Comparar reducción y pérdida de energía útil frente a FIR; no exigir al caso superpuesto la misma SNR que a P1/P2 |

P2_tonal conserva el antiguo caso 1 y sirve a la demo analógica; no es P1.
Las semillas y amplitudes están en [configuraciones](../../tarea1_grupo1/metadatos/configuraciones.json).
Para ampliar P5, factor=0.8 permite estudiar menos distorsión y menos supresión;
si se reporta esa condición, también requiere tres corridas y se resume por separado.
Restaurar minimo_hz=1600 y factor=0.1 al terminar.

### 1.5.2. Ensayos fisicos con parlante y microfono

Usar los audios del notebook y el montaje existente. No se necesitan instrumentos
nuevos ni se conecta electricamente una salida de audio al ADC.

| Paso | Accion | Registro minimo |
|---|---|---|
| Preparar | Ejecutar preparar_casos --audio del apartado 1.1 | resultados/estimulos/P1 hasta P5; usar 03_entrada_contaminada.wav |
| Fuente | Abrir el WAV en el reproductor de la computadora y activar repeticion | Fijar volumen, distancia y orientacion del parlante frente al microfono |
| Capturar | Abrir sesiones.py con --salidas resultados/pruebas_finales/P1, conservando los puertos de 1.3; ejecutar capturar mientras suena el WAV | Esperar SESION COMPLETA y detener el reproductor |
| Escuchar | Ejecutar reproducir entrada, reproducir fir y reproducir espectral por separado, a igual ganancia | No reproducir la salida durante captura: evita realimentacion |
| Anotar | nota Fuente P1; volumen ...; distancia ...; entrada ...; FIR ...; espectral ... | notas.txt fechado de la captura; incluir ruido residual y distorsion |
| Repetir | Tres capturas nuevas por condicion, cambiando Pn y WAV para P2 a P5 | Tres identificadores distintos. P5: minimo_hz=600 factor=0.1; restaurar 1600 al terminar |

La captura acustica tiene mezcla sola: MSE/SNR y atenuacion regional con referencia
no estan disponibles. El WAV limpio sintetico no esta sincronizado con el ADC.
Las metricas controladas del apartado 1.5.1 proceden de CSV evaluados en ESP32;
se reportan por separado. Parlante, habitacion y microfono alteran banda y nivel.

### 1.5.3. Media, variabilidad, espectros y atenuación

RUTA_SESION significa la ruta que imprimió la terminal, por ejemplo
resultados/pruebas_finales/identificador. Sustituirla por una sesión real.

| Comando PowerShell | Output local y significado |
|---|---|
| & '.venv/Scripts/python.exe' -m herramientas.resumen_pruebas resultados/pruebas_finales --salida resultados/entrega | resumen.csv y tabla_pruebas.tex; media/desviación muestral por prueba, condición y método. No copia WAV, no necesita validar, no declara aprobado el proyecto |
| & '.venv/Scripts/python.exe' -m herramientas.graficar_sesion RUTA_SESION --salida resultados/entrega/P1 --tonos 440 4000 | En P1: senales_espectros.png y atenuacion_tonos.csv; el tono de 440 Hz es útil, el de 4000 Hz es interferencia |
| & '.venv/Scripts/python.exe' -m herramientas.graficar_sesion RUTA_SESION --salida resultados/entrega/P4 --inicio 0.9 --duracion 0.3 | En P4: detalle temporal del intervalo elegido y espectros del registro completo; ajustar intervalo según el transitorio observado |
| & '.venv/Scripts/python.exe' -m herramientas.graficar_sesion RUTA_SESION --salida resultados/entrega/P2 | Mismo comando sin tonos para cualquier registro; generar P3/P5 en carpetas distintas |

El resumen mantiene condiciones distintas separadas y muestra cuántos valores
existen por métrica. Una sola corrida no tiene desviación estimada. Los campos
vacíos no son cero. Que haya tres corridas no significa que el desempeño cumpla:
comparar las métricas con los criterios previamente fijados y discutir límites.
Guardar parámetros y notas de sonido junto al resumen local.

## 1.6. Muestreo y limites analogicos declarados

| Comprobacion | Accion ejecutable | Interpretacion |
|---|---|---|
| Estimulos | Preparar --audio y conservar estimulo.json | WAV a 16000 Hz, escala comun sin recortes; fuente acustica sin calibracion analogica |
| Cadencia | Revisar tasa_bloques_estimada_hz en sesion.json | Estima llegada SPI en ESP32; no calibra el reloj ADC |
| Espectros | Ejecutar graficar_sesion para las capturas | Contenido digital hasta 8000 Hz; no identifica componentes plegadas por si solo |
| Cobertura del articulo | Declarar que no se midio rechazo analogico sobre Nyquist | No afirmar prevencion de aliasing con estas pruebas |
| Reconstruccion | Mantener modelo, esquema y resultados del Sallen-Key | Esta despues del DAC; no protege la entrada ADC |

Por decision del equipo no se realizan ensayos con osciloscopio ni generador.
La prevencion de aliasing y el retardo analogico extremo a extremo quedan como
limitaciones de cobertura del enunciado. Ejecutar el manual no las acredita.

## 1.7. Obtener tiempos y atenuacion sin modificar codigo

Programar el firmware del apartado 1.2 antes de las corridas finales.
version_mediciones=2 identifica las medidas nuevas; las sesiones antiguas se
pueden abrir y reproducir, con campos ausentes no disponibles.

| Magnitud | Accion | Resultado y significado |
|---|---|---|
| MSE, SNR, mejora y energia util | evaluar P1 hasta P5 | Referencia PCM16 y alineacion fija de 37 muestras |
| Atenuacion regional | Evaluar los casos conocidos | atenuacion_interferencia_db y estado_atenuacion_regional por ruta, calculados en ESP32 |
| Region para CSV propio | configurar interferencia_min_hz=2500 interferencia_max_hz=3800; despues evaluar ruta.csv | Ambos limites juntos; sin referencia permanece no disponible |
| Region automatica | configurar interferencia_min_hz=auto | P1/P2_tonal: 3950--4050 Hz; P2: 2500--3800 Hz; P3/P4: 0--8000 Hz; P5: 600--1500 Hz |
| Costo individual | Revisar ruta_cantidad, ruta_medio_us y ruta_max_us en FIR y espectral | FIR por 256 muestras; espectral por ventana 1024/salto 512. Incluyen calculo de referencia, incluso ceros sin referencia |
| Evaluacion y publicacion | Revisar evaluacion y publicacion con sufijos cantidad, medio_us y max_us | Evaluacion: metricas y FFT regional. Publicacion: cuantizacion y entrega al controlador UART |
| Espera en cola | Revisar cola_cantidad, cola_medio_us y cola_max_us | Desde recepcion SPI/UART hasta consumo del bloque; incluye preparacion anterior al DSP |
| Latencia digital | Revisar latencia_bloque_cantidad, latencia_bloque_medio_us y latencia_bloque_max_us | Desde bloque completo recibido en ESP32 hasta aceptacion UART de sus indices de salida; excluye ADC, viaje UART, escritura PC y DAC |
| Bordes | Revisar latencia_arranque y latencia_cierre con los mismos sufijos | Primera publicacion y vaciado separados del estado estable |
| Memoria y presupuesto | Revisar estado_dsp_bytes, heap_minimo_bytes y calculo_max_us | Presupuesto conjunto interno 32000 us; incluye evaluacion, no equivale a latencia fisica |
| Notas de escucha | nota FIR ...; espectral ...; ganancia ... | notas.txt de la sesion seleccionada |

La medida regional utiliza ruido de entrada mezcla menos limpia, y residuos de
salida menos componente util filtrada con las ganancias reales de ESP32.
Usa FFT de 1024, Hann simetrica y bloques completos no solapados del intervalo
valido; region_muestras explicita su longitud. El final parcial se excluye.
P3/P4 tienen interferencia de banda ancha; no se inventa un tono principal.
Los estados sin_referencia, sin_region, sin_bloques_completos, sin_energia_entrada
y residuo_no_resuelto explican los resultados no disponibles.

| Contraste adicional desde proyecto_1_grupal | Comando |
|---|---|
| Respuesta FIR digital | & '.venv/Scripts/python.exe' -m herramientas.respuesta_fir_medida resultados/sesiones/20261105T164327Z_614a343d --salida resultados/entrega/fir |
| Atenuacion tonal P1 | graficar_sesion con --tonos 440 4000 del apartado 1.5.3 |

Los contrastes sobre WAV son anteriores al DAC y tienen piso PCM16. La medida
regional nueva precede a esa cuantizacion. Ninguno mide respuesta analogica.

## 1.8. Ensayar P6 y la defensa

| Elemento | Ensayo |
|---|---|
| CSV desconocido | En asm: evaluar "C:/ruta/desconocida.csv". Formato con referencia: tiempo_s,limpia,ruido,contaminada; sin referencia: tiempo_s,contaminada |
| Límites reales | CSV uniforme a 16000 Hz, 256–960000 muestras, múltiplo de 256; bloques de entrada 256, FFT 1024 y salto 512 fijos. Comunicar esos límites antes de la prueba |
| Ajustes sin recompilar | configurar minimo_hz=... ancho_hz=... factor=... umbral=... ganancia=... estando detenido |
| Señal/ruido nuevos | Cambiar archivo o fuente física; no editar semillas/algoritmos históricos para favorecer una salida |
| Referencia ausente | Mostrar no disponible para MSE/SNR, justificar qué sí se puede medir y escuchar ambas salidas |
| Defensa real | P6 la configura el profesor. Ensayo local no equivale a conocerla ni completarla |
| Guion | ≤15 min, todos participan; arquitectura, métodos, espectros/polos/ceros, métricas, sonido, P6 y límites. Cada integrante explica el código que entrega |

## 1.9. Seleccionar outputs y dejar lista la entrega

| Paso | Qué hacer | Dónde queda |
|---|---|---|
| Conservar registros | Mantener los originales utilizados en resultados y sus notas; descartar después ensayos no utilizados y copias duplicadas | resultados/pruebas_finales, local; no se requieren copias completas en docs |
| Seleccionar estadísticas | Revisar resumen.csv y condiciones; copiar una selección final al artículo y, si sirve, a evidencias/pruebas/resumen_final.csv | Resultados pequeños versionables |
| Actualizar tabla del artículo | Tras tener medidas reales, copiar/adaptar resultados/entrega/tabla_pruebas.tex a docs/final/paper/tablas/pruebas_finales.tex | El artículo compila aun antes, con un pendiente explícito en esa fuente |
| Seleccionar figuras | Copiar solo las usadas: P1_senales_espectros.png, P2_senales_espectros.png, etc., y P1_atenuacion_tonos.csv a docs/final/evidencias/pruebas | El gitignore permite esa selección; los originales siguen locales |
| Filtro de reconstrucción | Mantener modelo/componentes, esquema y limitaciones de salida en el artículo | El PDF exige documentarlo. Demo analógica adicional es opcional y no es antialias del ADC |
| Reescribir resultados | Sustituir pendientes con datos medidos; distinguir simulación, CSV en ESP32, ADC físico y salida analógica | Artículo ≤4 páginas, incluyendo referencias |
| Herramientas | Mantener solo herramientas que se usaron y explicar para qué; declarar IA si se utilizó | Documento ≤2 páginas |
| Revisión final | Ejecutar tests, compilar PDF, revisar referencias y explicar cada módulo con el equipo | Revisión de entrega, no reemplazo de los ensayos físicos |
| Git y publicación | Revisar diff, preparar commits incrementales, integrar mediante development/master y tag según acuerdo del equipo | Pendiente de ejecución del equipo; este bloque no publica ni hace commits |

| Compilación documental | Comando desde proyecto_1_grupal |
|---|---|
| Fuente de letras del compilador local | $env:FONTCONFIG_FILE = (Resolve-Path 'firmware/esp32/build/herramientas_tex/fonts.conf').Path |
| Articulo, compilador local conservado | & 'firmware/esp32/build/herramientas_tex/tectonic.exe' docs/final/paper/main.tex |
| Herramientas, compilador local conservado | & 'firmware/esp32/build/herramientas_tex/tectonic.exe' docs/final/herramientas/herramientas.tex |
| Alternativa desde cada carpeta LaTeX | latexmk -pdf main.tex, o latexmk -pdf herramientas.tex, según la carpeta |

### 1.9.1. Diagnósticos opcionales

| Diagnóstico | Cuándo sirve | Lo que no implica |
|---|---|---|
| Capturar 60 s | Investigar continuidad/colas: configurar segundos=60 y capturar | El PDF no exige 60 s ×3 ni que esto sustituya P1–P5 |
| demo analogico | Revisar ganancia del filtro de salida usando sonda Pico guiada; ver [guía técnica §1.10](../../firmware/esp32/GUIA_SESIONES.md#110-demo-de-comparación-analógica-y-concordancia-porcentual) | No es validación de antialias en la entrada. El punto actual de 4 kHz no es válido |
| validar | Revisar discrepancias entre C y Python; criterio interno ≥90 % | No acredita eliminación de ruido, sonido, ADC ni circuito analógico |

Si un diagnóstico genera JSON o capturas intermedias, conservarlos localmente.
Solo promover a la entrega el resultado necesario para una afirmación del artículo
o para demostrar un requisito. Las acciones pendientes del TODO no se consideran
resueltas hasta ejecutar los ensayos y revisar sus resultados.

## 1.10. Comprobaciones realizadas durante la preparación

| Comprobación | Estado observado el 5 de noviembre de 2026 | Límite |
|---|---|---|
| Pruebas Python y C portable | 195 aprobadas en 18.26 s; sin omisiones | Incluye casos PCM16, energias regionales frente a NumPy, reloj controlado, notas, compatibilidad y controlador DAC |
| C del receptor con GCC | OK: ADC/DC/RMS, FFT frente a DFT, Hann, estimación, CRC8 y trama | Ejecución host, no prueba física de Pico |
| ESP-IDF | Única aplicación PC compilada correctamente después de retirar implementaciones antiguas | No se programaron placas ni se verificó sonido automáticamente |
| Artículo y herramientas | Compilados con Tectonic 0.17.0; 4 y 2 paginas, sin referencias sin resolver | Contienen pendientes reales hasta completar las medidas |
| Herramientas sobre registros anteriores | Figura de señales/espectros y respuesta FIR generadas desde la sesión histórica existente | Análisis posterior de un registro real; no son nuevas corridas P1–P5 |
| Gitignore y documentos | Código y texto obsoletos retirados; originales seleccionados y entregas anteriores protegidos | Limpieza física parcial: terminal bloqueó la eliminación de binarios y directorios. Sin commits ni archivos de respaldo |

## 1.11. Limpieza manual opcional de residuos bloqueados

La herramienta rechazo el borrado fisico con blocked by policy. No se elimino
ninguno de los directorios de esta lista en este bloque. Son residuos locales
ignorados y no impiden compilar, ejecutar las pruebas ni entregar las fuentes.
Desde el explorador pueden eliminarse exclusivamente los destinos siguientes,
relativos a proyecto_1_grupal. Las 21 carpetas suman 356.14 MiB, aun no liberados.

| Carpeta exacta | Archivos |
|---|---|
| [firmware/esp32/components/senales_embebidas](../../firmware/esp32/components/senales_embebidas) | 3 |
| [firmware/esp32/components/procesamiento_vivo](../../firmware/esp32/components/procesamiento_vivo) | 0 |
| [herramientas/exportacion_senales](../../herramientas/exportacion_senales) | 4 |
| [resultados/verificacion_final_pc](../../resultados/verificacion_final_pc) | 42 |
| [resultados/entrega](../../resultados/entrega) | 2 |
| [docs/final/evidencias/sesiones](../../docs/final/evidencias/sesiones) | 7 |
| [docs/final/evidencias/analogicas](../../docs/final/evidencias/analogicas) | 5 |
| [firmware/esp32/build/herramientas_tex/python](../../firmware/esp32/build/herramientas_tex/python) | 3903 |
| [firmware/esp32/build/herramientas_tex/python_directo](../../firmware/esp32/build/herramientas_tex/python_directo) | 349 |
| [resultados/sesiones/20261105T163651Z_ba92e584](../../resultados/sesiones/20261105T163651Z_ba92e584) | 3 |
| [resultados/sesiones/20261105T164137Z_f2c20270](../../resultados/sesiones/20261105T164137Z_f2c20270) | 4 |
| [resultados/sesiones/20261105T165130Z_4e835c38](../../resultados/sesiones/20261105T165130Z_4e835c38) | 3 |
| [resultados/sesiones/20261105T190945Z_fe045572](../../resultados/sesiones/20261105T190945Z_fe045572) | 3 |
| [resultados/sesiones/20261105T191324Z_a11b0064](../../resultados/sesiones/20261105T191324Z_a11b0064) | 4 |
| [resultados/sesiones/analogicas/20261105T173151Z_bd45e110](../../resultados/sesiones/analogicas/20261105T173151Z_bd45e110) | 0 |
| [resultados/sesiones/analogicas/20261105T174317Z_e04f1970](../../resultados/sesiones/analogicas/20261105T174317Z_e04f1970) | 1 |
| [resultados/sesiones/analogicas/20261105T182257Z_3f2eaaa7](../../resultados/sesiones/analogicas/20261105T182257Z_3f2eaaa7) | 1 |
| [tarea1_grupo1/pruebas/P1](../../tarea1_grupo1/pruebas/P1) | 3 |
| [tarea1_grupo1/pruebas/P3](../../tarea1_grupo1/pruebas/P3) | 3 |
| [tarea1_grupo1/pruebas/P4](../../tarea1_grupo1/pruebas/P4) | 3 |
| [src](../../src) | 0 |

Ademas pueden retirarse solamente estas capturas PNG de revision dentro de
firmware/esp32/build/herramientas_tex: herramientas_1.png, herramientas_2.png,
main_4.png, main_5.png, revision_3.png y revision_4.png.

| No eliminar | Motivo |
|---|---|
| resultados/sesiones/20261105T164053Z_77315ebc | Original fisico seleccionado |
| resultados/sesiones/20261105T164327Z_614a343d | Evaluacion controlada seleccionada |
| resultados/sesiones/20261105T165522Z_88f6f6f0 | Fuente de la medicion analogica |
| resultados/sesiones/analogicas/20261105T185714Z_80cf289c | Original analogico seleccionado |
| docs/final/evidencias/README.md y resultados_observados.csv | Indice y resultados seleccionados |
| docs/final/evidencias/fir y docs/final/evidencias/analogica | Cuatro archivos seleccionados; analogica es singular |
| .venv; firmware/esp32/build/ruta_compilacion.txt | Entorno y referencia a ultima compilacion |
| firmware/esp32/build/herramientas_tex/tectonic.exe y fonts.conf | Compilador documental local |
| resultados/estimulos y resultados/pruebas_finales | Estimulos actuales y futuras corridas del manual |
| proyecto_1; docs/avance2; historicos de tarea1_grupo1 | Entregas anteriores |

No eliminar las carpetas padre resultados/sesiones, docs/final/evidencias ni
firmware/esp32/build/herramientas_tex completas: contienen archivos protegidos.

## 1.12. Comprobar adquisicion y preparar la explicacion de la rubrica

La [matriz de evaluacion](RUBRICA_DEFENSA.md) define que demostrar y explicar por
categoria. Este apartado usa diagnosticos existentes, sin instrumentos nuevos.

| Paso | Comando o accion | Evidencia e interpretacion |
|---|---|---|
| Consola Pico | En otra ventana PowerShell desde proyecto_1_grupal: & '.venv/Scripts/python.exe' -m serial.tools.miniterm COM13 115200 | COM13 es ejemplo. Cerrar visualizador y demo analogica antes; no abrir el mismo puerto en dos aplicaciones |
| Preparar captura | Mantener la terminal de sesiones en COM12 y ejecutar capturar como en 1.3 | La captura normal usa SPI y el puerto ESP32; no solicita ADC1 por USB Pico |
| Nivel ADC | Observar Sat durante la misma fuente y volumen de la captura | Sat cuenta extremos ADC antes de quitar DC. Si aparece saturacion, reducir nivel de fuente o ganancia de microfono y repetir |
| Continuidad | Anotar Perd/Err/Rein antes y despues de la captura | Son acumulados desde arranque; comparar diferencias del intervalo. sin_READY puede crecer fuera de captura, cuando ESP32 no recibe; no equivale por si solo a error ADC |
| Nivel y escala | Observar DC, Vpp, RMS y Fs | Documentar offset, amplitud y cadencia estimada. Vref 3.3 V es nominal, no calibracion analogica |
| Frecuencia | Observar Pico Hz y el espectro del WAV de entrada con graficar_sesion | Pico Hz es el dominante de la mezcla del bloque mas intenso; no identifica automaticamente la interferencia |
| Notas | En asm: nota Pico Sat ...; Perd inicio/final ...; Err ...; Rein ...; volumen ... | Asociar observaciones de adquisicion con la sesion. recortes_entrada=0 en ESP32 no demuestra ausencia de saturacion ADC |
| Cerrar consola | Ctrl+] en miniterm | Libera USB Pico antes del visualizador o de demo analogico |

Explicar las tres resoluciones por separado: Pico usa 256 muestras, 62.5 Hz entre
bins; el filtro espectral usa 1024, 15.625 Hz; graficar_sesion usa el WAV completo
de 6 s, aproximadamente 0.167 Hz entre bins. La separacion de componentes tambien
depende de Hann; una figura mas fina no aumenta la resolucion de la FFT embebida.

Durante la defensa, mostrar la fuente, diagnosticar bandas de ruido, comparar las
dos salidas a igual ganancia y justificar la seleccion con metricas y escucha.
En P5, reconocer la superposicion y la perdida posible de energia util. Preparar
la explicacion del FIR, polos/ceros/estabilidad, simetria FFT, umbrales y OLA;
cada integrante debe explicar cualquier linea de codigo que se seleccione.

La orden capturar coordina adquisicion, filtros y guardado. La reproduccion sigue
requiriendo una orden posterior. La rubrica de integracion automatica y el
requisito cuasi real del PDF no se marcan acreditados por ejecutar esa secuencia.
