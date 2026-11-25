#!/usr/bin/env bash
# Arma el paquete de entrega de la Tarea 2: el PDF que pide el enunciado, los programas del
# microcontrolador y los archivos del ensayo de la pregunta 7.
# Uso: ./compilar.sh && ./empaquetar.sh
# Los programas y datos se extraen del commit entregado (ENTREGA), no del firmware actual.
set -euo pipefail
cd "$(dirname "$0")"

ENTREGA=6431b3b
SALIDA=../salidas/tarea_2
NOMBRE=Tarea2_ASM_Grupo1
RAIZ=$SALIDA/$NOMBRE
MICRO=$RAIZ/programas_microcontrolador
P2=$SALIDA/fuentes_entrega/proyecto_2_grupal
rm -rf "$RAIZ" "$SALIDA/$NOMBRE.zip" "$SALIDA/fuentes_entrega"
mkdir -p "$SALIDA/fuentes_entrega"
git -C "$(git rev-parse --show-toplevel)" archive "$ENTREGA" proyecto_2_grupal/firmware proyecto_2_grupal/experimentos proyecto_2_grupal/matlab_modelado \
    | tar -x -C "$SALIDA/fuentes_entrega"
mkdir -p "$MICRO/pregunta3_pid" "$MICRO/registrador_banco" "$RAIZ/pregunta7"

[[ -f informe.pdf ]] || { echo "Falta informe.pdf: correr ./compilar.sh"; exit 1; }
cp informe.pdf "$RAIZ/$NOMBRE.pdf"

# Pregunta 3: programa del lazo PID y los modulos que usa.
cp codigo/main_tarea2.c "$MICRO/pregunta3_pid/"
for f in pid_controller estimador_velocidad conversion_freno; do
    cp "$P2/firmware/src/$f.c" "$P2/firmware/include/$f.h" "$MICRO/pregunta3_pid/"
done
cp "$P2/firmware/include/hardware.h" "$MICRO/pregunta3_pid/"

# Preguntas 6 y 7: firmware del banco que ejecuto el ensayo, con la configuracion usada.
cp -r "$P2/firmware/src" "$P2/firmware/include" "$P2/firmware/CMakeLists.txt" \
      "$P2/firmware/sdkconfig.defaults" "$MICRO/registrador_banco/"
rm -f "$MICRO"/registrador_banco/{src,include}/README.md \
      "$MICRO"/registrador_banco/src/pid_controller.c "$MICRO"/registrador_banco/include/pid_controller.h  # no los compila el banco
cp codigo/sdkconfig.ensayo "$MICRO/registrador_banco/"

# Pregunta 7: datos del ensayo, analisis en MATLAB y consola que genero el CSV.
cp "$P2/experimentos/datos/escalon_02.csv" "$P2/experimentos/datos/escalon_02.json" \
   "$P2/matlab_modelado/visualizar_ensayo.m" "$P2/experimentos/consola_banco.py" "$RAIZ/pregunta7/"

cat > "$RAIZ/README.md" <<'EOF'
# Tarea 2: Modelado de sistemas (CE 1110)

El documento evaluado es `Tarea2_ASM_Grupo1.pdf`. Este comprimido agrega los programas que el
PDF referencia en el Anexo A.

| Carpeta | Contenido | Pregunta |
|---|---|---|
| `programas_microcontrolador/pregunta3_pid/` | Lazo PID sin `delay()` para el ESP32 (`main_tarea2.c`) y los módulos que usa | 3 |
| `programas_microcontrolador/registrador_banco/` | Firmware del banco (ESP-IDF 5.5) que ejecutó el ensayo: comandos FRENO, MOTOR, ENSAYO; `sdkconfig.ensayo` con pines y calibración | 6 y 7 |
| `pregunta7/` | `escalon_02.csv` y `.json` (ensayo presentado), `visualizar_ensayo.m` (MATLAB) y `consola_banco.py` (captura) | 7 |

## Videos (YouTube, no listados)

- Pregunta 6, planta en lazo abierto: https://youtu.be/B1e7-cnYzO4
- Pregunta 7, escalón, CSV, MATLAB y respuesta al impulso: https://youtube.com/shorts/y-FDs2-BfVk

## Reproducir

- Firmware: en `registrador_banco/`, `idf.py menuconfig` con los valores de `sdkconfig.ensayo`,
  luego `idf.py build flash`.
- Ensayo: `python consola_banco.py`, y en el prompt `CONFIG 20 10000 100`, `FRENO 120`,
  `ENSAYO 60 180 300`.
- Análisis: en MATLAB, `visualizar_ensayo` y elegir `escalon_02.csv`.
EOF

(cd "$SALIDA" && zip -qr "$NOMBRE.zip" "$NOMBRE")
echo "Listo: $SALIDA/$NOMBRE.zip"
unzip -l "$SALIDA/$NOMBRE.zip" | awk 'NR>3 {print $4}' | grep -v '^$' | grep -v '/$'
