# Proyecto grupal: Sistema distribuido de reducción adaptativa de ruido

Esta carpeta contiene el trabajo grupal de CE 1110 Análisis de Señales Mixtas. La primera entrega es la **Tarea 1: caracterización espectral y prototipado de filtros para reducción de ruido**: se generan señales de prueba reproducibles (limpia, ruido y contaminada), se caracterizan en tiempo y frecuencia, y se prototipan en computadora un filtro temporal FIR/IIR y un método de reducción espectral FFT/IFFT. Ese código es la referencia de software antes de pasar a los microcontroladores.

## Estructura

```
proyecto_1_grupal/
├── docs/references/      # Enunciado de la tarea (ASM_Tarea1_v7.pdf)
├── src/                  # Código compartido del proyecto
├── tarea1_grupo1/        # Entregable de la Tarea 1
│   ├── notebook.ipynb    # Generación y caracterización de señales
│   ├── src/              # filtros_temporales.py, filtrado_espectral.py
│   └── pruebas/caso_N/   # WAV (limpia, ruido, contaminada) y resultados (JSON, CSV, figuras)
└── requirements.txt      # Dependencias de Python
```

## Entorno

Requiere Python 3.10 o superior. Desde esta carpeta:

```bash
python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python -m ipykernel install --user --name asm-grupal --display-name "Python (ASM grupal)"
```

En VS Code o Jupyter, abra `tarea1_grupo1/notebook.ipynb` y seleccione el kernel **"Python (ASM grupal)"**. Activar el venv en la terminal no cambia el kernel del notebook. Para confirmarlo, `import sys; print(sys.executable)` debe apuntar a `proyecto_1_grupal/.venv`.

## Filtrado espectral (2.4)

`tarea1_grupo1/src/filtrado_espectral.py` contiene el procesamiento FFT/IFFT con
Hann, 50 % de solapamiento y normalización. Reutiliza la FFT de cada bloque para
detectar y atenuar ruido mediante un umbral adaptativo, calculado a partir de la
energía de cada bloque. Permite atenuar un pico o múltiples componentes.
La región inferior a `frecuencia_minima` queda protegida. El filtro no separa
perfectamente señal y ruido cuando comparten frecuencias.

Desde esta carpeta, ejecutar la comparación de los tres casos:

```bash
python tarea1_grupo1/src/filtrado_espectral.py
```

Desde el notebook, con `tarea1_grupo1/` como directorio de trabajo:

```python
from src import filtrado_espectral as fe

caso = fe.cargar_caso("caso_2")
metricas = fe.evaluar_filtro(
    caso["clean"], caso["noise"], caso["fs"]
)
salida = metricas["salida"]
```

`cargar_caso()` lee juntas las muestras y su configuración. `filtrar_senal()`
procesa cualquier arreglo de muestras contaminadas. `evaluar_filtro()` recibe
señal limpia, ruido y frecuencia de muestreo; no depende de los nombres de los
casos ni de sus archivos. Devuelve MSE, SNR, energía útil conservada, atenuación
y salida. La evaluación
mantiene las máscaras estimadas desde la mezcla al separar señal útil y ruido.
El tiempo y la memoria reportados corresponden al prototipo en computadora;
la memoria incluye arreglos completos y excluye temporales internos de NumPy.
El módulo no modifica CSV, WAV ni el notebook.

El archivo está separado en casos/utilidades, validación, detección espectral,
filtrado/reconstrucción, métricas y ejemplo de ejecución. `filtrar_bloque()`
realiza FFT, atenuación e IFFT; `filtrar_senal()` recorre y combina los bloques.

Las pruebas usan pytest, con fixtures y casos parametrizados como el filtro
temporal. Para ejecutar ambas suites desde esta carpeta:

```bash
python -m pytest tarea1_grupo1/tests -q
```
