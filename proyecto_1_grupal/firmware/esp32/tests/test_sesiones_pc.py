"""Verificacion final del codec, archivos y procesamiento finito C frente a Python."""
from pathlib import Path
import json
import shutil
import subprocess
import sys
import wave

import numpy as np
import pytest
from scipy.signal import lfilter

FIRMWARE = Path(__file__).resolve().parents[1]
PROYECTO = FIRMWARE.parents[1]
COMPONENTES = FIRMWARE / "components"
sys.path.insert(0, str(FIRMWARE / "tools"))
sys.path.insert(0, str(PROYECTO / "tarea1_grupo1"))
from pc.protocolo import Paquete, codificar, decodificar, SALIDA
from pc.archivos import SesionArchivos, abrir_sesion, cargar_csv, cuantizar
from pc.terminal import configurar, configuracion_inicial
from src.filtros.filtrado_espectral import filtrar_senal
from src.filtros.bloques_espectrales import aplicar_ganancias


@pytest.fixture(scope="module")
def ejecutables(tmp_path_factory):
    """Compila fuentes del firmware sin sustituir el algoritmo por un modelo."""
    carpeta = tmp_path_factory.mktemp("sesiones_c")
    compilador = shutil.which("gcc")
    assert compilador, "GCC requerido"
    comun = [compilador, "-std=c11", "-D__USE_MINGW_ANSI_STDIO=1", "-O2", "-Wall", "-Wextra", "-Werror"]
    for modulo in ("procesamiento_vivo", "filtros_digitales", "evaluacion_digital", "senales_embebidas", "enlace_pc"):
        comun += ["-I", str(COMPONENTES / modulo / "include")]
    fuentes = [COMPONENTES / "procesamiento_vivo/procesamiento_registro.c",
               *sorted((COMPONENTES / "filtros_digitales").glob("*.c")),
               COMPONENTES / "evaluacion_digital/metricas_digitales.c",
               COMPONENTES / "senales_embebidas/datos/coeficientes_fir.c"]
    salidas = {}
    for nombre, archivos in (("registro", fuentes), ("codec", [COMPONENTES / "enlace_pc/protocolo_pc.c"])):
        salidas[nombre] = carpeta / f"{nombre}.exe"
        resultado = subprocess.run([*comun, *map(str, archivos), str(FIRMWARE / f"tests/ejecutor_{nombre}.c"),
                                   "-lm", "-o", str(salidas[nombre])], capture_output=True, text=True)
        assert resultado.returncode == 0, resultado.stdout + resultado.stderr
    return salidas


@pytest.mark.parametrize("cantidad", [0, 1, 254, 255, 512, 4096])
def test_codec_cruzado(ejecutables, tmp_path, cantidad):
    """C y Python deben producir exactamente los mismos bytes, ceros y limites incluidos."""
    datos = bytes(posicion % 256 for posicion in range(cantidad))
    original = tmp_path / "original.bin"
    codificada = tmp_path / "codificada.bin"
    decodificada = tmp_path / "decodificada.bin"
    original.write_bytes(datos)
    subprocess.run([str(ejecutables["codec"]), "codificar", str(original), str(codificada)], check=True)
    paquete = Paquete(7, 13, 19, 23, 29, datos)
    assert codificada.read_bytes() == codificar(paquete)
    assert decodificar(codificada.read_bytes()[:-1]) == paquete
    subprocess.run([str(ejecutables["codec"]), "decodificar", str(codificada), str(decodificada)], check=True)
    assert decodificada.read_bytes() == datos
    danada = bytearray(codificada.read_bytes())
    danada[-3] ^= 1
    codificada.write_bytes(danada)
    with pytest.raises(ValueError):
        decodificar(danada[:-1])
    assert subprocess.run([str(ejecutables["codec"]), "decodificar", str(codificada), str(decodificada)]).returncode != 0


