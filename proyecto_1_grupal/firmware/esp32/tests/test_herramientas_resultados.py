"""Pruebas de los scripts que resumen evidencias; los datos son sinteticos, no de la placa."""
import csv
import json
from pathlib import Path
import sys
import wave

import numpy as np
import pytest
from scipy.signal import lfilter

PROYECTO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(PROYECTO))
from herramientas.respuesta_fir_medida import comparar, respuesta_calculada
from herramientas.resumen_pruebas import escribir_latex, leer_repeticiones, resumir
from herramientas.graficar_sesion import graficar, medir_tonos
from herramientas.exportar_coeficientes import exportar_coeficientes
from herramientas.preparar_casos import exportar_estimulo
from pc.archivos import SesionArchivos
from pc.protocolo import Paquete, SALIDA

COEFICIENTES = np.loadtxt(PROYECTO / "tarea1_grupo1/resultados/filtro_temporal/coeficientes_fir.csv",
                          delimiter=",", skiprows=1)[:, 1]


# Verifica que la reubicación conserva los valores publicados del FIR, sin generar señales.
def test_coeficientes_exportados_coinciden_con_firmware(tmp_path):
    """El nuevo exportador reproduce exactamente el archivo C que utiliza la aplicación."""
    destino = exportar_coeficientes(destino=tmp_path / "coeficientes_fir.c")
    vigente = PROYECTO / "firmware/esp32/components/filtros_digitales/coeficientes_fir.c"
    assert destino.read_text(encoding="utf-8") == vigente.read_text(encoding="utf-8")


# El audio acustico mantiene la mezcla y evita recortes aun si las amplitudes superan uno.
def test_estimulo_escala_comun_sin_recortes(tmp_path):
    """La misma ganancia conserva SNR y proporciones de los componentes del notebook."""
    limpia = np.array([0, 2, -2, 0], dtype=float)
    ruido = np.array([0, 1, -1, 0], dtype=float)
    datos = dict(clean=limpia, noise=ruido, noisy=limpia + ruido, fs=16000)
    carpeta = exportar_estimulo(tmp_path, "P1", datos)
    metadatos = json.loads((carpeta / "estimulo.json").read_text())
    assert metadatos["ganancia_comun"] == pytest.approx(.8 / 3)
    for nombre, senal in (("01_referencia_limpia.wav", limpia), ("02_ruido.wav", ruido),
                          ("03_entrada_contaminada.wav", limpia + ruido)):
        with wave.open(str(carpeta / nombre)) as archivo:
            muestras = np.frombuffer(archivo.readframes(4), dtype="<i2")
        assert np.max(np.abs(muestras.astype(float))) < 30000
        np.testing.assert_allclose(muestras / 32767, senal * .8 / 3, atol=1 / 16000)


def escribir_wav(ruta, muestras):
    """Guarda PCM16 sintético para comprobar el estimador sin una placa."""
    with wave.open(str(ruta), "wb") as archivo:
        archivo.setnchannels(1)
        archivo.setsampwidth(2)
        archivo.setframerate(16000)
        archivo.writeframes(np.clip(np.round(muestras), -32768, 32767).astype("<i2").tobytes())


def test_respuesta_fir_medida_recupera_la_calculada(tmp_path):
    """Una salida filtrada con los mismos coeficientes debe medir la misma ganancia."""
    frecuencias = [440.0, 880.0, 1320.0, 4000.0]
    tiempo = np.arange(32000) / 16000
    entrada = sum(4000 * np.sin(2 * np.pi * f * tiempo + 0.3 * k) for k, f in enumerate(frecuencias))
    escribir_wav(tmp_path / "entrada.wav", entrada)
    escribir_wav(tmp_path / "fir.wav", lfilter(COEFICIENTES, [1], entrada))
    filas = comparar(tmp_path, COEFICIENTES, frecuencias)
    for fila in filas[:3]:
        assert abs(fila["diferencia_db"]) < 0.05
    # A 4 kHz el FIR rechaza mas de 60 dB; la medida queda limitada por la cuantizacion PCM16.
    assert filas[3]["medida_db"] is None or filas[3]["medida_db"] < -40
    assert respuesta_calculada(COEFICIENTES, [4000.0])[0] < 1e-3


