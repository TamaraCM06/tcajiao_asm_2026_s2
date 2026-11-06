"""Demostracion guiada: el usuario cambia la sonda; la PC guarda y compara las medidas."""
import csv
from datetime import datetime, timezone
import json
from pathlib import Path
import uuid
import traceback

import numpy as np

from .analisis_analogico import comparar_respuesta, ganancia_teorica, guardar_figura, resumir_capturas
from .archivos import abrir_sesion, cargar_csv, guardar_json
from .concordancia import leer_pcm, validar_sesion
from .pico_instrumento import abrir_pico, medir_punto
from .presentacion import dato_disponible, tabla, valor_visible
from herramientas.capturas_pico import LectorPico
from src.datos.archivos import asegurar_muestras_caso


def cargar_modelo(raiz_proyecto):
    """Carga componentes y criterios visibles, fijados antes de tomar datos."""
    modelo = json.loads((raiz_proyecto / "metadatos/filtro_analogico.json").read_text(encoding="utf-8"))
    casos = json.loads((raiz_proyecto / "tarea1_grupo1/metadatos/configuraciones.json").read_text(encoding="utf-8"))
    caso = casos["P2_tonal"]
    frecuencias = sorted(set(caso["frecuencias_utiles_Hz"] + [caso["frecuencia_interferencia_Hz"]]))
    if caso["fs_Hz"] != 16000 or max(frecuencias) >= 8000:
        raise ValueError("La demo requiere P2_tonal a 16 kHz y frecuencias inferiores a Nyquist")
    if (not isinstance(modelo["capturas_por_punto"], int) or not 3 <= modelo["capturas_por_punto"] <= 16 or
            not 0 <= modelo["espera_estabilizacion_s"] <= 1 or
            not 0.1 <= modelo["intervalo_capturas_s"] <= 0.25 or
            not 0 < modelo["tolerancia_error_ganancia_pct"] <= 100 or
            not 0 < modelo["variabilidad_maxima_amplitud_pct"] <= 100):
        raise ValueError("Parametros de medicion fuera de los limites admitidos")
    ganancia_teorica(frecuencias, modelo)
    return modelo, frecuencias


def preparar_fuente(cliente, raiz_proyecto, raiz_sesiones, configuracion, seleccion=None):
    """Reutiliza una entrada P2_tonal verificada o la procesa en ESP32 sin generar otro estimulo."""
    archivo = asegurar_muestras_caso("P2_tonal", raiz_proyecto / "tarea1_grupo1")
    mezcla, referencia, escala, _ = cargar_csv(archivo)
    candidatos = ([Path(seleccion)] if seleccion else [])
    candidatos.extend(sorted(raiz_sesiones.glob("*/sesion.json"), reverse=True))
    for candidato in candidatos:
        ruta = candidato.parent if candidato.name == "sesion.json" else candidato
        try:
            ruta, datos = abrir_sesion(ruta)
            if (datos.get("unidad") == "normalizada" and np.float32(datos["escala"]) == np.float32(escala) and
                    np.array_equal(leer_pcm(ruta / "entrada.wav"), mezcla)):
                return ruta
        except (OSError, ValueError, KeyError):
            continue
    ruta, _ = cliente.registrar(raiz_sesiones, dict(configuracion, muestras=len(mezcla)),
        mezcla, referencia, escala, "archivo", str(archivo.resolve()))
    validar_sesion(ruta, raiz_proyecto)
    return ruta


def pedir_conexion(texto, preguntar=input):
    """Espera al usuario antes de energizar la reproduccion con una nueva sonda ADC."""
    respuesta = preguntar(texto + "\nPulse Enter cuando este listo, o escriba cancelar: ")
    if respuesta.strip().lower() not in ("", "listo"):
        raise RuntimeError("Demo cancelada por el usuario")


