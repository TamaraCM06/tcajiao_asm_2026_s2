"""Verificación final del mismo núcleo C del firmware, ejecutado en PC mediante GCC."""

from pathlib import Path
import csv
import hashlib
import json
import shutil
import subprocess
import sys

import numpy as np
import pytest
from scipy.signal import lfilter

RAIZ = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(RAIZ.parent))
from proyecto_1_grupal.tarea1_grupo1.src.filtros.filtrado_espectral import filtrar_senal
from proyecto_1_grupal.tarea1_grupo1.src.filtros.bloques_espectrales import aplicar_ganancias
from proyecto_1_grupal.tarea1_grupo1.src.mediciones.metricas import calcular_metricas

FIRMWARE = Path(__file__).resolve().parents[1]
COMPONENTES = FIRMWARE / "components"
DATOS = COMPONENTES / "senales_embebidas/datos"


# Compila el núcleo portable una vez; no requiere placa ni sustituye la compilación ESP-IDF.
@pytest.fixture(scope="session")
def ejecutor(tmp_path_factory):
    """Construye el banco C sin simular sus filtros ni sus métricas."""
    compilador = shutil.which("gcc")
    if not compilador:
        pytest.fail("Se necesita GCC para comprobar el código C portable.")
    carpeta = tmp_path_factory.mktemp("filtros_c")
    ejecutable = carpeta / "ejecutor.exe"
    fuentes = [*sorted((COMPONENTES / "filtros_digitales").glob("*.c")),
               *sorted((COMPONENTES / "evaluacion_digital").glob("*.c")),
               COMPONENTES / "senales_embebidas/lectura_float32.c",
               DATOS / "coeficientes_fir.c", Path(__file__).with_name("ejecutor_host.c")]
    # El enlazador de macOS no acepta --gc-sections; -dead_strip cumple la misma función.
    descartar = "-Wl,-dead_strip" if sys.platform == "darwin" else "-Wl,--gc-sections"
    comando = [compilador, "-std=gnu11", "-D__USE_MINGW_ANSI_STDIO=1", "-O2", "-Wall", "-Wextra", "-Werror",
               "-ffunction-sections", "-fdata-sections", descartar]
    for modulo in ("filtros_digitales", "evaluacion_digital", "senales_embebidas"):
        comando += ["-I", str(COMPONENTES / modulo / "include")]
    compilacion = subprocess.run([*comando, *map(str, fuentes), "-lm", "-o", str(ejecutable)],
                                 capture_output=True, text=True, errors="replace")
    assert compilacion.returncode == 0, compilacion.stdout + compilacion.stderr
    return ejecutable


# Invoca el ejecutable y recoge solo salidas calculadas por C.
def ejecutar(ejecutor, tmp_path, entrada, metodo, factor=0.1):
    """Devuelve pares salida/útil y métricas; los tiempos del PC no se comparan."""
    salida = tmp_path / "salidas.f32"
    resumen = tmp_path / "metricas.csv"
    subprocess.run([str(ejecutor), str(entrada), str(salida), str(resumen), metodo, str(factor)], check=True)
    with resumen.open() as archivo:
        medidas = {clave: float(valor) for clave, valor in next(csv.DictReader(archivo)).items()}
    return np.fromfile(salida, dtype="<f4").reshape(-1, 2), medidas


