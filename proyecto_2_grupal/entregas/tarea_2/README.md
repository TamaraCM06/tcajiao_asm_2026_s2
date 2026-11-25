# Tarea 2: modelado de sistemas (entrega 22 nov 2026, 23:59)

Documento LaTeX iterativo. Cada pregunta tiene su archivo en `secciones/` y lo que falta se
marca con `\pendiente{...}` (recuadro naranja en el PDF; buscar "Pendiente" antes de entregar).

```bash
./compilar.sh            # simulación + PDF  -> informe.pdf
./compilar.sh --solo-tex # solo LaTeX
./compilar.sh --limpiar
./empaquetar.sh          # salidas/tarea_2/Tarea2_ASM_Grupo1.zip: PDF + código + datos del commit entregado
```

Requiere `gcc`, `pdftoppm`, `pdflatex`, `bibtex`, `pgfplots`, `listings` y `standalone`. Los auxiliares y el ZIP quedan en `../../salidas/tarea_2/`. Entregada en el commit `6431b3b`; `empaquetar.sh` toma de ese commit los programas y datos.

| Ruta | Contenido |
|---|---|
| `informe.tex` | Preámbulo y orden de secciones |
| `secciones/p0_sistema.tex` | Descripción común del banco y convención de signo |
| `secciones/p1..p7_*.tex` | Una pregunta por archivo; 6 y 7 con los resultados del ensayo `escalon_02` |
| `secciones/anexo_*.tex` | Listados del micro y enlaces de video |
| `referencias.bib` | Bibliografía IEEE; agregar ahí las fuentes nuevas |
| `codigo/main_tarea2.c` | Lazo PID sin `delay()` para el ESP32 con ESP-IDF (pregunta 3) |
| `evidencias/simulacion_pid.c` | Simulación que usa `firmware/src/pid_controller.c`; genera CSV y métricas |
| `evidencias/generado/` | Salidas de la simulación (se versionan para compilar sin gcc) |
| `diagramas/` | Fuentes TikZ de la pregunta 4 (`estilo.tex` imita los diagramas Mermaid del avance 2 del Proyecto 1); `compilar.sh` genera los PNG |
| `figuras/` | Logo de portada y capturas de MATLAB del ensayo (pregunta 7) |

Los enlaces de YouTube se cambian en `informe.tex` (`\videoPlanta`, `\videoCaracterizacion`).
Toda evidencia simulada se etiqueta `[SIMULACIÓN]`; no mezclar con mediciones del banco.