@pytest.mark.parametrize("longitud", [256, 512, 768, 96000])
@pytest.mark.parametrize("factor", [1.0, 0.1])
def test_cierre_y_alineacion(ejecutables, tmp_path, longitud, factor):
    """Compara todas las muestras, incluido el ultimo salto parcial y las metricas alineadas."""
    tiempos = np.arange(longitud) / 16000
    limpia = .2 * np.sin(2 * np.pi * 440 * tiempos)
    mezcla = limpia + .1 * np.sin(2 * np.pi * 4000 * tiempos)
    pares, _ = cuantizar(np.column_stack((mezcla, limpia)), 1)
    pares = (pares.astype(np.float32) / 32768).astype("<f4")
    entrada = tmp_path / "entrada.f32"
    salida = tmp_path / "salida.f32"
    pares.tofile(entrada)
    resultado = subprocess.run([str(ejecutables["registro"]), str(entrada), str(salida), str(factor), "1"],
                              capture_output=True, text=True, check=True)
    calculadas = np.fromfile(salida, dtype="<f4").reshape(-1, 2)
    assert len(calculadas) == longitud
    coeficientes = np.loadtxt(PROYECTO / "tarea1_grupo1/resultados/filtro_temporal/coeficientes_fir.csv",
                             delimiter=",", skiprows=1)[:, 1].astype(np.float32)
    temporal = lfilter(coeficientes, [1], pares[:, 0])
    espectral, detalles = filtrar_senal(pares[:, 0].astype(float), 16000, factor=factor, devolver_detalles=True)
    np.testing.assert_allclose(calculadas[:, 0], temporal, atol=3e-6, rtol=0)
    np.testing.assert_allclose(calculadas[:, 1], np.r_[np.zeros(37), espectral[:-37]], atol=3e-6, rtol=0)
    utiles = [lfilter(coeficientes, [1], pares[:, 1])[37:], aplicar_ganancias(pares[:, 1], detalles)[:-37]]
    referencia = pares[:-37, 1].astype(float)
    for metodo, linea in enumerate(resultado.stdout.splitlines()):
        muestras, mse, snr, energia, atenuacion = map(float, linea.split(","))
        assert muestras == longitud - 37
        error = referencia - calculadas[37:, metodo]
        assert mse == pytest.approx(np.mean(error ** 2), abs=1e-8)
        assert snr == pytest.approx(10 * np.log10(np.sum(referencia ** 2) / np.sum(error ** 2)), abs=0.03)
        assert energia == pytest.approx(100 * np.sum(utiles[metodo] ** 2) / np.sum(referencia ** 2), abs=0.01)
        residual = calculadas[37:, metodo] - utiles[metodo]
        esperada = 10 * np.log10(np.sum((pares[:-37, 0] - referencia) ** 2) / np.sum(residual ** 2))
        assert atenuacion == pytest.approx(esperada, abs=0.03)


def test_sesion_incompleta_y_sin_sobrescritura(tmp_path):
    """Una perdida queda visible y no reemplaza grabaciones anteriores."""
    metadatos = dict(muestras=256, escala=1, unidad="normalizada")
    primera = SesionArchivos(tmp_path, metadatos)
    segunda = SesionArchivos(tmp_path, metadatos)
    assert primera.ruta != segunda.ruta
    with pytest.raises(ValueError):
        primera.agregar(Paquete(SALIDA, 1, indice=256, canal=1, datos=b"\0" * 512))
    primera.cerrar(causa="desconexion")
    segunda.cerrar(causa="cancelacion")
    with pytest.raises(ValueError):
        abrir_sesion(primera.ruta)
    assert json.loads((primera.ruta / "sesion.json").read_text())["estado"] == "incompleta"


def test_archivos_completos_y_reapertura(tmp_path):
    """Conserva 96000 muestras por ruta y detecta modificaciones posteriores del WAV."""
    sesion = SesionArchivos(tmp_path, dict(muestras=96000, escala=3.3, unidad="voltios"))
    for inicio in range(0, 96000, 256):
        for canal in (1, 2, 3):
            sesion.agregar(Paquete(SALIDA, 1, indice=inicio, canal=canal, datos=b"\0" * 512))
    sesion.informe = {"muestras": 96000, "fir": {"mse": None}, "espectral": {"mse": None}}
    sesion.cerrar(completo=True)
    assert abrir_sesion(sesion.ruta)[1]["muestras"] == 96000
    for nombre in ("entrada", "fir", "espectral"):
        with wave.open(str(sesion.ruta / f"{nombre}.wav")) as archivo:
            assert archivo.getnframes() == 96000
    (sesion.ruta / "fir.wav").write_bytes(b"cambio")
    with pytest.raises(ValueError):
        abrir_sesion(sesion.ruta)


@pytest.mark.parametrize("caso", [1, 2, 3])
def test_csv_originales(caso):
    """Reutiliza exactamente los tres CSV existentes sin regenerar sus ruidos."""
    mezcla, referencia, escala, recortes = cargar_csv(PROYECTO / f"tarea1_grupo1/resultados/muestras/caso_{caso}_muestras.csv")
    assert len(mezcla) == len(referencia) == 96000 and escala >= 1 and recortes == 0


def test_configuracion_atomica():
    """Una configuracion incorrecta no modifica los parametros activos."""
    actual = configuracion_inicial()
    with pytest.raises(ValueError):
        configurar(actual, ["segundos=2", "factor=nan"])
    assert actual["muestras"] == 96000
    assert configurar(actual, ["segundos=1"])["muestras"] == 16128
