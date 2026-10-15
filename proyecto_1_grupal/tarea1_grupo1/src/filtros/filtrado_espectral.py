"""Detección adaptativa y coordinación del filtro espectral FFT/IFFT.

Las funciones de reconstrucción, evaluación y archivos se delegan a sus módulos."""

from numbers import Real
from time import perf_counter
import numpy as np

from ..datos.archivos import cargar_caso
from .bloques_espectrales import (
    senal_real as _senal_real,
    preparar_reconstruccion,
    reconstruir_bloque as _reconstruir_bloque,
    normalizar_salida as _normalizar_salida,
    aplicar_ganancias as _referencia_filtrada,
    detalles_filtrado as _detalles_filtrado,
)
from ..mediciones.evaluacion import evaluar_espectral

# ---------------------------------------------------------------------------
# Parámetros y selección espectral
# ---------------------------------------------------------------------------


def _validar_parametros(fs, tam_bloque, frecuencia_minima, ancho_hz, factor, umbral_relativo):
    """Comprueba que la configuración permita procesar bloques reales."""
    if (
        isinstance(tam_bloque, (bool, np.bool_))
        or not isinstance(tam_bloque, (int, np.integer))
        or tam_bloque < 4
        or tam_bloque & (tam_bloque - 1)
    ):
        raise ValueError("tam_bloque debe ser una potencia de dos >= 4.")
    parametros = [fs, frecuencia_minima, ancho_hz, factor, umbral_relativo]
    if not all(isinstance(v, Real) and np.isfinite(v) for v in parametros):
        raise ValueError("Los parámetros numéricos deben ser reales y finitos.")
    if fs <= 0 or not 0 <= frecuencia_minima < fs / 2:
        raise ValueError("Se requiere fs > 0 y 0 <= frecuencia_minima < fs/2.")
    if not 0 <= ancho_hz <= fs / 2 or not 0 <= factor <= 1:
        raise ValueError("Se requiere 0 <= ancho_hz <= fs/2 y 0 <= factor <= 1.")
    if not 0 < umbral_relativo <= 1:
        raise ValueError("Se requiere 0 < umbral_relativo <= 1.")


def _ganancia_espectral(X, frecuencias, frecuencia_minima, ancho_hz, factor, umbral_relativo):
    """Estima ruido y devuelve una ganancia real para cada bin de rFFT."""
    energia = np.abs(X) ** 2
    ganancia = np.ones(len(X))
    region = frecuencias >= frecuencia_minima
    indices = np.flatnonzero(region)
    pico = indices[np.argmax(energia[indices])]

    # Evita interpretar silencio o fuga muy débil como una interferencia.
    if energia.max() == 0 or energia[pico] < 1e-3 * energia.max():
        return ganancia, np.nan

    # El umbral se vuelve a estimar con la energía de cada bloque.
    umbral = max(umbral_relativo * energia[pico], 1e-3 * energia.max())
    seleccion = region & (energia >= umbral)
    radio = int(np.floor(ancho_hz / (2 * (frecuencias[1] - frecuencias[0]))))
    if radio:
        seleccion = (
            np.convolve(
                seleccion.astype(int),
                np.ones(2 * radio + 1, dtype=int),
                mode="same",
            )
            > 0
        )

    # La expansión nunca invade la región protegida.
    ganancia[seleccion & region] = factor
    return ganancia, float(frecuencias[pico])


# ---------------------------------------------------------------------------
# Filtrado
# ---------------------------------------------------------------------------


def filtrar_bloque(
    bloque,
    frecuencias,
    ventana,
    frecuencia_minima=1600,
    ancho_hz=100,
    factor=0.1,
    umbral_relativo=0.05,
):
    """Procesa un bloque y devuelve salida, ganancias y frecuencia estimada.

    frecuencias y ventana se preparan una vez en filtrar_senal() y se reutilizan.
    La salida está ponderada por Hann: debe reconstruirse con los otros bloques.
    """
    espectro = np.fft.rfft(bloque * ventana)
    ganancia, estimada = _ganancia_espectral(
        espectro,
        frecuencias,
        frecuencia_minima,
        ancho_hz,
        factor,
        umbral_relativo,
    )
    salida = _reconstruir_bloque(espectro, ganancia, ventana)
    return salida, ganancia, estimada


