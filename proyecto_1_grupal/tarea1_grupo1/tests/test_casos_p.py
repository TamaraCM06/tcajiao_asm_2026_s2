"""Casos de defensa generados por el modelo existente; no acreditan una ejecución en placa."""
from pathlib import Path
import json
import sys

import numpy as np
import pytest

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))
from src.datos.archivos import asegurar_muestras_caso, cargar_caso, cargar_configuraciones
from src.datos.casos import EQUIVALENCIAS_HISTORICAS
from src.senales.generacion import generar_caso_configurado


# Cada CSV conserva la semilla, longitud, SNR y mezcla del generador del notebook.
@pytest.mark.parametrize("identificador", ["P1", "P2", "P2_tonal", "P3", "P4", "P5"])
def test_casos_defensa_reproducibles(identificador):
    """Cada CSV conserva la semilla, longitud, SNR y mezcla del generador del notebook."""
    configuracion = cargar_configuraciones(RAIZ / "metadatos/configuraciones.json")[identificador]
    regenerado = generar_caso_configurado(configuracion, 20)
    guardado = cargar_caso(identificador, RAIZ)
    assert len(guardado["noisy"]) == 96000
    assert regenerado["snr"] == pytest.approx(configuracion["snr_objetivo_dB"], abs=1e-10)
    for componente in ("clean", "noise", "noisy"):
        np.testing.assert_allclose(guardado[componente], regenerado[componente], rtol=0, atol=1e-14)
    assert np.max(np.abs(guardado["noisy"])) <= .8 + 1e-14


# P1 es un tono, P3 usa el barrido existente y P4 no se confunde con ruido de banda.
def test_casos_cubren_los_cinco_estimulos():
    """P1 es un tono, P3 usa el barrido existente y P4 no se confunde con ruido de banda."""
    casos = cargar_configuraciones(RAIZ / "metadatos/configuraciones.json")
    assert casos["P1"]["tipo_senal"] == "tono"
    assert casos["P1"]["frecuencias_utiles_Hz"] == [440]
    assert casos["P1"]["tipo_ruido"] == "tonal"
    assert (casos["P3"]["tipo_senal"], casos["P3"]["tipo_ruido"]) == ("chirp", "blanco")
    assert (casos["P4"]["tipo_senal"], casos["P4"]["tipo_ruido"]) == ("transitoria", "impulsivo")
    assert casos["P2"]["banda_ruido_Hz"] == [2500, 3800]
    assert casos["P5"]["banda_ruido_Hz"] == [600, 1500]


# Las sesiones y consumidores antiguos siguen abriendo exactamente los mismos registros.
@pytest.mark.parametrize("anterior,vigente", EQUIVALENCIAS_HISTORICAS.items())
def test_alias_historico_conserva_las_muestras(anterior, vigente):
    """Las sesiones y consumidores antiguos siguen abriendo exactamente los mismos registros."""
    anterior_cargado = cargar_caso(anterior, RAIZ)
    vigente_cargado = cargar_caso(vigente, RAIZ)
    for componente in ("clean", "noise", "noisy"):
        np.testing.assert_array_equal(anterior_cargado[componente], vigente_cargado[componente])


# Simula una copia del repositorio sin el CSV ignorado y verifica que la configuración no cambia.
def test_entrada_faltante_se_prepara_sin_reescribir_json(tmp_path):
    """Genera P1 con el modelo existente; una segunda carga reutiliza la copia local."""
    configuracion = cargar_configuraciones(RAIZ / "metadatos/configuraciones.json")["P1"]
    carpeta = tmp_path / "metadatos"
    carpeta.mkdir()
    archivo = carpeta / "configuraciones.json"
    archivo.write_text(json.dumps({"P1": configuracion}), encoding="utf-8")
    original = archivo.read_bytes()
    destino = asegurar_muestras_caso("P1", tmp_path)
    assert destino.exists() and archivo.read_bytes() == original
    contenido = destino.read_bytes()
    assert len(cargar_caso("P1", tmp_path)["clean"]) == 96000
    assert destino.read_bytes() == contenido and archivo.read_bytes() == original


# La preparación copia registros históricos sin cambiarlos ni reconstruirlos con otro generador.
def test_preparacion_copia_historico_byte_a_byte(tmp_path):
    """Conserva origen y destino idénticos al resolver caso_1 como P2_tonal."""
    configuracion = cargar_configuraciones(RAIZ / "metadatos/configuraciones.json")["P2_tonal"]
    (tmp_path / "metadatos").mkdir()
    (tmp_path / "metadatos/configuraciones.json").write_text(json.dumps({"P2_tonal": configuracion}), encoding="utf-8")
    carpeta = tmp_path / "resultados/muestras"
    carpeta.mkdir(parents=True)
    fuente = carpeta / "caso_1_muestras.csv"
    fuente.write_bytes((RAIZ / "resultados/muestras/caso_1_muestras.csv").read_bytes())
    destino = asegurar_muestras_caso("caso_1", tmp_path)
    assert destino.read_bytes() == fuente.read_bytes()
