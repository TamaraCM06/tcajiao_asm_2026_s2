"""Diseño y caracterización de filtros temporales FIR/IIR."""

import warnings
import numpy as np
from scipy import signal

# ---------------------------------------------------------------------------
# Diseño
# ---------------------------------------------------------------------------


def disenar_fir_kaiser(f_paso, f_rechazo, atenuacion_db, fs):
    """Pasa bajas FIR de fase lineal por el método de ventana de Kaiser.

    El orden y el parámetro beta salen de las fórmulas de Kaiser para la atenuación
    pedida y el ancho de transición. El número de coeficientes se fuerza a impar
    (FIR tipo I) para que el retardo de grupo (N-1)/2 sea un número entero de muestras.
    La frecuencia de corte (-6 dB) queda en el centro de la transición.

    Devuelve los coeficientes b y el parámetro beta.
    """
    ancho = (f_rechazo - f_paso) / (fs / 2)
    n_coef, beta = signal.kaiserord(atenuacion_db, ancho)
    n_coef |= 1
    b = signal.firwin(n_coef, (f_paso + f_rechazo) / 2, window=('kaiser', beta), fs=fs)
    return b, beta


def disenar_iir(f_paso, f_rechazo, rizado_db, atenuacion_db, fs):
    """Compara tres familias con las mismas especificaciones; devuelve orden y SOS."""
    especificaciones = dict(gpass=rizado_db, gstop=atenuacion_db, fs=fs)
    resultado = {}
    for nombre, calcular_orden, construir in [
        ("Butterworth", signal.buttord, signal.butter),
        ("Chebyshev I", signal.cheb1ord, signal.cheby1),
        ("Elíptico", signal.ellipord, signal.ellip),
    ]:
        orden, wn = calcular_orden(f_paso, f_rechazo, **especificaciones)
        opciones = dict(fs=fs, output="sos")
        if nombre != "Butterworth":
            opciones["rp"] = rizado_db
        if nombre == "Elíptico":
            opciones["rs"] = atenuacion_db
        resultado[nombre] = (orden, construir(orden, Wn=wn, **opciones))
    return resultado


# ---------------------------------------------------------------------------
# Caracterización
# ---------------------------------------------------------------------------


def respuesta_frecuencia(b, a=1.0, fs=1.0, n_puntos=8192):
    """Devuelve f (Hz), H complejo, magnitud (dB), fase desenvuelta (rad) y retardo de grupo (muestras).

    El retardo de grupo no está definido en los ceros sobre el círculo unitario, así
    que se deja en NaN donde la magnitud cae por debajo de -40 dB.
    """
    f, H = signal.freqz(b, a, worN=n_puntos, fs=fs)
    mag_db = 20 * np.log10(np.maximum(np.abs(H), 1e-12))
    fase = np.unwrap(np.angle(H))
    with warnings.catch_warnings():
        warnings.simplefilter('ignore')  # group_delay avisa en los ceros del círculo unitario
        _, gd = signal.group_delay((b, a), w=f, fs=fs)
    gd = np.where(mag_db > -40, gd, np.nan)
    return f, H, mag_db, fase, gd


def medir_especificacion(b, a, fs, f_paso, f_rechazo, n_puntos=16384):
    """Mide el rizado pico a pico en la banda de paso y la atenuación mínima en la de rechazo (dB)."""
    f, H = signal.freqz(b, a, worN=n_puntos, fs=fs)
    mag = np.abs(H)
    paso = mag[f <= f_paso]
    rechazo = mag[f >= f_rechazo]
    rizado_db = 20 * np.log10(paso.max() / paso.min())
    atenuacion_db = -20 * np.log10(rechazo.max() / paso.max())
    return float(rizado_db), float(atenuacion_db)


def polos_ceros(b, a=1.0):
    """Ceros y polos de H(z) = B(z)/A(z) escrita en potencias positivas de z.

    Para un FIR de orden M, H(z) = (b0 z^M + ... + bM)/z^M: M polos en z = 0.
    """
    b = np.atleast_1d(np.asarray(b, dtype=float))
    a = np.atleast_1d(np.asarray(a, dtype=float))
    orden = max(len(b), len(a)) - 1
    b = np.concatenate([b, np.zeros(orden + 1 - len(b))])
    a = np.concatenate([a, np.zeros(orden + 1 - len(a))])
    return np.roots(b), np.roots(a) if np.any(a[1:]) else np.zeros(orden)


def es_estable(polos):
    """Un sistema causal es estable si todos sus polos están dentro del círculo unitario."""
    return bool(np.all(np.abs(polos) < 1))
