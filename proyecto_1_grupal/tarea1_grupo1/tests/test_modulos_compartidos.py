"""Contratos compartidos, generación reproducible y ejemplo numérico de Fourier."""

import sys
import zipfile
from pathlib import Path

import numpy as np
import pytest
from scipy.io import wavfile

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))

from src.senales import analisis_fourier as af, generacion
from src.datos import archivos
from src.mediciones import metricas
from src.filtros import diseno_temporal as dt
from src.filtros import filtrado_espectral as fe, filtros_temporales as ft


def test_ejemplo_fourier():
    t = np.arange(8) / 8000
    x = np.cos(2 * np.pi * 1000 * t) + 0.5 * np.sin(2 * np.pi * 2000 * t)
    esperado = np.array([0, 4, -2j, 0, 0, 0, 2j, 4])
    np.testing.assert_allclose(af.dft_directa(x), esperado, atol=1e-12)
    np.testing.assert_allclose(af.dft_directa(x), np.fft.fft(x), atol=1e-12)
    np.testing.assert_allclose(np.fft.ifft(esperado), x, atol=1e-12)


@pytest.mark.parametrize("x", [[], [[1, 2], [3, 4]]])
def test_dft_rechaza_formato_invalido(x):
    with pytest.raises(ValueError):
        af.dft_directa(x)


@pytest.mark.parametrize("caso", ["caso_1", "caso_2", "caso_3"])
def test_generacion_reproducible_y_snr(caso):
    cfg = archivos.cargar_configuraciones(RAIZ / 'metadatos/configuraciones.json')[caso]
    primero = generacion.generar_caso_configurado(cfg, 20)
    segundo = generacion.generar_caso_configurado(cfg, 20)
    for clave in ("clean", "noise", "noisy"):
        np.testing.assert_array_equal(primero[clave], segundo[clave])
        assert len(primero[clave]) == 96000
    assert primero['snr'] == pytest.approx(cfg['snr_objetivo_dB'], abs=1e-10)
    np.testing.assert_allclose(primero['clean'] + primero['noise'], primero['noisy'], atol=1e-12)


def test_metricas_distinguen_error_y_potencia():
    clean = np.ones(8)
    noise = np.full(8, 0.1)
    m = metricas.calcular_metricas(clean, noise, clean + noise, clean)
    assert m['mse'] == pytest.approx(0.01)
    assert m['snr_salida_dB'] == pytest.approx(20)
    assert m['energia_util_conservada_pct'] == pytest.approx(100)
    assert m['atenuacion_ruido_dB'] == pytest.approx(0, abs=1e-12)


def test_snr_regularizada_y_casos_limite():
    x = np.zeros(8)
    assert np.isnan(metricas.snr_db(x, x))
    assert metricas.snr_db(x, x, epsilon=1e-15) == 0
    assert np.isposinf(metricas.snr_db(np.ones(8), np.ones(8)))


def test_fachadas_conservan_firmas_de_carga_y_diseno():
    temporal = ft.cargar_caso(RAIZ, 'caso_1')
    espectral = fe.cargar_caso('caso_1', RAIZ)
    assert set(temporal) == {'t', 'clean', 'noise', 'noisy'}
    assert espectral['fs'] == 16000
    np.testing.assert_array_equal(temporal['noisy'], espectral['noisy'])
    assert ft.disenar_fir_kaiser is dt.disenar_fir_kaiser
    with pytest.raises(ValueError, match='Caso desconocido'):
        fe.cargar_caso('no_existe', RAIZ)


def test_imports_anteriores_y_ruta_predeterminada():
    from src import archivos as archivos_anteriores, filtrado_espectral as filtro_anterior

    assert archivos_anteriores is archivos
    assert filtro_anterior is fe
    caso = archivos.cargar_caso('caso_1')
    assert caso['fs'] == 16000
    assert len(caso['clean']) == 96000


def test_diseno_iir_comparte_especificaciones():
    filtros = dt.disenar_iir(1600, 2400, 0.1, 60, 16000)
    assert set(filtros) == {'Butterworth', 'Chebyshev I', 'Elíptico'}
    from scipy import signal

    for orden, sos in filtros.values():
        assert orden > 0
        f, H = signal.sosfreqz(sos, worN=16384, fs=16000)
        assert -20 * np.log10(np.abs(H[f >= 2400]).max()) >= 60 - 1e-8


def test_exportacion_preserva_archivos_y_escala(tmp_path):
    carpeta = tmp_path / 'prueba'
    carpeta.mkdir()
    ajeno = carpeta / 'notas.txt'
    ajeno.write_text('conservar', encoding='utf-8')
    x = np.array([0, 0.1, -0.2, 0.8])
    datos = dict(t=np.arange(4) / 16000, clean=x, noise=x * 0, noisy=x, fs=16000)
    for _ in range(2):
        archivo_zip = archivos.exportar_prueba(carpeta, datos, {'semilla': 123}, 'prueba')
    assert ajeno.read_text(encoding='utf-8') == 'conservar'
    with zipfile.ZipFile(archivo_zip) as z:
        assert len(z.namelist()) == 6
        assert 'notas.txt' not in z.namelist()
    fs, wav = wavfile.read(carpeta / '03_entrada_contaminada.wav')
    assert fs == 16000
    np.testing.assert_array_equal(wav, np.int16(x * 32767))
    with pytest.raises(ValueError, match='rango PCM'):
        archivos.guardar_wav(carpeta / 'invalido.wav', 16000, np.array([1.1]), verificar_rango=True)


def test_tablas_se_reemplazan(tmp_path):
    ruta = tmp_path / 'subcarpeta/metricas.csv'
    filas = [{'caso': 'uno', 'valor': 1}, {'caso': 'dos', 'valor': ''}]
    for _ in range(2):
        archivos.guardar_csv(ruta, filas)
    assert ruta.read_text(encoding='utf-8').splitlines() == ['caso,valor', 'uno,1', 'dos,']


@pytest.mark.parametrize('longitud', [7, 8])
def test_energia_fourier_equivale_a_energia_temporal(longitud):
    x = np.random.default_rng(42).normal(size=longitud)
    assert af.energia_en_banda(x, 16000, 0, 8000) == pytest.approx(metricas.energia(x))
