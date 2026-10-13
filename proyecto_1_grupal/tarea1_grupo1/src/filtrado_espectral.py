"""Reducción espectral adaptativa por bloques (apartado 2.4).

Hann -> rFFT -> atenuación -> irFFT -> Hann -> reconstrucción solapada.
Un umbral adaptativo selecciona los componentes de ruido en cada bloque.
Las frecuencias inferiores a frecuencia_minima quedan protegidas.

cargar_caso() lee los datos. filtrar_senal() procesa muestras.
evaluar_filtro(clean, noise, fs, ...) mide resultados con cualquier señal.
La referencia limpia solo interviene en la evaluación.
"""

import json
from numbers import Real
from pathlib import Path
from time import perf_counter

import numpy as np


# ---------------------------------------------------------------------------
# Casos de prueba y utilidades
# ---------------------------------------------------------------------------

def cargar_caso(caso, raiz=None):
    """Lee una vez el CSV y su configuración; no modifica los datos."""
    raiz = Path(raiz) if raiz is not None else Path(__file__).resolve().parents[1]
    configs = json.loads((raiz / "metadatos/configuraciones.json").read_text(encoding="utf-8"))
    if caso not in configs:
        raise ValueError(f"Caso desconocido: {caso}. Opciones: {', '.join(configs)}")
    muestras = np.loadtxt(raiz / "resultados/muestras" / f"{caso}_muestras.csv",
                         delimiter=",", skiprows=1, ndmin=2)
    if muestras.shape[1] != 4:
        raise ValueError("El CSV debe contener tiempo, limpia, ruido y contaminada.")
    if not np.all(np.isfinite(muestras)):
        raise ValueError("El CSV contiene NaN o infinito.")
    if not np.allclose(muestras[:, 1] + muestras[:, 2], muestras[:, 3],
                       rtol=1e-12, atol=1e-14):
        raise ValueError("La señal contaminada no coincide con limpia + ruido.")
    return {"t": muestras[:, 0], "clean": muestras[:, 1],
            "noise": muestras[:, 2], "noisy": muestras[:, 3],
            "fs": configs[caso]["fs_Hz"], "configuracion": configs[caso]}


def _senal_real(entrada):
    """Valida muestras mono reales antes de convertirlas a float64."""
    x = np.asarray(entrada)
    if x.ndim != 1 or np.iscomplexobj(x):
        raise ValueError("entrada debe ser un arreglo unidimensional real.")
    x = np.asarray(x, dtype=np.float64)
    if not np.all(np.isfinite(x)):
        raise ValueError("entrada contiene NaN o infinito.")
    return x


def _energia(x):
    """Suma la energía de todas las muestras."""
    return float(np.sum(np.square(x, dtype=np.float64)))


def _relacion_db(numerador, denominador):
    if numerador == 0:
        return np.nan if denominador == 0 else -np.inf
    return np.inf if denominador == 0 else float(10 * np.log10(numerador / denominador))

# ---------------------------------------------------------------------------
# Validación de parámetros
# ---------------------------------------------------------------------------

def _validar_parametros(fs, tam_bloque, frecuencia_minima, ancho_hz,
                        factor, umbral_relativo):
    """Comprueba que la configuración permita procesar bloques reales."""
    if (isinstance(tam_bloque, (bool, np.bool_))
            or not isinstance(tam_bloque, (int, np.integer))
            or tam_bloque < 4 or tam_bloque & (tam_bloque - 1)):
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

# ---------------------------------------------------------------------------
# Detección y atenuación espectral
# ---------------------------------------------------------------------------

def _ganancia_espectral(X, frecuencias, frecuencia_minima, ancho_hz,
                        factor, umbral_relativo):
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
        seleccion = np.convolve(
            seleccion.astype(int), np.ones(2 * radio + 1, dtype=int),
            mode="same",
        ) > 0

    # La expansión nunca invade la región protegida.
    ganancia[seleccion & region] = factor
    return ganancia, float(frecuencias[pico])

# ---------------------------------------------------------------------------
# Filtrado y reconstrucción por bloques
# ---------------------------------------------------------------------------

def _reconstruir_bloque(espectro, ganancia, ventana):
    """Aplica la atenuación, la IFFT y la ventana de reconstrucción."""
    return np.fft.irfft(espectro * ganancia, n=len(ventana)) * ventana


