"""Exporta únicamente los coeficientes FIR del modelo al componente utilizado por ESP32."""
import argparse
from pathlib import Path

import numpy as np

PROYECTO = Path(__file__).resolve().parents[1]
ORIGEN = PROYECTO / "tarea1_grupo1/resultados/filtro_temporal/coeficientes_fir.csv"
DESTINO = PROYECTO / "firmware/esp32/components/filtros_digitales/coeficientes_fir.c"


# Conserva exactamente la conversión float32 del exportador anterior sin generar señales flash.
def exportar_coeficientes(origen=ORIGEN, destino=DESTINO):
    """Escribe los 75 coeficientes existentes; no rediseña el filtro ni cambia su escala."""
    coeficientes = np.loadtxt(origen, delimiter=",", skiprows=1)[:, 1]
    if len(coeficientes) != 75 or not np.all(np.isfinite(coeficientes)):
        raise ValueError("Se requieren 75 coeficientes FIR finitos")
    valores = ",\n    ".join(f"{float(valor):.9e}f" for valor in coeficientes.astype(np.float32))
    destino = Path(destino)
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_text('/* Generado desde coeficientes_fir.csv; no editar a mano. */\n'
                       '#include "coeficientes_fir.h"\n'
                       f'const float COEFICIENTES_FIR[75] = {{\n    {valores}\n}};\n', encoding="utf-8")
    return destino


# Permite actualizar el FIR de firmware únicamente cuando cambie su diseño fuente.
def main():
    """La salida puede dirigirse a un archivo temporal para verificarla sin modificar firmware."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--origen", type=Path, default=ORIGEN)
    parser.add_argument("--salida", type=Path, default=DESTINO)
    argumentos = parser.parse_args()
    print(exportar_coeficientes(argumentos.origen, argumentos.salida))


if __name__ == "__main__":
    main()
