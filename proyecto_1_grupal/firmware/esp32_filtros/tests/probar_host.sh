#!/usr/bin/env bash
set -euo pipefail
cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.."
carpeta_prueba=$(mktemp -d /tmp/audio-vivo.XXXXXX)
trap 'rm -f -- "$carpeta_prueba/test_audio"; rmdir -- "$carpeta_prueba"' EXIT
gcc -std=c11 -O2 -Wall -Wextra -Werror \
  -Icomponents/audio_vivo/include -I../esp32/components/filtros_digitales/include -I../receptor \
  components/audio_vivo/audio_vivo.c components/audio_vivo/trama_audio.c \
  ../esp32/components/filtros_digitales/filtro_fir.c \
  ../esp32/components/filtros_digitales/filtro_espectral.c \
  ../esp32/components/filtros_digitales/fft_radix2.c \
  ../receptor/nodo1_metodos.c tests/test_audio.c -lm -o "$carpeta_prueba/test_audio"
"$carpeta_prueba/test_audio"
