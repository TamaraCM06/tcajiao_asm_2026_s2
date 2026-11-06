"""Terminal interactiva: el hilo de trabajo mantiene libre el comando detener."""
import argparse
import math
from pathlib import Path
import shlex
import threading

from .archivos import cargar_csv, abrir_sesion, anotar_sesion
from .cliente import Cliente
from .concordancia import validar_sesion
from .presentacion import (ayuda_terminal, mostrar_configuracion, mostrar_metricas,
                           mostrar_validacion, tabla, valor_visible)
from src.datos.casos import CASOS_FINALES, CASOS_ADICIONALES, EQUIVALENCIAS_HISTORICAS, resolver_caso
from src.datos.archivos import asegurar_muestras_caso


def configuracion_inicial():
    """Conserva los parametros originales y seis segundos como duracion inicial."""
    return dict(muestras=96000, minimo_hz=1600.0, ancho_hz=100.0, factor=0.1, umbral=0.05, ganancia=1.0)


def configurar(actual, argumentos):
    """Valida todo antes de aplicar cambios y redondea la duracion a bloques completos."""
    nueva = actual.copy()
    for argumento in argumentos:
        clave, texto = argumento.split("=", 1)
        if clave in ("interferencia_min_hz", "interferencia_max_hz") and texto.lower() == "auto":
            nueva["interferencia_min_hz"] = nueva["interferencia_max_hz"] = None
            continue
        valor = float(texto)
        if not math.isfinite(valor):
            raise ValueError("Parametros no finitos")
        if clave == "segundos":
            if not 0.016 <= valor <= 60:
                raise ValueError("Duracion entre 0.016 y 60 segundos")
            nueva["muestras"] = math.ceil(valor * 16000 / 256) * 256
        elif clave in ("minimo_hz", "ancho_hz", "factor", "umbral", "ganancia",
                        "interferencia_min_hz", "interferencia_max_hz"):
            nueva[clave] = valor
        else:
            raise ValueError(f"Parametro desconocido: {clave}")
    if not (0 <= nueva["minimo_hz"] < 8000 and 0 <= nueva["ancho_hz"] <= 8000 and
            0 <= nueva["factor"] <= 1 and 0 < nueva["umbral"] <= 1 and 0 <= nueva["ganancia"] <= 100):
        raise ValueError("Parametros fuera de los limites admitidos")
    minimo = nueva.get("interferencia_min_hz")
    maximo = nueva.get("interferencia_max_hz")
    if (minimo is None) != (maximo is None) or (minimo is not None and not (
            0 <= minimo < maximo <= 8000 and math.ceil(minimo / 15.625) <= math.floor(maximo / 15.625))):
        raise ValueError("Indique ambos limites de interferencia, 0 <= minimo < maximo <= 8000, con un bin FFT")
    return nueva


# Consulta exclusivamente archivos de la sesion: no ordena adquisicion ni recalcula validacion.
def mostrar_metricas_sesion(ruta):
    """Recupera resultados ESP32 y validacion guardada sin modificar la evidencia."""
    if ruta is None:
        raise ValueError("Primero capture, evalue o abra una sesion; despues use metricas")
    ruta, metadatos = abrir_sesion(ruta)
    informe = metadatos.get("resultado_esp32")
    if not isinstance(informe, dict) or not all(isinstance(informe.get(metodo), dict)
                                               for metodo in ("fir", "espectral")):
        raise ValueError("La sesion no contiene un informe ESP32 de ambas rutas")
    fuente = metadatos.get("fuente")
    nombre_fuente = Path(str(fuente).replace("\\", "/")).name if fuente else "Captura Pico"
    print(tabla("SESION SELECCIONADA", ("Dato", "Valor"), (
        ("Identificador", ruta.name), ("Fuente", nombre_fuente),
        ("Estado", metadatos.get("estado")),
        ("Muestreo [Hz]", valor_visible(metadatos.get("frecuencia_hz"))),
        ("Escala por sesion", valor_visible(metadatos.get("escala"))),
        ("Unidad de amplitud", metadatos.get("unidad")),
    )))
    validacion = metadatos.get("validacion_python") or {}
    mostrar_metricas(informe, validacion.get("resultados"))
    print(f"Archivos de la sesion: {ruta}")


