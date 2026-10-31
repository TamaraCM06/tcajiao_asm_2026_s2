# 1. Proyecto grupal: reducción adaptativa de ruido

Proyecto de CE 1110, Análisis de Señales Mixtas. Contiene el modelo Python de
Tarea 1 y el avance del taller de semana 12: prototipo Python del sistema
completo, emisión de señales y evaluación digital de filtros en ESP32, y
receptor en Raspberry Pi Pico con su estrategia de validación.

Para preparar y ejecutar la demostración del taller, consultar el
[README de ESP32](firmware/esp32/README.md). Esta guía general explica dónde está
cada parte y cómo trabajar con el modelo Python.

## 1.1. Accesos principales

| Parte | Contenido | Acceso |
|---|---|---|
| Modelo Python de Tarea 1 | Señales reproducibles, análisis de Fourier, filtros temporal y espectral, métricas y figuras | [Notebook](tarea1_grupo1/notebook.ipynb) y [README de Tarea 1](tarea1_grupo1/README.md) |
| Taller: prototipo Python | Ejecuta los tres casos, el diseño FIR, el filtro espectral y las métricas sin abrir el notebook | [prototipo.py](prototipo.py) y [ajustes](metadatos/prototipo.json) |
| Taller: ESP32 | Firmware C que emite tres señales por DAC, evalúa ambos filtros sobre 95963 muestras y reúne los seis resultados en tablas finales | [Instrucciones de ESP32](firmware/esp32/README.md) |
| Preparación de señales | Exportador de los CSV del notebook a los datos incluidos en flash | [Exportador](herramientas/exportar_senales.py) |
| Taller: receptor Pico | Firmware C que adquiere por ADC a 10 kHz, analiza bloques de 256 con Hann y FFT y reporta diagnóstico por USB | [Instrucciones del receptor](firmware/receptor/README.md) |
| Taller: informe | Proceso de diseño, criterios, validación y discusión del avance, con las fuentes de sus diagramas | [Informe](docs/avance2/informe.pdf) y [diagramas](docs/avance2/README.md) |
| Requisitos de Tarea 1 | Enunciado académico de la primera entrega | [Enunciado](docs/references/ASM_Tarea1_v7.pdf) |

El convertidor digital a analógico (DAC) convierte los códigos numéricos en una
salida eléctrica. Evaluar filtros sobre datos guardados y comprobar esa salida
son actividades distintas.

## 1.2. Organización del proyecto

| Ubicación | Qué contiene |
|---|---|
| [tarea1_grupo1](tarea1_grupo1/) | Modelo Python, notebook, pruebas y resultados de Tarea 1 |
| [prototipo.py](prototipo.py) y [metadatos](metadatos/) | Prototipo Python del taller y sus ajustes |
| [firmware/esp32](firmware/esp32/) | Programa de la ESP32 e instrucciones del taller |
| [firmware/receptor](firmware/receptor/) | Programa del receptor Raspberry Pi Pico, pruebas y visualizador |
| [herramientas](herramientas/) | Preparación de datos para el firmware |
| [docs/avance2](docs/avance2/) | Informe del avance del taller y fuentes de sus diagramas |
| [configuraciones.json](tarea1_grupo1/metadatos/configuraciones.json) | Parámetros y semillas de los tres casos |
| [pruebas](tarea1_grupo1/pruebas/) | Archivos de audio WAV de entrada por caso |
| [resultados](tarea1_grupo1/resultados/) | Muestras, métricas, figuras y salidas de los filtros |

## 1.3. Módulos Python

El [notebook](tarea1_grupo1/notebook.ipynb) organiza los experimentos. Las funciones
reutilizables están en [src](tarea1_grupo1/src/) y las pruebas en
[tests](tarea1_grupo1/tests/).