# Compara los tres registros completos con los algoritmos originales del notebook.
@pytest.mark.parametrize("caso", [1, 2, 3])
@pytest.mark.parametrize("metodo", ["fir", "espectral"])
def test_coincidencia_con_python(ejecutor, tmp_path, caso, metodo):
    """Comprueba alineación, ambos canales, métricas y extremos de la reconstrucción."""
    entrada = DATOS / f"caso_{caso}.f32"
    pares = np.fromfile(entrada, dtype="<f4").reshape(-1, 2).astype(np.float64)
    mezcla, referencia = pares.T
    longitud = len(mezcla) - 37
    if metodo == "fir":
        coeficientes = np.loadtxt(RAIZ / "tarea1_grupo1/resultados/filtro_temporal/coeficientes_fir.csv",
                                 delimiter=",", skiprows=1)[:, 1].astype(np.float32)
        salida_python = lfilter(coeficientes, [1], mezcla)[37:]
        util_python = lfilter(coeficientes, [1], referencia)[37:]
    else:
        salida_python, detalles = filtrar_senal(mezcla, 16000, devolver_detalles=True)
        util_python = aplicar_ganancias(referencia, detalles)
    salida_c, medidas = ejecutar(ejecutor, tmp_path, entrada, metodo)
    np.testing.assert_allclose(salida_c[:, 0], salida_python, atol=3e-6, rtol=0)
    np.testing.assert_allclose(salida_c[:, 1], util_python, atol=3e-6, rtol=0)
    esperadas = calcular_metricas(referencia[:longitud], (mezcla - referencia)[:longitud],
                                 salida_python[:longitud], util_python[:longitud])
    assert medidas["muestras"] == longitud
    for clave, esperado in esperadas.items():
        # Una distorsion casi nula queda dominada por float32; comparar dB seria enganoso.
        if clave == "snr_distorsion_util_dB" and esperado > 100:
            assert medidas[clave] > 100
            continue
        tolerancia = 1e-7 if clave == "mse" else 0.03
        assert medidas[clave] == pytest.approx(esperado, abs=tolerancia)
    if caso in (1, 2):
        assert medidas["delta_snr_dB"] > 10


# Verifica padding, silencio, vaciado y ganancia unitaria con longitudes no múltiplos de 512.
@pytest.mark.parametrize("longitud", [256, 768, 96000])
@pytest.mark.parametrize("silencio", [False, True])
def test_reconstruccion_unitaria(ejecutor, tmp_path, longitud, silencio):
    """Con factor uno la reconstrucción debe preservar cada muestra, incluso los extremos."""
    mezcla = np.zeros(longitud) if silencio else np.random.default_rng(93).uniform(-0.8, 0.8, longitud)
    pares = np.column_stack((mezcla, mezcla * 0.7)).astype("<f4")
    entrada = tmp_path / "entrada.f32"
    pares.tofile(entrada)
    salida, medidas = ejecutar(ejecutor, tmp_path, entrada, "espectral", 1)
    np.testing.assert_allclose(salida, pares, atol=3e-6, rtol=0)
    assert medidas["muestras"] == longitud - 37


# Una configuración inválida no debe producir resultados aparentes.
def test_rechaza_factor_invalido(ejecutor, tmp_path):
    """Comprueba el error público del banco para parámetros no finitos."""
    with pytest.raises(subprocess.CalledProcessError):
        ejecutar(ejecutor, tmp_path, DATOS / "caso_1.f32", "espectral", "nan")


# Comprueba que los registros flash provienen del CSV original y sus hashes son correctos.
@pytest.mark.parametrize("caso", [1, 2, 3])
def test_origen_datos_flash(caso, tmp_path):
    """Verifica igualdad float32 y reproducción byte por byte del exportador."""
    from proyecto_1_grupal.herramientas.exportacion_senales.preparacion import preparar_senal
    from proyecto_1_grupal.herramientas.exportacion_senales.datos_evaluacion import exportar_datos_evaluacion
    senal = preparar_senal(caso=f"caso_{caso}")
    generado = exportar_datos_evaluacion(senal, f"caso_{caso}", tmp_path)
    contenido = (DATOS / f"caso_{caso}.f32").read_bytes()
    assert generado.read_bytes() == contenido
    metadatos = json.loads((DATOS / f"caso_{caso}_evaluacion.json").read_text(encoding="utf-8"))
    assert metadatos["sha256"] == hashlib.sha256(contenido).hexdigest()
    assert metadatos["crc32_dac"] == f"{senal.crc32:08X}"
