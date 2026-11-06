"""Identificadores de defensa y equivalencias con los registros históricos, sin regenerarlos."""

CASOS_FINALES = ("P1", "P2", "P3", "P4", "P5")
CASOS_ADICIONALES = ("P2_tonal",)
EQUIVALENCIAS_HISTORICAS = {"caso_1": "P2_tonal", "caso_2": "P2", "caso_3": "P5"}


# Acepta nombres históricos al abrir sesiones anteriores y devuelve su nombre vigente.
def resolver_caso(identificador):
    """Acepta nombres históricos al abrir sesiones anteriores y devuelve su nombre vigente."""
    return EQUIVALENCIAS_HISTORICAS.get(identificador, identificador)
