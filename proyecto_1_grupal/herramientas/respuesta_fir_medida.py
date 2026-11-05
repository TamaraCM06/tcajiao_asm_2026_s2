"""Respuesta del FIR medida en una sesion de la ESP32 frente a la calculada con sus coeficientes.

Uso desde proyecto_1_grupal/:
    python -m herramientas.respuesta_fir_medida resultados/sesiones/<id> --salida docs/final/evidencias/fir
Lee entrada.wav y fir.wav de la sesion; no reprocesa la senal en la PC.
"""
import argparse
import csv
import json
from pathlib import Path
import sys
import wave

import numpy as np

PROYECTO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROYECTO / "firmware/esp32/tools"))
from pc.analisis_analogico import amplitudes_componentes  # noqa: E402

FS = 16000
BLOQUE = 1024
RETARDO_FIR = 37


def leer_wav(ruta):
    """Devuelve las muestras PCM16 como flotantes; la escala comun se cancela en la razon."""
    with wave.open(str(ruta), "rb") as archivo:
        if (archivo.getnchannels(), archivo.getsampwidth(), archivo.getframerate()) != (1, 2, FS):
            raise ValueError(f"{ruta} debe ser WAV mono PCM16 a {FS} Hz")
        return np.frombuffer(archivo.readframes(archivo.getnframes()), dtype="<i2").astype(float)


def respuesta_calculada(coeficientes, frecuencias):
    """Evalua |H(e^jw)| del FIR en las frecuencias pedidas."""
    n = np.arange(len(coeficientes))
    return np.array([abs(np.sum(coeficientes * np.exp(-2j * np.pi * f / FS * n))) for f in frecuencias])


def respuesta_medida(entrada, salida, frecuencias):
    """Ajusta cada tono por bloques en entrada y salida; devuelve media y desviacion de la ganancia."""
    entrada = entrada[2 * RETARDO_FIR:]
    salida = salida[2 * RETARDO_FIR:]
    ganancias = []
    for inicio in range(0, min(len(entrada), len(salida)) - BLOQUE + 1, BLOQUE):
        antes, _, _ = amplitudes_componentes(entrada[inicio:inicio + BLOQUE], FS, frecuencias)
        despues, _, _ = amplitudes_componentes(salida[inicio:inicio + BLOQUE], FS, frecuencias)
        ganancias.append(np.where(antes > 0, despues / np.where(antes > 0, antes, 1), np.nan))
    if not ganancias:
        raise ValueError("La sesion no tiene muestras suficientes")
    ganancias = np.asarray(ganancias)
    return np.nanmean(ganancias, axis=0), np.nanstd(ganancias, axis=0)


def comparar(sesion, coeficientes, frecuencias):
    """Arma una fila por tono con ganancia calculada, medida y diferencia en dB."""
    medida, desviacion = respuesta_medida(leer_wav(sesion / "entrada.wav"), leer_wav(sesion / "fir.wav"), frecuencias)
    calculada = respuesta_calculada(coeficientes, frecuencias)
    filas = []
    for f, h, m, d in zip(frecuencias, calculada, medida, desviacion):
        filas.append(dict(frecuencia_hz=float(f), ganancia_calculada=float(h), ganancia_medida=float(m),
                          desviacion_medida=float(d), calculada_db=float(20 * np.log10(h)),
                          medida_db=float(20 * np.log10(m)) if m > 0 else None,
                          diferencia_db=float(20 * np.log10(m / h)) if m > 0 else None))
    return filas


def frecuencias_de_sesion(sesion, raiz=PROYECTO):
    """Usa los tonos utiles y la interferencia del caso guardado en la sesion, si existe."""
    metadatos = json.loads((sesion / "sesion.json").read_text(encoding="utf-8"))
    caso = Path(str(metadatos.get("fuente", ""))).stem.replace("_muestras", "")
    casos = json.loads((raiz / "tarea1_grupo1/metadatos/configuraciones.json").read_text(encoding="utf-8"))
    if caso not in casos:
        raise ValueError("No se reconoce el caso de la sesion; pasar --frecuencias")
    datos = casos[caso]
    frecuencias = list(datos["frecuencias_utiles_Hz"])
    if datos.get("tipo_ruido") == "tonal":
        frecuencias.append(datos["frecuencia_interferencia_Hz"])
    return frecuencias


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("sesion", type=Path)
    parser.add_argument("--salida", type=Path, default=PROYECTO / "docs/final/evidencias/fir")
    parser.add_argument("--frecuencias", type=float, nargs="+")
    argumentos = parser.parse_args()
    coeficientes = np.loadtxt(PROYECTO / "tarea1_grupo1/resultados/filtro_temporal/coeficientes_fir.csv",
                              delimiter=",", skiprows=1)[:, 1]
    frecuencias = argumentos.frecuencias or frecuencias_de_sesion(argumentos.sesion)
    filas = comparar(argumentos.sesion, coeficientes, frecuencias)
    argumentos.salida.mkdir(parents=True, exist_ok=True)
    with (argumentos.salida / "respuesta_fir_medida.csv").open("w", newline="", encoding="utf-8") as archivo:
        escritor = csv.DictWriter(archivo, fieldnames=list(filas[0]))
        escritor.writeheader()
        escritor.writerows(filas)
    for fila in filas:
        medida = "n/d" if fila["medida_db"] is None else f"{fila['medida_db']:8.2f}"
        print(f"{fila['frecuencia_hz']:7.0f} Hz | calculada {fila['calculada_db']:8.2f} dB | medida {medida} dB")


if __name__ == "__main__":
    main()
