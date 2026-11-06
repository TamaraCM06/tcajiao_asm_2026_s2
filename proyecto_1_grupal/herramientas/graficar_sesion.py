"""Figuras de los WAV de placa para P1--P5; no vuelve a ejecutar los filtros."""
import argparse
import csv
from pathlib import Path
import sys

import numpy as np

PROYECTO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROYECTO / "firmware/esp32/tools"))
from pc.analisis_analogico import amplitudes_componentes
from pc.archivos import abrir_sesion
from pc.concordancia import leer_pcm


# Usa tonos presentes para medir ganancia y distinguir el piso de cuantización de una atenuación resuelta.
def medir_tonos(rutas, frecuencias):
    """Devuelve atenuación digital por tono; no atribuye toda la energía al ruido."""
    entrada = rutas["entrada"][74:]
    amplitudes_entrada, _, residuo = amplitudes_componentes(entrada, 16000, frecuencias)
    limite_entrada = max(2, 3 * residuo * np.sqrt(2 / len(entrada)))
    if np.any(amplitudes_entrada <= limite_entrada):
        raise ValueError("Un tono solicitado no está resuelto en la entrada; usar frecuencias realmente presentes")
    filas = []
    for metodo in ("fir", "espectral"):
        salida = rutas[metodo][74:]
        amplitudes_salida, _, residuo = amplitudes_componentes(salida, 16000, frecuencias)
        limite_salida = max(2, 3 * residuo * np.sqrt(2 / len(salida)))
        for frecuencia, antes, despues in zip(frecuencias, amplitudes_entrada, amplitudes_salida):
            resuelta = despues > limite_salida
            filas.append(dict(metodo=metodo, frecuencia_hz=float(frecuencia),
                amplitud_entrada_pcm=float(antes), amplitud_salida_pcm=float(despues),
                atenuacion_db=float(20 * np.log10(antes / despues)) if resuelta else None,
                atenuacion_minima_db=float(20 * np.log10(antes / limite_salida)) if not resuelta else None,
                salida_resuelta=bool(resuelta)))
    return filas


# Dibuja los resultados ya calculados por la ESP32 con una escala común.
def graficar(sesion, destino, inicio_s=0, duracion_s=None, tonos=None):
    """Exporta forma temporal y espectros digitales; no mide latencia física ni antialias analógico."""
    from matplotlib.figure import Figure
    from matplotlib.backends.backend_agg import FigureCanvasAgg
    sesion, metadatos = abrir_sesion(sesion)
    rutas = {nombre: leer_pcm(sesion / f"{nombre}.wav").astype(float)
             for nombre in ("entrada", "fir", "espectral")}
    cantidad = len(rutas["entrada"])
    duracion_s = cantidad / 16000 - inicio_s if duracion_s is None else duracion_s
    if not np.isfinite(inicio_s) or not np.isfinite(duracion_s) or inicio_s < 0 or duracion_s <= 0:
        raise ValueError("Inicio y duración deben definir un intervalo positivo y finito")
    inicio = int(inicio_s * 16000)
    final = min(cantidad, inicio + int(duracion_s * 16000))
    if final - inicio < 16:
        raise ValueError("El intervalo elegido no contiene suficientes muestras")
    destino = Path(destino)
    destino.mkdir(parents=True, exist_ok=True)
    figura = Figure(figsize=(10, 7), layout="constrained")
    FigureCanvasAgg(figura)
    ejes = figura.subplots(3, 2, sharex="col")
    escala = float(metadatos["escala"]) / 32768
    maximo = max(np.max(np.abs(muestras)) for muestras in rutas.values()) * escala
    for posicion, (nombre, muestras) in enumerate(rutas.items()):
        tiempo = np.arange(inicio, final) / 16000
        ejes[posicion, 0].plot(tiempo, muestras[inicio:final] * escala, linewidth=.6)
        ejes[posicion, 0].set(ylabel=nombre, ylim=(-max(maximo, .001), max(maximo, .001)))
        ventana = np.hanning(cantidad)
        amplitud = 2 * np.abs(np.fft.rfft(muestras * escala * ventana)) / ventana.sum()
        frecuencias = np.fft.rfftfreq(cantidad, 1 / 16000)
        ejes[posicion, 1].plot(frecuencias, 20 * np.log10(np.maximum(amplitud, 1e-8)), linewidth=.6)
        ejes[posicion, 1].set(ylim=(-120, 20), xlim=(0, 8000), ylabel="dB re 1 unidad")
        for eje in ejes[posicion]:
            eje.grid(alpha=.25)
    ejes[0, 0].set_title("Forma temporal; retardo causal conservado")
    ejes[0, 1].set_title("Espectro Hann del registro completo")
    ejes[-1, 0].set_xlabel("Tiempo [s]")
    ejes[-1, 1].set_xlabel("Frecuencia [Hz]")
    figura.suptitle(f"{sesion.name}: WAV PCM16 antes del DAC; no mide latencia física")
    figura.savefig(destino / "senales_espectros.png", dpi=160)
    if tonos:
        filas = medir_tonos(rutas, tonos)
        with (destino / "atenuacion_tonos.csv").open("w", newline="", encoding="utf-8") as archivo:
            escritor = csv.DictWriter(archivo, fieldnames=list(filas[0]))
            escritor.writeheader()
            escritor.writerows(filas)
    return destino / "senales_espectros.png"


# Prepara las figuras y, solo si se pide, la atenuación de los tonos conocidos de P1.
def main():
    """Todas las salidas predeterminadas quedan en resultados, ignorado por Git."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("sesion", type=Path)
    parser.add_argument("--salida", type=Path)
    parser.add_argument("--inicio", type=float, default=0)
    parser.add_argument("--duracion", type=float)
    parser.add_argument("--tonos", type=float, nargs="+")
    argumentos = parser.parse_args()
    destino = argumentos.salida or PROYECTO / "resultados/entrega" / argumentos.sesion.name
    print(graficar(argumentos.sesion, destino, argumentos.inicio, argumentos.duracion, argumentos.tonos))


if __name__ == "__main__":
    main()
