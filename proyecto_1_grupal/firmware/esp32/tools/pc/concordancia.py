"""Validacion independiente en PC de los resultados calculados por la ESP32."""
import csv
import hashlib
from pathlib import Path
import wave

import numpy as np
from scipy.signal import lfilter

from .archivos import abrir_sesion, cuantizar, guardar_json


def concordancia_modelo(medida, teorica):
    """Define 100*max(0,1-NRMSE); es concordancia de muestras, no exactitud de clasificacion."""
    medida, teorica = np.asarray(medida, dtype=float), np.asarray(teorica, dtype=float)
    if medida.shape != teorica.shape or medida.size == 0 or not np.all(np.isfinite(medida)) or not np.all(np.isfinite(teorica)):
        raise ValueError("La comparacion requiere muestras finitas de igual forma")
    error_rms = float(np.sqrt(np.mean((medida - teorica) ** 2)))
    rms_teorico = float(np.sqrt(np.mean(teorica ** 2)))
    if rms_teorico == 0:
        return dict(concordancia_modelo_python_pct=100.0 if error_rms == 0 else None,
                    nrmse_modelo_python=0.0 if error_rms == 0 else None, error_rms_modelo=error_rms)
    error_normalizado = error_rms / rms_teorico
    return dict(concordancia_modelo_python_pct=100 * max(0.0, 1 - error_normalizado),
                nrmse_modelo_python=error_normalizado, error_rms_modelo=error_rms)


def leer_pcm(ruta):
    """Lee un WAV mono PCM16 sin normalizarlo ni alterar sus bytes."""
    with wave.open(str(ruta), "rb") as archivo:
        if (archivo.getnchannels(), archivo.getsampwidth(), archivo.getframerate()) != (1, 2, 16000):
            raise ValueError("Se requiere WAV mono PCM16 a 16000 Hz")
        return np.frombuffer(archivo.readframes(archivo.getnframes()), dtype="<i2").copy()


def validar_sesion(ruta, raiz_proyecto):
    """Compara ESP32 con los mismos modelos del notebook sobre la entrada PCM16 guardada."""
    from src.filtros.filtrado_espectral import filtrar_senal
    ruta, metadatos = abrir_sesion(ruta)
    raiz_proyecto = Path(raiz_proyecto)
    escala = np.float32(metadatos["escala"])
    entrada = leer_pcm(ruta / "entrada.wav").astype(np.float32) * (escala / np.float32(32768))
    ruta_coeficientes = raiz_proyecto / "tarea1_grupo1/resultados/filtro_temporal/coeficientes_fir.csv"
    coeficientes = np.loadtxt(ruta_coeficientes, delimiter=",", skiprows=1)[:, 1].astype(np.float32)
    temporal = lfilter(coeficientes, [1], entrada.astype(float))
    espectral = filtrar_senal(entrada.astype(float), 16000, tam_bloque=1024,
        frecuencia_minima=metadatos["minimo_hz"], ancho_hz=metadatos["ancho_hz"],
        factor=metadatos["factor"], umbral_relativo=metadatos["umbral"])
    espectral = np.r_[np.zeros(37), espectral[:-37]]
    resultados = {}
    for nombre, teorica in (("fir", temporal), ("espectral", espectral)):
        teorica_pcm, recortes = cuantizar(teorica, escala)
        medida_pcm = leer_pcm(ruta / f"{nombre}.wav")
        medidas = concordancia_modelo(medida_pcm, teorica_pcm)
        medidas.update(error_maximo_pcm=int(np.max(np.abs(medida_pcm.astype(int) - teorica_pcm.astype(int)))),
                       recortes_modelo_python=recortes, muestras_comparadas=len(medida_pcm))
        resultados[nombre] = medidas
    validacion = dict(origen="validacion_independiente_PC", formula="100*max(0,1-RMSE/RMS_teorico)",
        significado="Concordancia de implementacion; no mide eliminacion de ruido ni el circuito analogico",
        dominio="WAV PCM16; misma escala y retardo causal de 37 muestras, sin ajustar ganancia o fase",
        coeficientes_sha256=hashlib.sha256(ruta_coeficientes.read_bytes()).hexdigest(), resultados=resultados)
    guardar_json(ruta / "validacion_python.json", validacion)
    with (ruta / "validacion_python.csv").open("w", newline="", encoding="utf-8") as archivo:
        filas = [dict(metodo=nombre, **resultado) for nombre, resultado in resultados.items()]
        escritor = csv.DictWriter(archivo, fieldnames=list(filas[0]))
        escritor.writeheader()
        escritor.writerows(filas)
    # Las medidas de placa permanecen identificadas; solo se agregan columnas de validacion PC.
    with (ruta / "metricas.csv").open(encoding="utf-8", newline="") as archivo:
        filas_metricas = list(csv.DictReader(archivo))
    for fila in filas_metricas:
        fila.update(resultados[fila["metodo"]])
    if filas_metricas:
        with (ruta / "metricas.csv").open("w", encoding="utf-8", newline="") as archivo:
            escritor = csv.DictWriter(archivo, fieldnames=list(filas_metricas[0]))
            escritor.writeheader()
            escritor.writerows(filas_metricas)
    metadatos["validacion_python"] = validacion
    guardar_json(ruta / "sesion.json", metadatos)
    return resultados
