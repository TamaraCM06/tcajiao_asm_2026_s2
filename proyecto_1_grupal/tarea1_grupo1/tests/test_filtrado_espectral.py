"""Pruebas automáticas del filtro espectral (apartado 2.4).

Ejecutar desde tarea1_grupo1/: python -m pytest tests
"""

import sys
from pathlib import Path

import numpy as np
import pytest

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "src"))

import filtrado_espectral as fe

FS = 16_000
TOLERANCIA = 1e-12


@pytest.fixture(scope="module")
def casos():
    return {caso: fe.cargar_caso(caso, RAIZ)
            for caso in ("caso_1", "caso_2", "caso_3")}


@pytest.fixture(scope="module")
def metricas(casos):
    return {nombre: fe.evaluar_filtro(c["clean"], c["noise"], c["fs"])
            for nombre, c in casos.items()}


@pytest.mark.parametrize("n", [0, 1, 17, 511, 512, 513, 1024, 2305])
@pytest.mark.parametrize("tam_bloque", [4, 64, 1024])
def test_reconstruccion_longitudes_y_extremos(n, tam_bloque):
    rng = np.random.default_rng(42)
    x = rng.uniform(-0.8, 0.8, n)
    original = x.copy()
    y = fe.filtrar_senal(x, FS, tam_bloque=tam_bloque, factor=1)

    assert y.shape == x.shape
    assert not np.iscomplexobj(y)
    np.testing.assert_allclose(y, x, atol=TOLERANCIA, rtol=TOLERANCIA)
    np.testing.assert_array_equal(x, original)


def test_silencio():
    y, detalles = fe.filtrar_senal(
        np.zeros(513, dtype=int), FS, devolver_detalles=True
    )
    np.testing.assert_array_equal(y, np.zeros(513))
    assert np.all(np.isnan(detalles["frecuencias_estimadas_Hz"]))


def test_arreglos_enteros():
    x = np.array([1, -1, 1, 0, -1])
    np.testing.assert_allclose(fe.filtrar_senal(x, FS, factor=1), x,
                               atol=TOLERANCIA)


@pytest.mark.parametrize(
    "entrada", [[[1, 2]], [1 + 2j], [np.nan], [np.inf]],
    ids=["matriz", "compleja", "nan", "infinito"],
)
def test_rechaza_muestras_invalidas(entrada):
    with pytest.raises(ValueError):
        fe.filtrar_senal(entrada, FS)


@pytest.mark.parametrize("parametros", [
    {"tam_bloque": 1000}, {"tam_bloque": 2},
    {"tam_bloque": True}, {"tam_bloque": 1024.0},
    {"fs": 0}, {"fs": "16000"}, {"fs": np.nan},
    {"frecuencia_minima": 8000}, {"frecuencia_minima": -1},
    {"factor": -0.1}, {"factor": 1.1},
    {"ancho_hz": -1}, {"ancho_hz": 9000},
    {"umbral_relativo": 0}, {"umbral_relativo": 1.1},
])
def test_rechaza_parametros_invalidos(parametros):
    with pytest.raises(ValueError):
        fe.filtrar_senal(np.zeros(1024), **{"fs": FS, **parametros})


