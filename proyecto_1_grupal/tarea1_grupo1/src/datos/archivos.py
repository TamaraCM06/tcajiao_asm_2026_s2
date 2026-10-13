"""Entrada y salida de configuraciones, muestras, audio y tablas."""

import csv
import json
import zipfile
from pathlib import Path

import numpy as np
from scipy.io import wavfile

# ---------------------------------------------------------------------------
# Lectura
# ---------------------------------------------------------------------------


def cargar_configuraciones(ruta):
    """Lee el JSON de casos sin modificarlo."""
    return json.loads(Path(ruta).read_text(encoding="utf-8"))


def cargar_caso(caso, raiz=None, incluir_configuracion=True):
    """Lee una vez el CSV y su configuración; no modifica los datos."""
    raiz = Path(raiz) if raiz is not None else Path(__file__).resolve().parents[2]
    if incluir_configuracion:
        configs = cargar_configuraciones(raiz / "metadatos/configuraciones.json")
        if caso not in configs:
            raise ValueError(f"Caso desconocido: {caso}. Opciones: {', '.join(configs)}")
    muestras = np.loadtxt(
        raiz / "resultados/muestras" / f"{caso}_muestras.csv", delimiter=",", skiprows=1, ndmin=2
    )
    if muestras.shape[1] != 4:
        raise ValueError("El CSV debe contener tiempo, limpia, ruido y contaminada.")
    if not np.all(np.isfinite(muestras)):
        raise ValueError("El CSV contiene NaN o infinito.")
    if not np.allclose(muestras[:, 1] + muestras[:, 2], muestras[:, 3], rtol=1e-12, atol=1e-14):
        raise ValueError("La señal contaminada no coincide con limpia + ruido.")
    datos = {
        "t": muestras[:, 0],
        "clean": muestras[:, 1],
        "noise": muestras[:, 2],
        "noisy": muestras[:, 3],
    }
    if incluir_configuracion:
        datos.update(fs=configs[caso]["fs_Hz"], configuracion=configs[caso])
    return datos


# ---------------------------------------------------------------------------
# Exportación
# ---------------------------------------------------------------------------


def pcm16(x):
    """Convierte a PCM de 16 bits para exportar WAV (igual que el generador del notebook)."""
    return np.int16(np.clip(x, -1, 1) * 32767)


def guardar_json(ruta, datos):
    ruta = Path(ruta)
    ruta.parent.mkdir(parents=True, exist_ok=True)
    ruta.write_text(json.dumps(datos, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def guardar_csv(ruta, filas):
    """Reemplaza una tabla completa; no acumula filas entre ejecuciones."""
    ruta = Path(ruta)
    ruta.parent.mkdir(parents=True, exist_ok=True)
    with ruta.open("w", newline="", encoding="utf-8") as f:
        escritor = csv.DictWriter(f, fieldnames=list(filas[0]), lineterminator="\n")
        escritor.writeheader()
        escritor.writerows(filas)


def guardar_wav(ruta, fs, muestras, verificar_rango=False):
    """Exporta PCM16 sin renormalizar. Opcionalmente rechaza saturación."""
    if verificar_rango and np.max(np.abs(muestras)) > 1:
        raise ValueError("La salida excede el rango PCM; revise su escala.")
    ruta = Path(ruta)
    ruta.parent.mkdir(parents=True, exist_ok=True)
    wavfile.write(ruta, fs, pcm16(muestras))


def guardar_muestras(ruta, datos):
    ruta = Path(ruta)
    ruta.parent.mkdir(parents=True, exist_ok=True)
    np.savetxt(
        ruta,
        np.column_stack([datos[k] for k in ("t", "clean", "noise", "noisy")]),
        delimiter=",",
        header="tiempo_s,limpia,ruido,contaminada",
        comments="",
    )


def exportar_senales(carpeta, datos):
    """Sobrescribe solo los tres WAV conocidos; conserva otros archivos."""
    nombres = [
        ("clean", "01_referencia_limpia.wav"),
        ("noise", "02_ruido.wav"),
        ("noisy", "03_entrada_contaminada.wav"),
    ]
    rutas = []
    for clave, nombre in nombres:
        ruta = Path(carpeta) / nombre
        guardar_wav(ruta, datos["fs"], datos[clave])
        rutas.append(ruta)
    return rutas


def exportar_prueba(carpeta, datos, metadata, nombre):
    """Exporta la prueba adicional y empaqueta únicamente sus archivos conocidos."""
    carpeta = Path(carpeta)
    rutas = exportar_senales(carpeta, datos)
    muestras = carpeta / "muestras_referencia.csv"
    guardar_muestras(muestras, datos)
    configuracion = carpeta / "metadatos_prueba.json"
    guardar_json(configuracion, metadata)
    leame = carpeta / "LEAME.txt"
    leame.write_text(
        "03_entrada_contaminada.wav: señal que se aplica al sistema.\n"
        "01_referencia_limpia.wav: referencia reservada para calcular métricas.\n"
        "02_ruido.wav: componente de ruido aislada.\n",
        encoding="utf-8",
    )
    zip_path = carpeta.parent / f"{nombre}.zip"
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as z:
        for ruta in [*rutas, muestras, configuracion, leame]:
            z.write(ruta, arcname=ruta.name)
    return zip_path
