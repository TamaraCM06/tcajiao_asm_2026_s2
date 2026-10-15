"""Evaluación de filtros mediante funciones inyectadas; no depende de sus módulos."""

import numpy as np

from .metricas import calcular_metricas, atenuacion_interferencia
from ..filtros.bloques_espectrales import senal_real

# ---------------------------------------------------------------------------
# Filtro temporal lineal
# ---------------------------------------------------------------------------


def evaluar_temporal(clean, noise, filtrar, retardo):
    """Alinea el filtro lineal y mide señal útil y ruido por separado."""
    longitud = len(clean) - retardo
    util = filtrar(clean)[retardo : retardo + longitud]
    ruido = filtrar(noise)[retardo : retardo + longitud]
    salida = util + ruido
    metricas = calcular_metricas(
        clean[:longitud], noise[:longitud], salida, util, ruido_salida=ruido
    )
    return {**metricas, "salida": salida}


# ---------------------------------------------------------------------------
# Filtro espectral adaptativo
# ---------------------------------------------------------------------------


def evaluar_espectral(
    clean, noise, fs, filtrar, reconstruir_referencia, *, longitud_evaluacion=None, **parametros
):
    """Evalúa el filtro espectral con cualquier pareja de señal limpia y ruido.

    Recibe muestras, no nombres de casos ni archivos. Los parámetros adicionales
    se pasan a filtrar_senal(). La mezcla clean + noise determina las ganancias;
    la referencia sirve únicamente para medir distorsión y ruido residual.
    longitud_evaluacion limita las métricas al tramo inicial indicado; el filtro
    procesa toda la entrada y siempre devuelve la salida completa.
    Tiempo y memoria corresponden al prototipo offline, no al microcontrolador.
    La memoria cuenta arreglos explícitos, excluyendo temporales de NumPy.
    """
    clean, noise = senal_real(clean), senal_real(noise)
    if not len(clean) or len(clean) != len(noise):
        raise ValueError("clean y noise deben tener la misma longitud, no vacía.")
    longitud = len(clean) if longitud_evaluacion is None else longitud_evaluacion
    if (
        isinstance(longitud, (bool, np.bool_))
        or not isinstance(longitud, (int, np.integer))
        or not 1 <= longitud <= len(clean)
    ):
        raise ValueError("longitud_evaluacion debe ser un entero entre 1 y la longitud de entrada.")
    parametros = dict(parametros)
    parametros.pop("devolver_detalles", None)
    salida, detalles = filtrar(clean + noise, fs, devolver_detalles=True, **parametros)
    util = reconstruir_referencia(clean, detalles)
    metricas = calcular_metricas(
        clean[:longitud], noise[:longitud], salida[:longitud], util[:longitud]
    )
    metricas["atenuacion_interferencia_dB"] = atenuacion_interferencia(
        noise[:longitud], salida[:longitud] - util[:longitud], fs, parametros.get("ancho_hz", 100)
    )
    for clave in ("tiempo_por_bloque_us", "memoria_trabajo_bytes", "tam_bloque", "salto"):
        metricas[clave] = detalles[clave]
    metricas["salida"] = salida
    metricas["muestras_evaluadas"] = int(longitud)
    return metricas