def test_interferencia_cambia_de_frecuencia():
    t = np.arange(8192) / FS
    limpia = 0.5 * np.sin(2 * np.pi * 440 * t)
    ruido = 0.2 * np.sin(2 * np.pi * 3000 * t)
    ruido[len(t) // 2:] = 0.2 * np.sin(2 * np.pi * 4100 * t[len(t) // 2:])

    y, detalles = fe.filtrar_senal(limpia + ruido, FS, devolver_detalles=True)

    assert np.mean((limpia - y) ** 2) < np.mean(ruido ** 2) / 10
    estimadas = detalles["frecuencias_estimadas_Hz"]
    assert np.any(np.abs(estimadas - 3000) <= FS / 1024)
    assert np.any(np.abs(estimadas - 4100) <= FS / 1024)


def test_banda_util_protegida_y_mascaras_reales():
    t = np.arange(8192) / FS
    limpia = 0.5 * np.sin(2 * np.pi * 440 * t)
    mezcla = limpia + 0.2 * np.sin(2 * np.pi * 4000 * t)

    _, detalles = fe.filtrar_senal(
        mezcla, FS, ancho_hz=8000, devolver_detalles=True
    )
    f = np.fft.rfftfreq(1024, 1 / FS)
    np.testing.assert_array_equal(detalles["ganancias"][:, f < 1600], 1)
    util = fe._referencia_filtrada(limpia, detalles)

    # El corte abrupto contiene energía fuera de banda. La distorsión total
    # debe quedar 40 dB bajo la potencia útil; también se verifica el interior.
    assert np.mean((limpia - util) ** 2) < 1e-4 * np.mean(limpia ** 2)
    assert np.mean((limpia[1024:-1024] - util[1024:-1024]) ** 2) < TOLERANCIA


@pytest.mark.parametrize("caso", ["caso_1", "caso_2", "caso_3"])
def test_casos_reales(caso, casos, metricas):
    m = metricas[caso]
    assert len(m["salida"]) == len(casos[caso]["clean"]) == 96000
    assert np.all(np.isfinite(m["salida"]))
    assert m["tiempo_por_bloque_us"] > 0
    assert m["memoria_trabajo_bytes"] > 0

    if caso != "caso_3":
        assert m["delta_snr_dB"] > 10
        assert m["energia_util_conservada_pct"] > 99
    else:
        assert abs(m["delta_snr_dB"]) < 0.1


def test_compromiso_ruido_distorsion(casos):
    c = casos["caso_3"]
    suave = fe.evaluar_filtro(c["clean"], c["noise"], c["fs"],
                             frecuencia_minima=600, factor=0.8)
    fuerte = fe.evaluar_filtro(c["clean"], c["noise"], c["fs"],
                              frecuencia_minima=600, factor=0.1)

    assert fuerte["atenuacion_ruido_dB"] > suave["atenuacion_ruido_dB"]
    assert fuerte["energia_util_conservada_pct"] < suave["energia_util_conservada_pct"]
    assert fuerte["snr_distorsion_util_dB"] < suave["snr_distorsion_util_dB"]


def test_metricas_coinciden_con_referencia_directa(casos):
    caso = casos["caso_1"]
    m = fe.evaluar_filtro(caso["clean"], caso["noise"], caso["fs"],
                         factor=1)
    np.testing.assert_allclose(m["salida"], caso["noisy"], atol=TOLERANCIA)

    mse = np.mean((caso["clean"] - caso["noisy"]) ** 2)
    assert m["mse"] == pytest.approx(mse, abs=TOLERANCIA, rel=0)
    assert m["snr_salida_dB"] == pytest.approx(m["snr_entrada_dB"], abs=1e-10, rel=0)
    assert m["energia_util_conservada_pct"] == pytest.approx(100, abs=1e-10, rel=0)
    assert m["atenuacion_ruido_dB"] == pytest.approx(0, abs=1e-10, rel=0)


def test_evaluar_filtro_con_senal_propia():
    t = np.arange(8192) / FS
    limpia = 0.5 * np.sin(2 * np.pi * 700 * t)
    ruido = 0.2 * np.sin(2 * np.pi * 3500 * t)

    m = fe.evaluar_filtro(limpia, ruido, FS)

    assert len(m["salida"]) == len(limpia)
    assert m["delta_snr_dB"] > 10
    assert m["energia_util_conservada_pct"] > 99


@pytest.mark.parametrize("clean, noise", [([], []), ([1], [1, 2])])
def test_evaluar_filtro_rechaza_longitudes_invalidas(clean, noise):
    with pytest.raises(ValueError, match="misma longitud, no vacía"):
        fe.evaluar_filtro(clean, noise, FS)
