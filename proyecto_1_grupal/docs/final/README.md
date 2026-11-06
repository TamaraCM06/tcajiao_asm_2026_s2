# 1. Entrega final

| Campo | Valor |
|---|---|
| Requisitos | [ASM Proyecto Grupal 1 v7](../references/ASM_Proyecto_Grupal1_v7.pdf) |
| Plazo | 6 de noviembre de 2026, 23:50, Costa Rica |
| Operación | [Manual de usuario](MANUAL_USUARIO.md) |
| Rúbrica | [Criterios de defensa y límites](RUBRICA_DEFENSA.md) |

## 1.1. Qué se entrega

| Elemento | Ubicación | Estado |
|---|---|---|
| Artículo IEEE | [Fuente](paper/main.tex), [PDF](paper/main.pdf) | 4 páginas con referencias; resultados P1–P5 en placa |
| Herramientas de ingeniería | [Fuente](herramientas/herramientas.tex), [PDF](herramientas/herramientas.pdf) | 2 páginas: selección, aplicación y adaptación |
| Modelo reproducible | [Notebook](../../tarea1_grupo1/notebook.ipynb), [prototipo](../../prototipo.py) | Señales P1–P5, DFT/FFT, candidatos FIR/IIR, figuras y tablas |
| Resultados seleccionados | [Evidencias](evidencias/README.md) | Resumen de 14 evaluaciones en placa, espectros P1–P5, FIR medido y filtro analógico |
| Sistema funcional | [Firmware Pico](../../firmware/receptor/README.md), [ESP32](../../firmware/esp32/README.md), [terminal](../../firmware/esp32/tools/sesiones.py) | Se demuestra en la defensa |

## 1.2. Resultados principales (6/11, ESP32)

| Prueba | FIR ΔSNR | Espectral ΔSNR | Comentario |
|---|---|---|---|
| P1, P2 (ruido fuera de banda) | 58–60 dB | 18–20 dB | Ambos cumplen ΔSNR ≥ 10 dB y energía útil ≥ 90 % |
| P3 (ruido blanco) | 6.2 dB | 6.4 dB | Solo se quita el ruido sobre la banda útil |
| P4 (impulsos) | 0.2 dB | 0.1 dB | La energía de los impulsos cae en la banda útil |
| P5 (superpuesto) | 0.0 dB | 5.9 dB con 72 % de energía útil | Compromiso ruido–distorsión |

Cálculo medio 8.4–9.5 ms por bloque de 16 ms; máximo 31.5 ms frente a 32 ms;
cero pérdidas y recortes; concordancia con Python ≥ 99.999 %.
Criterios fijados antes de las pruebas: [criterios_finales.json](../../metadatos/criterios_finales.json).

## 1.3. Qué es local y qué va en Git

| Grupo | Política |
|---|---|
| Código, tests, configuración, documentos y PDF | En Git |
| Sesiones completas (WAV, `sesion.json`, `metricas.csv`) | Locales en `resultados/` (ignorado) |
| Tablas y figuras que usa el artículo | En Git bajo [evidencias](evidencias/README.md) |
| CSV de P1–P5 y estímulos WAV | Regenerables con `python -m herramientas.preparar_casos` |
