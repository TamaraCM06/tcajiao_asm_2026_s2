"""Filtro temporal FIR/IIR: diseño, implementación propia y análisis (sección 2.3).

La biblioteca (scipy.signal) se usa solo para diseñar los coeficientes y como
referencia. El filtrado se hace con la ecuación de diferencias implementada aquí:

    y[n] = sum_{k=0}^{M} b[k] x[n-k] - sum_{k=1}^{P} a[k] y[n-k]      (a[0] = 1)
"""

import warnings
from pathlib import Path

import numpy as np
from scipy import signal


# ---------------------------------------------------------------------------
# Casos de prueba y utilidades
# ---------------------------------------------------------------------------

def cargar_caso(raiz, caso):
    """Lee las señales de un caso desde resultados/muestras/<caso>_muestras.csv.

    El CSV lo escribe el generador del notebook. Se usa en lugar de los WAV porque
    conserva las muestras en punto flotante, sin la cuantización a 16 bits.
    Devuelve un diccionario con t, clean, noise y noisy.
    """
    ruta = Path(raiz)/'resultados'/'muestras'/f'{caso}_muestras.csv'
    d = np.loadtxt(ruta, delimiter=',', skiprows=1)
    return {'t': d[:, 0], 'clean': d[:, 1], 'noise': d[:, 2], 'noisy': d[:, 3]}


def snr_db(clean, observed):
    """SNR en dB de observed respecto a la referencia clean (ecuación 2 del enunciado)."""
    return 10*np.log10(np.sum(clean**2)/np.sum((observed - clean)**2))


def pcm16(x):
    """Convierte a PCM de 16 bits para exportar WAV (igual que el generador del notebook)."""
    return np.int16(np.clip(x, -1, 1)*32767)


def espectro_db(x, fs):
    """Magnitud de la FFT con ventana Hann en dB (escalada para leer la amplitud de un tono)."""
    w = signal.get_window('hann', len(x), fftbins=True)
    X = np.fft.rfft(x*w)
    f = np.fft.rfftfreq(len(x), 1/fs)
    return f, 20*np.log10(np.maximum(np.abs(X)/(np.sum(w)/2), 1e-12))


def energia_en_banda(x, fs, f_lo, f_hi):
    """Energía de x (suma de x^2, vía Parseval) contenida entre f_lo y f_hi Hz."""
    X = np.fft.rfft(x)
    f = np.fft.rfftfreq(len(x), 1/fs)
    P = np.abs(X)**2
    # rfft: los bins interiores representan dos bins del espectro completo
    peso = np.full(len(P), 2.0); peso[0] = 1.0
    if len(x) % 2 == 0: peso[-1] = 1.0
    sel = (f >= f_lo) & (f <= f_hi)
    return float(np.sum(peso[sel]*P[sel])/len(x))


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
    ancho = (f_rechazo - f_paso)/(fs/2)
    n_coef, beta = signal.kaiserord(atenuacion_db, ancho)
    n_coef |= 1
    b = signal.firwin(n_coef, (f_paso + f_rechazo)/2, window=('kaiser', beta), fs=fs)
    return b, beta


# ---------------------------------------------------------------------------
# Implementación propia de la ecuación de diferencias
# ---------------------------------------------------------------------------

def ecuacion_diferencias(b, a, x):
    """Aplica la ecuación de diferencias muestra por muestra (forma directa I).

    Implementación de referencia, válida para FIR (a = [1]) e IIR. Las condiciones
    iniciales son nulas, igual que scipy.signal.lfilter sin zi.
    """
    b = np.asarray(b, dtype=float)
    a = np.atleast_1d(np.asarray(a, dtype=float))
    b, a = b/a[0], a/a[0]
    M, P = len(b) - 1, len(a) - 1
    x_hist = np.zeros(M + 1)            # x[n], x[n-1], ..., x[n-M]
    y_hist = np.zeros(max(P, 1))        # y[n-1], ..., y[n-P]
    y = np.empty(len(x))
    for n, xn in enumerate(x):
        x_hist[1:] = x_hist[:-1]; x_hist[0] = xn
        yn = np.dot(b, x_hist)
        if P:
            yn -= np.dot(a[1:], y_hist[:P])
            y_hist[1:] = y_hist[:-1]; y_hist[0] = yn
        y[n] = yn
    return y