def filtrar_bloque(bloque, frecuencias, ventana, frecuencia_minima=1600,
                  ancho_hz=100, factor=0.1, umbral_relativo=0.05):
    """Procesa un bloque y devuelve salida, ganancias y frecuencia estimada.

    frecuencias y ventana se preparan una vez en filtrar_senal() y se reutilizan.
    La salida está ponderada por Hann: debe reconstruirse con los otros bloques.
    """
    espectro = np.fft.rfft(bloque * ventana)
    ganancia, estimada = _ganancia_espectral(
        espectro, frecuencias, frecuencia_minima, ancho_hz, factor,
        umbral_relativo,
    )
    salida = _reconstruir_bloque(espectro, ganancia, ventana)
    return salida, ganancia, estimada


def _normalizar_salida(salida, pesos, tam_bloque, longitud):
    """Quita el relleno y compensa los pesos de los bloques superpuestos."""
    fin = tam_bloque + longitud
    return salida[tam_bloque:fin] / pesos[tam_bloque:fin]


def filtrar_senal(entrada, fs, tam_bloque=1024, frecuencia_minima=1600,
                  ancho_hz=100, factor=0.1,
                  umbral_relativo=0.05, devolver_detalles=False):
    """Procesa una señal real con Hann y 50 % de solapamiento.

    Conserva longitud y escala, sin recortar amplitudes. factor=1 comprueba
    reconstrucción sin atenuación. Si devolver_detalles=True, devuelve
    (salida, detalles), con las ganancias de cada bloque para su evaluación.
    """
    x = _senal_real(entrada)
    _validar_parametros(fs, tam_bloque, frecuencia_minima, ancho_hz,
                        factor, umbral_relativo)
    t0 = perf_counter()
    ventana = np.hanning(tam_bloque)
    ventana_cuadrada = ventana ** 2
    frecuencias = np.fft.rfftfreq(tam_bloque, d=1 / fs)
    extendida = np.pad(x, (tam_bloque, tam_bloque))
    salida = np.zeros(len(extendida))
    pesos = np.zeros(len(extendida))
    salto = tam_bloque // 2
    inicios = range(0, len(extendida) - tam_bloque + 1, salto) if len(x) else range(0)
    ganancias = np.empty((len(inicios), len(frecuencias))) if devolver_detalles else None
    estimadas = np.empty(len(inicios)) if devolver_detalles else None

    for i, inicio in enumerate(inicios):
        fin = inicio + tam_bloque
        filtrado, ganancia, estimada = filtrar_bloque(
            extendida[inicio:fin], frecuencias, ventana, frecuencia_minima,
            ancho_hz, factor, umbral_relativo,
        )
        salida[inicio:fin] += filtrado
        pesos[inicio:fin] += ventana_cuadrada
        if devolver_detalles:
            ganancias[i], estimadas[i] = ganancia, estimada

    resultado = _normalizar_salida(salida, pesos, tam_bloque, len(x))
    if not devolver_detalles:
        return resultado
    memoria = sum(a.nbytes for a in (extendida, salida, pesos, ventana,
                                     ventana_cuadrada, frecuencias, ganancias, estimadas))
    if len(inicios):
        memoria += len(frecuencias) * (np.dtype(complex).itemsize + ganancia.itemsize)
    detalles = _detalles_filtrado(
        ganancias, estimadas, tam_bloque, perf_counter() - t0, memoria
    )
    return resultado, detalles


def _referencia_filtrada(referencia, detalles):
    """Repite las decisiones de la mezcla sobre la referencia limpia.

    Conserva las mismas ganancias: reestimar el ruido a partir de la señal
    limpia cambiaría el filtro y daría métricas incorrectas.
    """
    n = detalles["tam_bloque"]
    ventana = np.hanning(n)
    extendida = np.pad(referencia, (n, n))
    salida = np.zeros(len(extendida))
    pesos = np.zeros(len(extendida))
    for i, ganancia in enumerate(detalles["ganancias"]):
        inicio = i * detalles["salto"]
        fin = inicio + n
        espectro = np.fft.rfft(extendida[inicio:fin] * ventana)
        salida[inicio:fin] += _reconstruir_bloque(espectro, ganancia, ventana)
        pesos[inicio:fin] += ventana ** 2
    return _normalizar_salida(salida, pesos, n, len(referencia))

