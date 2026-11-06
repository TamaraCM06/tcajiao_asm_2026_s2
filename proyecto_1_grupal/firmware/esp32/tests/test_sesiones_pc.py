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
from src.datos.archivos import asegurar_muestras_caso
from src.mediciones.metricas import calcular_metricas


@pytest.fixture(scope="module")
def ejecutables(tmp_path_factory):
    """Compila fuentes del firmware sin sustituir el algoritmo por un modelo."""
    carpeta = tmp_path_factory.mktemp("sesiones_c")
    compilador = shutil.which("gcc")
    assert compilador, "GCC requerido"
    comun = [compilador, "-std=c11", "-D__USE_MINGW_ANSI_STDIO=1", "-O2", "-Wall", "-Wextra", "-Werror"]
    for modulo in ("procesamiento_registro", "filtros_digitales", "evaluacion_digital", "enlace_pc"):
        comun += ["-I", str(COMPONENTES / modulo / "include")]
    fuentes = [*sorted((COMPONENTES / "procesamiento_registro").glob("*.c")),
               *sorted((COMPONENTES / "filtros_digitales").glob("*.c")),
               *sorted((COMPONENTES / "evaluacion_digital").glob("*.c"))]
    salidas = {}
    for nombre, archivos in (("registro", fuentes), ("codec", [COMPONENTES / "enlace_pc/protocolo_pc.c"])):
        salidas[nombre] = carpeta / f"{nombre}.exe"
        resultado = subprocess.run([*comun, *map(str, archivos), str(FIRMWARE / f"tests/ejecutor_{nombre}.c"),
                                   "-lm", "-o", str(salidas[nombre])], capture_output=True, text=True)
        assert resultado.returncode == 0, resultado.stdout + resultado.stderr
    return salidas


# Comprueba integracion regional y que observar tiempos no cambia una sola muestra de salida.
def test_instrumentacion_y_region_del_registro(ejecutables, tmp_path):
    """Usa las ganancias de la mezcla del modelo independiente para contrastar residuos reales."""
    tiempos = np.arange(4096) / 16000
    referencia = .2 * np.sin(2 * np.pi * 440 * tiempos)
    mezcla = referencia + .03 * np.random.default_rng(62).normal(size=4096)
    pares = np.column_stack((mezcla, referencia)).astype("<f4")
    entrada = tmp_path / "entrada.f32"
    pares.tofile(entrada)
    salidas = []
    for medida in (False, True):
        salida = tmp_path / f"salida_{medida}.f32"
        resultado = subprocess.run([str(ejecutables["registro"]), str(entrada), str(salida), ".1", "1",
                                   *(["600", "1500"] if medida else [])], capture_output=True, text=True, check=True)
        salidas.append(salida.read_bytes())
    assert salidas[0] == salidas[1]
    muestras, *energias_c = map(float, resultado.stderr.splitlines()[0].split(","))
    assert muestras == 3072
    calculadas = np.frombuffer(salidas[1], dtype="<f4").reshape(-1, 2)
    coeficientes = np.loadtxt(PROYECTO / "tarea1_grupo1/resultados/filtro_temporal/coeficientes_fir.csv",
                             delimiter=",", skiprows=1)[:, 1].astype(np.float32)
    _, detalles = filtrar_senal(pares[:, 0].astype(float), 16000, devolver_detalles=True)
    utiles = [lfilter(coeficientes, [1], pares[:, 1])[37:], aplicar_ganancias(pares[:, 1], detalles)[:-37]]
    residuos = np.column_stack((pares[:-37, 0] - pares[:-37, 1],
                                calculadas[37:, 0] - utiles[0], calculadas[37:, 1] - utiles[1]))[:3072]
    espectros = np.fft.rfft(residuos.reshape(3, 1024, 3) * np.hanning(1024)[None, :, None], axis=1)
    frecuencias = np.fft.rfftfreq(1024, 1 / 16000)
    mascara = (frecuencias >= 600) & (frecuencias <= 1500)
    esperadas = np.sum(2 * np.abs(espectros[:, mascara]) ** 2, axis=(0, 1))
    np.testing.assert_allclose(energias_c, esperadas, rtol=3e-4, atol=1e-7)
    fir, espectral, arranque, cierre = map(int, resultado.stderr.splitlines()[1].split(","))
    assert fir >= 16 and espectral >= 8 and arranque == 2 and cierre > 0


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