# Crea una sesión de interfaz sintética; no necesita validación PC ni copias de WAV para resumir.
def crear_repeticion(raiz, numero, snr=20, factor=.1, completa=True, fuente="P1_muestras.csv"):
    """Dos filas por método y configuración reproducible para comprobar agrupación."""
    carpeta = raiz / f"sesion_{numero}"
    carpeta.mkdir(parents=True)
    metadatos = dict(estado="completa" if completa else "incompleta", fuente=fuente, origen="archivo",
        con_referencia=True, frecuencia_hz=16000, muestras=96000, escala=1, minimo_hz=1600,
        ancho_hz=100, factor=factor, umbral=.05, sha256={"entrada": "entrada_sintetica"})
    (carpeta / "sesion.json").write_text(json.dumps(metadatos), encoding="utf-8")
    with (carpeta / "metricas.csv").open("w", newline="", encoding="utf-8") as archivo:
        escritor = csv.writer(archivo)
        escritor.writerow(["metodo", "mse", "snr_salida_db", "mejora_snr_db", "energia_util_pct", "calculo_max_us"])
        for metodo in ("fir", "espectral"):
            escritor.writerow([metodo, .001, snr, snr-10, 99, 16000])
    return carpeta


# Las regiones y las versiones de medicion forman parte de la condicion, no solo del texto.
def test_resumen_separa_region_y_version(tmp_path):
    """No promedia medidas regionales incompatibles ni supone medidas nuevas en sesiones viejas."""
    for numero in range(3):
        carpeta = crear_repeticion(tmp_path, numero)
        archivo = carpeta / "sesion.json"
        datos = json.loads(archivo.read_text())
        datos.update(interferencia_min_hz=3900 + numero * 10, interferencia_max_hz=4100)
        datos["resultado_esp32"] = dict(firmware="misma_version", version_mediciones=numero)
        archivo.write_text(json.dumps(datos), encoding="utf-8")
    filas = resumir(leer_repeticiones(tmp_path))
    assert len(filas) == 6
    assert all(fila["atenuacion_interferencia_db_cantidad"] == 0 for fila in filas)


# El requisito de media y desviación no depende de otro análisis de concordancia.
def test_resumen_promedia_sesiones_directas_sin_validacion(tmp_path):
    """Recupera 22 +/- 2 dB de tres repeticiones sin crear otra carpeta de evidencias."""
    for numero, snr in enumerate((20, 22, 24), 1):
        crear_repeticion(tmp_path, numero, snr=snr)
    filas = resumir(leer_repeticiones(tmp_path))
    assert len(filas) == 2
    for fila in filas:
        assert fila["repeticiones"] == 3
        assert fila["snr_salida_db_media"] == 22
        assert fila["snr_salida_db_desviacion"] == 2
        assert fila["estado_repeticiones"] == "tres_o_mas"
        assert fila["concordancia_modelo_python_pct_media"] is None


# Condiciones distintas se reportan por separado, sin promediar configuraciones incompatibles.
def test_resumen_separa_configuraciones(tmp_path):
    """Dos factores generan dos grupos por método, cada uno con una sola corrida."""
    crear_repeticion(tmp_path, 1, factor=.1)
    crear_repeticion(tmp_path, 2, factor=.8)
    filas = resumir(leer_repeticiones(tmp_path))
    assert len(filas) == 4
    assert all(fila["repeticiones"] == 1 and fila["snr_salida_db_desviacion"] is None for fila in filas)


# Una sesión incompleta no puede contar como repetición medida.
def test_resumen_omite_incompletas_sin_inventar_datos(tmp_path, capsys):
    """Conserva dos corridas válidas y deja claro que faltan repeticiones."""
    for numero in (1, 2, 3):
        crear_repeticion(tmp_path, numero, completa=numero != 3)
    filas = resumir(leer_repeticiones(tmp_path))
    assert all(fila["repeticiones"] == 2 and fila["estado_repeticiones"] == "faltan_repeticiones" for fila in filas)
    assert "incompleta" in capsys.readouterr().err


