#!/usr/bin/env bash
# Regenera las evidencias simuladas y compila informe.tex -> informe.pdf.
# Uso: ./compilar.sh          (todo)
#      ./compilar.sh --solo-tex  (no recompila la simulación)
#      ./compilar.sh --limpiar   (borra auxiliares y generados)
# Requiere gcc, pdftoppm (poppler) y una distribución TeX con pdflatex, bibtex,
# pgfplots, listings y standalone. El PID simulado se toma del commit entregado (ENTREGA),
# asi la Tarea 2 no cambia cuando evoluciona el firmware del proyecto.
set -euo pipefail
cd "$(dirname "$0")"

ENTREGA=6431b3b
AUX=../salidas/tarea_2
TAREA=$(pwd)
GEN=evidencias/generado
PID=$AUX/pid_entregado

if [[ "${1:-}" == "--limpiar" ]]; then
    rm -rf "$AUX" "$GEN"/*.csv "$GEN"/metricas.tex
    echo "Limpio."
    exit 0
fi

mkdir -p "$AUX" "$GEN"

if [[ "${1:-}" != "--solo-tex" ]]; then
    echo "==> Simulación del PID (evidencia pregunta 3)"
    mkdir -p "$PID"
    git show "$ENTREGA:proyecto_2_grupal/firmware/src/pid_controller.c" >"$PID/pid_controller.c"
    git show "$ENTREGA:proyecto_2_grupal/firmware/include/pid_controller.h" >"$PID/pid_controller.h"
    gcc -std=c11 -O2 -Wall -Wextra -Werror -I"$PID" \
        evidencias/simulacion_pid.c "$PID/pid_controller.c" -lm -o "$AUX/simulacion_pid"
    "$AUX/simulacion_pid" "$GEN"

    echo "==> Diagramas (pregunta 4): TikZ -> PNG a 300 ppp"
    for fuente in diagramas/[0-9]*.tex; do
        nombre=$(basename "$fuente" .tex)
        (cd diagramas && pdflatex -interaction=nonstopmode -halt-on-error \
            -output-directory="../$AUX" "$nombre.tex" >"../$AUX/$nombre.log") \
            || { tail -n 20 "$AUX/$nombre.log"; exit 1; }
        pdftoppm -r 300 -png -singlefile "$AUX/$nombre.pdf" "diagramas/$nombre"
    done
fi

echo "==> LaTeX"
latex() { pdflatex -interaction=nonstopmode -halt-on-error -output-directory="$AUX" informe.tex >"$AUX/pdflatex.log" \
    || { tail -n 40 "$AUX/pdflatex.log"; exit 1; }; }
latex
# bibtex no escribe en rutas con ../ (openout_any = p): se ejecuta dentro de AUX.
(cd "$AUX" && BIBINPUTS="$TAREA:" bibtex informe >bibtex.log) || { cat "$AUX/bibtex.log"; exit 1; }
latex
latex

cp "$AUX/informe.pdf" informe.pdf
grep -E "Warning.*(undefined|Citation)" "$AUX/informe.log" | sort -u || true
echo "==> informe.pdf listo"