def ejecutar_demo(cliente, raiz_proyecto, raiz_sesiones, configuracion, seleccion=None,
                  puerto_pico=None, preguntar=input, informar=print):
    """Mide dos puntos con el mismo archivo y guarda evidencia incluso si la prueba falla."""
    raiz_proyecto, raiz_sesiones = Path(raiz_proyecto), Path(raiz_sesiones)
    modelo, frecuencias = cargar_modelo(raiz_proyecto)
    identificador = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "_" + uuid.uuid4().hex[:8]
    carpeta = raiz_sesiones / "analogicas" / identificador
    carpeta.mkdir(parents=True, exist_ok=False)
    datos = dict(estado="incompleta", modelo=modelo, frecuencias_hz=frecuencias, ganancia_reproduccion=1,
        muestreo_hz=16000, bloques_separados=True,
        formula_concordancia="max(0,100-100*abs(ganancia_medida/ganancia_teorica-1))",
        limite="Medicion de ganancia, sin calibrar ADC ni medir imagenes alrededor de 16 kHz")
    guardar_json(carpeta / "medicion.json", datos)
    try:
        informar("\nDEMO ANALOGICA: P2_tonal del notebook; se reproduce siempre entrada con ganancia 1.")
        informar("Los bloques ADC estan separados por huecos; se guardan individualmente en CSV.")
        informar("Pico GP26/ADC0 es pin fisico 31; GND comun. No conectar 5 V ni salidas del parlante.")
        informar("Desconecte el microfono de GP26. Verifique con multimetro que ambos puntos esten entre 0 y 3.3 V.")
        informar("Volumen del GF1002 al minimo. El filtro LM358 permanece alimentado y conectado a GPIO25.")
        informar(tabla("CRITERIO ANALOGICO FIJADO ANTES DE MEDIR", ("Dato", "Valor"), (
            ("Error de ganancia maximo [%]", valor_visible(modelo["tolerancia_error_ganancia_pct"])),
            ("Ganancia de reproduccion", "1"), ("Estimulo", "Entrada P2_tonal del notebook"))))
        informar("Preparando/reutilizando el archivo original del P2_tonal...")
        fuente = preparar_fuente(cliente, raiz_proyecto, raiz_sesiones, configuracion, seleccion)
        datos["sesion_fuente"] = str(fuente)
        guardar_json(carpeta / "medicion.json", datos)
        resumenes = {}
        for punto, conexion in (("antes", "Conecte GP26 de la PICO a GPIO25 de la ESP32 (antes del divisor)."),
                                ("despues", "Mueva SOLO la sonda GP26 de la PICO al pin 7 del LM358 (salida del filtro).")):
            datos["etapa"] = f"conexion_{punto}"
            guardar_json(carpeta / "medicion.json", datos)
            pedir_conexion(conexion, preguntar)
            # La sonda puede reconectarse con la Pico apagada: abrir USB solo despues.
            with abrir_pico(puerto_pico) as puerto:
                datos["puerto_pico"] = puerto.port
                datos["etapa"] = f"verificacion_usb_{punto}"
                guardar_json(carpeta / "medicion.json", datos)
                informar(f"Comprobando la Pico en {puerto.port} antes de reproducir...")
                LectorPico(puerto).solicitar()
                datos["etapa"] = f"medicion_{punto}"
                guardar_json(carpeta / "medicion.json", datos)
                informar(f"Midiendo {punto}; espere a que termine la reproduccion de seis segundos...")
                capturas, reproduccion = medir_punto(cliente, fuente, puerto, carpeta / f"medicion_{punto}.csv", modelo)
                resumenes[punto] = resumir_capturas(capturas, frecuencias)
                datos[punto] = dict(resumenes[punto], reproduccion=reproduccion)
                guardar_json(carpeta / "medicion.json", datos)
                informar(tabla(f"ADQUISICION ANALOGICA: {punto.upper()}", ("Dato", "Valor"), (
                    ("Nivel DC medio [V]", valor_visible(resumenes[punto]["nivel_dc_v"], ".3f")),
                    ("Muestras saturadas", valor_visible(resumenes[punto]["saturadas"])))))
        filas = comparar_respuesta(resumenes["antes"], resumenes["despues"], frecuencias, modelo)
        with (carpeta / "comparacion_analogica.csv").open("w", encoding="utf-8", newline="") as archivo:
            escritor = csv.DictWriter(archivo, fieldnames=list(filas[0]))
            escritor.writeheader()
            escritor.writerows(filas)
        guardar_figura(carpeta / "respuesta_analogica.png", filas, modelo)
        datos.update(estado="completa", etapa="finalizada", resultados=filas,
                     cumple_criterio=all(fila["cumple_criterio"] for fila in filas))
        guardar_json(carpeta / "medicion.json", datos)
        filas_visibles = []
        filas_revision = []
        for fila in filas:
            estado = "CUMPLE" if fila["cumple_criterio"] else (
                "REVISAR: fuera de tolerancia" if fila["medida_valida"] else "REVISAR: " + fila["observacion"])
            if all(dato_disponible(fila[clave]) for clave in ("ganancia_medida", "concordancia_teorica_pct")):
                filas_visibles.append((valor_visible(fila["frecuencia_hz"], ".0f"),
                    valor_visible(fila["ganancia_teorica"], ".4f"), valor_visible(fila["ganancia_medida"], ".4f"),
                    valor_visible(fila["concordancia_teorica_pct"], ".2f"), estado))
            else:
                filas_revision.append((valor_visible(fila["frecuencia_hz"], ".0f"), estado))
        informar(tabla("RESPUESTA ANALOGICA", ("Hz", "Ganancia modelo", "Ganancia medida", "Concordancia [%]", "Criterio"),
                       filas_visibles, (0, 1, 2, 3)))
        if filas_revision:
            informar(tabla("MEDICIONES ANALOGICAS A REVISAR", ("Hz", "Observacion"), filas_revision, (0,)))
        informar(f"MEDICION GUARDADA: {carpeta}")
        informar("Antes de volver a capturar sonidos, desconecte la sonda y restablezca el microfono en GP26.")
        return carpeta, fuente
    except BaseException as error:
        datos.update(estado="incompleta", causa=str(error))
        guardar_json(carpeta / "medicion.json", datos)
        (carpeta / "diagnostico_error.txt").write_text(traceback.format_exc(), encoding="utf-8")
        informar(f"Medicion incompleta conservada en {carpeta}")
        raise
