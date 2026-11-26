"""Verifica las muestras dibujadas, la exportacion y el cierre sin bloquear el receptor."""
import json
import math
import os
from pathlib import Path
import subprocess
import sys

import pytest


# La figura conserva todas las muestras, el pico intermedio y el angulo ordenado.
def test_figura_conserva_datos_y_huecos(consola):
    from graficas_captura import crear_figura
    filas = [(0.5, 90, 1800), (20.5, 90, 2100), (40.5, 152, math.nan), (60.5, 152, 0)]
    figura = crear_figura(filas, {"completo": False}, "prueba")
    try:
        curva_rpm = figura.axes[0].lines[0]
        assert list(curva_rpm.get_xdata()) == [0.0005, 0.0205, 0.0405, 0.0605]
        assert list(curva_rpm.get_ydata())[:2] == [1800, 2100]
        assert math.isnan(curva_rpm.get_ydata()[2]) and curva_rpm.get_ydata()[3] == 0
        assert list(figura.axes[1].lines[0].get_ydata()) == [90, 90, 152, 152]
        assert "INCOMPLETA" in figura._suptitle.get_text()
    finally:
        figura.clear()


# El PNG se genera desde el archivo cerrado y no cambia sus bytes ni sus metadatos originales.
def test_png_desde_csv_sin_modificar_datos(consola, tmp_path):
    from graficas_captura import generar_grafica_csv
    ruta_csv = tmp_path / "frenado.csv"
    original_csv = b"tiempo_ms,freno_deg,velocidad_rpm\n0,90,1000\n20,152,900\n40,152,0\n"
    original_json = json.dumps({"completo": True}).encode()
    ruta_csv.write_bytes(original_csv)
    ruta_csv.with_suffix(".json").write_bytes(original_json)
    ruta_png = generar_grafica_csv(ruta_csv)
    assert ruta_png == ruta_csv.with_suffix(".png")
    assert ruta_png.read_bytes().startswith(b"\x89PNG\r\n\x1a\n")
    assert ruta_csv.read_bytes() == original_csv and ruta_csv.with_suffix(".json").read_bytes() == original_json


# El cierre deja libre la captura y entrega el trabajo al ejecutor, sin esperar la figura en UART.
def test_fin_entrega_postproceso_fuera_del_receptor(consola, monkeypatch, tmp_path):
    trabajos = []

    # Registra las tareas solicitadas sin ejecutarlas en el hilo de recepcion.
    class EjecutorRegistrado:
        # Conserva la funcion y los argumentos para comprobar la separacion del cierre.
        def submit(self, funcion, *argumentos):
            trabajos.append((funcion, argumentos))

    monkeypatch.setattr(consola, "DATOS", tmp_path)
    monkeypatch.setattr(consola, "mostrar", lambda *argumentos: None)
    banco = consola.Banco(None, "prueba", abrir_graficas=False)
    banco.procesamiento_capturas.shutdown()
    banco.procesamiento_capturas = EjecutorRegistrado()
    banco.captura = consola.Captura("prueba")
    banco.captura.linea_datos(consola.CABECERA)
    banco.captura.linea_datos("0,90,1000")
    banco.mensaje_json({"tipo": "fin", "completo": True, "enviadas": 1, "producidas": 1})
    assert banco.captura is None and len(trabajos) == 1
    assert trabajos[0][1][0].read_text().splitlines()[-1] == "0,90,1000"


# La falta de la libreria no afecta el CSV ya cerrado y produce una instruccion util.
def test_dependencia_ausente_conserva_csv(consola, monkeypatch, tmp_path):
    ruta_csv = tmp_path / "prueba.csv"
    ruta_csv.write_text("tiempo_ms,freno_deg,velocidad_rpm\n0,90,1000\n20,152,0\n", encoding="utf-8")
    lineas = []

    # Simula una instalacion sin la dependencia grafica, despues del analisis del CSV.
    def fallar_dependencia(ruta):
        raise ImportError("matplotlib")

    monkeypatch.setattr(consola, "mostrar", lambda texto, color="": lineas.append(texto))
    monkeypatch.setattr(consola, "generar_grafica_csv", fallar_dependencia)
    banco = consola.Banco(None, "prueba", abrir_graficas=False)
    banco.procesar_csv(ruta_csv, {})
    banco.procesamiento_capturas.shutdown()
    assert ruta_csv.exists() and "python banco.py preparar" in lineas[-1]