def filtrar_senal(
    entrada,
    fs,
    tam_bloque=1024,
    frecuencia_minima=1600,
    ancho_hz=100,
    factor=0.1,
    umbral_relativo=0.05,
    devolver_detalles=False,
):
    """Procesa una señal real con Hann y 50 % de solapamiento.

    Conserva longitud y escala, sin recortar amplitudes. factor=1 comprueba
    reconstrucción sin atenuación. Si devolver_detalles=True, devuelve
    (salida, detalles), con las ganancias de cada bloque para su evaluación.
    """
    x = _senal_real(entrada)
    _validar_parametros(fs, tam_bloque, frecuencia_minima, ancho_hz, factor, umbral_relativo)
    t0 = perf_counter()
    ventana, extendida, salida, pesos = preparar_reconstruccion(x, tam_bloque)
    ventana_cuadrada = ventana**2
    frecuencias = np.fft.rfftfreq(tam_bloque, d=1 / fs)
    salto = tam_bloque // 2
    inicios = range(0, len(extendida) - tam_bloque + 1, salto) if len(x) else range(0)
    ganancias = np.empty((len(inicios), len(frecuencias))) if devolver_detalles else None
    estimadas = np.empty(len(inicios)) if devolver_detalles else None

    for i, inicio in enumerate(inicios):
        fin = inicio + tam_bloque
        filtrado, ganancia, estimada = filtrar_bloque(
            extendida[inicio:fin],
            frecuencias,
            ventana,
            frecuencia_minima,
            ancho_hz,
            factor,
            umbral_relativo,
        )
        salida[inicio:fin] += filtrado
        pesos[inicio:fin] += ventana_cuadrada
        if devolver_detalles:
            ganancias[i], estimadas[i] = ganancia, estimada

    resultado = _normalizar_salida(salida, pesos, tam_bloque, len(x))
    if not devolver_detalles:
        return resultado
    memoria = sum(
        a.nbytes
        for a in (
            extendida,
            salida,
            pesos,
            ventana,
            ventana_cuadrada,
            frecuencias,
            ganancias,
            estimadas,
        )
    )
    if len(inicios):
        memoria += len(frecuencias) * (np.dtype(complex).itemsize + ganancia.itemsize)
    detalles = _detalles_filtrado(ganancias, estimadas, tam_bloque, perf_counter() - t0, memoria)
    return resultado, detalles


# ---------------------------------------------------------------------------
# Interfaz de evaluación
# ---------------------------------------------------------------------------


def evaluar_filtro(clean, noise, fs, *, longitud_evaluacion=None, **parametros):
    """Evalúa el tramo inicial solicitado y devuelve siempre la salida completa.

    Las decisiones se estiman desde la mezcla y se reutilizan sobre la referencia.
    Tiempo y memoria corresponden al prototipo offline, no al microcontrolador.
    """
    return evaluar_espectral(
        clean,
        noise,
        fs,
        filtrar_senal,
        _referencia_filtrada,
        longitud_evaluacion=longitud_evaluacion,
        **parametros,
    )


# ---------------------------------------------------------------------------
# Ejemplo de ejecución
# ---------------------------------------------------------------------------


def main():
    """Carga los casos y los evalúa; los archivos no forman parte del filtro."""
    casos = {nombre: cargar_caso(nombre) for nombre in ("caso_1", "caso_2", "caso_3")}
    print(f"{'Caso':8} {'SNR entrada':>12} {'SNR salida':>12} {'Delta SNR':>12} {'MSE':>12}")
    for nombre, datos in casos.items():
        m = evaluar_filtro(datos["clean"], datos["noise"], datos["fs"])
        print(
            f"{nombre:8} {m['snr_entrada_dB']:12.3f} "
            f"{m['snr_salida_dB']:12.3f} {m['delta_snr_dB']:12.3f} {m['mse']:12.3e}"
        )

    print("\nCaso 3: buscar desde 600 Hz invade la banda util.")
    datos = casos["caso_3"]
    for factor in (0.8, 0.1):
        m = evaluar_filtro(
            datos["clean"], datos["noise"], datos["fs"], frecuencia_minima=600, factor=factor
        )
        print(
            f"factor={factor}: atenuacion ruido={m['atenuacion_ruido_dB']:.2f} dB; "
            f"energia util conservada={m['energia_util_conservada_pct']:.2f} %"
        )


if __name__ == "__main__":
    main()
