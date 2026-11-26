"""Grafica las muestras originales del CSV y exporta un PNG sin requerir interfaz grafica."""
import argparse
import importlib.util
import json
import math
import os
from pathlib import Path
import subprocess
import sys
from threading import Lock

from analisis_captura import analizar_filas, leer_csv, numero_medicion

_bloqueo_matplotlib = Lock()


# Dibuja velocidad y orden de servo en ejes separados, conservando todas las muestras y los huecos.
def crear_figura(filas, metadatos, nombre, figura=None):
    from matplotlib.backends.backend_agg import FigureCanvasAgg
    from matplotlib.figure import Figure

    analisis = analizar_filas(filas)
    tiempos_s = [fila[0] / 1000 for fila in filas]
    velocidades_rpm = [fila[2] if math.isfinite(fila[2]) and fila[2] >= 0 else math.nan for fila in filas]
    angulos_deg = [fila[1] for fila in filas]
    if figura is None:
        figura = Figure(figsize=(11, 7), layout="constrained")
        FigureCanvasAgg(figura)
    eje_velocidad, eje_freno = figura.subplots(2, 1, sharex=True, gridspec_kw={"height_ratios": [3, 1]})
    estado = "Captura completa" if metadatos.get("completo") is True else (
        "CAPTURA INCOMPLETA" if metadatos.get("completo") is False else "Integridad sin verificar")
    figura.suptitle(f"Frenado · {nombre}\n{estado} · {len(filas)} muestras · "
                   f"periodo medio {numero_medicion(analisis['periodo_medio_ms'])} ms", fontsize=12)
    eje_velocidad.plot(tiempos_s, velocidades_rpm, color="#1766a3", linewidth=1.4, label="RPM del CSV, sin filtrar")
    eje_freno.step(tiempos_s, angulos_deg, where="post", color="#b85b12", linewidth=1.6, label="Orden al servo")
    eje_velocidad.set_ylabel("Velocidad estimada [RPM]")
    eje_freno.set_ylabel("Orden [°]")
    eje_velocidad.set_ylim(bottom=0)
    eje_freno.margins(y=0.25)
    for eje in (eje_velocidad, eje_freno):
        eje.grid(True, alpha=0.22)
        eje.set_xlim(0, max(tiempos_s[-1], 0.02))
    for numero_cambio, indice_cambio in enumerate(analisis["cambios_freno"]):
        tiempo_cambio_s = tiempos_s[indice_cambio]
        for eje in (eje_velocidad, eje_freno):
            eje.axvline(tiempo_cambio_s, color="#b85b12", linestyle="--", alpha=0.8,
                        label=f"Cambio de orden: {tiempo_cambio_s:.3f} s" if numero_cambio == 0 else None)
    if analisis["indice_maximo"] is not None:
        indice_pico = analisis["indice_maximo"]
        eje_velocidad.scatter([tiempos_s[indice_pico]], [velocidades_rpm[indice_pico]], color="#1766a3", s=25, zorder=3)
        eje_velocidad.annotate(f"Pico: {velocidades_rpm[indice_pico]:.1f} RPM\nt = {tiempos_s[indice_pico]:.3f} s",
                              xy=(tiempos_s[indice_pico], velocidades_rpm[indice_pico]), xytext=(24, -35),
                              textcoords="offset points", fontsize=9, bbox={"facecolor": "white", "edgecolor": "none", "alpha": 0.85},
                              arrowprops={"arrowstyle": "->", "color": "#1766a3"})
    if analisis["indice_parada"] is not None:
        tiempo_cero_s = tiempos_s[analisis["indice_parada"]]
        eje_velocidad.axvline(tiempo_cero_s, color="#327b46", linestyle=":", linewidth=1.6,
                             label=f"Primer 0 RPM: {tiempo_cero_s:.3f} s")
    eje_velocidad.legend(loc="upper right", fontsize=9)
    eje_freno.legend(loc="upper right", fontsize=9)
    figura.supxlabel("Tiempo desde el corte del motor [s]\n"
                     "Angulo = orden al servo · 0 RPM = ausencia de pulsos · Fuente: CSV original", fontsize=9)
    return figura


