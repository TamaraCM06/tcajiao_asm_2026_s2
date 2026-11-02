"""Arma el ZIP de entrega del avance 2 a partir de los archivos versionados del repositorio.

Desde la raíz del repositorio: python proyecto_1_grupal/docs/avance2/empaquetar_entrega.py
En la raíz del ZIP quedan el informe y la guía de ejecución; debajo, proyecto_1_grupal/ con
los programas, igual que en el repositorio. Se omiten resultados generados y el informe de la
Tarea 1, que no forman parte de esta entrega.
"""

import argparse
import subprocess
import zipfile
from pathlib import Path

AVANCE = Path(__file__).resolve().parent
RAIZ_REPO = AVANCE.parents[2]
NOMBRE = "ASM_Semana12_Grupo1"
INCLUIDOS = (
    "proyecto_1_grupal/README.md",
    "proyecto_1_grupal/requirements.txt",
    "proyecto_1_grupal/prototipo.py",
    "proyecto_1_grupal/metadatos",
    "proyecto_1_grupal/tarea1_grupo1",
    "proyecto_1_grupal/firmware",
    "proyecto_1_grupal/herramientas",
    "proyecto_1_grupal/docs/avance2",
)
EXCLUIDOS = {"proyecto_1_grupal/tarea1_grupo1/informe.pdf"}


def archivos_del_repositorio():
    """Lista los archivos versionados o por versionar, respetando .gitignore."""
    salida = subprocess.run(
        ["git", "ls-files", "--cached", "--others", "--exclude-standard", "--", *INCLUIDOS],
        cwd=RAIZ_REPO, check=True, capture_output=True, text=True,
    ).stdout.splitlines()
    return sorted(r for r in set(salida) if r not in EXCLUIDOS and (RAIZ_REPO / r).is_file())


def main():
    """Escribe el ZIP con el informe y la guía en la raíz y el proyecto debajo."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--salida", type=Path, default=Path(f"{NOMBRE}.zip"),
                        help="Ruta del ZIP generado (predeterminado: en el directorio actual).")
    destino = parser.parse_args().salida.resolve()
    rutas = archivos_del_repositorio()
    with zipfile.ZipFile(destino, "w", zipfile.ZIP_DEFLATED) as paquete:
        paquete.write(AVANCE / "informe.pdf", f"{NOMBRE}/{NOMBRE}.pdf")
        paquete.write(AVANCE / "README_EJECUCION.txt", f"{NOMBRE}/README_EJECUCION.txt")
        for ruta in rutas:
            paquete.write(RAIZ_REPO / ruta, f"{NOMBRE}/{ruta}")
    print(f"{destino} ({len(rutas) + 2} archivos)")


if __name__ == "__main__":
    main()
