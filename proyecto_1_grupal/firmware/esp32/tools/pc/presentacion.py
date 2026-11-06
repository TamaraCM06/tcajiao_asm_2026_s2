"""Tablas de consola: presentan valores existentes sin recalcular ni guardar mediciones."""
import math
from numbers import Integral, Real
import shutil
import textwrap

ETIQUETAS_ESTADO = {
    "disponible": "Disponible", "sin_referencia": "Sin referencia",
    "sin_region": "Sin region", "sin_bloques_completos": "Sin bloques completos",
    "sin_energia_entrada": "Sin energia de entrada", "residuo_no_resuelto": "Residuo no resuelto",
}
METRICAS_CALIDAD = (
    ("mse", "MSE", ".6e"),
    ("snr_entrada_db", "SNR entrada [dB]", ".3f"),
    ("snr_salida_db", "SNR salida [dB]", ".3f"),
    ("mejora_snr_db", "Mejora SNR [dB]", ".3f"),
    ("energia_util_pct", "Energia util conservada [%]", ".3f"),
    ("atenuacion_interferencia_db", "Atenuacion regional [dB]", ".3f"),
    ("estado_atenuacion_regional", "Estado de medida regional", None),
    ("atenuacion_ruido_total_db", "Atenuacion ruido total [dB]", ".3f"),
    ("distorsion_util_db", "Distorsion util [dB]", ".3f"),
    ("energia_total", "Energia total de salida", ".6e"),
    ("recortes_salida", "Recortes de salida", ".0f"),
)
METRICAS_VALIDACION = (
    ("concordancia_modelo_python_pct", "Concordancia con Python [%]", ".4f"),
    ("umbral_concordancia_pct", "Umbral interno [%]", ".2f"),
    ("cumple_concordancia", "Cumple concordancia", None),
    ("nrmse_modelo_python", "Error RMS normalizado", ".6e"),
    ("error_rms_modelo", "Error RMS del modelo", ".6e"),
    ("error_maximo_pcm", "Error maximo [codigos PCM]", ".0f"),
    ("recortes_modelo_python", "Recortes del modelo", ".0f"),
    ("muestras_comparadas", "Muestras comparadas", ".0f"),
    ("snr_salida_python_float_db", "SNR Python float [dB]", ".3f"),
    ("diferencia_snr_placa_python_db", "SNR placa menos Python [dB]", ".6e"),
)


# Distingue medidas disponibles de ausencias, sin descartar ceros ni resultados negativos.
def dato_disponible(valor):
    """Reconoce valores finitos y textos utiles, incluidos estados de fallo medidos."""
    if valor is None:
        return False
    if isinstance(valor, Real):
        return math.isfinite(valor)
    return str(valor).strip().casefold() not in ("", "n/d", "no disponible", "none", "nan", "inf", "-inf")


# Mantiene ceros y signos; las ausencias se omiten al construir las tablas.
def valor_visible(valor, formato=None):
    """Devuelve texto vacio para ausentes; nunca los convierte en cero."""
    if not dato_disponible(valor):
        return ""
    if isinstance(valor, bool):
        return "Si" if valor else "No"
    if isinstance(valor, Real):
        return str(valor) if formato is None and isinstance(valor, Integral) else format(valor, formato or ".6g")
    return ETIQUETAS_ESTADO.get(str(valor), str(valor))


