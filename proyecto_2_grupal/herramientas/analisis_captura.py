"""Lectura y mediciones del CSV original; no interpola ni filtra sus muestras."""
import csv
import math
from pathlib import Path
from statistics import mean

COLUMNAS_CSV = ["tiempo_ms", "freno_deg", "velocidad_rpm"]


# Lee las tres columnas originales y exige tiempos finitos y estrictamente crecientes.
def leer_csv(ruta_csv):
    filas = []
    with Path(ruta_csv).open(encoding="utf-8-sig", newline="") as archivo:
        lector = csv.DictReader(archivo)
        if lector.fieldnames != COLUMNAS_CSV:
            raise ValueError("El CSV debe contener tiempo_ms,freno_deg,velocidad_rpm")
        for numero_linea, registro in enumerate(lector, start=2):
            try:
                fila = tuple(float(registro[columna]) for columna in COLUMNAS_CSV)
            except (TypeError, ValueError, KeyError) as error:
                raise ValueError(f"Fila {numero_linea} no numerica") from error
            tiempo_ms, freno_deg, _ = fila
            if not math.isfinite(tiempo_ms) or tiempo_ms < 0 or not math.isfinite(freno_deg):
                raise ValueError(f"Fila {numero_linea}: tiempo o angulo no valido")
            if filas and tiempo_ms <= filas[-1][0]:
                raise ValueError(f"Fila {numero_linea}: tiempo repetido o decreciente")
            filas.append(fila)
    if not filas:
        raise ValueError("El CSV no contiene muestras")
    return filas


# Ajusta una pendiente RPM/s usando las muestras finitas y positivas del intervalo solicitado.
def pendiente_rpm_s(filas, inicio_ms, fin_ms, incluir_fin=True):
    puntos = [(tiempo_ms / 1000, velocidad_rpm) for tiempo_ms, _, velocidad_rpm in filas
              if inicio_ms <= tiempo_ms and (tiempo_ms <= fin_ms if incluir_fin else tiempo_ms < fin_ms)
              and math.isfinite(velocidad_rpm) and velocidad_rpm > 0]
    if len(puntos) < 2:
        return math.nan
    tiempo_medio = mean(punto[0] for punto in puntos)
    velocidad_media = mean(punto[1] for punto in puntos)
    denominador = sum((tiempo_s - tiempo_medio) ** 2 for tiempo_s, _ in puntos)
    if denominador == 0:
        return math.nan
    return sum((tiempo_s - tiempo_medio) * (velocidad_rpm - velocidad_media)
               for tiempo_s, velocidad_rpm in puntos) / denominador


# Obtiene extremos, temporizacion y cambio de freno sin deducir mediciones fisicas ausentes.
def analizar_filas(filas):
    if not filas:
        raise ValueError("No hay muestras para analizar")
    validas = [(indice, fila) for indice, fila in enumerate(filas) if math.isfinite(fila[2]) and fila[2] >= 0]
    intervalos_ms = [actual[0] - anterior[0] for anterior, actual in zip(filas, filas[1:])]
    cambios = [indice for indice in range(1, len(filas)) if filas[indice][1] != filas[indice - 1][1]]
    indice_maximo = max(validas, key=lambda elemento: elemento[1][2])[0] if validas else None
    resultado = {"cantidad": len(filas), "invalidas_rpm": len(filas) - len(validas),
                 "indice_maximo": indice_maximo, "cambios_freno": cambios,
                 "periodo_medio_ms": mean(intervalos_ms) if intervalos_ms else math.nan,
                 "periodo_minimo_ms": min(intervalos_ms) if intervalos_ms else math.nan,
                 "periodo_maximo_ms": max(intervalos_ms) if intervalos_ms else math.nan,
                 "rpm_minima": min(fila[2] for _, fila in validas) if validas else math.nan,
                 "rpm_media": mean(fila[2] for _, fila in validas) if validas else math.nan,
                 "indice_parada": None}
    if len(cambios) == 1:
        indice_freno = cambios[0]
        tiempo_freno_ms = filas[indice_freno][0]
        resultado["pendiente_antes_rpm_s"] = pendiente_rpm_s(filas, tiempo_freno_ms - 300, tiempo_freno_ms, False)
        resultado["pendiente_despues_rpm_s"] = pendiente_rpm_s(filas, tiempo_freno_ms, tiempo_freno_ms + 300)
        resultado["indice_parada"] = next((indice for indice in range(indice_freno, len(filas))
                                           if filas[indice][2] == 0), None)
    return resultado


