#!/usr/bin/env bash
# Arma el paquete de entrega de la Tarea 2: el PDF que pide el enunciado y, como respaldo,
# el codigo del microcontrolador y los datos y scripts del ensayo presentado.
# Uso: ./empaquetar.sh   (compila el informe antes con ./compilar.sh)
set -euo pipefail
cd "$(dirname "$0")"

P2=../..
NOMBRE=Tarea2_ASM_Grupo1
DESTINO=build/$NOMBRE
rm -rf "$DESTINO" "$NOMBRE.zip"
mkdir -p "$DESTINO"/{codigo,datos,analisis,captura}

[[ -f informe.pdf ]] || { echo "Falta informe.pdf: correr ./compilar.sh"; exit 1; }
cp informe.pdf "$DESTINO/$NOMBRE.pdf"

cp codigo/main_tarea2.c "$DESTINO/codigo/"
for f in pid_controller estimador_velocidad conversion_freno; do
    cp "$P2/firmware/src/$f.c" "$P2/firmware/include/$f.h" "$DESTINO/codigo/"
done
cp "$P2/firmware/include/hardware.h" "$DESTINO/codigo/"
cp "$P2/experimentos/datos/escalon_02.csv" "$P2/experimentos/datos/escalon_02.json" "$DESTINO/datos/"
cp "$P2/matlab_modelado/visualizar_ensayo.m" "$DESTINO/analisis/"
cp "$P2/experimentos/consola_banco.py" "$DESTINO/captura/"

cat > "$DESTINO/LEEME.txt" <<'EOF'
Tarea 2 - Modelado de sistemas (CE 1110). El documento evaluado es el PDF.
codigo/    Programa del ESP32 de la pregunta 3 (main_tarea2.c) y modulos que usa.
datos/     Ensayo al escalon presentado en la pregunta 7 (CSV y metadatos).
analisis/  visualizar_ensayo.m: graficas, ajuste de K y tau, respuesta al impulso.
captura/   consola_banco.py: consola serie que genero el CSV.
EOF

(cd build && zip -qr "../$NOMBRE.zip" "$NOMBRE")
echo "Listo: $(pwd)/$NOMBRE.zip"
unzip -l "$NOMBRE.zip" | tail -n +4 | head -n -2