# Los datos indefinidos siguen como no disponibles y el resumen no aprueba algoritmos.
def test_resumen_indefinidos_y_latex(tmp_path):
    """Una sola muestra no estima variabilidad; NaN no se convierte a cero."""
    carpeta = crear_repeticion(tmp_path, 1)
    archivo = carpeta / "metricas.csv"
    archivo.write_text(archivo.read_text().replace("0.001", "nan"), encoding="utf-8")
    filas = resumir(leer_repeticiones(tmp_path))
    assert all(fila["mse_media"] is None and fila["mse_cantidad"] == 0 for fila in filas)
    escribir_latex(filas, tmp_path / "tabla.tex")
    tabla = (tmp_path / "tabla.tex").read_text(encoding="utf-8")
    assert "dagger" in tabla and "Cumple" not in tabla


# El registro histórico de tres tonos no es la prueba P1.
def test_resumen_excluye_variante_historica(tmp_path):
    """No cuenta P2_tonal como una de las pruebas mínimas."""
    crear_repeticion(tmp_path, 1, fuente="caso_1_muestras.csv")
    assert leer_repeticiones(tmp_path) == {}


# Una captura sin referencia puede agruparse explícitamente como física, sin inventar SNR.
def test_resumen_distingue_origen_adc_y_csv(tmp_path):
    """El mismo estímulo declarado no mezcla modos ADC y archivo."""
    crear_repeticion(tmp_path, 1)
    carpeta = crear_repeticion(tmp_path / "P1", 2)
    metadatos = json.loads((carpeta / "sesion.json").read_text())
    metadatos.update(origen="pico", fuente=None, con_referencia=False)
    (carpeta / "sesion.json").write_text(json.dumps(metadatos), encoding="utf-8")
    filas = resumir(leer_repeticiones(tmp_path))
    assert len(filas) == 4


# La entrada incompleta del resumidor debe señalar su archivo ausente.
def test_resumen_exige_metricas(tmp_path):
    """No ignora silenciosamente una sesión marcada completa pero sin métricas."""
    carpeta = crear_repeticion(tmp_path, 1)
    (carpeta / "metricas.csv").unlink()
    with pytest.raises(ValueError, match="metricas.csv"):
        leer_repeticiones(tmp_path)


# Comprueba la medición tonal usando una atenuación conocida y el piso de PCM16.
def test_medicion_tonal_resuelta_y_cota():
    """Una ganancia 0.1 da 20 dB y el silencio devuelve una cota, no infinito."""
    tiempo = np.arange(16000) / 16000
    entrada = 6000 * np.sin(2*np.pi*440*tiempo) + 3000*np.sin(2*np.pi*4000*tiempo)
    filas = medir_tonos(dict(entrada=entrada, fir=.1*entrada, espectral=np.zeros_like(entrada)), [440, 4000])
    assert filas[0]["atenuacion_db"] == pytest.approx(20)
    assert filas[-1]["atenuacion_db"] is None
    assert filas[-1]["atenuacion_minima_db"] > 40


# Verifica la figura con los archivos de sesión reales de interfaz, sin conectar placas.
def test_grafica_sesion_pcm16(tmp_path):
    """El análisis no modifica WAV ni sus metadatos y produce PNG/CSV consultables."""
    tiempo = np.arange(4096) / 16000
    entrada = np.round(4000 * np.sin(2*np.pi*440*tiempo)).astype("<i2")
    sesion = SesionArchivos(tmp_path / "sesiones", dict(muestras=len(entrada), escala=1, unidad="normalizada"))
    for canal in (1, 2, 3):
        sesion.agregar(Paquete(SALIDA, 1, canal=canal, datos=entrada.tobytes()))
    sesion.informe = dict(fir={"mse": 0}, espectral={"mse": 0})
    sesion.cerrar(completo=True)
    original = (sesion.ruta / "sesion.json").read_bytes()
    figura = graficar(sesion.ruta, tmp_path / "figuras", tonos=[440])
    assert figura.read_bytes().startswith(b"\x89PNG")
    assert (figura.parent / "atenuacion_tonos.csv").exists()
    assert (sesion.ruta / "sesion.json").read_bytes() == original
