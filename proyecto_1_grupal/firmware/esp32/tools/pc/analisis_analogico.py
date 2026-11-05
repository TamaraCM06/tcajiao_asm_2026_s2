"""Amplitudes y respuesta Sallen-Key; no ajusta componentes para mejorar el resultado."""
import math
import numpy as np


def ganancia_teorica(frecuencias, modelo):
    """Calcula H(jw) del seguidor Sallen-Key con divisor de entrada independiente."""
    resistencia_1 = float(modelo["resistencia_1_ohm"])
    resistencia_2 = float(modelo["resistencia_2_ohm"])
    tierra = float(modelo["capacitor_tierra_nf"]) * 1e-9
    realimentacion = float(modelo["capacitor_realimentacion_nf"]) * 1e-9
    divisor = float(modelo["ganancia_divisor"])
    valores = (resistencia_1, resistencia_2, tierra, realimentacion, divisor)
    if not all(math.isfinite(valor) and valor > 0 for valor in valores):
        raise ValueError("Los componentes del modelo deben ser positivos y finitos")
    frecuencia = np.asarray(frecuencias, dtype=float)
    if np.any(~np.isfinite(frecuencia)) or np.any(frecuencia < 0):
        raise ValueError("Frecuencias invalidas")
    angular = 2 * np.pi * frecuencia
    denominador = 1 - angular ** 2 * resistencia_1 * resistencia_2 * tierra * realimentacion
    denominador = denominador + 1j * angular * tierra * (resistencia_1 + resistencia_2)
    return np.abs(divisor / denominador)


def amplitudes_componentes(voltios, frecuencia_muestreo, frecuencias):
    """Ajusta simultaneamente seno/coseno y DC; la fase inicial de cada bloque es libre."""
    voltios = np.asarray(voltios, dtype=float)
    frecuencias = np.asarray(frecuencias, dtype=float)
    if voltios.ndim != 1 or not np.all(np.isfinite(voltios)) or len(voltios) <= 2 * len(frecuencias) + 1:
        raise ValueError("Bloque de muestras invalido")
    if (not len(frecuencias) or not np.isfinite(frecuencia_muestreo) or frecuencia_muestreo <= 0 or
            len(np.unique(frecuencias)) != len(frecuencias) or np.any(~np.isfinite(frecuencias)) or
            np.any(frecuencias <= 0) or np.any(frecuencias >= frecuencia_muestreo / 2)):
        raise ValueError("Las frecuencias deben ser distintas y estar entre cero y Nyquist")
    tiempo = np.arange(len(voltios)) / frecuencia_muestreo
    columnas = [np.ones(len(voltios))]
    for frecuencia in frecuencias:
        columnas.extend((np.sin(2 * np.pi * frecuencia * tiempo), np.cos(2 * np.pi * frecuencia * tiempo)))
    matriz = np.column_stack(columnas)
    coeficientes, _, rango, _ = np.linalg.lstsq(matriz, voltios, rcond=None)
    if rango != matriz.shape[1]:
        raise ValueError("No se pueden separar las componentes con este bloque")
    amplitudes = np.hypot(coeficientes[1::2], coeficientes[2::2])
    residual = voltios - matriz @ coeficientes
    return amplitudes, float(coeficientes[0]), float(np.sqrt(np.mean(residual ** 2)))


