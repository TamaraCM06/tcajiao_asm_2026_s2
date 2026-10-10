"""Pruebas automáticas del filtro temporal: implementación propia contra scipy.

Ejecutar desde tarea1_grupo1/:  python -m pytest tests
"""

import sys
from pathlib import Path

import numpy as np
import pytest
from scipy import signal

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ/'src'))

import filtros_temporales as ft

FS = 16_000
F_PASO, F_RECHAZO = 1600.0, 2400.0
RIZADO_MAX_DB, ATENUACION_MIN_DB = 0.1, 60.0
TOLERANCIA = 1e-12


@pytest.fixture(scope='module')
def b_fir():
    return ft.disenar_fir_kaiser(F_PASO, F_RECHAZO, ATENUACION_MIN_DB, FS)[0]


@pytest.fixture(scope='module')
def casos():
    return {c: ft.cargar_caso(RAIZ, c) for c in ('caso_1', 'caso_2', 'caso_3')}


def test_diseno_cumple_especificacion(b_fir):
    rizado, atenuacion = ft.medir_especificacion(b_fir, 1.0, FS, F_PASO, F_RECHAZO)
    assert rizado <= RIZADO_MAX_DB
    assert atenuacion >= ATENUACION_MIN_DB


def test_fir_tipo_i_fase_lineal(b_fir):
    assert len(b_fir) % 2 == 1
    assert np.allclose(b_fir, b_fir[::-1])


def test_estabilidad(b_fir):
    _, polos = ft.polos_ceros(b_fir)
    assert ft.es_estable(polos)


@pytest.mark.parametrize('caso', ['caso_1', 'caso_2', 'caso_3'])
def test_ecuacion_diferencias_igual_a_lfilter(b_fir, casos, caso):
    x = casos[caso]['noisy']
    y = ft.ecuacion_diferencias(b_fir, [1.0], x)
    assert np.max(np.abs(y - signal.lfilter(b_fir, 1.0, x))) <= TOLERANCIA


@pytest.mark.parametrize('tam_bloque', [1, 64, 256, 1000])
def test_por_bloques_igual_a_lfilter(b_fir, casos, tam_bloque):
    # 1000 no divide la longitud: el último bloque queda incompleto
    x = casos['caso_2']['noisy'][:20_000]
    y = ft.filtrar_por_bloques(b_fir, x, tam_bloque)
    assert np.max(np.abs(y - signal.lfilter(b_fir, 1.0, x))) <= TOLERANCIA


def test_ecuacion_diferencias_iir():
    rng = np.random.default_rng(0)
    x = rng.standard_normal(5000)
    b, a = signal.ellip(6, 0.1, 60, 2000, fs=FS)
    assert np.max(np.abs(ft.ecuacion_diferencias(b, a, x) - signal.lfilter(b, a, x))) <= TOLERANCIA


def test_reduce_ruido_fuera_de_banda(b_fir, casos):
    retardo = (len(b_fir) - 1)//2
    filtro = lambda v: ft.filtrar_por_bloques(b_fir, v)
    for caso in ('caso_1', 'caso_2'):
        m = ft.evaluar_filtro(casos[caso]['clean'], casos[caso]['noise'], filtro, retardo)
        assert m['delta_snr_dB'] > 55