# ---------------------------------------------------------------------------
# Métricas
# ---------------------------------------------------------------------------

def _detalles_filtrado(ganancias, estimadas, tam_bloque, tiempo, memoria):
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


def _calcular_metricas(clean, noise, salida, util):
    """Compara la mezcla filtrada con la referencia y separa sus errores."""
    energia_util = _energia(clean)
    snr_entrada = _relacion_db(energia_util, _energia(noise))
    snr_salida = _relacion_db(energia_util, _energia(clean - salida))
    ruido_salida = salida - util
    return {
        "snr_entrada_dB": snr_entrada,
        "snr_salida_dB": snr_salida,
        "delta_snr_dB": snr_salida - snr_entrada,
        "mse": _energia(clean - salida) / len(clean),
        "energia_util_conservada_pct": 100 * _energia(util) / energia_util
        if energia_util else np.nan,
        "snr_distorsion_util_dB": _relacion_db(energia_util, _energia(clean - util)),
        "atenuacion_ruido_dB": _relacion_db(_energia(noise), _energia(ruido_salida)),
    }


def _atenuacion_interferencia(noise, ruido_salida, fs, ancho_hz):
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
    return _relacion_db(
        np.sum(peso[banda] * np.abs(R[banda]) ** 2),
        np.sum(peso[banda] * np.abs(R_salida[banda]) ** 2),
    )


def evaluar_filtro(clean, noise, fs, **parametros):
    """Evalúa el filtro espectral con cualquier pareja de señal limpia y ruido.

    Recibe muestras, no nombres de casos ni archivos. Los parámetros adicionales
    se pasan a filtrar_senal(). La mezcla clean + noise determina las ganancias;
    la referencia sirve únicamente para medir distorsión y ruido residual.
    Tiempo y memoria corresponden al prototipo offline, no al microcontrolador.
    La memoria cuenta arreglos explícitos, excluyendo temporales de NumPy.
    """
    clean, noise = _senal_real(clean), _senal_real(noise)
    if not len(clean) or len(clean) != len(noise):
        raise ValueError("clean y noise deben tener la misma longitud, no vacía.")
    parametros = dict(parametros)
    parametros.pop("devolver_detalles", None)
    salida, detalles = filtrar_senal(
        clean + noise, fs, devolver_detalles=True, **parametros
    )
    util = _referencia_filtrada(clean, detalles)
    metricas = _calcular_metricas(clean, noise, salida, util)
    metricas["atenuacion_interferencia_dB"] = _atenuacion_interferencia(
        noise, salida - util, fs, parametros.get("ancho_hz", 100)
    )
    for clave in ("tiempo_por_bloque_us", "memoria_trabajo_bytes", "tam_bloque", "salto"):
        metricas[clave] = detalles[clave]
    metricas["salida"] = salida
    return metricas

# ---------------------------------------------------------------------------
# Ejemplo de ejecución
# ---------------------------------------------------------------------------

def main():
    """Carga los casos y los evalúa; los archivos no forman parte del filtro."""
    casos = {nombre: cargar_caso(nombre)
             for nombre in ("caso_1", "caso_2", "caso_3")}
    print(f"{'Caso':8} {'SNR entrada':>12} {'SNR salida':>12} {'Delta SNR':>12} {'MSE':>12}")
    for nombre, datos in casos.items():
        m = evaluar_filtro(datos["clean"], datos["noise"], datos["fs"])
        print(f"{nombre:8} {m['snr_entrada_dB']:12.3f} "
              f"{m['snr_salida_dB']:12.3f} {m['delta_snr_dB']:12.3f} {m['mse']:12.3e}")

    print("\nCaso 3: buscar desde 600 Hz invade la banda util.")
    datos = casos["caso_3"]
    for factor in (0.8, 0.1):
        m = evaluar_filtro(datos["clean"], datos["noise"], datos["fs"],
                           frecuencia_minima=600, factor=factor)
        print(f"factor={factor}: atenuacion ruido={m['atenuacion_ruido_dB']:.2f} dB; "
              f"energia util conservada={m['energia_util_conservada_pct']:.2f} %")


if __name__ == "__main__":
    main()
