"""Filtrado temporal por ecuación de diferencias y bloques con estado.

Los imports de diseño y utilidades conservan la interfaz histórica."""

import numpy as np

from ..datos.archivos import cargar_caso as _cargar_caso, pcm16
from ..mediciones.metricas import snr_db
from ..senales.analisis_fourier import espectro_db, energia_en_banda
from .diseno_temporal import (
    disenar_fir_kaiser,
    respuesta_frecuencia,
    medir_especificacion,
    polos_ceros,
    es_estable,
)
from ..mediciones.evaluacion import evaluar_temporal as evaluar_filtro

# ---------------------------------------------------------------------------
# Compatibilidad de lectura
# ---------------------------------------------------------------------------


def cargar_caso(raiz, caso):
    """Conserva el orden histórico de argumentos y las cuatro claves de muestras."""
    return _cargar_caso(caso, raiz, incluir_configuracion=False)


# ---------------------------------------------------------------------------
# Filtrado temporal
# ---------------------------------------------------------------------------


def ecuacion_diferencias(b, a, x):
    """Aplica la ecuación de diferencias muestra por muestra (forma directa I).

    Implementación de referencia, válida para FIR (a = [1]) e IIR. Las condiciones
    iniciales son nulas, igual que scipy.signal.lfilter sin zi.
    """
    b = np.asarray(b, dtype=float)
    a = np.atleast_1d(np.asarray(a, dtype=float))
    b, a = b / a[0], a / a[0]
    M, P = len(b) - 1, len(a) - 1
    x_hist = np.zeros(M + 1)  # x[n], x[n-1], ..., x[n-M]
    y_hist = np.zeros(max(P, 1))  # y[n-1], ..., y[n-P]
    y = np.empty(len(x))
    for n, xn in enumerate(x):
        x_hist[1:] = x_hist[:-1]
        x_hist[0] = xn
        yn = np.dot(b, x_hist)
        if P:
            yn -= np.dot(a[1:], y_hist[:P])
            y_hist[1:] = y_hist[:-1]
            y_hist[0] = yn
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
        x_ext = np.concatenate([self.estado, bloque])  # x[n-M] ... x[n+B-1]
        y = np.zeros(B)
        for k, bk in enumerate(self.b):  # suma de la ecuación de diferencias
            y += bk * x_ext[M - k : M - k + B]
        self.estado = x_ext[-M:] if M else self.estado
        return y


def filtrar_por_bloques(b, x, tam_bloque=256):
    """Filtra x completa con FIRPorBloques en bloques de tam_bloque muestras."""
    fir = FIRPorBloques(b)
    return np.concatenate(
        [fir.procesar(x[i : i + tam_bloque]) for i in range(0, len(x), tam_bloque)]
    )
