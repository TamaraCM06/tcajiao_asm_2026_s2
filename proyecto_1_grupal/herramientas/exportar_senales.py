"""Exporta los CSV del notebook como arreglos C incluidos en la flash de ESP32."""

import argparse
from pathlib import Path

from .exportacion_senales.escritura_c import exportar_senal_c
from .exportacion_senales.preparacion import preparar_senal
from .exportacion_senales.datos_evaluacion import exportar_datos_evaluacion, exportar_coeficientes

CASOS = ("caso_1", "caso_2", "caso_3")
CARPETA_DATOS = (Path(__file__).resolve().parents[1] /
                 "firmware/esp32/components/senales_embebidas/datos")


# Exporta los casos elegidos sin regenerar los ruidos ni modificar el notebook.
def main():
    """Selecciona CSV existentes y guarda arreglos C y metadatos por caso."""
    argumentos = argparse.ArgumentParser(description=__doc__)
    argumentos.add_argument("--caso", choices=["todos", *CASOS], default="todos")
    argumentos.add_argument("--archivo", type=Path,
                            help="CSV del notebook para reemplazar un caso del firmware.")
    opciones = argumentos.parse_args()
    if opciones.archivo is not None and opciones.caso == "todos":
        argumentos.error("--archivo requiere elegir un caso concreto con --caso.")
    casos_seleccionados = CASOS if opciones.caso == "todos" else (opciones.caso,)
    try:
        for caso in casos_seleccionados:
            senal = (preparar_senal(ruta_csv=opciones.archivo) if opciones.archivo is not None
                     else preparar_senal(caso=caso))
            archivo_c, archivo_metadatos = exportar_senal_c(senal, caso, CARPETA_DATOS)
            exportar_datos_evaluacion(senal, caso, CARPETA_DATOS)
            print(f"{caso}: {senal.cantidad_muestras} muestras, {senal.frecuencia_muestreo_hz} Hz, "
                  f"CRC-32 {senal.crc32:08X}, recortes {senal.cantidad_recortes}")
            print(f"  Datos: {archivo_c}\n  Metadatos: {archivo_metadatos}")
        exportar_coeficientes(
            Path(__file__).resolve().parents[1] /
            "tarea1_grupo1/resultados/filtro_temporal/coeficientes_fir.csv", CARPETA_DATOS)
    except (OSError, ValueError) as error:
        argumentos.exit(1, f"Error de exportación: {error}\n")


if __name__ == "__main__":
    main()
