# 1. Manual de operación, pruebas y preparación de entrega

| Campo | Valor |
|---|---|
| Fuente de verdad | [PDF del proyecto](../references/ASM_Proyecto_Grupal1_v7.pdf) |
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
| Preescucha sintética opcional | & '.venv/Scripts/python.exe' -m herramientas.preparar_casos --audio | WAV de limpia, ruido y mezcla; no son salidas de la placa |
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

### 1.5.2. Ensayos físicos

| Paso | Acción | Registro mínimo |
|---|---|---|
| Fuente | P1 coordina una fuente conocida, acondicionada y limitada en banda; usar las señales del notebook | Fuente, escala, conexión y banda efectiva; no aplicar audio bipolar directamente al ADC |
| Adquirir | Aplicar cada condición y capturar/escuchar ambos métodos; para agrupar capturas físicas puede abrirse sesiones.py con --salidas resultados/pruebas_finales/P1, cambiando el Pn según corresponda | Tres sesiones por condición física utilizada; no mezclar esas métricas con las del CSV |
| Referencia | Si se requieren MSE/SNR físicos, resolver adquisición/referencia sincronizada y alineación | El firmware físico actual tiene mezcla sola; no asignar la referencia del CSV a un micrófono por conveniencia |
| Sonido | Probar ambas rutas del mismo estímulo, volumen comparable y sin realimentación | Notas breves por prueba: ruido residual, distorsión, pérdidas y cambios de parámetros |

Las métricas digitales controladas y la demostración física se reportan como
evidencias distintas. Si no se dispone todavía del montaje/referencia, esa parte
sigue pendiente; no se cierra con tres evaluaciones CSV.

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

## 1.6. Verificar muestreo y prevención de aliasing

| Ensayo | Procedimiento | Interpretación correcta |
|---|---|---|
| Banda prevista | Documentar máximas frecuencias útiles/ruido y cómo se limita la banda que llega a GP26 | A 16 kHz, Nyquist es 8 kHz. Una fuente realmente limitada bajo ese valor ayuda a cumplir las condiciones previstas |
| Entrada analógica | Medir la respuesta de la fuente/acondicionamiento/filtro antes del ADC con señal conocida y nivel comprobado | El circuito de reconstrucción situado después de GPIO25 no evita aliasing ocurrido antes en la Pico |
| Diagnóstico sobre Nyquist | Si se dispone de fuente e instrumento adecuados, aplicar un tono conocido sobre 8 kHz a nivel seguro y comparar antes/después del acondicionamiento de entrada | Un tono de 9 kHz aparece alrededor de 7 kHz al muestrear a 16 kHz si no se atenúa. Ese resultado demuestra un problema, no cumplimiento |
| Sin pico observado | Verificar que la fuente sí entregó el tono con amplitud conocida antes de concluir | Un celular que no emite suficiente nivel o un micrófono que no lo recoge no validan automáticamente el filtro |

Este es un diagnóstico de muestreo, no una nueva batería que sustituya las señales
del notebook. Si falta protección/validación de la entrada, resolverla con P1 y
documentar el límite; no afirmar que se evitó aliasing solo por usar 16 kHz.

## 1.7. Completar las métricas y contrastes obligatorios

| Magnitud | Lo disponible | Cómo completar el requisito |
|---|---|---|
| MSE, SNR, ΔSNR, energía útil | ESP32 los calcula con referencia en evaluar; sin referencia están no disponibles | Reportar condiciones, escala y alineación. No inventar referencia física |
| Atenuación principal | ESP32 informa ruido total; graficar_sesion mide tonos conocidos en sus WAV | P1: reportar la componente de 4 kHz. Rechazo bajo PCM16: cota, no atenuación exacta. P2/P5: definir región y método de separación; completar su evaluación, sin confundirla con energía total |
| Respuesta FIR | herramienta respuesta_fir_medida usa tonos presentes y los coeficientes existentes | Ejecutar comando siguiente sobre una sesión P2_tonal; conservar CSV/figura y explicar piso PCM16. Es respuesta digital antes del DAC |
| Costo y memoria | Cálculo conjunto, estado DSP y heap en sesion.json/metricas.csv | Reportarlos con firmware/configuración; no dividir el máximo conjunto entre dos para inventar costos individuales |
| Latencia | No medida físicamente en los archivos actuales | Instrumentar llegada, procesamiento y publicación de bloques en sesiones PC con marcas sincronizadas; medir el trayecto DAC por separado con un instrumento. Anotar criterio, configuración, colas y dispersión; los WAV y el tiempo total de sesión no son latencia física |

| Comando desde proyecto_1_grupal | Resultado |
|---|---|
| & '.venv/Scripts/python.exe' -m herramientas.respuesta_fir_medida resultados/sesiones/20261105T164327Z_614a343d --salida resultados/entrega/fir | Reutiliza la sesión histórica local de cuatro tonos y genera respuesta_fir_medida.csv/png y procedencia local; usar otra sesión compatible si esa no está en la PC |

Para completar la atenuación de banda, el modelo ya dispone de
[atenuacion_interferencia](../../tarea1_grupo1/src/mediciones/metricas.py) y su uso
en [evaluar_espectral](../../tarea1_grupo1/src/mediciones/evaluacion.py). P4 debe
integrar la medida correspondiente a las salidas reales: identificar la región
principal desde el ruido de entrada mezcla menos limpia; obtener ruido de salida
restando la componente útil filtrada, con las ganancias estimadas desde la mezcla;
y comparar energía de esa misma región antes/después. En P2 la banda conocida es
2500–3800 Hz; en P5 hay superposición y la referencia/alineación son necesarias
para separar ruido y útil. No aplicar ese análisis a un micrófono sin referencia
ni presentar el resultado del modelo como medida de placa.

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
| Artículo, con Tectonic instalado | tectonic docs/final/paper/main.tex |
| Herramientas, con Tectonic instalado | tectonic docs/final/herramientas/herramientas.tex |
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
resueltas hasta observarlas o implementar la parte que falta.

## 1.10. Comprobaciones realizadas durante la preparación

| Comprobación | Estado observado el 5 de noviembre de 2026 | Límite |
|---|---|---|
| Pruebas Python y C portable | 175 aprobadas después de retirar el banco antiguo | Incluye los seis casos sobre PCM16, silencio, reconstrucción unitaria, parámetros inválidos, generación de entradas ausentes y controlador DAC vigente |
| C del receptor con GCC | OK: ADC/DC/RMS, FFT frente a DFT, Hann, estimación, CRC8 y trama | Ejecución host, no prueba física de Pico |
| ESP-IDF | Única aplicación PC compilada correctamente después de retirar implementaciones antiguas | No se programaron placas ni se verificó sonido automáticamente |
| Artículo y herramientas | Compilados con Tectonic 0.17.0; 4 y 2 páginas, respectivamente | Contienen pendientes reales hasta completar las medidas |
| Herramientas sobre registros anteriores | Figura de señales/espectros y respuesta FIR generadas desde la sesión histórica existente | Análisis posterior de un registro real; no son nuevas corridas P1–P5 |
| Gitignore y documentos | Código y texto obsoletos retirados; originales seleccionados y entregas anteriores protegidos | Limpieza física parcial: terminal bloqueó la eliminación de binarios y directorios. Sin commits ni archivos de respaldo |
