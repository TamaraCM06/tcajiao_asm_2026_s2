"""Verifica las muestras dibujadas, la exportacion y el cierre sin bloquear el receptor."""
import json
import math


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
