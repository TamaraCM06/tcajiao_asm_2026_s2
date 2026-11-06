"""Comprueba consulta sin efectos laterales; usa sesiones sinteticas y ningun puerto fisico."""
import copy
import os
from pathlib import Path
import sys

import numpy as np
import pytest

FIRMWARE = Path(__file__).resolve().parents[1]
PROYECTO = FIRMWARE.parents[1]
sys.path.insert(0, str(FIRMWARE / "tools"))
sys.path.insert(0, str(PROYECTO / "tarea1_grupo1"))
from pc import terminal
from pc.archivos import SesionArchivos
from pc.presentacion import mostrar_metricas, mostrar_validacion, tabla, valor_visible
from pc.protocolo import Paquete, SALIDA


# Construye un registro valido sin referencia, con una validacion PC que ya existia.
@pytest.fixture
def sesion(tmp_path):
    """Incluye cero medido, campos ausentes y negativos para evitar inferencias de presentacion."""
    registro = SesionArchivos(tmp_path, dict(muestras=256, escala=1, unidad="normalizada",
        origen="archivo", fuente="P1_muestras.csv", con_referencia=False))
    muestras = np.zeros((256, 3), dtype="<i2")
    registro.agregar(Paquete(SALIDA, 1, canal=0, datos=muestras.tobytes()))
    registro.informe = dict(calculo_max_us=12345, recortes_entrada=0,
        fir=dict(mse=0.0, mejora_snr_db=-2.5, recortes_salida=0),
        espectral=dict(mse=None, mejora_snr_db=None, recortes_salida=0))
    registro.metadatos["validacion_python"] = dict(resultados={
        "fir": dict(concordancia_modelo_python_pct=99.999656, umbral_concordancia_pct=90, cumple_concordancia=True),
        "espectral": dict(concordancia_modelo_python_pct=None, umbral_concordancia_pct=90, cumple_concordancia=None),
    })
    registro.cerrar(completo=True)
    return registro.ruta


# Consultar dos veces debe conservar byte a byte tanto WAV como JSON/CSV y eventos.
def test_metricas_guardadas_sin_recalcular_ni_escribir(sesion, monkeypatch, capsys):
    """La consulta mantiene incluso sesiones anteriores que no tienen tiempos individuales."""
    originales = {archivo.name: archivo.read_bytes() for archivo in sesion.iterdir()}

    # Una consulta que intentara ejecutar la validacion falla deliberadamente.
    def prohibir_validacion(*argumentos, **opciones):
        raise AssertionError("metricas no debe recalcular")

    monkeypatch.setattr(terminal, "validar_sesion", prohibir_validacion)
    for _ in range(2):
        terminal.mostrar_metricas_sesion(sesion)
    texto = capsys.readouterr().out
    assert "FIR" in texto and "ESPECTRAL" in texto and "VALIDACION INDEPENDIENTE EN PC" in texto
    assert "0.000000e+00" in texto and "-2.500" in texto and "99.9997" in texto and "N/D" not in texto
    assert "MEDIDAS POR RUTA" in texto
    assert "CALCULO POR RUTA" not in texto and "TIEMPOS DIGITALES" not in texto
    assert "12.345" in texto
    assert originales == {archivo.name: archivo.read_bytes() for archivo in sesion.iterdir()}


# Las fuentes pueden contener campos nuevos: la vista no debe perderlos al agrupar.
def test_presentacion_conserva_valores_y_campos_adicionales(capsys):
    """Evita convertir indefiniciones en cero o mutar los numeros para redondearlos."""
    informe = dict(calculo_max_us=0, dato_adicional=42, fir=dict(mse=float("nan"), extra_fir=87),
                   espectral=dict(mse=float("inf"), mejora_snr_db=-3.25))
    copia = copy.deepcopy(informe)
    mostrar_metricas(informe)
    texto = capsys.readouterr().out
    assert "dato_adicional" in texto and "42" in texto and "extra_fir" in texto and "87" in texto
    assert "-3.250" in texto and "N/D" not in texto and "MSE" not in texto
    assert informe["espectral"] == copia["espectral"] and informe["calculo_max_us"] == 0
    assert np.isnan(informe["fir"]["mse"])
    assert valor_visible(0, ".3f") == "0.000"
    assert valor_visible(False) == "No"
    assert valor_visible(None) == "" and valor_visible(float("nan")) == ""


