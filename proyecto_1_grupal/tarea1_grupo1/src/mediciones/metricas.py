"""Medidas numéricas de señales y filtros; no filtra ni lee archivos."""

import numpy as np

# ---------------------------------------------------------------------------
# Medidas básicas
# ---------------------------------------------------------------------------


def energia(x):
    """Suma la energía de todas las muestras."""
    return float(np.sum(np.square(x, dtype=np.float64)))


def relacion_db(numerador, denominador):
    """Relación de energías; conserva infinito y NaN en casos límite."""
    if numerador == 0:
        return np.nan if denominador == 0 else -np.inf
    return np.inf if denominador == 0 else float(10 * np.log10(numerador / denominador))


def snr_db(clean, observed, epsilon=0.0):
    """SNR respecto a la referencia; generación usa epsilon=1e-15."""
    return relacion_db(energia(clean) + epsilon, energia(np.asarray(observed) - clean) + epsilon)


def rms(x):
    """Valor eficaz de las muestras, usado al ajustar la SNR de generación."""
    return float(np.sqrt(np.mean(np.square(x, dtype=np.float64))))


# ---------------------------------------------------------------------------
# Evaluación de calidad
# ---------------------------------------------------------------------------


def calcular_metricas(clean, noise, salida, util, ruido_salida=None):
    """Compara la mezcla filtrada con la referencia y separa sus errores."""
    energia_util = energia(clean)
    snr_entrada = relacion_db(energia_util, energia(noise))
    snr_salida = relacion_db(energia_util, energia(clean - salida))
    if ruido_salida is None:
        ruido_salida = salida - util
    return {
        "snr_entrada_dB": snr_entrada,
        "snr_salida_dB": snr_salida,
        "delta_snr_dB": snr_salida - snr_entrada,
        "mse": energia(clean - salida) / len(clean),
        "energia_util_conservada_pct": (
            100 * energia(util) / energia_util if energia_util else np.nan
        ),
        "snr_distorsion_util_dB": relacion_db(energia_util, energia(clean - util)),
        "atenuacion_ruido_dB": relacion_db(energia(noise), energia(ruido_salida)),
    }


def atenuacion_interferencia(noise, ruido_salida, fs, ancho_hz):
    """Mide energía cerca del pico dominante del ruido, solo para evaluar."""
    R = np.fft.rfft(noise)
    R_salida = np.fft.rfft(ruido_salida)
    frecuencias = np.fft.rfftfreq(len(noise), 1 / fs)
    dominante = frecuencias[np.argmax(np.abs(R) ** 2)]
    banda = np.abs(frecuencias - dominante) <= max(ancho_hz / 2, fs / len(noise))
    peso = np.full(len(R), 2.0)
    peso[0] = 1
    if len(noise) % 2 == 0:
        peso[-1] = 1
    return relacion_db(
        np.sum(peso[banda] * np.abs(R[banda]) ** 2),
        np.sum(peso[banda] * np.abs(R_salida[banda]) ** 2),
    )


def snr_mejor_retardo(s, y, max_retardo=120):
    """Devuelve la mejor SNR y su retardo entero dentro del rango evaluado."""
    # SNR de la salida alineada con el retardo entero que la maximiza
    return max((snr_db(s[: len(s) - d], y[d:]), d) for d in range(max_retardo))
