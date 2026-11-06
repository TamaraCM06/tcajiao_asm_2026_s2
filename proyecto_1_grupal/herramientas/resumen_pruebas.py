"""Promedia repeticiones P1--P5 según §4 del enunciado; no filtra ni califica el sistema."""
import argparse
import csv
import hashlib
import json
import math
from pathlib import Path
import statistics
import sys

from tarea1_grupo1.src.datos.casos import CASOS_FINALES, resolver_caso

PROYECTO = Path(__file__).resolve().parents[1]
METRICAS = ("mse", "snr_entrada_db", "snr_salida_db", "mejora_snr_db", "energia_util_pct",
            "atenuacion_ruido_total_db", "distorsion_util_db", "calculo_medio_us", "calculo_max_us",
            "atenuacion_interferencia_db", "ruta_medio_us", "ruta_max_us",
            "latencia_bloque_medio_us", "latencia_bloque_max_us",
            "latencia_arranque_medio_us", "latencia_arranque_max_us",
            "latencia_cierre_medio_us", "latencia_cierre_max_us",
            "cola_medio_us", "cola_max_us", "evaluacion_medio_us", "evaluacion_max_us",
            "publicacion_medio_us", "publicacion_max_us", "region_muestras",
            "estado_dsp_bytes", "heap_minimo_bytes", "perdidas",
            "recortes_entrada", "recortes_salida", "concordancia_modelo_python_pct")


# Ignora valores ausentes o indefinidos, conservando su cantidad disponible.
def numero_finito(valor):
    """Devuelve None para texto, NaN o infinitos; nunca los sustituye por cero."""
    try:
        numero = float(valor)
    except (TypeError, ValueError):
        return None
    return numero if math.isfinite(numero) else None


# Identifica el estímulo de un CSV o la carpeta Pn elegida por el usuario para una captura.
def identificar_prueba(metadatos, carpeta):
    """P2_tonal queda fuera de P1--P5: no equivale a la prueba de tono único."""
    fuente = Path(str(metadatos.get("fuente") or "").replace("\\", "/")).stem.replace("_muestras", "")
    identificador = resolver_caso(fuente)
    if identificador in CASOS_FINALES:
        return identificador
    if identificador:
        return None
    return next((directorio.name for directorio in carpeta.parents if directorio.name in CASOS_FINALES), None)