# Una captura sin limpia no presenta una lista de metricas de calidad inexistentes.
def test_captura_antigua_muestra_solo_datos_registrados(capsys):
    """Oculta tablas vacias y conserva ceros, energia y tiempo conjunto disponibles."""
    informe = dict(con_referencia=False, calculo_max_us=16288, perdidas=0,
        fir=dict(mse=None, snr_salida_db=None, energia_total=0, recortes_salida=0),
        espectral=dict(mse=None, snr_salida_db=None, energia_total=901.6472, recortes_salida=0))
    mostrar_metricas(informe)
    texto = capsys.readouterr().out
    assert "sin referencia limpia" in texto and "16.288" in texto
    assert "Energia total" in texto and "0.000000e+00" in texto
    for ausente in ("N/D", "MSE", "SNR", "CALCULO POR RUTA", "TIEMPOS DIGITALES", "Version de mediciones",
                    "VALIDACION INDEPENDIENTE", "Costos incluyen ruta de referencia"):
        assert ausente not in texto
    assert informe["fir"]["mse"] is None


# La limpieza visual no debe ocultar medidas negativas ni el incumplimiento de un criterio.
def test_validacion_parcial_conserva_incumplimiento(capsys):
    """Una ruta puede tener resultado sin que se invente el de la otra."""
    mostrar_validacion(dict(fir=dict(concordancia_modelo_python_pct=75, cumple_concordancia=False,
                                    umbral_concordancia_pct=90),
                            espectral=dict(concordancia_modelo_python_pct=None, cumple_concordancia=None,
                                           umbral_concordancia_pct=90)))
    texto = capsys.readouterr().out
    assert "75.0000" in texto and "No" in texto and "MEDIDAS POR RUTA" in texto
    assert "N/D" not in texto


# El caso sin seleccion debe guiar al usuario sin iniciar una captura.
def test_metricas_sin_sesion():
    """La consulta requiere una sesion seleccionada y nunca fabrica resultados."""
    with pytest.raises(ValueError, match="Primero capture"):
        terminal.mostrar_metricas_sesion(None)


# Recorta el ancho mediante envoltura de celdas, sin omitir partes de una ruta larga.
def test_tabla_en_terminal_angosta(monkeypatch):
    """Los bordes se alinean y el contenido sigue completo al reducir la ventana."""
    monkeypatch.setattr("pc.presentacion.shutil.get_terminal_size", lambda *_: os.terminal_size((60, 24)))
    ruta_larga = "C:/" + "/".join(["directorio_de_prueba"] * 5)
    texto = tabla("PRUEBA", ("Campo", "Valor"), (("Ruta", ruta_larga), ("Ausente", "N/D")))
    lineas = [linea for linea in texto.splitlines() if linea.startswith(("+", "|"))]
    assert max(map(len, lineas)) <= 60
    partes = [linea.split("|")[2].strip() for linea in lineas if linea.startswith("|")][1:]
    assert ruta_larga in "".join(partes)
    assert "Ausente" not in texto and "N/D" not in texto
    assert tabla("VACIA", ("Dato", "Valor"), (("Sin dato", None),)) == ""


# Ejecuta el enrutado real de comandos con un cliente que no conoce operaciones DSP.
def test_comando_metricas_usa_archivos_y_no_el_firmware(sesion, monkeypatch, capsys):
    """Abrir y consultar repetidamente solo conectan para el saludo inicial de la terminal."""
    import serial
    conexiones = []
    originales = {archivo.name: archivo.read_bytes() for archivo in sesion.iterdir()}

    class PuertoPrueba:
        """Doble de apertura y cierre; nunca representa una placa."""

        # La terminal abre un puerto al arrancar, antes de aceptar comandos.
        def open(self):
            pass

        # Permite comprobar salida limpia de la terminal real.
        def close(self):
            pass

    class ClientePrueba:
        """Solo admite saludo y prueba de enlace; cualquier orden adicional falla."""

        # Recibe el doble de puerto con la misma firma del cliente de produccion.
        def __init__(self, puerto):
            self.puerto = puerto

        # Cuenta las consultas al firmware para detectar llamadas de metricas.
        def conectar(self):
            conexiones.append("HELLO")
            return "ASM2 detenido"

        # Devuelve una velocidad conocida sin transferir datos.
        def comprobar_enlace(self):
            return 99000

    ordenes = iter(["metricas", f'abrir "{sesion}"', "metricas", "metricas", "salir"])
    monkeypatch.setattr(serial, "Serial", lambda **_: PuertoPrueba())
    monkeypatch.setattr(terminal, "Cliente", ClientePrueba)
    monkeypatch.setattr("builtins.input", lambda _: next(ordenes))
    monkeypatch.setattr(sys, "argv", ["sesiones.py", "--puerto", "PRUEBA"])
    terminal.main(PROYECTO)
    texto = capsys.readouterr().out
    assert conexiones == ["HELLO"]
    assert texto.count("SESION SELECCIONADA") == 2 and "Primero capture" in texto
    assert "N/D" not in texto
    assert originales == {archivo.name: archivo.read_bytes() for archivo in sesion.iterdir()}