# Usa bordes ASCII para PowerShell, sin colores obligatorios ni dependencias adicionales.
def tabla(titulo, encabezados, filas, columnas_numericas=()):
    """Muestra filas completas y omite tablas vacias; envuelve el contenido disponible."""
    filas = [[valor_visible(celda) for celda in fila] for fila in filas]
    filas = [fila for fila in filas if all(celda.strip() for celda in fila)]
    if not filas:
        return ""
    contenido = [list(encabezados), *filas]
    anchos = [max(len(linea) for fila in contenido for linea in str(fila[columna]).splitlines() or [""])
              for columna in range(len(encabezados))]
    limite = max(48, min(110, shutil.get_terminal_size((100, 24)).columns))
    while sum(anchos) + 3 * len(anchos) + 1 > limite and max(anchos) > 8:
        columna = max(range(len(anchos)), key=lambda posicion: anchos[posicion])
        anchos[columna] -= 1
    borde = "+" + "+".join("-" * (ancho + 2) for ancho in anchos) + "+"
    salida = ["", titulo, borde]
    for numero_fila, fila in enumerate(contenido):
        celdas = [sum((textwrap.wrap(linea, width=anchos[columna], break_on_hyphens=False) or [""]
                       for linea in str(celda).splitlines() or [""]), [])
                  for columna, celda in enumerate(fila)]
        for linea in range(max(map(len, celdas))):
            textos = [celda[linea] if linea < len(celda) else "" for celda in celdas]
            salida.append("| " + " | ".join(
                texto.rjust(anchos[columna]) if numero_fila and columna in columnas_numericas
                else texto.ljust(anchos[columna]) for columna, texto in enumerate(textos)) + " |")
        if numero_fila == 0:
            salida.append(borde)
    salida.append(borde)
    return "\n".join(salida)


# Reutiliza las mismas columnas para resultados de placa y validacion independiente.
def comparacion(titulo, resultados, especificaciones):
    """Compara medidas compartidas; conserva las de una sola ruta en su propia tabla."""
    conocidas = {clave for clave, _, _ in especificaciones}
    adicionales = sorted({clave for metodo in ("fir", "espectral")
                          for clave in resultados.get(metodo, {})} - conocidas)
    filas = []
    individuales = []
    for clave, etiqueta, formato in (*especificaciones, *((clave, clave, None) for clave in adicionales)):
        valores = {metodo: valor_visible(resultados.get(metodo, {}).get(clave), formato)
                   for metodo in ("fir", "espectral")}
        if all(valores.values()):
            filas.append((etiqueta, valores["fir"], valores["espectral"]))
        else:
            individuales.extend((etiqueta, metodo.upper(), valor) for metodo, valor in valores.items() if valor)
    compartidas = tabla(titulo, ("Medida", "FIR", "ESPECTRAL"), filas, (1, 2))
    exclusivas = tabla(titulo + " | MEDIDAS POR RUTA", ("Medida", "Ruta", "Valor"), individuales, (2,))
    return "\n".join(parte for parte in (compartidas, exclusivas) if parte)


# Mantiene origen y alcance de la concordancia separados de las medidas del microcontrolador.
def mostrar_validacion(resultados):
    """Presenta una validacion ya calculada; no llama a los filtros Python."""
    resumen = comparacion("VALIDACION INDEPENDIENTE EN PC", resultados, METRICAS_VALIDACION)
    if resumen:
        print(resumen)
        print("Concordancia compara ESP32 con Python; no es porcentaje de ruido eliminado.")


