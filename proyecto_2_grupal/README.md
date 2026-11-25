# Proyecto Grupal 2: banco de frenado

CE 1110, II semestre 2026. Disco movido por un motor CD, frenado por un servo MG90S con goma y
medido con un sensor óptico de 20 marcas; un ESP32 registra y (próximamente) controla con PID la
velocidad durante el frenado. Entrega y defensa: **2 de diciembre de 2026**, 23:50.
[Enunciado](entregas/enunciados/ENUNCIADO_PROYECTO_2.md).

| Documento | Para qué |
|---|---|
| [Ejecución](docs/01_ejecucion.md) | Instalar, programar, consola, ensayos, calibración, análisis y pruebas |
| [Conexiones](docs/02_conexiones.md) | Cableado y calibración vigente |
| [Flujo](docs/03_flujo.md) | Cómo funciona: bloques, firmware, ensayo y datos |
| [Capturas](docs/capturas/) | Fotos y capturas de pantalla |

```text
banco.py        entrada única: preparar, compilar, flashear, consola, monitor, pruebas, limpiar
firmware/       ESP-IDF 5.5.5 (src, include, tests en PC)
herramientas/   consola.py y visualizar_ensayo.m
datos/          capturas crudas (CSV + JSON), no se editan
entregas/       enunciados y Tarea 2 entregada
salidas/        todo lo generado (ignorado por git)
```

## Estado

Hecho: banco construido, registro a lazo abierto con ensayo automático, calibración del servo
desde la consola, velocidad promediada por vuelta, caracterización por escalón (Tarea 2) y PID
discreto probado en simulación.

Pendiente para la entrega:

- [ ] Identificación: ensayos a varios ángulos y dos velocidades; validar con ensayos no usados en el ajuste
- [ ] PID en el firmware: referencia decreciente, anti-windup y registro de referencia, error y mando
- [ ] Sintonía de Kp, Ki y Kd con gráficas intermedias
- [ ] Comparación final: lazo abierto vs. PID, 2 velocidades × 3 repeticiones (≥ 12 ensayos), IAE/RMSE
- [ ] Artículo IEEE en LaTeX (≤ 4 páginas, abstract en inglés)
- [ ] Integrar a `master` con tag de entrega
