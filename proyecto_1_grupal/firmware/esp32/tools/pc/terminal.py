"""Terminal interactiva: el hilo de trabajo mantiene libre el comando detener."""
import argparse
import math
from pathlib import Path
import shlex
import threading

from .archivos import cargar_csv, abrir_sesion
from .cliente import Cliente


def configuracion_inicial():
    """Conserva los parametros originales y seis segundos como duracion inicial."""
    return dict(muestras=96000, minimo_hz=1600.0, ancho_hz=100.0, factor=0.1, umbral=0.05, ganancia=1.0)


def configurar(actual, argumentos):
    """Valida todo antes de aplicar cambios y redondea la duracion a bloques completos."""
    nueva = actual.copy()
    for argumento in argumentos:
        clave, texto = argumento.split("=", 1)
        valor = float(texto)
        if not math.isfinite(valor):
            raise ValueError("Parametros no finitos")
        if clave == "segundos":
            if not 0.016 <= valor <= 60:
                raise ValueError("Duracion entre 0.016 y 60 segundos")
            nueva["muestras"] = math.ceil(valor * 16000 / 256) * 256
        elif clave in ("minimo_hz", "ancho_hz", "factor", "umbral", "ganancia"):
            nueva[clave] = valor
        else:
            raise ValueError(f"Parametro desconocido: {clave}")
    if not (0 <= nueva["minimo_hz"] < 8000 and 0 <= nueva["ancho_hz"] <= 8000 and
            0 <= nueva["factor"] <= 1 and 0 < nueva["umbral"] <= 1 and 0 <= nueva["ganancia"] <= 100):
        raise ValueError("Parametros fuera de los limites admitidos")
    return nueva


def mostrar_metricas(informe):
    """Presenta las cifras recibidas del microcontrolador, sin calcular sustitutos en PC."""
    for metodo in ("fir", "espectral"):
        ruta = informe[metodo]
        print(f"\n{metodo.upper()}:")
        for clave, valor in ruta.items():
            print(f"  {clave}: {'no disponible' if valor is None else valor}")
    print(f"Calculo maximo: {informe['calculo_max_us']} us. No equivale a latencia analogica.")


def main(raiz_proyecto):
    """Abre un unico puerto y coordina operaciones sin bloquear la consola del usuario."""
    import serial
    from serial.tools import list_ports
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--puerto")
    parser.add_argument("--listar", action="store_true")
    parser.add_argument("--salidas", type=Path, default=raiz_proyecto / "resultados/sesiones")
    argumentos = parser.parse_args()
    if argumentos.listar:
        for puerto in list_ports.comports():
            print(puerto.device, puerto.description)
        return
    if not argumentos.puerto:
        parser.error("Indique --puerto COMx; use --listar para ver los puertos")
    puerto = serial.Serial(port=None, baudrate=2000000, timeout=0.05, write_timeout=1)
    puerto.dtr = False
    puerto.rts = False
    puerto.port = argumentos.puerto
    puerto.open()
    cliente = Cliente(puerto)
    configuracion = configuracion_inicial()
    ultima_sesion = None
    tarea = None

    def trabajar(operacion, seleccion=None):
        """Ejecuta una sesion; solo actualiza la seleccion cuando termino correctamente."""
        nonlocal ultima_sesion
        try:
            if operacion == "reproducir":
                print(cliente.reproducir(ultima_sesion, seleccion, configuracion["ganancia"]))
                return
            if operacion == "capturar":
                resultado = cliente.registrar(argumentos.salidas, configuracion)
            else:
                ruta = raiz_proyecto / "tarea1_grupo1/resultados/muestras" / f"{seleccion}_muestras.csv" if seleccion in (
                    "caso_1", "caso_2", "caso_3") else Path(seleccion)
                mezcla, referencia, escala, recortes = cargar_csv(ruta)
                print(f"Entrada: {len(mezcla)} muestras; recortes de preparacion: {recortes}")
                resultado = cliente.registrar(argumentos.salidas, configuracion, mezcla, referencia,
                                              escala, "archivo", str(ruta.resolve()))
            ultima_sesion, informe = resultado
            mostrar_metricas(informe)
            print(f"\nSESION COMPLETA: {ultima_sesion}")
        except Exception as error:
            print(f"\nERROR: {error}")
            try:
                cliente.cancelar()
            except OSError:
                pass
        finally:
            print("\nPuede escribir otro comando.")

    ayuda = ("ayuda | estado | capturar | evaluar caso_1/caso_2/caso_3 o ruta.csv\n"
             "configurar segundos=6 minimo_hz=1600 ancho_hz=100 factor=0.1 umbral=0.05 ganancia=1\n"
             "abrir ruta_sesion | reproducir entrada/fir/espectral | detener | salir\n"
             "No abra idf.py monitor al mismo tiempo. Capturar no reproduce sonido.")
    try:
        print(cliente.conectar())
        print(f"Enlace verificado: {cliente.comprobar_enlace():.0f} bytes/s")
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
                    print("OCUPADO" if ocupada else cliente.conectar())
                    print(configuracion, "sesion:", ultima_sesion)
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
                    print(configuracion, f"Duracion efectiva: {configuracion['muestras'] / 16000:.3f} s")
                elif orden == "abrir" and len(partes) == 2:
                    ultima_sesion, _ = abrir_sesion(partes[1])
                    print(ultima_sesion)
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