# Contrasta todos los casos sobre el mismo PCM16 que recibe la aplicación vigente.
@pytest.mark.parametrize("caso", ["P1", "P2", "P3", "P4", "P5", "P2_tonal"])
def test_casos_notebook_en_procesador_pc(ejecutables, tmp_path, caso):
    """Conserva comparación de salidas y métricas sin depender del banco flash retirado."""
    archivo_csv = asegurar_muestras_caso(caso, PROYECTO / "tarea1_grupo1")
    mezcla_pcm, referencia_pcm, escala, _ = cargar_csv(archivo_csv)
    pares = np.column_stack((mezcla_pcm, referencia_pcm)).astype(np.float32)
    pares *= np.float32(escala) / np.float32(32768)
    entrada, salida = tmp_path / "entrada.f32", tmp_path / "salida.f32"
    pares.astype("<f4").tofile(entrada)
    resultado = subprocess.run([str(ejecutables["registro"]), str(entrada), str(salida), ".1", "1"],
                              capture_output=True, text=True, check=True)
    calculadas = np.fromfile(salida, dtype="<f4").reshape(-1, 2)
    mezcla, referencia = pares.astype(float).T
    coeficientes = np.loadtxt(
        PROYECTO / "tarea1_grupo1/resultados/filtro_temporal/coeficientes_fir.csv",
        delimiter=",", skiprows=1)[:, 1].astype(np.float32)
    temporal = lfilter(coeficientes, [1], mezcla)
    espectral, detalles = filtrar_senal(mezcla, 16000, devolver_detalles=True)
    np.testing.assert_allclose(calculadas[:, 0], temporal, atol=3e-6, rtol=0)
    np.testing.assert_allclose(calculadas[:, 1], np.r_[np.zeros(37), espectral[:-37]], atol=3e-6, rtol=0)
    utiles = (lfilter(coeficientes, [1], referencia)[37:], aplicar_ganancias(referencia, detalles)[:-37])
    assert len(calculadas) == len(mezcla_pcm)
    for metodo, linea in enumerate(resultado.stdout.splitlines()):
        cantidad, mse, snr, energia, atenuacion = map(float, linea.split(","))
        esperadas = calcular_metricas(referencia[:-37], mezcla[:-37] - referencia[:-37],
                                     calculadas[37:, metodo], utiles[metodo])
        assert cantidad == len(mezcla) - 37
        assert mse == pytest.approx(esperadas["mse"], abs=1e-8)
        assert snr == pytest.approx(esperadas["snr_salida_dB"], abs=.03)
        assert energia == pytest.approx(esperadas["energia_util_conservada_pct"], abs=.01)
        assert atenuacion == pytest.approx(esperadas["atenuacion_ruido_dB"], abs=.03)


# Comprueba silencio y reconstrucción unitaria en el mismo ejecutor que usa las sesiones.
@pytest.mark.parametrize("longitud", [256, 768, 96000])
@pytest.mark.parametrize("silencio", [True, False])
def test_silencio_y_reconstruccion_unitaria(ejecutables, tmp_path, longitud, silencio):
    """Incluye extremos y cierre parcial sin incorporar registros de señales en la flash."""
    mezcla = np.zeros(longitud) if silencio else np.random.default_rng(93).uniform(-.8, .8, longitud)
    pares = np.column_stack((mezcla, mezcla * .7)).astype("<f4")
    entrada, salida = tmp_path / "entrada.f32", tmp_path / "salida.f32"
    pares.tofile(entrada)
    resultado = subprocess.run([str(ejecutables["registro"]), str(entrada), str(salida), "1", "1"],
                              capture_output=True, text=True, check=True)
    calculadas = np.fromfile(salida, dtype="<f4").reshape(-1, 2)
    np.testing.assert_allclose(calculadas[:, 1], np.r_[np.zeros(37), pares[:-37, 0]], atol=3e-6, rtol=0)
    assert len(calculadas) == longitud
    assert all(int(linea.split(",")[0]) == longitud - 37 for linea in resultado.stdout.splitlines())
    if silencio:
        assert not np.any(calculadas)


# Los parámetros no finitos o fuera de rango se rechazan antes de procesar.
@pytest.mark.parametrize("factor", ["nan", "-0.1", "1.1"])
def test_factor_invalido_en_registro(ejecutables, tmp_path, factor):
    """Traslada el rechazo del banco retirado al procesador utilizado actualmente."""
    entrada, salida = tmp_path / "entrada.f32", tmp_path / "salida.f32"
    np.zeros((256, 2), dtype="<f4").tofile(entrada)
    resultado = subprocess.run([str(ejecutables["registro"]), str(entrada), str(salida), factor, "1"],
                              capture_output=True, text=True)
    assert resultado.returncode == 3


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


def test_paquete_tres_rutas_sin_perdida(tmp_path):
    """El ahorro de cabeceras conserva cada bit PCM16 y el orden de las tres rutas."""
    sesion = SesionArchivos(tmp_path, dict(muestras=512, escala=3.3, unidad="voltios"))
    columnas = np.column_stack((np.arange(512), -np.arange(512), np.full(512, 32767))).astype("<i2")
    sesion.agregar(Paquete(SALIDA, 1, canal=0, datos=columnas.tobytes()))
    sesion.informe = {"fir": {"mse": None}, "espectral": {"mse": None}}
    sesion.cerrar(completo=True)
    for columna, nombre in enumerate(("entrada", "fir", "espectral")):
        with wave.open(str(sesion.ruta / f"{nombre}.wav")) as archivo:
            np.testing.assert_array_equal(np.frombuffer(archivo.readframes(512), dtype="<i2"), columnas[:, columna])