# El visor usa otro proceso del mismo Python, conserva las rutas con espacios y no abre URLs.
def test_visor_nativo_independiente(consola, monkeypatch, tmp_path):
    import graficas_captura
    llamadas = []
    ruta_csv = tmp_path / "captura con espacios.csv"
    ruta_csv.write_text("tiempo_ms,freno_deg,velocidad_rpm\n0,90,1000\n", encoding="utf-8")
    monkeypatch.setattr(graficas_captura.subprocess, "Popen",
                        lambda argumentos, **opciones: llamadas.append((argumentos, opciones)))
    assert graficas_captura.abrir_grafica(ruta_csv.with_suffix(".png"))
    argumentos, opciones = llamadas[0]
    assert argumentos[0] == sys.executable and argumentos[2:] == [str(ruta_csv), "--ventana"]
    assert opciones["env"]["QT_API"] == "pyside6"
    assert opciones["stdin"] == subprocess.DEVNULL
    assert not any(argumento.startswith("file:") for argumento in argumentos)


# Un equipo sin Qt recibe un error explicito, manteniendo el PNG generado para su consulta.
def test_visor_sin_dependencia(consola, monkeypatch, tmp_path):
    import graficas_captura
    ruta_csv = tmp_path / "prueba.csv"
    ruta_csv.write_text("tiempo_ms,freno_deg,velocidad_rpm\n0,90,1000\n", encoding="utf-8")
    monkeypatch.setattr(graficas_captura.importlib.util, "find_spec", lambda nombre: None)
    with pytest.raises(ImportError, match="PySide6-Essentials"):
        graficas_captura.abrir_grafica(ruta_csv.with_suffix(".png"))


# Verifica Qt y los mismos ejes del CSV en un proceso separado, sin mostrar ventanas durante las pruebas.
@pytest.mark.skipif(sys.platform.startswith("linux") and not (os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY")),
                    reason="La seleccion del backend interactivo requiere un entorno de escritorio")
def test_ventana_matplotlib_qt(consola, tmp_path):
    ruta_csv = tmp_path / "prueba.csv"
    ruta_csv.write_text("tiempo_ms,freno_deg,velocidad_rpm\n0,90,1000\n20,152,900\n40,152,0\n", encoding="utf-8")
    herramientas = Path(consola.__file__).parent
    programa = """
import sys
sys.path.insert(0, sys.argv[1])
import matplotlib
matplotlib.use('qtagg')
from matplotlib import pyplot
from graficas_captura import mostrar_grafica_csv
def comprobar():
    figura = pyplot.gcf()
    figura.canvas.draw()
    assert 'QTAgg' in type(figura.canvas).__name__
    assert len(figura.axes) == 2
    assert list(figura.axes[0].lines[0].get_ydata()) == [1000, 900, 0]
    assert list(figura.axes[1].lines[0].get_ydata()) == [90, 152, 152]
pyplot.show = comprobar
mostrar_grafica_csv(sys.argv[2])
assert not pyplot.get_fignums()
print('Ventana Qt y datos originales verificados')
"""
    resultado = subprocess.run([sys.executable, "-c", programa, str(herramientas), str(ruta_csv)],
                               env=dict(os.environ, QT_API="pyside6", QT_QPA_PLATFORM="offscreen", PYTHONUTF8="1"),
                               capture_output=True, text=True, timeout=30)
    assert resultado.returncode == 0, resultado.stderr
    assert "verificados" in resultado.stdout
