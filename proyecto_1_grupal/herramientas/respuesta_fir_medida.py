"""Compara la respuesta digital medida en WAV de ESP32 con los coeficientes FIR."""
import argparse
import csv
import hashlib
import json
from pathlib import Path
import sys

import numpy as np

PROYECTO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROYECTO / "firmware/esp32/tools"))
from pc.analisis_analogico import amplitudes_componentes
from pc.concordancia import leer_pcm
from tarea1_grupo1.src.datos.casos import resolver_caso

FRECUENCIA_MUESTREO_HZ = 16000
MUESTRAS_POR_BLOQUE = 1024
RETARDO_FIR_MUESTRAS = 37


# Evalúa |H| sin corregir ganancia ni fase a partir de la medición.
def respuesta_calculada(coeficientes, frecuencias):
    """Evalúa |H| sin corregir ganancia ni fase a partir de la medición."""
    indices_coeficientes = np.arange(len(coeficientes))
    return np.array([abs(np.sum(coeficientes * np.exp(
        -2j * np.pi * frecuencia / FRECUENCIA_MUESTREO_HZ * indices_coeficientes)))
        for frecuencia in frecuencias])


# Omite el arranque causal y estima ganancias y límites de detección PCM16 por bloque.
def medir_componentes(entrada, salida, frecuencias):
    """Omite el arranque causal y estima ganancias y límites de detección PCM16 por bloque."""
    if entrada.shape != salida.shape or entrada.ndim != 1:
        raise ValueError("Entrada y FIR deben tener igual longitud")
    ganancias, limites = [], []
    for inicio in range(2 * RETARDO_FIR_MUESTRAS,
                        len(entrada) - MUESTRAS_POR_BLOQUE + 1, MUESTRAS_POR_BLOQUE):
        intervalo = slice(inicio, inicio + MUESTRAS_POR_BLOQUE)
        antes, _, residuo_entrada = amplitudes_componentes(
            entrada[intervalo], FRECUENCIA_MUESTREO_HZ, frecuencias)
        despues, _, residuo_salida = amplitudes_componentes(
            salida[intervalo], FRECUENCIA_MUESTREO_HZ, frecuencias)
        minimo_entrada = max(2.0, 3 * residuo_entrada * np.sqrt(2 / MUESTRAS_POR_BLOQUE))
        minimo_salida = max(2.0, 3 * residuo_salida * np.sqrt(2 / MUESTRAS_POR_BLOQUE))
        if np.any(antes <= minimo_entrada):
            raise ValueError("Un tono de entrada está bajo el límite de detección; elegir tonos presentes")
        ganancias.append(despues / antes)
        limites.append(minimo_salida / antes)
    if len(ganancias) < 2:
        raise ValueError("Se requieren al menos dos bloques completos después del arranque")
    ganancias = np.asarray(ganancias)
    return (ganancias.mean(axis=0), ganancias.std(axis=0, ddof=1),
            np.mean(limites, axis=0), len(ganancias))


# Distingue una ganancia resuelta de una salida bajo el piso de cuantización.
def comparar(sesion, coeficientes, frecuencias):
    """Distingue una ganancia resuelta de una salida bajo el piso de cuantización."""
    medida, desviacion, limites, bloques = medir_componentes(
        leer_pcm(sesion / "entrada.wav").astype(float), leer_pcm(sesion / "fir.wav").astype(float), frecuencias)
    calculada = respuesta_calculada(coeficientes, frecuencias)
    filas = []
    for frecuencia, teorica, observada, dispersion, limite in zip(
            frecuencias, calculada, medida, desviacion, limites):
        resuelta = observada > limite
        filas.append(dict(frecuencia_hz=float(frecuencia), ganancia_calculada=float(teorica),
            ganancia_medida=float(observada), desviacion_medida=float(dispersion), bloques=bloques,
            limite_deteccion_ganancia=float(limite), medida_resuelta=bool(resuelta),
            calculada_db=float(20 * np.log10(max(teorica, np.finfo(float).tiny))),
            medida_db=float(20 * np.log10(observada)) if resuelta else None,
            diferencia_db=float(20 * np.log10(observada / teorica)) if resuelta and teorica > 0 else None,
            limite_superior_db=float(20 * np.log10(limite)) if not resuelta else None,
            observacion="ganancia digital resuelta" if resuelta else "salida bajo limite de deteccion PCM16"))
    return filas


