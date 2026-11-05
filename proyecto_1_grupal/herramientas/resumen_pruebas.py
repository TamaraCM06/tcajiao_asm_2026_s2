"""Promedio y desviacion de las repeticiones P1-P5 guardadas como evidencia.

Estructura esperada: <evidencias>/<prueba>/<repeticion>/metricas.csv, por ejemplo
docs/final/evidencias/P1/rep_1/metricas.csv. Cada metricas.csv es el de una sesion
(una fila por metodo); se promedian todas sus columnas numericas.

Uso desde proyecto_1_grupal/:
    python -m herramientas.resumen_pruebas docs/final/evidencias
"""
import argparse
import csv
from pathlib import Path
import statistics


def _numero(valor):
    try:
        numero = float(valor)
    except (TypeError, ValueError):
        return None
    return numero if numero == numero else None


def leer_repeticiones(raiz):
    """Agrupa las filas por (prueba, metodo); cada valor es la lista de repeticiones."""
    grupos = {}
    for archivo in sorted(Path(raiz).glob("*/*/metricas.csv")):
        prueba = archivo.parent.parent.name
        with archivo.open(encoding="utf-8", newline="") as entrada:
            for fila in csv.DictReader(entrada):
                metodo = fila.get("metodo", "")
                grupo = grupos.setdefault((prueba, metodo), {})
                for columna, valor in fila.items():
                    numero = _numero(valor)
                    if numero is not None:
                        grupo.setdefault(columna, []).append(numero)
    return grupos


def resumir(grupos):
    """Devuelve una fila por prueba y metodo con media, desviacion y numero de repeticiones."""
    filas = []
    for (prueba, metodo), columnas in sorted(grupos.items()):
        fila = dict(prueba=prueba, metodo=metodo, repeticiones=max(len(v) for v in columnas.values()))
        for columna, valores in sorted(columnas.items()):
            fila[f"{columna}_media"] = statistics.fmean(valores)
            fila[f"{columna}_desviacion"] = statistics.stdev(valores) if len(valores) > 1 else 0.0
        filas.append(fila)
    return filas


def escribir(filas, ruta):
    columnas = []
    for fila in filas:
        columnas += [c for c in fila if c not in columnas]
    with Path(ruta).open("w", newline="", encoding="utf-8") as salida:
        escritor = csv.DictWriter(salida, fieldnames=columnas)
        escritor.writeheader()
        escritor.writerows(filas)


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("evidencias", type=Path)
    argumentos = parser.parse_args()
    filas = resumir(leer_repeticiones(argumentos.evidencias))
    if not filas:
        raise SystemExit("No se encontraron <prueba>/<repeticion>/metricas.csv")
    escribir(filas, argumentos.evidencias / "resumen.csv")
    for fila in filas:
        aviso = "" if fila["repeticiones"] >= 3 else "  (menos de 3 repeticiones)"
        print(f"{fila['prueba']} {fila['metodo']}: {fila['repeticiones']} repeticiones{aviso}")


if __name__ == "__main__":
    main()