# Separa condiciones distintas en lugar de mezclarlas como si fueran repeticiones.
def describir_condicion(metadatos):
    """Incluye parámetros, versión, referencia y huella de entrada controlada."""
    parametros = {clave: metadatos.get(clave) for clave in
                  ("origen", "con_referencia", "frecuencia_hz", "muestras", "escala",
                   "minimo_hz", "ancho_hz", "factor", "umbral",
                   "interferencia_min_hz", "interferencia_max_hz")}
    parametros["firmware"] = metadatos.get("resultado_esp32", {}).get("firmware")
    parametros["version_mediciones"] = metadatos.get("resultado_esp32", {}).get("version_mediciones")
    if metadatos.get("origen") == "archivo":
        parametros["entrada_sha256"] = metadatos.get("sha256", {}).get("entrada")
    texto = json.dumps(parametros, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(texto.encode()).hexdigest()[:8], texto


# Lee las sesiones donde se guardaron, sin copiar WAV ni exigir validación Python adicional.
def leer_repeticiones(raiz):
    """Solo usa sesiones completas; informa las incompletas y mantiene separadas sus condiciones."""
    grupos = {}
    for archivo in sorted(Path(raiz).rglob("sesion.json")):
        if archivo.parent.name == "originales":
            continue
        metadatos = json.loads(archivo.read_text(encoding="utf-8"))
        prueba = identificar_prueba(metadatos, archivo.parent)
        if prueba is None:
            continue
        if metadatos.get("estado") != "completa":
            print(f"Omitida sesión incompleta: {archivo.parent}", file=sys.stderr)
            continue
        ruta_metricas = archivo.with_name("metricas.csv")
        if not ruta_metricas.exists():
            raise ValueError(f"Falta metricas.csv en {archivo.parent}")
        condicion, parametros = describir_condicion(metadatos)
        with ruta_metricas.open(encoding="utf-8", newline="") as entrada:
            filas = list(csv.DictReader(entrada))
        if sorted(fila.get("metodo", "") for fila in filas) != ["espectral", "fir"]:
            raise ValueError(f"Se esperan exactamente FIR y espectral en {ruta_metricas}")
        for fila in filas:
            fila["_parametros"] = parametros
            fila["_sesion"] = archivo.parent.name
            grupos.setdefault((prueba, condicion, fila["metodo"]), []).append(fila)
    return grupos


# Calcula estadísticas entre ejecuciones independientes, sin crear criterios académicos nuevos.
def resumir(grupos):
    """Una sola corrida no tiene desviación; las celdas sin referencia permanecen vacías."""
    filas = []
    for (prueba, condicion, metodo), repeticiones in sorted(grupos.items()):
        fila = dict(prueba=prueba, condicion=condicion, metodo=metodo, repeticiones=len(repeticiones),
                    estado_repeticiones="tres_o_mas" if len(repeticiones) >= 3 else "faltan_repeticiones",
                    parametros=repeticiones[0]["_parametros"],
                    sesiones=";".join(repeticion["_sesion"] for repeticion in repeticiones))
        for columna in METRICAS:
            valores = [numero_finito(repeticion.get(columna)) for repeticion in repeticiones]
            valores = [valor for valor in valores if valor is not None]
            fila[f"{columna}_cantidad"] = len(valores)
            fila[f"{columna}_media"] = statistics.fmean(valores) if valores else None
            fila[f"{columna}_desviacion"] = statistics.stdev(valores) if len(valores) > 1 else None
        filas.append(fila)
    return filas


# Exporta un resumen local, conservando las métricas originales de cada sesión.
def escribir(filas, ruta):
    """Las celdas vacías significan no disponible, no cero."""
    with Path(ruta).open("w", newline="", encoding="utf-8") as salida:
        escritor = csv.DictWriter(salida, fieldnames=list(filas[0]))
        escritor.writeheader()
        escritor.writerows(filas)


# Presenta medias y dispersión para una tabla breve del artículo.
def valor_latex(fila, nombre):
    """La cantidad de medidas disponibles sigue explícita en resumen.csv."""
    media = fila[f"{nombre}_media"]
    desviacion = fila[f"{nombre}_desviacion"]
    if media is None:
        return "--"
    formato = ".2e" if nombre == "mse" else ".2f"
    texto = format(media, formato)
    return texto + (r" $\pm$ " + format(desviacion, formato) if desviacion is not None else r" $^\dagger$")


# Produce una tabla optativa: el equipo selecciona lo que entra en las cuatro páginas.
def escribir_latex(filas, ruta):
    """No aprueba el sistema: tres repeticiones no prueban por sí solas calidad ni adquisición física."""
    lineas = [r"\begin{table}[H]\centering\scriptsize\setlength{\tabcolsep}{2pt}",
              r"\caption{Evaluaciones por condición: media $\pm$ desviación muestral; --: no disponible.}",
              r"\label{tab:repeticiones}\resizebox{\columnwidth}{!}{\begin{tabular}{llrlll}\toprule",
              r"Prueba/cond. & Método & $r$ & $\Delta$SNR (dB) & MSE & Útil (\%) \\\midrule"]
    for fila in filas:
        etiqueta = fila["prueba"] + "/" + fila["condicion"][:4]
        lineas.append(f"{etiqueta} & {fila['metodo'].capitalize()} & {fila['repeticiones']} & "
                      f"{valor_latex(fila, 'mejora_snr_db')} & {valor_latex(fila, 'mse')} & "
                      f"{valor_latex(fila, 'energia_util_pct')}" + r" \\")
    lineas.extend([r"\bottomrule\end{tabular}}\end{table}",
                  r"\noindent\footnotesize $^\dagger$: una sola medida; condiciones y origen ADC/CSV en el resumen CSV.", ""])
    Path(ruta).write_text("\n".join(lineas), encoding="utf-8")


# Genera solamente las salidas que respaldan el reporte de repeticiones del §4.
def main():
    """No necesita rutas de esta PC ni una carpeta de copias bajo docs."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("sesiones", type=Path, help="Carpeta de sesiones de las pruebas finales")
    parser.add_argument("--salida", type=Path, default=PROYECTO / "resultados/entrega")
    argumentos = parser.parse_args()
    filas = resumir(leer_repeticiones(argumentos.sesiones))
    if not filas:
        parser.error("No hay sesiones completas P1--P5; primero ejecutar las pruebas, sin inventar filas vacías")
    argumentos.salida.mkdir(parents=True, exist_ok=True)
    escribir(filas, argumentos.salida / "resumen.csv")
    escribir_latex(filas, argumentos.salida / "tabla_pruebas.tex")
    for fila in filas:
        print(f"{fila['prueba']} {fila['condicion']} {fila['metodo']}: "
              f"{fila['repeticiones']} repeticiones; {fila['estado_repeticiones']}")
    print("Es un resumen estadístico; revisar métricas, sonido y requisitos físicos por separado.")


if __name__ == "__main__":
    main()
