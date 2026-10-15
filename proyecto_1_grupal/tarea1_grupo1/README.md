# Tarea 1: Caracterización espectral y prototipado de filtros para reducción de ruido

CE 1110 Análisis de Señales Mixtas, Instituto Tecnológico de Costa Rica.

- **Repositorio:** https://github.com/TamaraCM06/tcajiao_asm_2026_s2
- **Etiqueta:** `tarea1_prototipo`

## Contenido

| Ruta | Contenido |
|---|---|
| `informe.pdf` | Informe de la tarea |
| `notebook.ipynb` | Regenera señales, resultados, gráficas y métricas |
| `src/` | Código fuente (filtros en `src/filtros/`) |
| `tests/` | Pruebas automáticas |
| `pruebas/caso_N/` | WAV de cada caso: limpia, ruido y contaminada |
| `resultados/` | `metricas.csv`, `figuras/` y salidas de cada filtro |
| `metadatos/configuraciones.json` | Parámetros y semillas de los tres casos |

## Ejecución

Requiere Python 3.10+ con numpy, scipy, matplotlib, ipykernel y pytest.

```bash
pip install numpy scipy matplotlib ipykernel pytest
```

Abrir `notebook.ipynb` con `tarea1_grupo1/` como directorio de trabajo y ejecutar todas las celdas. Pruebas: `python -m pytest tests`.
