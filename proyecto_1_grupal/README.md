# Proyecto grupal: reducción adaptativa de ruido

Primera entrega de CE 1110 Análisis de Señales Mixtas: señales reproducibles,
fundamentos de Fourier y prototipos de filtrado temporal y espectral. El enunciado
está en `docs/references/ASM_Tarea1_v7.pdf`.

## Estructura

El trabajo está en `tarea1_grupo1/`: el notebook organiza los experimentos,
`src/` contiene las funciones reutilizables y `tests/` sus pruebas.
Las semillas están en `metadatos/configuraciones.json`, los WAV de entrada en
`pruebas/caso_N/` y las muestras, métricas, figuras y salidas en `resultados/`.

| Ubicación en src | Qué buscar aquí |
|---|---|
| filtros/filtros_temporales.py | Ecuación de diferencias y FIR por bloques con estado. |
| filtros/filtrado_espectral.py | Parámetros, umbral adaptativo y coordinación FFT/IFFT. |
| filtros/bloques_espectrales.py | Hann, relleno, reconstrucción y ganancias guardadas. |
| filtros/diseno_temporal.py | Diseño FIR/IIR, respuesta, especificaciones, polos y estabilidad. |
| senales/generacion.py | Señales, ruido, semillas, suavizado y escalado de SNR. |
| senales/analisis_fourier.py | DFT directa, espectros y energía por bandas. |
| mediciones/metricas.py | Energía, SNR, MSE, distorsión y atenuación. |
| mediciones/evaluacion.py | Alineación temporal y evaluación espectral con ganancias de la mezcla. |
| datos/archivos.py | JSON, CSV, PCM16, WAV y ZIP. |
| visualizacion/graficas.py | Construcción de figuras, sin mostrarlas ni guardarlas. |

Las carpetas agrupan filtrado y diseño (`filtros`), señales y Fourier (`senales`),
medidas y evaluación (`mediciones`), archivos (`datos`) y figuras (`visualizacion`).
`src/__init__.py` conserva también los imports anteriores `from src import ...`.

Los módulos de filtrado conservan su interfaz pública como fachadas: las llamadas
anteriores a sus funciones de lectura, diseño y evaluación siguen disponibles.
Para código nuevo, importar cada utilidad desde el módulo responsable.
Los evaluadores reciben funciones de filtrado, evitando dependencias circulares.

## Entorno

Se requiere Python 3.10 o superior. Desde `proyecto_1_grupal/`:

```bash
python -m venv .venv
# Windows PowerShell:
.venv\Scripts\Activate.ps1
# Linux/macOS: source .venv/bin/activate
pip install -r requirements.txt
python -m ipykernel install --user --name asm-grupal --display-name "Python (ASM grupal)"
```

Abrir `tarea1_grupo1/notebook.ipynb`, seleccionar el kernel **Python (ASM grupal)**
y ejecutar todas las celdas con `tarea1_grupo1/` como directorio de trabajo.
`sys.executable` debe apuntar al entorno `.venv` del proyecto.

## Recorrido del notebook

1. Importaciones, rutas y configuración.
2. Ejemplo de 2.1a: ocho muestras, DFT directa, FFT e IFFT, magnitud y fase.
3. Generación, escucha y exportación de señales.
4. Diseño, verificación y aplicación del filtro temporal.
5. Aplicación del filtro espectral.
6. Compromiso entre reducción de ruido y distorsión.
7. Comparación y exportación común de métricas.

`CASO` elige la señal mostrada y escuchada al inicio. Los tres casos del JSON
siempre se regeneran con semillas independientes. Con `CASO = None`, se genera
además una prueba manual o `defensa_aleatoria`. Su exportación sobrescribe solo
los archivos conocidos y el ZIP; conserva los demás archivos de la carpeta.

El notebook cubre el trabajo implementado y el ejemplo de 2.1a. Los demás
apartados teóricos pendientes y la propuesta embebida corresponden al trabajo del grupo.

## Uso de los módulos

Desde `tarea1_grupo1/`:

```python
from src.datos import archivos
from src.filtros import filtrado_espectral as fe

caso = archivos.cargar_caso('caso_2')
resultado = fe.evaluar_filtro(
    caso['clean'], caso['noise'], caso['fs'], longitud_evaluacion=95963
)
salida = resultado['salida']  # Conserva las 96000 muestras.
```

`filtrar_senal()` recibe muestras contaminadas y no utiliza la referencia limpia.
Procesa bloques con Hann, rFFT, umbral adaptativo, irFFT y reconstrucción con
50 % de solapamiento. Las frecuencias inferiores a `frecuencia_minima` se protegen.
El método no separa perfectamente señal y ruido cuando comparten frecuencias.

`evaluar_filtro()` procesa la señal completa y limita las métricas al intervalo
solicitado. Para medir distorsión conserva las ganancias estimadas desde la mezcla
al procesar la referencia. El FIR compensa su retardo de 37 muestras: actualmente
ambos filtros y la entrada se comparan sobre las primeras 95963 muestras.

La ejecución directa sigue disponible desde `proyecto_1_grupal/`:

```bash
python -m tarea1_grupo1.src.filtros.filtrado_espectral
```

## Resultados

- `resultados/metricas.csv`: nueve filas, tres casos por tres métodos.
- `resultados/filtro_temporal/`: coeficientes, comparación de diseños y WAV filtrados.
- `resultados/filtro_espectral/`: experimento del caso 3 y WAV filtrados.
- `resultados/figuras/`: figuras de generación, filtros y ejemplo de Fourier.
- `resultados/fourier_coeficientes.csv`: componentes no nulos del ejemplo de 2.1a.
- `resultados/fourier_verificacion.csv`: errores DFT–FFT e IFFT frente a las muestras.

Los WAV mantienen la escala de amplitud; las métricas se calculan sobre muestras
en punto flotante. Las celdas de exportación reemplazan sus tablas completas.
Los campos todavía no calculados para un método quedan vacíos.

Los tiempos y la memoria corresponden al prototipo en computadora. La memoria
espectral cuenta arreglos explícitos, incluidas las ganancias guardadas para
evaluación; excluye temporales internos de NumPy y no representa la RAM del microcontrolador.

## Pruebas

Desde `proyecto_1_grupal/`:

```bash
python -m pytest tarea1_grupo1/tests -q
```

Las pruebas de filtros utilizan los CSV de los casos; si faltan, ejecutar primero
el notebook. Se comprueban la implementación contra SciPy, reconstrucción y
extremos, ruido cambiante, protección de banda, evaluación parcial, compatibilidad
de interfaces, generación reproducible y exportación sin borrar archivos ajenos.