# Presenta todo el informe disponible con unidades y agrupaciones utiles para la defensa.
def mostrar_metricas(informe, validacion=None):
    """Organiza calidad, costos, latencia y recursos sin modificar el informe original."""
    rutas = {metodo: informe.get(metodo, {}) for metodo in ("fir", "espectral")}
    if informe.get("con_referencia") is False:
        print("Captura sin referencia limpia: se muestran las medidas registradas y la concordancia disponible.")
    claves_ruta = {"ruta_cantidad", "ruta_medio_us", "ruta_max_us"}
    calidad = {metodo: {clave: valor for clave, valor in datos.items() if clave not in claves_ruta}
               for metodo, datos in rutas.items()}
    resumen_calidad = comparacion("RESULTADOS DE LA ESP32 | MEDIDAS REGISTRADAS", calidad, METRICAS_CALIDAD)
    if resumen_calidad:
        print(resumen_calidad)
    resumen_rutas = tabla("CALCULO POR RUTA [ms]", ("Etapa", "Llamadas", "Media", "Maximo"), [
        (etiqueta, valor_visible(rutas[metodo].get("ruta_cantidad")),
         milisegundos(rutas[metodo].get("ruta_medio_us")), milisegundos(rutas[metodo].get("ruta_max_us")))
        for metodo, etiqueta in (("fir", "FIR / 256 muestras"), ("espectral", "Espectral / salto 512"))], (1, 2, 3))
    if resumen_rutas:
        print(resumen_rutas)
    tiempos = (("cola", "Recepcion hasta consumo"), ("latencia_bloque", "Latencia digital estable"),
               ("latencia_arranque", "Latencia de arranque"), ("latencia_cierre", "Latencia de cierre"),
               ("evaluacion", "Evaluacion de metricas"), ("publicacion", "Publicacion de salidas"))
    resumen_tiempos = tabla("TIEMPOS DIGITALES [ms]", ("Etapa", "Cantidad", "Media", "Maximo"), [
        (etiqueta, valor_visible(informe.get(prefijo + "_cantidad")),
         milisegundos(informe.get(prefijo + "_medio_us")), milisegundos(informe.get(prefijo + "_max_us")))
        for prefijo, etiqueta in tiempos], (1, 2, 3))
    if resumen_tiempos:
        print(resumen_tiempos)
    diagnostico = (
        ("origen", "Origen"), ("firmware", "Firmware"), ("esp_idf", "ESP-IDF"),
        ("version_mediciones", "Version de mediciones"), ("con_referencia", "Referencia limpia disponible"),
        ("muestras", "Muestras del registro"), ("muestras_evaluadas", "Muestras evaluadas"),
        ("retardo_muestras", "Retardo de alineacion [muestras]"),
        ("region_minima_hz", "Region: limite inferior [Hz]"), ("region_maxima_hz", "Region: limite superior [Hz]"),
        ("region_muestras", "Muestras de medida regional"),
        ("estado_dsp_bytes", "Estado DSP [bytes]"), ("heap_libre_bytes", "Heap libre [bytes]"),
        ("heap_minimo_bytes", "Heap minimo [bytes]"), ("perdidas", "Perdidas de bloques"),
        ("recortes_entrada", "Recortes de entrada PCM"),
        ("tasa_bloques_estimada_hz", "Cadencia estimada [muestras/s]"),
        ("calculo_rutas_incluye_referencia", "Costos incluyen ruta de referencia"),
    )
    filas = [(etiqueta, valor_visible(informe.get(clave))) for clave, etiqueta in diagnostico]
    filas.extend((etiqueta, milisegundos(informe.get(clave))) for clave, etiqueta in (
        ("calculo_total_us", "Calculo conjunto total [ms]"), ("calculo_medio_us", "Calculo conjunto medio [ms]"),
        ("calculo_max_us", "Calculo conjunto maximo [ms]"), ("tiempo_sesion_us", "Tiempo de sesion [ms]")))
    conocidas = {clave for clave, _ in diagnostico} | {"fir", "espectral", "calculo_total_us", "calculo_medio_us",
        "calculo_max_us", "tiempo_sesion_us"} | {
        prefijo + sufijo for prefijo, _ in tiempos for sufijo in ("_cantidad", "_medio_us", "_max_us")}
    filas.extend((clave, valor_visible(valor)) for clave, valor in informe.items() if clave not in conocidas)
    resumen_recursos = tabla("REGISTRO, REGION Y RECURSOS", ("Dato", "Valor"), filas, (1,))
    if resumen_recursos:
        print(resumen_recursos)
    if validacion:
        mostrar_validacion(validacion)
    print("Solo se muestran datos disponibles. Ceros y resultados negativos se conservan; archivos sin cambios.")
    if any(dato_disponible(informe.get(prefijo + "_medio_us"))
           for prefijo in ("latencia_bloque", "latencia_arranque", "latencia_cierre")):
        print("Latencia digital: recepcion ESP32 hasta aceptacion UART; excluye ADC, PC y DAC.")
    if informe.get("calculo_rutas_incluye_referencia") is True:
        print("FIR y espectral incluyen calculo de referencia; sus llamadas tienen distinta longitud.")


