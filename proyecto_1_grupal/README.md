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