# Reconoce también la fuente histórica caso_1 de las sesiones originales.
def frecuencias_de_sesion(sesion, raiz=PROYECTO):
    """Reconoce también la fuente histórica caso_1 de las sesiones originales."""
    metadatos = json.loads((sesion / "sesion.json").read_text(encoding="utf-8"))
    identificador = resolver_caso(Path(str(metadatos.get("fuente", "")).replace("\\", "/")).stem.replace("_muestras", ""))
    casos = json.loads((raiz / "tarea1_grupo1/metadatos/configuraciones.json").read_text(encoding="utf-8"))
    if identificador not in casos:
        raise ValueError("No se reconoce el caso de la sesión; pasar --frecuencias")
    datos = casos[identificador]
    if datos["tipo_senal"] not in ("tono", "multitono"):
        raise ValueError("El ajuste estacionario exige tonos; no aplicarlo a barridos o transitorios")
    frecuencias = list(datos["frecuencias_utiles_Hz"])
    if datos.get("tipo_ruido") == "tonal":
        frecuencias.append(datos["frecuencia_interferencia_Hz"])
    return sorted(set(frecuencias))


# Guarda curva calculada, tonos medidos y cotas del piso PCM16.
def guardar_figura(ruta, filas, coeficientes):
    """Guarda curva calculada, tonos medidos y cotas del piso PCM16."""
    from matplotlib.figure import Figure
    from matplotlib.backends.backend_agg import FigureCanvasAgg
    figura = Figure(figsize=(7, 3.5), layout="constrained")
    FigureCanvasAgg(figura)
    eje = figura.subplots()
    frecuencias = np.linspace(0, 8000, 4096)
    respuesta = respuesta_calculada(coeficientes, frecuencias)
    eje.plot(frecuencias, 20 * np.log10(np.maximum(respuesta, 1e-8)), label="FIR calculado")
    for resuelta, marcador, etiqueta in ((True, "o", "ESP32: WAV PCM16"), (False, "v", "Cota: piso PCM16")):
        seleccion = [fila for fila in filas if fila["medida_resuelta"] == resuelta]
        if seleccion:
            eje.scatter([fila["frecuencia_hz"] for fila in seleccion],
                        [fila["medida_db"] if resuelta else fila["limite_superior_db"] for fila in seleccion],
                        marker=marcador, label=etiqueta)
    eje.set(xlabel="Frecuencia [Hz]", ylabel="Ganancia [dB]", ylim=(-120, 5), xlim=(0, 8000))
    eje.grid(alpha=.3)
    eje.legend()
    figura.savefig(ruta, dpi=180)


# Exporta CSV, figura y procedencia sin alterar las muestras originales.
def main():
    """Exporta CSV, figura y procedencia sin alterar las muestras originales."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("sesion", type=Path)
    parser.add_argument("--salida", type=Path, default=PROYECTO / "resultados/entrega/fir")
    parser.add_argument("--frecuencias", type=float, nargs="+")
    argumentos = parser.parse_args()
    ruta_coeficientes = PROYECTO / "tarea1_grupo1/resultados/filtro_temporal/coeficientes_fir.csv"
    coeficientes = np.loadtxt(ruta_coeficientes, delimiter=",", skiprows=1)[:, 1]
    frecuencias = argumentos.frecuencias or frecuencias_de_sesion(argumentos.sesion)
    filas = comparar(argumentos.sesion, coeficientes, frecuencias)
    argumentos.salida.mkdir(parents=True, exist_ok=True)
    with (argumentos.salida / "respuesta_fir_medida.csv").open("w", newline="", encoding="utf-8") as archivo:
        escritor = csv.DictWriter(archivo, fieldnames=list(filas[0]))
        escritor.writeheader()
        escritor.writerows(filas)
    guardar_figura(argumentos.salida / "respuesta_fir_medida.png", filas, coeficientes)
    procedencia = dict(sesion=str(argumentos.sesion), dominio="digital ESP32, WAV PCM16 antes del DAC",
        metodo="ajuste conjunto de seno/coseno y DC; omitir 74 muestras iniciales, sin optimizar desfase",
        coeficientes_sha256=hashlib.sha256(ruta_coeficientes.read_bytes()).hexdigest(),
        archivos_sha256={nombre: hashlib.sha256((argumentos.sesion / nombre).read_bytes()).hexdigest()
                        for nombre in ("entrada.wav", "fir.wav")})
    (argumentos.salida / "procedencia.json").write_text(
        json.dumps(procedencia, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    for fila in filas:
        medida = f"{fila['medida_db']:.3f}" if fila["medida_resuelta"] else f"< {fila['limite_superior_db']:.2f}"
        print(f"{fila['frecuencia_hz']:7.0f} Hz | calculada {fila['calculada_db']:.3f} dB | medida {medida} dB")


if __name__ == "__main__":
    main()
