"""Transformadas y medidas espectrales; no genera figuras ni archivos."""

import numpy as np
from scipy import signal

# ---------------------------------------------------------------------------
# Transformación directa y visualización del espectro
# ---------------------------------------------------------------------------


def dft_directa(x):
    """Calcula la definición de la DFT. Usar con ejemplos pequeños: coste O(N²)."""
    x = np.asarray(x)
    if x.ndim != 1 or not len(x):
        raise ValueError("x debe ser un vector no vacío.")
    n = np.arange(len(x))
    return np.exp(-2j * np.pi * np.outer(n, n) / len(x)) @ x


def espectro_db(x, fs):
    """Magnitud de la FFT con ventana Hann en dB (escalada para leer la amplitud de un tono)."""
    w = signal.get_window('hann', len(x), fftbins=True)
    X = np.fft.rfft(x * w)
    f = np.fft.rfftfreq(len(x), 1 / fs)
    return f, 20 * np.log10(np.maximum(np.abs(X) / (np.sum(w) / 2), 1e-12))


# ---------------------------------------------------------------------------
# Energía por bandas
# ---------------------------------------------------------------------------


def energia_en_banda(x, fs, f_lo, f_hi):
    """Energía de x (suma de x^2, vía Parseval) contenida entre f_lo y f_hi Hz."""
    X = np.fft.rfft(x)
    f = np.fft.rfftfreq(len(x), 1 / fs)
    P = np.abs(X) ** 2
    # rfft: los bins interiores representan dos bins del espectro completo
    peso = np.full(len(P), 2.0)
    peso[0] = 1.0
    if len(x) % 2 == 0:
        peso[-1] = 1.0
    sel = (f >= f_lo) & (f <= f_hi)
    return float(np.sum(peso[sel] * P[sel]) / len(x))