| Módulo dentro de src | Responsabilidad |
|---|---|
| [filtros/filtros_temporales.py](tarea1_grupo1/src/filtros/filtros_temporales.py) | Ecuación de diferencias y filtro de respuesta finita al impulso (FIR) por bloques con estado |
| [filtros/filtrado_espectral.py](tarea1_grupo1/src/filtros/filtrado_espectral.py) | Parámetros, umbral adaptativo y coordinación del filtro espectral |
| [filtros/bloques_espectrales.py](tarea1_grupo1/src/filtros/bloques_espectrales.py) | Ventana Hann, reconstrucción y ganancias guardadas |
| [filtros/diseno_temporal.py](tarea1_grupo1/src/filtros/diseno_temporal.py) | Diseño FIR y de respuesta infinita al impulso (IIR), respuesta en frecuencia, polos y estabilidad |
| [senales/generacion.py](tarea1_grupo1/src/senales/generacion.py) | Generación de señales y ruido, semillas, suavizado y ajuste de la relación señal a ruido (SNR) |
| [senales/analisis_fourier.py](tarea1_grupo1/src/senales/analisis_fourier.py) | Transformada discreta de Fourier (DFT), espectros y energía por bandas |
| [mediciones/metricas.py](tarea1_grupo1/src/mediciones/metricas.py) | Energía, SNR, error cuadrático medio (MSE), distorsión y atenuación |
| [mediciones/evaluacion.py](tarea1_grupo1/src/mediciones/evaluacion.py) | Alineación temporal y evaluación con las ganancias calculadas desde la mezcla |
| [datos/archivos.py](tarea1_grupo1/src/datos/archivos.py) | Lectura y escritura de parámetros, muestras, audio y paquetes de entrega |
| [visualizacion/graficas.py](tarea1_grupo1/src/visualizacion/graficas.py) | Construcción de figuras; el notebook decide cuándo mostrarlas o guardarlas |

Los módulos conservan las llamadas públicas anteriores, incluidos los imports
desde src. Las funciones se importan desde el módulo que las define.
Los evaluadores reciben las funciones de filtrado como argumentos.

## 1.4. Entorno Python

Se requiere Python 3.10 o superior. Ejecutar los comandos siguientes desde
proyecto_1_grupal/; los pasos de activación son alternativas según el sistema.

| Paso | Comando |
|---|---|
| Crear el entorno | python -m venv .venv |
| Activar en Windows PowerShell | .venv\Scripts\Activate.ps1 |
| Activar en Linux o macOS | source .venv/bin/activate |
| Instalar dependencias | python -m pip install -r requirements.txt |
| Registrar el entorno en Jupyter | python -m ipykernel install --user --name asm-grupal --display-name "Python (ASM grupal)" |

Para ejecutar el prototipo del taller sin notebook, desde proyecto_1_grupal/:

| Paso | Comando |
|---|---|
| Ejecutar los tres casos | python prototipo.py --caso todos |
| Ejecutar un caso | python prototipo.py --caso caso_2 |
| Elegir otra salida o ajustes | python prototipo.py --salida carpeta --config archivo.json |

Los resultados quedan en resultados/simulacion/<caso>/, con figuras, WAV,
muestras, metricas.csv y la configuración efectiva (configuracion_ejecutada.json
y configuracion.csv). Los ajustes de procesamiento están en
[prototipo.json](metadatos/prototipo.json) y los casos en configuraciones.json.

Abrir el [notebook](tarea1_grupo1/notebook.ipynb), seleccionar **Python (ASM grupal)**
como entorno de ejecución y ejecutar todas las celdas con tarea1_grupo1/ como
directorio de trabajo. La ruta indicada por sys.executable debe corresponder al
entorno .venv del proyecto.

## 1.5. Recorrido del notebook

| Orden | Contenido |
|---|---|
| 1 | Importaciones, rutas y configuración |
| 2 | Ejemplo de 2.1a: ocho muestras, DFT, transformada rápida de Fourier (FFT), su inversa (IFFT), magnitud y fase |
| 3 | Generación, escucha y exportación de señales |
| 4 | Diseño, verificación y aplicación del filtro temporal |
| 5 | Aplicación del filtro espectral |
| 6 | Comparación entre reducción de ruido y distorsión |
| 7 | Comparación y exportación de métricas |

CASO selecciona la señal inicial. Para un caso fijo, los parámetros efectivos se
cargan desde configuraciones.json. Los tres casos se regeneran con sus propias
semillas. Con CASO = None también se genera una señal manual o defensa_aleatoria.
La exportación reemplaza los archivos conocidos y el ZIP, conservando los demás
archivos de la carpeta.

