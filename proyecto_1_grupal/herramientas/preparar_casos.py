"""Exporta los casos de defensa del JSON con el mismo generador del notebook."""
import argparse
from pathlib import Path
import json

import numpy as np

from tarea1_grupo1.src.datos import archivos
from tarea1_grupo1.src.datos.casos import CASOS_FINALES, CASOS_ADICIONALES

PROYECTO = Path(__file__).resolve().parents[1]


# Conserva proporciones y SNR al escalar conjuntamente los tres componentes para PCM16.
def exportar_estimulo(raiz, identificador, datos):
    """Exporta audio local a 80 % de escala, sin recortar ni tocar WAV historicos."""
    carpeta = Path(raiz) / "resultados/estimulos" / identificador
    carpeta.mkdir(parents=True, exist_ok=True)
    pico = max(float(np.max(np.abs(datos[clave]))) for clave in ("clean", "noise", "noisy"))
    ganancia = .8 / pico if pico > 0 else 1.0
    for clave, nombre in (("clean", "01_referencia_limpia.wav"), ("noise", "02_ruido.wav"),
                         ("noisy", "03_entrada_contaminada.wav")):
        archivos.guardar_wav(carpeta / nombre, datos["fs"], datos[clave] * ganancia, verificar_rango=True)
    (carpeta / "estimulo.json").write_text(json.dumps(dict(caso=identificador,
        frecuencia_hz=datos["fs"], ganancia_comun=ganancia, muestras=len(datos["noisy"]),
        uso="Parlante hacia microfono; no es referencia sincronizada de la captura"), indent=2) + "\n", encoding="utf-8")
    return carpeta


# Conserva byte a byte los CSV históricos y genera únicamente los registros nuevos.
def preparar_casos(raiz=PROYECTO, regenerar=False, audio=False):
    """Prepara entradas locales sin cambiar el JSON; los WAV de escucha son opcionales."""
    raiz = Path(raiz)
    tarea = raiz / "tarea1_grupo1"
    for identificador in (*CASOS_FINALES, *CASOS_ADICIONALES):
        archivos.asegurar_muestras_caso(identificador, tarea, regenerar=regenerar)
        if audio:
            datos = archivos.cargar_caso(identificador, tarea)
            exportar_estimulo(raiz, identificador, datos)
    return tarea / "resultados/muestras"


# Prepara las entradas de evaluar P1--P5 desde cualquier directorio de ejecución.
def main():
    """Prepara las entradas de evaluar P1--P5 desde cualquier directorio de ejecución."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--regenerar", action="store_true", help="Actualizar los CSV locales desde el JSON; conserva los archivos caso_N históricos")
    parser.add_argument("--audio", action="store_true", help="Exportar WAV de estimulo sin recortes en resultados/estimulos")
    argumentos = parser.parse_args()
    print(preparar_casos(regenerar=argumentos.regenerar, audio=argumentos.audio))


if __name__ == "__main__":
    main()
