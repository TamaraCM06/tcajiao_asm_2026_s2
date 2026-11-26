"""Carga las herramientas reales sin abrir el puerto de la ESP32."""
import importlib.util
from pathlib import Path

import pytest


# Comparte la consola y sus modulos locales entre pruebas de analisis, interfaz y graficas.
@pytest.fixture(scope="module")
def consola():
    ruta = Path(__file__).resolve().parents[2] / "herramientas/consola.py"
    with pytest.MonkeyPatch.context() as ajustes:
        ajustes.syspath_prepend(str(ruta.parent))
        especificacion = importlib.util.spec_from_file_location("consola_banco", ruta)
        modulo = importlib.util.module_from_spec(especificacion)
        especificacion.loader.exec_module(modulo)
        yield modulo