Estas señales son la base del taller y de la defensa. El exportador para ESP32
lee los CSV existentes. Las instrucciones de exportación, compilación y
programación están en el [README del emisor](firmware/esp32/README.md#14-preparación-y-ejecución).

## 1.6. Uso de los filtros Python

El filtro espectral analiza bloques con Hann y 50 % de solapamiento. Calcula
las frecuencias mediante una FFT para señales reales (rFFT), aplica las ganancias
y reconstruye mediante la transformada inversa. Las frecuencias inferiores a
frecuencia_minima quedan protegidas. Cuando ruido y señal comparten frecuencias,
el método no puede separarlos perfectamente.

| Función o dato | Uso |
|---|---|
| filtrar_senal() | Recibe la mezcla contaminada y no utiliza la referencia limpia |
| evaluar_filtro() | Procesa toda la señal y limita las métricas al intervalo solicitado |
| Ganancias espectrales | Se calculan desde la mezcla y se reutilizan sobre la referencia para medir distorsión |
| Alineación FIR | Compensa el retardo conocido de 37 muestras |
| Intervalo actual | Entrada y ambos filtros se comparan sobre 95963 muestras; la salida espectral conserva las 96000 |

Ejemplo de evaluación desde tarea1_grupo1/. Cada fila continúa el ejemplo anterior.
Los nombres clean, noise y fs son las claves existentes de la interfaz Python.

| Paso | Instrucción Python |
|---|---|
| Importar lectura | from src.datos import archivos |
| Importar filtro | from src.filtros import filtrado_espectral |
| Cargar caso | caso = archivos.cargar_caso('caso_2') |
| Evaluar | resultado = filtrado_espectral.evaluar_filtro(caso['clean'], caso['noise'], caso['fs'], longitud_evaluacion=95963) |
| Obtener salida | salida = resultado['salida'] |

También se puede ejecutar el módulo directamente:

| Directorio | Comando |
|---|---|
| proyecto_1_grupal/ | python -m tarea1_grupo1.src.filtros.filtrado_espectral |

## 1.7. Resultados del modelo Python

| Ubicación | Contenido |
|---|---|
| [metricas.csv](tarea1_grupo1/resultados/metricas.csv) | Nueve filas: tres casos por tres métodos, incluida la entrada sin filtrar |
| [filtro_temporal](tarea1_grupo1/resultados/filtro_temporal/) | Coeficientes, comparación de diseños y audio filtrado |
| [filtro_espectral](tarea1_grupo1/resultados/filtro_espectral/) | Experimento del caso 3 y audio filtrado |
| [figuras](tarea1_grupo1/resultados/figuras/) | Figuras de señales, filtros y ejemplo de Fourier |
| [fourier_coeficientes.csv](tarea1_grupo1/resultados/fourier_coeficientes.csv) | Componentes no nulas del ejemplo de 2.1a |
| [fourier_verificacion.csv](tarea1_grupo1/resultados/fourier_verificacion.csv) | Errores de DFT frente a FFT y de IFFT frente a las muestras originales |

Los WAV mantienen la escala de amplitud. Las métricas se calculan sobre muestras
en punto flotante. Las tablas exportadas conservan los campos vacíos y las celdas
de exportación reemplazan sus tablas completas.

Los tiempos y la memoria de estos resultados corresponden a la computadora.
La memoria espectral cuenta arreglos explícitos, incluidas las ganancias de
evaluación; excluye temporales internos de NumPy. Estos datos no representan la
memoria ni los tiempos del microcontrolador.

## 1.8. Pruebas

La verificación en computadora reúne 117 pruebas aprobadas: 94 del modelo Python,
16 del núcleo C de filtros y 7 del cierre DAC con eventos controlados.
Para ejecutar las pruebas del modelo Python:

| Directorio | Comando |
|---|---|
| proyecto_1_grupal/ | python -m pytest tarea1_grupo1/tests -q |

Las pruebas de filtros usan los CSV de los casos generados por el notebook.
Cubren comparación con SciPy, reconstrucción, extremos, ruido cambiante,
protección de banda, evaluación parcial, compatibilidad de interfaces, generación
reproducible y exportación sin borrar archivos ajenos. La verificación conjunta
con el núcleo C se describe en el [README de ESP32](firmware/esp32/README.md#17-verificación-numérica).
