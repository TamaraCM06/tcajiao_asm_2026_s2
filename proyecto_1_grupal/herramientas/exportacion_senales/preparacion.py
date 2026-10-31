"""Lectura de los CSV del notebook y conversión al formato DAC, sin sintetizar señales."""

from dataclasses import dataclass
from pathlib import Path
import binascii

import numpy as np

from ...tarea1_grupo1.src.datos.archivos import cargar_caso, cargar_muestras_csv

FRECUENCIA_MUESTREO_HZ = 16000
MUESTRAS_POR_BLOQUE = 256
CANTIDAD_MAXIMA_MUESTRAS = 96000
RAIZ_TAREA = Path(__file__).resolve().parents[2] / "tarea1_grupo1"


@dataclass(frozen=True)
class SenalPreparada:
    """Describe el registro cuantizado que se incorporará al firmware."""

    identificador: str
    ruta_csv: Path
    frecuencia_muestreo_hz: int
    cantidad_muestras: int
    codigos_dac: bytes
    crc32: int
    cantidad_recortes: int


# Convierte las amplitudes del CSV sin agregar una nueva normalización.
def convertir_codigos_dac(muestras):
    """Cuantiza a 8 bits con redondeo positivo y devuelve bytes y número de recortes."""
    muestras = np.asarray(muestras, dtype=np.float64)
    if muestras.ndim != 1 or not np.all(np.isfinite(muestras)):
        raise ValueError("Las muestras deben ser un vector finito.")
    cantidad_recortes = int(np.count_nonzero((muestras < -1.0) | (muestras > 1.0)))
    muestras_limitadas = np.clip(muestras, -1.0, 1.0)
    codigos = np.floor(127.5 * (muestras_limitadas + 1.0) + 0.5).astype(np.uint8)
    return codigos.tobytes(), cantidad_recortes


# Reúne lectura, comprobaciones y cuantización de una señal ya generada.
def preparar_senal(*, caso=None, ruta_csv=None):
    """Carga un caso o CSV del notebook y valida tiempo, tamaño y formato para la placa."""
    if (caso is None) == (ruta_csv is None):
        raise ValueError("Selecciona exactamente un caso o un archivo CSV.")
    if caso is not None:
        datos = cargar_caso(caso, RAIZ_TAREA)
        frecuencia_muestreo_hz = datos["fs"]
        ruta_csv = RAIZ_TAREA / "resultados" / "muestras" / f"{caso}_muestras.csv"
        identificador = caso
    else:
        ruta_csv = Path(ruta_csv).resolve()
        datos = cargar_muestras_csv(ruta_csv)
        frecuencia_muestreo_hz = FRECUENCIA_MUESTREO_HZ
        identificador = ruta_csv.stem
    if frecuencia_muestreo_hz != FRECUENCIA_MUESTREO_HZ:
        raise ValueError("El reproductor inicial admite únicamente 16000 Hz.")
    cantidad_muestras = len(datos["noisy"])
    if caso is not None:
        cantidad_configurada = round(datos["configuracion"]["duracion_s"] * frecuencia_muestreo_hz)
        if cantidad_muestras != cantidad_configurada:
            raise ValueError("La longitud del CSV no coincide con la duración del JSON del caso.")
    if not MUESTRAS_POR_BLOQUE <= cantidad_muestras <= CANTIDAD_MAXIMA_MUESTRAS:
        raise ValueError("El registro debe tener entre 256 y 96000 muestras.")
    if cantidad_muestras % MUESTRAS_POR_BLOQUE:
        raise ValueError("La longitud debe ser múltiplo de 256 muestras.")
    if not np.allclose(np.diff(datos["t"]), 1.0 / FRECUENCIA_MUESTREO_HZ,
                       rtol=1e-7, atol=1e-10):
        raise ValueError("El tiempo del CSV no corresponde a un muestreo uniforme de 16000 Hz.")
    codigos_dac, cantidad_recortes = convertir_codigos_dac(datos["noisy"])
    return SenalPreparada(
        identificador=identificador,
        ruta_csv=Path(ruta_csv),
        frecuencia_muestreo_hz=FRECUENCIA_MUESTREO_HZ,
        cantidad_muestras=cantidad_muestras,
        codigos_dac=codigos_dac,
        crc32=binascii.crc32(codigos_dac) & 0xFFFFFFFF,
        cantidad_recortes=cantidad_recortes,
    )
