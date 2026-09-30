<div align="center">

# Taller 2 - Diseño de un sistema de radar acústico para estimación de distancia

**CE1110 — Análisis de Señales Mixtas** · Instituto Tecnológico de Costa Rica · II Semestre 2026

- Nicolás Florez Jiménez (2024086367)
- Tamara Vanessa Cajiao Molina (2024143333)

<sub>Avance del Primer Proyecto, por lo que el código vive en `proyecto_1/`</sub>

</div>

## Documentación

La documentación completa del proceso, revisión literaria, desarrollo de los
experimentos, interpretación de resultados, anexos y referencias, está en el PDF:

> **[`proyecto_1/docs/Taller2-ASM.pdf`](proyecto_1/docs/Taller2-ASM.pdf)**

Este README cubre únicamente cómo ejecutar los programas.

## Ejecución

Requiere Python 3.9+ con `numpy` y `matplotlib`. Abra `proyecto_1/` como carpeta de
trabajo, no archivos sueltos: los scripts guardan las gráficas en rutas relativas y se
ejecutan desde ahí.

```bash
cd proyecto_1
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

**Parte 2 — Experimentos con FFT:** implementación de la DFT y la FFT, espectros de
magnitud y fase, y comparación de tiempos para distintos tamaños de N.

```bash
.venv/bin/python src/fft_dft/experimentos_fft.py
```

**Parte 3 — Experimentos de detección de ecos:** genera una señal con ecos de retardo
conocido y recupera los retardos por correlación directa y por correlación vía FFT.

```bash
.venv/bin/python src/deteccion_ecos/deteccion_ecos.py
```

Ambos abren las gráficas y las guardan en `outputs/`. El módulo
`src/generacion_señales/generacion_señales.py` contiene la generación del chirp y de la
secuencia de pulsos que ambas partes reutilizan.
