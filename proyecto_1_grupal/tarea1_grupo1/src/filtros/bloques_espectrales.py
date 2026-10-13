"""Ventanas y reconstrucción solapada del procesamiento espectral."""

import numpy as np

# ---------------------------------------------------------------------------
# Preparación
# ---------------------------------------------------------------------------


def senal_real(entrada):
    """Valida muestras mono reales antes de convertirlas a float64."""
    x = np.asarray(entrada)
    if x.ndim != 1 or np.iscomplexobj(x):
        raise ValueError("entrada debe ser un arreglo unidimensional real.")
    x = np.asarray(x, dtype=np.float64)
    if not np.all(np.isfinite(x)):
        raise ValueError("entrada contiene NaN o infinito.")
    return x


def preparar_reconstruccion(x, tam_bloque):
    """Reserva Hann, entrada con relleno y acumuladores de salida y pesos."""
    ventana = np.hanning(tam_bloque)
    extendida = np.pad(x, (tam_bloque, tam_bloque))
    return ventana, extendida, np.zeros(len(extendida)), np.zeros(len(extendida))


# ---------------------------------------------------------------------------
# Síntesis y compensación de pesos
# ---------------------------------------------------------------------------


def reconstruir_bloque(espectro, ganancia, ventana):
    """Aplica la atenuación, la IFFT y la ventana de reconstrucción."""
    return np.fft.irfft(espectro * ganancia, n=len(ventana)) * ventana


def normalizar_salida(salida, pesos, tam_bloque, longitud):
    """Quita el relleno y compensa los pesos de los bloques superpuestos."""
    fin = tam_bloque + longitud
    return salida[tam_bloque:fin] / pesos[tam_bloque:fin]


def aplicar_ganancias(referencia, detalles):
    """Repite las decisiones de la mezcla sobre la referencia limpia.

    Conserva las mismas ganancias: reestimar el ruido a partir de la señal
    limpia cambiaría el filtro y daría métricas incorrectas.
    """
    n = detalles["tam_bloque"]
    ventana, extendida, salida, pesos = preparar_reconstruccion(referencia, n)
    ventana_cuadrada = ventana**2
    for i, ganancia in enumerate(detalles["ganancias"]):
        inicio = i * detalles["salto"]
        fin = inicio + n
        espectro = np.fft.rfft(extendida[inicio:fin] * ventana)
        salida[inicio:fin] += reconstruir_bloque(espectro, ganancia, ventana)
        pesos[inicio:fin] += ventana_cuadrada
    return normalizar_salida(salida, pesos, n, len(referencia))


# ---------------------------------------------------------------------------
# Información del procesamiento
# ---------------------------------------------------------------------------


def detalles_filtrado(ganancias, estimadas, tam_bloque, tiempo, memoria):
    """Registra decisiones, tiempo por bloque y memoria aproximada."""
    return {
        "ganancias": ganancias,
        "frecuencias_estimadas_Hz": estimadas,
        "tam_bloque": tam_bloque,
        "salto": tam_bloque // 2,
        "numero_bloques": len(ganancias),
        "tiempo_por_bloque_us": 1e6 * tiempo / max(len(ganancias), 1),
        "memoria_trabajo_bytes": memoria,
    }