def main(raiz_proyecto):
    """Abre un unico puerto y coordina operaciones sin bloquear la consola del usuario."""
    import serial
    from serial.tools import list_ports
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--puerto")
    parser.add_argument("--listar", action="store_true")
    parser.add_argument("--puerto-pico", help="Puerto del instrumento Pico; por defecto deteccion USB automatica")
    parser.add_argument("--salidas", type=Path, default=raiz_proyecto / "resultados/sesiones")
    argumentos = parser.parse_args()
    if argumentos.listar:
        puertos = [(puerto.device, puerto.description or "Puerto serie") for puerto in list_ports.comports()]
        print(tabla("PUERTOS DISPONIBLES", ("Puerto", "Descripcion"), puertos) if puertos else "No se detectaron puertos serie.")
        return
    if not argumentos.puerto:
        parser.error("Indique --puerto COMx; use --listar para ver los puertos")
    puerto = serial.Serial(port=None, baudrate=1000000, timeout=0.05, write_timeout=1)
    puerto.dtr = False
    puerto.rts = False
    puerto.port = argumentos.puerto
    puerto.open()
    cliente = Cliente(puerto)
    configuracion = configuracion_inicial()
    ultima_sesion = None
    tarea = None

    # Ejecuta una sesion; solo actualiza la seleccion cuando termino correctamente.
    def trabajar(operacion, seleccion=None):
        """Ejecuta una sesion; solo actualiza la seleccion cuando termino correctamente."""
        nonlocal ultima_sesion
        try:
            if operacion == "reproducir":
                resultado_audio = cliente.reproducir(ultima_sesion, seleccion, configuracion["ganancia"])
                print(tabla("REPRODUCCION FINALIZADA", ("Dato", "Valor"), [
                    ("Ruta", seleccion), ("Ganancia", valor_visible(configuracion["ganancia"])),
                    *[(clave, valor_visible(valor)) for clave, valor in resultado_audio.items()]]))
                return
            if operacion == "capturar":
                resultado = cliente.registrar(argumentos.salidas, configuracion)
            else:
                ruta = (asegurar_muestras_caso(resolver_caso(seleccion), raiz_proyecto / "tarea1_grupo1")
                        if seleccion in (*CASOS_FINALES, *CASOS_ADICIONALES, *EQUIVALENCIAS_HISTORICAS)
                        else Path(seleccion))
                mezcla, referencia, escala, recortes = cargar_csv(ruta)
                print(tabla("ENTRADA PREPARADA", ("Dato", "Valor"), (
                    ("Muestras", str(len(mezcla))), ("Recortes de preparacion", str(recortes)))))
                resultado = cliente.registrar(argumentos.salidas, configuracion, mezcla, referencia,
                                              escala, "archivo", str(ruta.resolve()))
            ultima_sesion, _ = resultado
            try:
                validar_sesion(ultima_sesion, raiz_proyecto)
            except Exception as error:
                print(f"La captura esta completa; no se pudo calcular concordancia PC: {error}")
            mostrar_metricas_sesion(ultima_sesion)
            print(f"\nSESION COMPLETA: {ultima_sesion}")
        except Exception as error:
            print(f"\nERROR: {error}")
            try:
                cliente.cancelar()
            except OSError:
                pass
        finally:
            print("\nPuede escribir otro comando.")

    ayuda = ayuda_terminal()
    try:
        saludo = cliente.conectar()
        velocidad = cliente.comprobar_enlace()
        print(tabla("CONEXION ESP32", ("Dato", "Valor"), (
            ("Estado", saludo), ("Enlace verificado [bytes/s]", f"{velocidad:.0f}"))))
        print(ayuda)
        while True:
            try:
                texto = input("asm> ")
            except (EOFError, KeyboardInterrupt):
                texto = "salir"
            partes = [parte.strip('"') for parte in shlex.split(texto, posix=False)]
            if not partes:
                continue
            orden = partes[0].lower()
            ocupada = tarea is not None and tarea.is_alive()
            try:
                if orden == "ayuda":
                    print(ayuda)
                elif orden == "estado":
                    mostrar_configuracion(configuracion, ultima_sesion, "OCUPADO" if ocupada else cliente.conectar())
                elif orden == "detener":
                    if ocupada:
                        cliente.cancelar()
                    else:
                        print("Ya esta detenido")
                elif orden == "salir":
                    if ocupada:
                        cliente.cancelar()
                        tarea.join(timeout=5)
                    break
                elif ocupada:
                    print("Hay una operacion activa. Espere o escriba detener.")
                elif orden == "configurar":
                    configuracion = configurar(configuracion, partes[1:])
                    mostrar_configuracion(configuracion, ultima_sesion)
                elif orden == "abrir" and len(partes) == 2:
                    ultima_sesion, _ = abrir_sesion(partes[1])
                    print(tabla("SESION ABIERTA", ("Dato", "Valor"), (
                        ("Identificador", ultima_sesion.name), ("Consulta", "metricas"),
                        ("Escucha", "reproducir entrada / fir / espectral"))))
                    print(f"Archivos de la sesion: {ultima_sesion}")
                elif orden == "metricas":
                    if len(partes) != 1:
                        raise ValueError("Use metricas sin argumentos; abrir selecciona la sesion")
                    mostrar_metricas_sesion(ultima_sesion)
                elif orden == "validar":
                    if ultima_sesion is None:
                        raise ValueError("Primero capture, evalue o abra una sesion")
                    resultados = validar_sesion(ultima_sesion, raiz_proyecto)
                    mostrar_validacion(resultados)
                elif orden == "nota":
                    if ultima_sesion is None:
                        raise ValueError("Primero capture, evalue o abra una sesion completa")
                    ruta_nota = anotar_sesion(ultima_sesion, " ".join(partes[1:]))
                    print(tabla("OBSERVACION GUARDADA", ("Dato", "Valor"), (("Archivo", str(ruta_nota)),)))
                elif orden == "demo" and len(partes) == 2 and partes[1].lower() == "analogico":
                    from .demo_analogica import ejecutar_demo
                    _, ultima_sesion = ejecutar_demo(cliente, raiz_proyecto, argumentos.salidas,
                        configuracion, ultima_sesion, argumentos.puerto_pico)
                elif orden in ("capturar", "evaluar", "reproducir"):
                    if orden != "capturar" and len(partes) != 2:
                        raise ValueError("Falta seleccionar archivo o senal")
                    if orden == "reproducir" and ultima_sesion is None:
                        raise ValueError("Primero capture, evalue o abra una sesion completa")
                    tarea = threading.Thread(target=trabajar, args=(orden, partes[1] if len(partes) > 1 else None), daemon=True)
                    tarea.start()
                else:
                    print("Comando desconocido. Escriba ayuda.")
            except (ValueError, OSError, RuntimeError, TimeoutError) as error:
                print(f"ERROR: {error}")
    finally:
        puerto.close()