# Lee el CSV cerrado y su JSON asociado, serializa Matplotlib y guarda el PNG junto a los datos.
def generar_grafica_csv(ruta_csv):
    ruta_csv = Path(ruta_csv).resolve()
    filas = leer_csv(ruta_csv)
    ruta_json = ruta_csv.with_suffix(".json")
    metadatos = json.loads(ruta_json.read_text(encoding="utf-8")) if ruta_json.exists() else {}
    ruta_png = ruta_csv.with_suffix(".png")
    with _bloqueo_matplotlib:
        figura = crear_figura(filas, metadatos, ruta_csv.stem)
        try:
            figura.savefig(ruta_png, dpi=160, metadata={"Title": ruta_csv.stem,
                           "Description": f"Fuente: {ruta_csv.name}; {len(filas)} muestras originales; sin filtrado"})
        finally:
            figura.clear()
    return ruta_png


# Abre el CSV en una ventana nativa en otro proceso; la consola no espera a que se cierre.
def abrir_grafica(ruta_png):
    ruta_csv = Path(ruta_png).resolve().with_suffix(".csv")
    if not ruta_csv.is_file():
        raise FileNotFoundError(f"El visor necesita el CSV original: {ruta_csv}")
    if importlib.util.find_spec("PySide6") is None:
        raise ImportError("La ventana nativa requiere PySide6-Essentials")
    carpeta_logs = Path(__file__).resolve().parents[1] / "salidas" / "visores"
    carpeta_logs.mkdir(parents=True, exist_ok=True)
    with (carpeta_logs / f"{ruta_csv.stem}.log").open("ab") as registro:
        subprocess.Popen([sys.executable, str(Path(__file__).resolve()), str(ruta_csv), "--ventana"],
                         stdin=subprocess.DEVNULL, stdout=registro, stderr=subprocess.STDOUT,
                         env=dict(os.environ, PYTHONUTF8="1", QT_API="pyside6"),
                         creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    return True


# Ejecuta la GUI de Qt en el hilo principal de su propio proceso, con ejes y barra de herramientas.
def mostrar_grafica_csv(ruta_csv):
    os.environ["QT_API"] = "pyside6"
    import matplotlib
    matplotlib.use("qtagg")
    from matplotlib import pyplot

    ruta_csv = Path(ruta_csv).resolve()
    filas = leer_csv(ruta_csv)
    ruta_json = ruta_csv.with_suffix(".json")
    metadatos = json.loads(ruta_json.read_text(encoding="utf-8")) if ruta_json.exists() else {}
    figura = pyplot.figure(figsize=(11, 7), layout="constrained")
    try:
        crear_figura(filas, metadatos, ruta_csv.stem, figura=figura)
        figura.canvas.manager.set_window_title(f"Frenado — {ruta_csv.stem}")
        pyplot.show()
    finally:
        pyplot.close(figura)


# Permite regenerar una figura desde banco.py o desde el CSV sin conectar la placa.
def main():
    argumentos = argparse.ArgumentParser(description=__doc__)
    argumentos.add_argument("archivo", type=Path)
    argumentos.add_argument("--abrir", action="store_true")
    argumentos.add_argument("--ventana", action="store_true", help="muestra el CSV en una ventana nativa de Matplotlib")
    opciones = argumentos.parse_args()
    try:
        if opciones.ventana:
            mostrar_grafica_csv(opciones.archivo)
            return
        ruta_png = generar_grafica_csv(opciones.archivo)
        print(f"Grafica guardada: {ruta_png}")
        if opciones.abrir:
            abrir_grafica(ruta_png)
    except (OSError, ValueError, ImportError) as error:
        argumentos.exit(1, f"No se pudo generar la grafica: {error}\n")


if __name__ == "__main__":
    main()
