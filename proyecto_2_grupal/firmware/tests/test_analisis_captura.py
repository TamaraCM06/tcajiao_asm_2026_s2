"""Contrasta el resumen con muestras conocidas y conserva los picos fuera del refresco de pantalla."""
import math

import pytest


# El pico intermedio, el cambio de orden y el primer cero deben conservar sus filas originales.
def test_resumen_y_filas_del_csv(consola, tmp_path):
    from analisis_captura import analizar_filas, leer_csv, seleccionar_muestras
    ruta = tmp_path / "captura.csv"
    ruta.write_text("tiempo_ms,freno_deg,velocidad_rpm\n0.5,90,1800\n20.5,90,2100\n"
                    "40.5,152,1700\n60.5,152,1300\n80.5,152,0\n100.5,152,0\n", encoding="utf-8")
    filas = leer_csv(ruta)
    analisis = analizar_filas(filas)
    assert analisis["indice_maximo"] == 1 and analisis["cambios_freno"] == [2]
    assert analisis["indice_parada"] == 4 and analisis["periodo_medio_ms"] == 20
    assert seleccionar_muestras(filas, analisis) == list(enumerate(filas, start=1))
    resumen = "\n".join(consola.resumir(filas))
    assert "RPM maxima 2100.000" in resumen and "fila 2" in resumen
    assert "0.040 s despues del freno" in resumen and "50.00 Hz" in resumen
    assert "20.500" in resumen and "2100.000" in resumen


# Las velocidades no finitas se contabilizan como ausentes y no alteran los extremos validos.
def test_velocidad_ausente_y_captura_sin_escalon(consola):
    from analisis_captura import analizar_filas
    filas = [(0, 90, math.nan), (20, 90, 900), (40, 90, math.inf)]
    analisis = analizar_filas(filas)
    assert analisis["invalidas_rpm"] == 2 and analisis["indice_maximo"] == 1
    resumen = "\n".join(consola.resumir(filas))
    assert "RPM inicial no disponible" in resumen and "no hay un escalon unico" in resumen


# La seleccion conserva el pico aunque no coincida con las posiciones uniformes de la tabla.
def test_seleccion_no_oculta_pico(consola):
    from analisis_captura import analizar_filas, seleccionar_muestras
    filas = [(indice * 20, 90 if indice < 15 else 152, 2500 if indice == 7 else 1000)
             for indice in range(100)]
    seleccion = seleccionar_muestras(filas, analizar_filas(filas))
    assert (8, filas[7]) in seleccion and (16, filas[15]) in seleccion
    assert seleccion[0] == (1, filas[0]) and seleccion[-1] == (100, filas[-1])
    assert all(fila == filas[numero - 1] for numero, fila in seleccion)


# Rechaza filas que no pueden representar una serie temporal real, sin inventar sustitutos.
@pytest.mark.parametrize("contenido", ["otro,formato\n", "tiempo_ms,freno_deg,velocidad_rpm\n",
    "tiempo_ms,freno_deg,velocidad_rpm\n0,90,100\n0,90,90\n",
    "tiempo_ms,freno_deg,velocidad_rpm\nnan,90,100\n"])
def test_csv_no_valido(consola, tmp_path, contenido):
    from analisis_captura import leer_csv
    ruta = tmp_path / "incorrecto.csv"
    ruta.write_text(contenido, encoding="utf-8")
    with pytest.raises(ValueError):
        leer_csv(ruta)
