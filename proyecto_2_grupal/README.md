# 1. Proyecto Grupal 2: banco de frenado

CE 1110, II semestre 2026. Disco movido por un motor CD, frenado por un servo MG90S con goma y
medido con un *LM393 Motor Speed Measuring Sensor Module* (horquilla óptica) sobre un disco de
20 ranuras; un ESP32 registra y (próximamente) controla con PID la
velocidad durante el frenado. Entrega y defensa: **2 de diciembre de 2026**, 23:50.
[Enunciado](ENUNCIADO.md).

| Documento | Para qué |
|---|---|
| [Ejecución, capturas y gráficas](docs/04_capturas_y_graficas.md) | Comandos, resumen del CSV, PNG automático, valores efectivos y pruebas |
| [Conexiones](docs/02_conexiones.md) | Componentes y pinout |
| [Ensayos y modelo](docs/05_ensayos_y_modelo.md) | Campaña de identificación (`banco.py pid`) y modelo de la planta (`banco.py modelo`) |
| [Flujo](docs/03_flujo.md) | Cómo funciona: bloques, firmware, ensayo y datos |
| [Capturas originales y figuras](datos/) | CSV, JSON y PNG de los tres ensayos recientes |

~~~text
banco.py        entrada única: preparar, compilar, flashear, consola, graficar, pid, modelo, monitor, pruebas, limpiar
firmware/       ESP-IDF 5.5.5 (src, include, tests en PC)
herramientas/   consola, campaña PID, análisis CSV, gráficas Python, modelo_planta.m y visualizar_ensayo.m
datos/          capturas de la consola (CSV + JSON + PNG) y campañas en datos/<campaña>/ con su modelo
tarea_2/        Tarea 2 entregada (informe, código y su enunciado), independiente del resto
salidas/        todo lo generado (ignorado por git)
~~~

## 1.1. Estado

Hecho: banco construido, registro a lazo abierto con ensayo automático, consola con ajustes
por ensayo, velocidad promediada por vuelta, caracterización por escalón (Tarea 2) y PID
discreto probado en simulación. El [escalón histórico](tarea_2/evidencias/banco_anterior/escalon_02.csv)
es del banco anterior (TCRT5000, 10 marcas):
sirve como referencia de la Tarea 2, no para identificar el banco actual.

Pendiente para la entrega:

- [ ] Identificación: campaña (`banco.py pid`) y modelo (`banco.py modelo`) listos y probados en simulación; falta correrlos en el banco
- [ ] PID en el firmware: referencia decreciente, anti-windup y registro de referencia, error y mando
- [ ] Sintonía de Kp, Ki y Kd con gráficas intermedias
- [ ] Comparación final: lazo abierto vs. PID, 2 velocidades × 3 repeticiones (≥ 12 ensayos), IAE/RMSE
- [ ] Artículo IEEE en LaTeX (≤ 4 páginas, abstract en inglés)
- [ ] Integrar a master con tag de entrega
