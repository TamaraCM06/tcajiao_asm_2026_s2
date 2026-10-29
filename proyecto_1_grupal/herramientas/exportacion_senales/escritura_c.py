"""Escritura de arreglos C y metadatos reproducibles, sin comunicación con placas."""

import json
from pathlib import Path

from .preparacion import SenalPreparada

RAIZ_REPOSITORIO = Path(__file__).resolve().parents[3]


# Construye datos constantes que ESP-IDF puede ubicar en la memoria flash.
def _construir_fuente_c(senal: SenalPreparada, caso):
    """Representa los códigos DAC como un arreglo y su descriptor de lectura."""
    nombre_arreglo = f"CODIGOS_{caso.upper()}"
    nombre_descriptor = f"DATOS_{caso.upper()}"
    lineas = [
        "/* Archivo generado desde el CSV del notebook; no editar las muestras a mano.",
        " * Regenerar con: python -m proyecto_1_grupal.herramientas.exportar_senales",
        " */",
        '#include "senales_embebidas.h"',
        "",
        f"static const uint8_t {nombre_arreglo}[] = {{",
    ]
    for posicion in range(0, len(senal.codigos_dac), 16):
        valores = ", ".join(f"{codigo:3d}" for codigo in senal.codigos_dac[posicion:posicion + 16])
        lineas.append(f"    {valores},")
    lineas.extend([
        "};",
        "",
        f'_Static_assert(sizeof({nombre_arreglo}) == {senal.cantidad_muestras},',
        '               "La longitud del arreglo debe coincidir con el registro exportado.");',
        "",
        f"const senal_embebida_t {nombre_descriptor} = {{",
        f'    .nombre = "{caso}",',
        f"    .codigos_dac = {nombre_arreglo},",
        f"    .cantidad_muestras = sizeof({nombre_arreglo}),",
        f"    .frecuencia_muestreo_hz = {senal.frecuencia_muestreo_hz},",
        f"    .crc32 = 0x{senal.crc32:08X}u,",
        "};",
        "",
    ])
    return "\n".join(lineas)


# Guarda cada registro por separado para actualizarlo sin borrar otros casos.
def exportar_senal_c(senal: SenalPreparada, caso, carpeta_destino):
    """Escribe el arreglo y los metadatos de su origen, escala e identificación."""
    if caso not in ("caso_1", "caso_2", "caso_3"):
        raise ValueError("El destino debe ser caso_1, caso_2 o caso_3.")
    carpeta_destino = Path(carpeta_destino)
    carpeta_destino.mkdir(parents=True, exist_ok=True)
    archivo_c = carpeta_destino / f"{caso}.c"
    archivo_metadatos = carpeta_destino / f"{caso}.json"
    ruta_origen = senal.ruta_csv.resolve()
    if ruta_origen.is_relative_to(RAIZ_REPOSITORIO):
        origen_documentado = ruta_origen.relative_to(RAIZ_REPOSITORIO).as_posix()
    else:
        origen_documentado = ruta_origen.name
    metadatos = {
        "version_formato": 1,
        "caso_firmware": caso,
        "identificador_origen": senal.identificador,
        "archivo_csv": origen_documentado,
        "archivo_c": archivo_c.name,
        "frecuencia_muestreo_hz": senal.frecuencia_muestreo_hz,
        "cantidad_muestras": senal.cantidad_muestras,
        "duracion_s": senal.cantidad_muestras / senal.frecuencia_muestreo_hz,
        "formato": "uint8 DAC",
        "conversion": "floor(127.5 * (clip(muestra, -1, 1) + 1) + 0.5)",
        "cantidad_recortes": senal.cantidad_recortes,
        "crc32_codigos": f"{senal.crc32:08X}",
    }
    archivo_c.write_text(_construir_fuente_c(senal, caso), encoding="utf-8", newline="\n")
    archivo_metadatos.write_text(json.dumps(metadatos, indent=2, ensure_ascii=False) + "\n",
                                encoding="utf-8", newline="\n")
    return archivo_c, archivo_metadatos
