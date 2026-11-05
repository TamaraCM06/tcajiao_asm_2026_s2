"""Entrada de la herramienta de captura; ejecutar con el entorno Python del proyecto."""
from pathlib import Path
import sys

RAIZ_PROYECTO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(RAIZ_PROYECTO / "tarea1_grupo1"))

from pc.terminal import main

if __name__ == "__main__":
    try:
        main(RAIZ_PROYECTO)
    except (OSError, RuntimeError, ValueError, TimeoutError) as error:
        print(f"No se pudo completar la operacion: {error}", file=sys.stderr)
        sys.exit(1)