def resumir_capturas(capturas, frecuencias):
    """Resume bloques separados sin concatenarlos ni atribuirles continuidad temporal."""
    if len(capturas) < 3:
        raise ValueError("Se requieren al menos tres capturas por punto")
    inicial = capturas[0]
    amplitudes, residuos, niveles_dc = [], [], []
    saturadas = 0
    for captura in capturas:
        if captura.fs != inicial.fs or captura.vref != inicial.vref:
            raise ValueError("Cambio la escala o el muestreo durante la medicion")
        if (captura.perdidos, captura.errores, captura.reinicios) != (inicial.perdidos, inicial.errores, inicial.reinicios):
            raise ValueError("La Pico registro perdidas, errores o reinicios durante la medicion")
        estimadas, nivel_dc, residuo = amplitudes_componentes(captura.voltios, captura.fs, frecuencias)
        amplitudes.append(estimadas)
        residuos.append(residuo)
        niveles_dc.append(nivel_dc)
        saturadas += sum(codigo in (0, 4095) for codigo in captura.codigos)
    amplitudes = np.asarray(amplitudes)
    medias = amplitudes.mean(axis=0)
    desviaciones = amplitudes.std(axis=0, ddof=1)
    limite_deteccion = max(2 * inicial.vref / 4095,
                          3 * float(np.mean(residuos)) * math.sqrt(2 / len(inicial.codigos)))
    return dict(amplitudes_v=medias.tolist(), desviaciones_v=desviaciones.tolist(),
                capturas=len(capturas), nivel_dc_v=float(np.mean(niveles_dc)),
                residuo_rms_v=float(np.mean(residuos)), saturadas=saturadas,
                limite_deteccion_v=limite_deteccion)


def comparar_respuesta(antes, despues, frecuencias, modelo):
    """Compara ganancias absolutas con el modelo sin recalibrar divisor ni frecuencia de corte."""
    teoricas = ganancia_teorica(frecuencias, modelo)
    filas = []
    for posicion, frecuencia in enumerate(frecuencias):
        entrada = antes["amplitudes_v"][posicion]
        salida = despues["amplitudes_v"][posicion]
        razones = []
        if antes["saturadas"] or despues["saturadas"]:
            razones.append("ADC saturado")
        if entrada <= antes["limite_deteccion_v"] or salida <= despues["limite_deteccion_v"]:
            razones.append("componente por debajo del limite de deteccion")
        variacion_entrada = 100 * antes["desviaciones_v"][posicion] / entrada if entrada else float("inf")
        variacion_salida = 100 * despues["desviaciones_v"][posicion] / salida if salida else float("inf")
        if max(variacion_entrada, variacion_salida) > modelo["variabilidad_maxima_amplitud_pct"]:
            razones.append("amplitud inestable")
        medida = salida / entrada if entrada > 0 else None
        error = 100 * abs(medida / teoricas[posicion] - 1) if medida is not None else None
        valida = not razones
        concordancia = max(0.0, 100 - error) if valida else None
        cumple = valida and error <= modelo["tolerancia_error_ganancia_pct"]
        filas.append(dict(frecuencia_hz=float(frecuencia), amplitud_antes_v=entrada,
            amplitud_despues_v=salida, ganancia_teorica=float(teoricas[posicion]),
            ganancia_medida=medida, error_relativo_pct=error if valida else None,
            concordancia_teorica_pct=concordancia, medida_valida=valida,
            cumple_criterio=bool(cumple), observacion="; ".join(razones) if razones else "medida valida"))
    return filas


def guardar_figura(ruta, filas, modelo):
    """Exporta una figura independiente sin abrir una ventana ni cambiar el backend global."""
    from matplotlib.figure import Figure
    from matplotlib.backends.backend_agg import FigureCanvasAgg
    figura = Figure(figsize=(8, 4.5), layout="constrained")
    FigureCanvasAgg(figura)
    eje = figura.subplots()
    frecuencias = np.geomspace(100, 7500, 500)
    eje.semilogx(frecuencias, ganancia_teorica(frecuencias, modelo), label="Modelo del circuito")
    validas = [fila for fila in filas if fila["medida_valida"]]
    if validas:
        eje.scatter([fila["frecuencia_hz"] for fila in validas],
                    [fila["ganancia_medida"] for fila in validas], color="tab:orange", label="Pico: amplitud después/antes")
    eje.set(xlabel="Frecuencia [Hz]", ylabel="Ganancia de amplitud [V/V]",
            title="Filtro analógico: modelo y medición por componentes", ylim=(0, None))
    eje.grid(True, which="both", alpha=0.3)
    eje.legend()
    figura.savefig(ruta, dpi=160)
