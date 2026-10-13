"""Herramientas organizadas por función; conserva los imports históricos de módulos."""

from importlib import import_module

_MODULOS = {
    'filtros_temporales': '.filtros.filtros_temporales',
    'filtrado_espectral': '.filtros.filtrado_espectral',
    'bloques_espectrales': '.filtros.bloques_espectrales',
    'diseno_temporal': '.filtros.diseno_temporal',
    'generacion': '.senales.generacion',
    'analisis_fourier': '.senales.analisis_fourier',
    'metricas': '.mediciones.metricas',
    'evaluacion': '.mediciones.evaluacion',
    'archivos': '.datos.archivos',
    'graficas': '.visualizacion.graficas',
}
__all__ = list(_MODULOS)


def __getattr__(nombre):
    """Carga el módulo solicitado desde su carpeta correspondiente."""
    if nombre not in _MODULOS:
        raise AttributeError(f"El paquete {__name__} no contiene {nombre}.")
    modulo = import_module(_MODULOS[nombre], __name__)
    globals()[nombre] = modulo
    return modulo
