"""Pruebas de los scripts que resumen evidencias; los datos son sinteticos, no de la placa."""
import csv
from pathlib import Path
import sys
import wave

import numpy as np
from scipy.signal import lfilter

PROYECTO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(PROYECTO))
from herramientas.respuesta_fir_medida import comparar, respuesta_calculada
from herramientas.resumen_pruebas import leer_repeticiones, resumir

COEFICIENTES = np.loadtxt(PROYECTO / "tarea1_grupo1/resultados/filtro_temporal/coeficientes_fir.csv",
                          delimiter=",", skiprows=1)[:, 1]


def escribir_wav(ruta, muestras):
    with wave.open(str(ruta), "wb") as archivo:
        archivo.setnchannels(1)
        archivo.setsampwidth(2)
        archivo.setframerate(16000)
        archivo.writeframes(np.clip(np.round(muestras), -32768, 32767).astype("<i2").tobytes())


def test_respuesta_fir_medida_recupera_la_calculada(tmp_path):
    """Una salida filtrada con los mismos coeficientes debe medir la misma ganancia."""
    frecuencias = [440.0, 880.0, 1320.0, 4000.0]
    tiempo = np.arange(32000) / 16000
    entrada = sum(4000 * np.sin(2 * np.pi * f * tiempo + 0.3 * k) for k, f in enumerate(frecuencias))
    escribir_wav(tmp_path / "entrada.wav", entrada)
    escribir_wav(tmp_path / "fir.wav", lfilter(COEFICIENTES, [1], entrada))
    filas = comparar(tmp_path, COEFICIENTES, frecuencias)
    for fila in filas[:3]:
        assert abs(fila["diferencia_db"]) < 0.05
    # A 4 kHz el FIR rechaza mas de 60 dB; la medida queda limitada por la cuantizacion PCM16.
    assert filas[3]["medida_db"] is None or filas[3]["medida_db"] < -40
    assert respuesta_calculada(COEFICIENTES, [4000.0])[0] < 1e-3


def test_resumen_promedia_tres_repeticiones(tmp_path):
    """Calcula media y desviacion por prueba y metodo; ignora columnas no numericas."""
    for numero, snr in enumerate((20.0, 22.0, 24.0), start=1):
        carpeta = tmp_path / "P1" / f"rep_{numero}"
        carpeta.mkdir(parents=True)
        with (carpeta / "metricas.csv").open("w", newline="", encoding="utf-8") as archivo:
            escritor = csv.writer(archivo)
            escritor.writerow(["metodo", "snr_salida_db", "nota"])
            escritor.writerow(["fir", snr, "texto"])
    filas = resumir(leer_repeticiones(tmp_path))
    assert len(filas) == 1
    fila = filas[0]
    assert (fila["prueba"], fila["metodo"], fila["repeticiones"]) == ("P1", "fir", 3)
    assert fila["snr_salida_db_media"] == 22.0
    assert abs(fila["snr_salida_db_desviacion"] - 2.0) < 1e-12
    assert "nota_media" not in fila