# Convierte unidades solo al presentar; la fuente sigue expresada en microsegundos.
def milisegundos(valor):
    """Devuelve tres decimales en ms, o texto vacio cuando no existe una medida finita."""
    return valor_visible(valor / 1000, ".3f") if isinstance(valor, Real) else ""


# Hace visibles parametros efectivos y seleccion de sesion sin diccionarios crudos.
def mostrar_configuracion(configuracion, sesion=None, estado=None):
    """Presenta parametros actuales para la siguiente operacion y ganancia de escucha."""
    filas = [("Estado del enlace", estado)] if estado is not None else []
    filas += [("Sesion seleccionada", str(sesion) if sesion else "Ninguna")]
    parametros = (("minimo_hz", "Banda protegida hasta [Hz]"), ("ancho_hz", "Ancho espectral [Hz]"),
                  ("factor", "Factor de atenuacion"), ("umbral", "Umbral relativo"),
                  ("ganancia", "Ganancia de reproduccion"), ("muestras", "Muestras de captura"))
    filas.extend((etiqueta, valor_visible(configuracion.get(clave))) for clave, etiqueta in parametros)
    filas.append(("Duracion de captura [s]", valor_visible(configuracion["muestras"] / 16000, ".3f")))
    for clave, etiqueta in (("interferencia_min_hz", "Interferencia: minimo [Hz]"),
                            ("interferencia_max_hz", "Interferencia: maximo [Hz]")):
        filas.append((etiqueta, valor_visible(configuracion[clave]) if configuracion.get(clave) is not None else "Automatico por caso"))
    print(tabla("CONFIGURACION ACTUAL", ("Parametro", "Valor"), filas))


# Mantiene ayudas y ejemplos en la misma presentacion que los resultados.
def ayuda_terminal():
    """Describe comandos existentes y consulta de resultados sin procesamiento adicional."""
    return tabla("SESIONES ASM | COMANDOS", ("Comando", "Funcion"), (
        ("ayuda", "Mostrar esta tabla"), ("estado", "Ver enlace, configuracion y sesion seleccionada"),
        ("capturar", "Capturar Pico y guardar entrada, FIR y espectral"),
        ("evaluar P1 / P2 / P3 / P4 / P5 / P2_tonal", "Procesar un caso en ESP32"),
        ('evaluar "ruta.csv"', "Procesar un CSV propio en ESP32"),
        ("metricas", "Consultar resultados guardados de la sesion seleccionada"),
        ('abrir "ruta_sesion"', "Seleccionar una sesion anterior; despues metricas o reproducir"),
        ("reproducir entrada / fir / espectral", "Escuchar la ruta seleccionada por DAC"),
        ("configurar ganancia=0.3", "Cambiar nivel de escucha, sin modificar los WAV"),
        ("configurar segundos=6 minimo_hz=1600 ancho_hz=100 factor=0.1 umbral=0.05", "Ajustar la siguiente operacion estando detenido"),
        ("configurar interferencia_min_hz=2500 interferencia_max_hz=3800", "Region de evaluacion para CSV propio"),
        ("configurar interferencia_min_hz=auto", "Restablecer regiones automaticas por caso"),
        ("validar", "Recalcular comparacion independiente con Python"),
        ("nota texto", "Guardar observaciones de la sesion seleccionada"),
        ("demo analogico", "Medicion guiada con Pico como instrumento"),
        ("detener", "Cancelar la operacion activa"), ("salir", "Cerrar la terminal"),
    )) + "\nNo abra idf.py monitor al mismo tiempo. Capturar no reproduce sonido."