# Selecciona filas reales distribuidas y conserva inicio, final, pico, cambios y primer cero.
def seleccionar_muestras(filas, analisis, cantidad_base=20):
    if cantidad_base < 2:
        raise ValueError("Se requieren al menos dos posiciones para mostrar muestras")
    indices = {round(posicion * (len(filas) - 1) / (cantidad_base - 1)) for posicion in range(cantidad_base)}
    for indice in [analisis["indice_maximo"], analisis["indice_parada"], *analisis["cambios_freno"]]:
        if indice is not None:
            indices.add(indice)
            if indice > 0:
                indices.add(indice - 1)
    return [(indice + 1, filas[indice]) for indice in sorted(indices)]


# Formatea mediciones ausentes sin convertirlas en ceros que aparenten haber sido observados.
def numero_medicion(valor, decimales=3):
    return f"{valor:.{decimales}f}" if valor is not None and math.isfinite(valor) else "no disponible"


# Resume el CSV completo y sus filas representativas, con unidades y referencias temporales explicitas.
def resumir(filas, metadatos=None):
    analisis = analizar_filas(filas)
    periodo_ms = analisis["periodo_medio_ms"]
    frecuencia_hz = 1000 / periodo_ms if math.isfinite(periodo_ms) and periodo_ms > 0 else math.nan
    lineas = [f"{len(filas)} filas · primera {filas[0][0] / 1000:.3f} s · ultima {filas[-1][0] / 1000:.3f} s",
              f"RPM inicial {numero_medicion(filas[0][2])} · final {numero_medicion(filas[-1][2])} · "
              f"minima {numero_medicion(analisis['rpm_minima'])} · media {numero_medicion(analisis['rpm_media'])}",
              f"Muestreo observado: {numero_medicion(periodo_ms)} ms promedio ({numero_medicion(frecuencia_hz, 2)} Hz); "
              f"min {numero_medicion(analisis['periodo_minimo_ms'])} ms · max {numero_medicion(analisis['periodo_maximo_ms'])} ms",
              f"Lecturas RPM no validas: {analisis['invalidas_rpm']}"]
    if analisis["indice_maximo"] is not None:
        pico = filas[analisis["indice_maximo"]]
        lineas.append(f"RPM maxima {pico[2]:.3f} en t = {pico[0] / 1000:.3f} s (fila {analisis['indice_maximo'] + 1})")
    if len(analisis["cambios_freno"]) == 1:
        indice_freno = analisis["cambios_freno"][0]
        tiempo_ms, angulo_deg, velocidad_rpm = filas[indice_freno]
        lineas.extend([f"Orden de freno {filas[indice_freno - 1][1]:g}° → {angulo_deg:g}° en t = {tiempo_ms / 1000:.3f} s "
                       f"con {numero_medicion(velocidad_rpm)} RPM (fila {indice_freno + 1})",
                       f"Pendiente antes {numero_medicion(analisis['pendiente_antes_rpm_s'], 1)} RPM/s · "
                       f"despues {numero_medicion(analisis['pendiente_despues_rpm_s'], 1)} RPM/s (ventanas de 300 ms)"])
        if analisis["indice_parada"] is not None:
            parada_ms = filas[analisis["indice_parada"]][0]
            lineas.append(f"Primer 0 RPM en t = {parada_ms / 1000:.3f} s; {(parada_ms - tiempo_ms) / 1000:.3f} s despues del freno "
                          "(estimacion por ausencia de pulsos)")
        else:
            lineas.append("La captura no contiene una lectura de 0 RPM posterior al freno")
    else:
        lineas.append(f"Cambios de orden de freno: {len(analisis['cambios_freno'])}; no hay un escalon unico para calcular pendientes")
    if metadatos:
        fin = metadatos.get("fin") or {}
        lineas.append("Transporte: " + " · ".join(f"{etiqueta} {fin.get(campo, 'no disponible')}" for etiqueta, campo in (
            ("producidas", "producidas"), ("enviadas", "enviadas"), ("vencimientos perdidos", "vencimientos_perdidos"),
            ("pulsos rechazados", "pulsos_rechazados"))))
    muestras = seleccionar_muestras(filas, analisis)
    lineas.extend([f"Muestras del CSV: {len(muestras)} de {len(filas)} filas; el archivo conserva todas",
                   "fila | tiempo_ms | freno_deg (orden) | velocidad_rpm"])
    lineas.extend(f"{numero_fila:4d} | {tiempo_ms:9.3f} | {freno_deg:17.3f} | {velocidad_rpm:13.3f}"
                  for numero_fila, (tiempo_ms, freno_deg, velocidad_rpm) in muestras)
    return lineas
