"""Exporta los casos de defensa del JSON con el mismo generador del notebook."""
import argparse
from pathlib import Path

from tarea1_grupo1.src.datos import archivos
from tarea1_grupo1.src.datos.casos import CASOS_FINALES, CASOS_ADICIONALES

PROYECTO = Path(__file__).resolve().parents[1]


# Conserva byte a byte los CSV históricos y genera únicamente los registros nuevos.
def preparar_casos(raiz=PROYECTO, regenerar=False, audio=False):
    """Prepara entradas locales sin cambiar el JSON; los WAV de escucha son opcionales."""
    raiz = Path(raiz)
    tarea = raiz / "tarea1_grupo1"
    for identificador in (*CASOS_FINALES, *CASOS_ADICIONALES):
        archivos.asegurar_muestras_caso(identificador, tarea, regenerar=regenerar)
        if audio:
            datos = archivos.cargar_caso(identificador, tarea)
            archivos.exportar_senales(tarea / "pruebas" / identificador, datos)
    return tarea / "resultados/muestras"


# Prepara las entradas de evaluar P1--P5 desde cualquier directorio de ejecución.
def main():
    """Prepara las entradas de evaluar P1--P5 desde cualquier directorio de ejecución."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--regenerar", action="store_true", help="Actualizar los CSV locales desde el JSON; conserva los archivos caso_N históricos")
    parser.add_argument("--audio", action="store_true", help="Exportar también WAV sintéticos de preescucha")
    argumentos = parser.parse_args()
    print(preparar_casos(regenerar=argumentos.regenerar, audio=argumentos.audio))


if __name__ == "__main__":
    main()
