# Tarea 2: modelado de sistemas (entrega 22 nov 2026, 23:59)

Documento LaTeX iterativo. Cada pregunta tiene su archivo en `secciones/` y lo que falta se
marca con `\pendiente{...}` (recuadro naranja en el PDF; buscar "Pendiente" antes de entregar).

```bash
./compilar.sh            # simulación + PDF  -> informe.pdf
./compilar.sh --solo-tex # solo LaTeX
./compilar.sh --limpiar
```

Requiere `gcc`, `pdflatex`, `bibtex`, `pgfplots` y `listings`. Los auxiliares quedan en `build/`.

| Ruta | Contenido |
|---|---|
| `informe.tex` | Preámbulo y orden de secciones |
| `secciones/p0_sistema.tex` | Descripción común del banco y convención de signo |
| `secciones/p1..p7_*.tex` | Una pregunta por archivo (1, 2, 3 y 5 redactadas; 4, 6 y 7 pendientes) |
| `secciones/anexo_*.tex` | Listados del micro y enlaces de video |
| `referencias.bib` | Bibliografía IEEE; agregar ahí las fuentes nuevas |
| `codigo/main_tarea2.c` | Lazo PID sin `delay()` para la Pico (pregunta 3) |
| `evidencias/simulacion_pid.c` | Simulación que usa `firmware/src/pid_controller.c`; genera CSV y métricas |
| `evidencias/generado/` | Salidas de la simulación (se versionan para compilar sin gcc) |
| `figuras/` | Logo de portada, fotos y diagramas (preguntas 4 y 6) |

Toda evidencia simulada se etiqueta `[SIMULACIÓN]`; no mezclar con mediciones del banco.
