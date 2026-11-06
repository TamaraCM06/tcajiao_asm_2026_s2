"""Region de interferencia para evaluar registros; no modifica los filtros ni los estimulos."""
from pathlib import Path

from src.datos.casos import resolver_caso

REGIONES_CASOS = {
    "P1": (3950.0, 4050.0), "P2_tonal": (3950.0, 4050.0),
    "P2": (2500.0, 3800.0), "P3": (0.0, 8000.0),
    "P4": (0.0, 8000.0), "P5": (600.0, 1500.0),
}


# Prioriza una region explicita; en automatico identifica exclusivamente los casos conocidos.
def configuracion_medicion(configuracion, fuente=None):
    """Devuelve una copia por sesion, sin arrastrar la region de un caso al siguiente."""
    efectiva = configuracion.copy()
    if efectiva.get("interferencia_min_hz") is None:
        nombre = Path(str(fuente or "").replace("\\", "/")).stem.removesuffix("_muestras")
        region = REGIONES_CASOS.get(resolver_caso(nombre))
        if region:
            efectiva["interferencia_min_hz"], efectiva["interferencia_max_hz"] = region
    return efectiva
