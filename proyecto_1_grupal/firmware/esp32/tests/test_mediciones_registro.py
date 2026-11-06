"""Contrastes independientes de energias regionales y reloj digital; no son ensayos fisicos."""
from pathlib import Path
import shutil
import subprocess
import sys

import numpy as np
import pytest

FIRMWARE = Path(__file__).resolve().parents[1]
COMPONENTES = FIRMWARE / "components"
sys.path.insert(0, str(FIRMWARE / "tools"))
from pc.mediciones import configuracion_medicion
from pc.terminal import configuracion_inicial, configurar


# Compila las mismas fuentes portables de produccion, sin una FFT alternativa en C.
@pytest.fixture(scope="module")
def ejecutor(tmp_path_factory):
    """Requiere GCC como las demas comprobaciones host del proyecto."""
    salida = tmp_path_factory.mktemp("mediciones") / "mediciones.exe"
    orden = [shutil.which("gcc"), "-std=c11", "-D__USE_MINGW_ANSI_STDIO=1", "-O2", "-Wall", "-Wextra", "-Werror"]
    for modulo in ("procesamiento_registro", "filtros_digitales", "evaluacion_digital"):
        orden += ["-I", str(COMPONENTES / modulo / "include")]
        orden += [str(archivo) for archivo in sorted((COMPONENTES / modulo).glob("*.c"))]
    subprocess.run([*orden, str(FIRMWARE / "tests/ejecutor_mediciones.c"), "-lm", "-o", str(salida)], check=True)
    return salida


# Calcula la energia con NumPy sobre los mismos bloques float32 y Hann simetrica.
@pytest.mark.parametrize("minimo,maximo", [(3950, 4050), (2500, 3800), (600, 1500), (0, 8000)])
def test_energia_regional_independiente(ejecutor, tmp_path, minimo, maximo):
    """Incluye ruido superpuesto, DC, Nyquist y un final parcial que se excluye."""
    generador = np.random.default_rng(882)
    tiempos = np.arange(4096 + 731) / 16000
    ruido = .1 * np.sin(2 * np.pi * 4000 * tiempos) + .07 * generador.normal(size=len(tiempos))
    residuos = np.column_stack((ruido, .3 * ruido + .005, .1 * ruido + .01 * (-1) ** np.arange(len(tiempos)))).astype("<f4")
    archivo = tmp_path / "residuos.f32"
    residuos.tofile(archivo)
    resultado = subprocess.run([str(ejecutor), str(archivo), str(minimo), str(maximo)], capture_output=True, text=True, check=True)
    muestras, *calculadas = map(float, resultado.stdout.splitlines()[0].split(","))
    assert muestras == 4096
    bloques = residuos[:4096].reshape(-1, 1024, 3)
    espectros = np.fft.rfft(bloques * np.hanning(1024)[None, :, None], axis=1)
    frecuencias = np.fft.rfftfreq(1024, 1 / 16000)
    pesos = np.full(513, 2.0)
    pesos[[0, -1]] = 1
    banda = (frecuencias >= minimo) & (frecuencias <= maximo)
    esperadas = np.sum(np.abs(espectros[:, banda]) ** 2 * pesos[None, banda, None], axis=(0, 1))
    np.testing.assert_allclose(calculadas, esperadas, rtol=3e-6, atol=1e-8)
    assert resultado.stdout.splitlines()[1:] == ["disponible", "disponible"]


# Distingue ausencia de datos de una atenuacion numerica.
@pytest.mark.parametrize("longitud,entrada,cantidad_salida,motivo", [
    (256, 1, 1, "sin_bloques_completos"), (2048, 0, 0, "sin_energia_entrada"),
    (2048, 1, 0, "residuo_no_resuelto")])
def test_regional_no_disponible(ejecutor, tmp_path, longitud, entrada, cantidad_salida, motivo):
    """No se sustituye un denominador cero por un valor arbitrario."""
    archivo = tmp_path / "residuos.f32"
    np.tile(np.array([entrada, cantidad_salida, cantidad_salida], dtype="<f4"), (longitud, 1)).tofile(archivo)
    resultado = subprocess.run([str(ejecutor), str(archivo), "0", "8000"], capture_output=True, text=True, check=True)
    assert resultado.stdout.splitlines()[1:] == [motivo, motivo]


# Comprueba ambos lados del contrato de validacion de regiones.
@pytest.mark.parametrize("minimo,maximo", [(-1, 100), (100, 100), (0, 8001), (1, 2), (float("nan"), 8000)])
def test_region_invalida(ejecutor, tmp_path, minimo, maximo):
    """Las regiones invalidas no empiezan una medicion."""
    assert subprocess.run([str(ejecutor), str(tmp_path / "sin_archivo"), str(minimo), str(maximo)]).returncode == 3
    with pytest.raises(ValueError):
        configurar(configuracion_inicial(), [f"interferencia_min_hz={minimo}", f"interferencia_max_hz={maximo}"])


# Los instantes fijos comprueban sumas y maximos sin depender de la velocidad de la PC.
def test_marcas_y_reinicio(ejecutor):
    """Distingue arranque, estado estable y vaciado, ademas de indices reutilizados."""
    resultado = subprocess.run([str(ejecutor)], capture_output=True, text=True, check=True)
    assert "OK tiempos" in resultado.stdout


# Los alias se traducen solo para seleccionar metadatos del ensayo.
def test_regiones_automaticas_y_explicitas():
    """No arrastra la region P5 a P1 ni cambia parametros de los filtros."""
    inicial = configuracion_inicial()
    assert configuracion_medicion(inicial, "caso_1_muestras.csv")["interferencia_min_hz"] == 3950
    assert configuracion_medicion(inicial, "P5_muestras.csv")["interferencia_min_hz"] == 600
    assert "interferencia_min_hz" not in inicial
    assert configuracion_medicion(inicial, "desconocida.csv").get("interferencia_min_hz") is None
    explicita = configurar(inicial, ["interferencia_min_hz=2000", "interferencia_max_hz=3000"])
    assert configuracion_medicion(explicita, "P5_muestras.csv")["interferencia_min_hz"] == 2000
    assert configurar(explicita, ["interferencia_min_hz=auto"])["interferencia_max_hz"] is None