class FIRPorBloques:
    """FIR que procesa la señal por bloques y conserva su estado entre bloques.

    Imita la operación en el microcontrolador: llega un bloque de B muestras, se
    calcula y[n] = sum_k b[k] x[n-k] usando las últimas M muestras del bloque anterior
    (línea de retardo) y se guarda el final del bloque para el siguiente.
    """

    def __init__(self, b):
        self.b = np.asarray(b, dtype=float)
        self.reiniciar()

    def reiniciar(self):
        """Vacía la línea de retardo (condiciones iniciales nulas)."""
        self.estado = np.zeros(len(self.b) - 1)

    def procesar(self, bloque):
        """Filtra un bloque y actualiza la línea de retardo."""
        M = len(self.b) - 1
        B = len(bloque)
        x_ext = np.concatenate([self.estado, bloque])        # x[n-M] ... x[n+B-1]
        y = np.zeros(B)
        for k, bk in enumerate(self.b):                      # suma de la ecuación de diferencias
            y += bk*x_ext[M - k:M - k + B]
        self.estado = x_ext[-M:] if M else self.estado
        return y


def filtrar_por_bloques(b, x, tam_bloque=256):
    """Filtra x completa con FIRPorBloques en bloques de tam_bloque muestras."""
    fir = FIRPorBloques(b)
    return np.concatenate([fir.procesar(x[i:i + tam_bloque]) for i in range(0, len(x), tam_bloque)])


# ---------------------------------------------------------------------------
# Análisis
# ---------------------------------------------------------------------------

def respuesta_frecuencia(b, a=1.0, fs=1.0, n_puntos=8192):
    """Devuelve f (Hz), H complejo, magnitud (dB), fase desenvuelta (rad) y retardo de grupo (muestras).

    El retardo de grupo no está definido en los ceros sobre el círculo unitario, así
    que se deja en NaN donde la magnitud cae por debajo de -40 dB.
    """
    f, H = signal.freqz(b, a, worN=n_puntos, fs=fs)
    mag_db = 20*np.log10(np.maximum(np.abs(H), 1e-12))
    fase = np.unwrap(np.angle(H))
    with warnings.catch_warnings():
        warnings.simplefilter('ignore')     # group_delay avisa en los ceros del círculo unitario
        _, gd = signal.group_delay((b, a), w=f, fs=fs)
    gd = np.where(mag_db > -40, gd, np.nan)
    return f, H, mag_db, fase, gd


def medir_especificacion(b, a, fs, f_paso, f_rechazo, n_puntos=16384):
    """Mide el rizado pico a pico en la banda de paso y la atenuación mínima en la de rechazo (dB)."""
    f, H = signal.freqz(b, a, worN=n_puntos, fs=fs)
    mag = np.abs(H)
    paso = mag[f <= f_paso]
    rechazo = mag[f >= f_rechazo]
    rizado_db = 20*np.log10(paso.max()/paso.min())
    atenuacion_db = -20*np.log10(rechazo.max()/paso.max())
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


# ---------------------------------------------------------------------------
# Métricas
# ---------------------------------------------------------------------------

def _energia(x):
    return float(np.sum(np.square(x, dtype=np.float64)))


def evaluar_filtro(clean, noise, filtrar, retardo):
    """Métricas de un filtro lineal sobre un caso de prueba.

    filtrar(x) aplica el filtro. Como el sistema es lineal, la salida de la mezcla es
    filtrar(clean) + filtrar(noise), lo que permite separar cuánto ruido se elimina
    de cuánto se distorsiona la señal útil. La salida se compara con la referencia
    adelantándola retardo muestras (retardo de grupo del filtro).
    """
    L = len(clean) - retardo
    s = clean[:L]
    y_util = filtrar(clean)[retardo:retardo + L]
    y_ruido = filtrar(noise)[retardo:retardo + L]
    s_hat = y_util + y_ruido
    error = s - s_hat
    snr_in = 10*np.log10(_energia(s)/_energia(noise[:L]))
    snr_out = 10*np.log10(_energia(s)/_energia(error))
    return {
        'snr_entrada_dB': snr_in,
        'snr_salida_dB': snr_out,
        'delta_snr_dB': snr_out - snr_in,
        'mse': _energia(error)/L,
        'energia_util_conservada_pct': 100*_energia(y_util)/_energia(s),
        'snr_distorsion_util_dB': 10*np.log10(_energia(s)/_energia(s - y_util)),
        'atenuacion_ruido_dB': 10*np.log10(_energia(noise[:L])/_energia(y_ruido)),
        'salida': s_hat,
    }
