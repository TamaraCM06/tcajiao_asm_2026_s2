"""Generación reproducible de señales y ruido con escalado común."""

import numpy as np
from scipy.signal import butter, sosfiltfilt, chirp

from ..mediciones.metricas import rms, snr_db

# ---------------------------------------------------------------------------
# Preparación de señales
# ---------------------------------------------------------------------------


def fade(x, fs, ms=20):
    """Suaviza el comienzo y el final sin cambiar el interior de la señal."""
    n = min(int(fs * ms / 1000), len(x) // 2)
    if n > 0:
        ramp = np.sin(np.linspace(0, np.pi / 2, n)) ** 2
        x = x.copy()
        x[:n] *= ramp
        x[-n:] *= ramp[::-1]
    return x


def normalizar_conjunto(*signals, peak=0.8):
    """Aplica una misma ganancia para conservar las relaciones señal/ruido."""
    maximum = max(np.max(np.abs(x)) for x in signals)
    gain = peak / maximum if maximum > 0 else 1.0
    return [x * gain for x in signals], gain


# ---------------------------------------------------------------------------
# Señal útil y ruido
# ---------------------------------------------------------------------------


def generar_limpia(kind, t, freqs, amps, phases_deg, rng):
    """Construye la referencia útil del tipo solicitado con el RNG recibido."""
    if kind == 'tono':
        return amps[0] * np.sin(2 * np.pi * freqs[0] * t + np.deg2rad(phases_deg[0]))
    if kind == 'multitono':
        return sum(
            a * np.sin(2 * np.pi * f * t + np.deg2rad(p))
            for f, a, p in zip(freqs, amps, phases_deg)
        )
    if kind == 'chirp':
        return chirp(t, f0=freqs[0], f1=freqs[-1], t1=t[-1], method='linear')
    if kind == 'armonicos':
        f0 = freqs[0]
        return sum(
            (1 / k) * np.sin(2 * np.pi * k * f0 * t + rng.uniform(-np.pi, np.pi))
            for k in range(1, 6)
        )
    if kind == 'transitoria':
        env = np.exp(-5 * (t % 1.0)) * (np.sin(2 * np.pi * 2 * t) > 0)
        return env * np.sin(2 * np.pi * freqs[0] * t)
    raise ValueError(f'Tipo de señal no reconocido: {kind}')


def ruido_banda(n, fs, band, rng):
    """Concentra ruido gaussiano en la banda mediante un Butterworth."""
    low, high = band
    if not (0 < low < high < fs / 2):
        raise ValueError(f'BANDA_RUIDO debe cumplir 0 < low < high < {fs/2}')
    sos = butter(6, [low, high], btype='bandpass', fs=fs, output='sos')
    return sosfiltfilt(sos, rng.standard_normal(n))


def generar_ruido(kind, t, fs, f_int, band, impulses, rng):
    """Genera ruido conservando el orden de sorteos del generador original.

    Se construyen todas las variantes antes de seleccionar: cambiar ese orden
    modificaría las muestras asociadas a las semillas ya usadas en el informe.
    """
    n = len(t)
    tonal = np.sin(2 * np.pi * f_int * t + rng.uniform(-np.pi, np.pi))
    red = sum(
        (1 / k) * np.sin(2 * np.pi * 60 * k * t + rng.uniform(-np.pi, np.pi)) for k in range(1, 5)
    )
    white = rng.standard_normal(n)
    band_noise = ruido_banda(n, fs, band, rng)
    impulse = np.zeros(n)
    locations = rng.choice(
        np.arange(int(0.1 * fs), n - int(0.1 * fs)),
        size=min(impulses, max(1, n // 100)),
        replace=False,
    )
    for loc in locations:
        width = max(2, int(rng.uniform(0.0005, 0.004) * fs))
        stop = min(n, loc + width)
        impulse[loc:stop] += rng.choice([-1, 1]) * np.hanning(2 * (stop - loc))[: stop - loc]
    options = {
        'tonal': tonal,
        'red_60hz': red,
        'blanco': white,
        'banda': band_noise,
        'impulsivo': impulse,
    }
    if kind == 'mixto':
        return 0.55 * tonal + 0.30 * band_noise + 0.15 * impulse
    if kind not in options:
        raise ValueError(f'Tipo de ruido no reconocido: {kind}')
    return options[kind]


# ---------------------------------------------------------------------------
# Escalado y generación de un caso
# ---------------------------------------------------------------------------


def escalar_ruido_para_snr(clean, noise, target_db):
    """Ajusta la amplitud del ruido a la SNR objetivo sin modificar su forma."""
    target_noise_rms = rms(clean) / (10 ** (target_db / 20))
    return noise * (target_noise_rms / (rms(noise) + 1e-15))


def generar_caso_configurado(cfg, fade_ms):
    """Regenera un caso completo desde su configuración y una semilla propia."""
    # Cada caso tiene su propio generador para conservar su semilla.
    fs = cfg['fs_Hz']
    if fs < 2 * max(
        cfg['frecuencias_utiles_Hz']
        + [cfg['frecuencia_interferencia_Hz'], cfg['banda_ruido_Hz'][1]]
    ):
        raise ValueError('La configuración viola Nyquist.')
    rng_caso = np.random.default_rng(cfg['semilla'])
    t_caso = np.arange(int(fs * cfg['duracion_s'])) / fs
    limpia = generar_limpia(
        cfg['tipo_senal'],
        t_caso,
        cfg['frecuencias_utiles_Hz'],
        cfg['amplitudes_utiles'],
        cfg['fases_grados'],
        rng_caso,
    )
    limpia = fade(limpia, fs, fade_ms)
    ruido = generar_ruido(
        cfg['tipo_ruido'],
        t_caso,
        fs,
        cfg['frecuencia_interferencia_Hz'],
        cfg['banda_ruido_Hz'],
        cfg['numero_impulsos'],
        rng_caso,
    )
    ruido = escalar_ruido_para_snr(limpia, ruido, cfg['snr_objetivo_dB'])
    (limpia, ruido, mezcla), ganancia = normalizar_conjunto(
        limpia, ruido, limpia + ruido, peak=cfg['pico_maximo']
    )
    snr_obtenida = snr_db(limpia, mezcla, epsilon=1e-15)
    assert np.isclose(snr_obtenida, cfg['snr_objetivo_dB'], rtol=0, atol=1e-10)
    np.testing.assert_allclose(limpia + ruido, mezcla, rtol=1e-12, atol=1e-14)
    return {
        't': t_caso,
        'clean': limpia,
        'noise': ruido,
        'noisy': mezcla,
        'fs': fs,
        'gain': ganancia,
        'snr': snr_obtenida,
    }
