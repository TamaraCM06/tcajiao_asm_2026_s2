"""Exporta mezcla y referencia float32 y coeficientes existentes; no genera señales."""

import hashlib
import json
from pathlib import Path

import numpy as np

from ...tarea1_grupo1.src.datos.archivos import cargar_muestras_csv


# Guarda pares mezcla/referencia little-endian para lectura por bloques desde flash.
def exportar_datos_evaluacion(senal, caso, carpeta_datos):
    """Añade datos digitales sin cuantización DAC y metadatos reproducibles."""
    muestras = cargar_muestras_csv(senal.ruta_csv)
    pares = np.column_stack((muestras["noisy"], muestras["clean"])).astype("<f4")
    if not np.all(np.isfinite(pares)):
        raise ValueError("La mezcla o referencia excede el rango float32.")
    contenido = pares.tobytes()
    carpeta_datos = Path(carpeta_datos)
    destino = carpeta_datos / f"{caso}.f32"
    destino.write_bytes(contenido)
    metadatos = {
        "caso": caso, "formato": "float32 little-endian intercalado: mezcla, referencia",
        "muestras": len(pares), "frecuencia_muestreo_hz": senal.frecuencia_muestreo_hz,
        "bytes": len(contenido), "sha256": hashlib.sha256(contenido).hexdigest(),
        "crc32_dac": f"{senal.crc32:08X}",
        "origen": senal.ruta_csv.name,
        "uso_referencia": "Solo evaluación; no interviene en detección de ruido",
    }
    (carpeta_datos / f"{caso}_evaluacion.json").write_text(
        json.dumps(metadatos, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return destino


# Exporta los coeficientes que ya usa el notebook, sin volver a diseñar el FIR.
def exportar_coeficientes(ruta_csv, carpeta_datos):
    """Genera una constante C float32 con los 75 coeficientes del filtro temporal."""
    coeficientes = np.loadtxt(ruta_csv, delimiter=",", skiprows=1)[:, 1]
    if len(coeficientes) != 75 or not np.all(np.isfinite(coeficientes)):
        raise ValueError("Se requieren 75 coeficientes FIR finitos.")
    valores = ",\n    ".join(f"{float(valor):.9e}f" for valor in coeficientes.astype(np.float32))
    (Path(carpeta_datos) / "coeficientes_fir.c").write_text(
        '/* Generado desde coeficientes_fir.csv; no editar a mano. */\n'
        '#include "datos_digitales.h"\n'
        f'const float COEFICIENTES_FIR[75] = {{\n    {valores}\n}};\n', encoding="utf-8")
