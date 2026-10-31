#!/usr/bin/env python3
"""Visualiza capturas ADC de la Pico; no une bloques separados en el tiempo."""

import argparse
from dataclasses import dataclass
import math
import grp
import os
import queue
import shlex
import threading
import time


@dataclass(frozen=True)
class Captura:
    bloque: int
    fs: int
    vref: float
    perdidos: int
    errores: int
    reinicios: int
    codigos: tuple[int, ...]

    @property
    def voltios(self):
        return [codigo * self.vref / 4095 for codigo in self.codigos]


def decodificar(linea: bytes):
    """Ignora tabla, datos incompletos y tramas fuera del contrato ADC1."""
    try:
        campos = linea.decode("ascii").strip().split(",")
        if campos[0] != "ADC1" or len(campos) < 8:
            return None
        bloque, fs = int(campos[1]), int(campos[2])
        vref = float(campos[3])
        perdidos, errores, reinicios, n = map(int, campos[4:8])
        if n != 256 or len(campos) != 8 + n or fs != 10000:
            return None
        if not math.isfinite(vref) or not 0 < vref <= 5:
            return None
        if not all(0 <= valor <= 0xFFFFFFFF for valor in (bloque, perdidos, errores, reinicios)):
            return None
        codigos = tuple(map(int, campos[8:]))
        if any(codigo < 0 or codigo > 4095 for codigo in codigos):
            return None
        return Captura(bloque, fs, vref, perdidos, errores, reinicios, codigos)
    except (ValueError, UnicodeDecodeError):
        return None


def recibir(puerto, ultimos, detener):
    """Lee fuera del hilo grafico y conserva solo la captura mas reciente."""
    def publicar(dato):
        try:
            ultimos.get_nowait()
        except queue.Empty:
            pass
        ultimos.put_nowait((dato, time.monotonic()))

    proxima = 0.0
    try:
        while not detener.is_set():
            if time.monotonic() >= proxima:
                puerto.write(b"g")
                proxima = time.monotonic() + 0.2
            captura = decodificar(puerto.readline(4096))
            if captura is not None:
                publicar(captura)
    except OSError as exc:
        publicar(str(exc))


def crear_figura():
    import matplotlib.pyplot as plt

    figura, (adc, ac) = plt.subplots(2, 1, figsize=(11, 7), sharex=True)
    figura.canvas.manager.set_window_title("Pico — micrófono en GPIO26")
    figura.suptitle("Esperando muestras de la Pico…")
    linea_adc, = adc.plot([], [], color="#1874b5", linewidth=1.3)
    linea_ac, = ac.plot([], [], color="#d66b13", linewidth=1.3)
    adc.set(title="Voltaje de entrada medido por el ADC (incluye offset DC)", ylabel="Voltaje [V]", ylim=(0, 3.3))
    ac.set(title="Señal sin DC — muestras equivalentes a la futura salida SPI",
           ylabel="Amplitud [mV]", xlabel="Tiempo dentro del bloque [ms]", ylim=(-10, 10))
    ac.axhline(0, color="gray", linewidth=0.6)
    for eje in (adc, ac):
        eje.grid(True, alpha=0.25)
        eje.set_xlim(0, 25.6)
    estado = figura.text(0.02, 0.02, "", fontsize=9)
    figura.tight_layout(rect=(0, 0.10, 1, 0.93))
    return figura, adc, ac, linea_adc, linea_ac, estado


def mostrar(captura, elementos, numero=None):
    figura, adc, ac, linea_adc, linea_ac, estado = elementos
    voltios = captura.voltios
    media = sum(voltios) / len(voltios)
    sin_dc = [(valor - media) * 1000 for valor in voltios]
    tiempos = [i * 1000 / captura.fs for i in range(len(voltios))]
    rms = math.sqrt(sum(valor * valor for valor in sin_dc) / len(sin_dc))
    saturadas = sum(valor in (0, 4095) for valor in captura.codigos)
    linea_adc.set_data(tiempos, voltios)
    linea_ac.set_data(tiempos, sin_dc)
    adc.set_ylim(0, captura.vref)
    escala = max(1.0, max(abs(valor) for valor in sin_dc) * 1.2)
    ac.set_ylim(-escala, escala)
    titulo = (f"GPIO26 | bloque {captura.bloque} | DC {media:.3f} V | "
              f"RMS {rms:.2f} mV | Vpp {(max(voltios) - min(voltios)) * 1000:.2f} mV")
    figura.suptitle(titulo if numero is None else titulo + f" | captura #{numero}")
    estado.set_text(f"{captura.fs} muestras/s · 256 muestras = 25.6 ms · ~5 capturas/s (hay huecos entre bloques)\n"
                    f"Saturadas: {saturadas}/256 | Perdidos: {captura.perdidos} | Errores ADC: {captura.errores} | "
                    f"Reinicios: {captura.reinicios} | Escala AC automática; compare RMS y Vpp.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--puerto", help="Por ejemplo /dev/ttyACM0; por defecto busca una Pico")
    args = parser.parse_args()
    try:
        import serial
        from serial.tools import list_ports
        import matplotlib
        if matplotlib.get_backend().lower() == "agg":
            try:
                import tkinter  # noqa: F401; comprueba tambien la biblioteca nativa Tk
                matplotlib.use("TkAgg")
            except (ImportError, RuntimeError) as exc:
                parser.exit(1, f"No hay un backend grafico disponible: {exc}\n"
                               "En Arch Linux instale: sudo pacman -S --needed tk\n"
                               "Luego ejecute desde una terminal del escritorio, sin sudo.\n")
        import matplotlib.pyplot as plt
        from matplotlib.animation import FuncAnimation
    except ImportError as exc:
        parser.exit(1, f"Falta una dependencia: {exc}. Instale tools/requirements.txt en un entorno virtual.\n")
    nombre = args.puerto
    if not nombre:
        candidatos = [p.device for p in list_ports.comports() if p.vid == 0x2E8A and p.pid == 0x000A]
        if len(candidatos) != 1:
            parser.exit(1, "Conecte una Pico con el firmware receptor o indique --puerto /dev/ttyACM0.\n")
        nombre = candidatos[0]
    try:
        puerto = serial.Serial(nombre, 115200, timeout=0.1, write_timeout=0.5, exclusive=True)
    except (serial.SerialException, OSError) as exc:
        consejo = "Cierre cat/otras terminales y revise permisos del puerto.\n"
        if exc.errno == 13:
            try:
                grupo = grp.getgrgid(os.stat(nombre).st_gid).gr_name
                consejo = (f'Agregue su usuario al grupo del puerto: sudo usermod -aG {shlex.quote(grupo)} "$USER"\n'
                           "Cierre sesion de Linux y vuelva a entrar; luego ejecute sin sudo.\n")
            except (OSError, KeyError):
                pass
        parser.exit(1, f"No se pudo abrir {nombre}: {exc}\n{consejo}")

    detener = threading.Event()
    ultimos = queue.Queue(maxsize=1)
    hilo = None
    try:
        puerto.reset_input_buffer()
        elementos = crear_figura()
        figura = elementos[0]
        hilo = threading.Thread(target=recibir, args=(puerto, ultimos, detener), daemon=True)
        hilo.start()
        ultima = time.monotonic()
        recibidas = 0

        def actualizar(_):
            nonlocal ultima, recibidas
            try:
                dato, instante = ultimos.get_nowait()
            except queue.Empty:
                if not detener.is_set() and time.monotonic() - ultima > 2:
                    elementos[-1].set_text("SIN DATOS RECIENTES: revise USB y cargue el nuevo firmware.\n"
                                           "Cierre cualquier otra consola que esté leyendo este puerto.")
                return
            if isinstance(dato, str):
                elementos[-1].set_text(f"USB desconectado o error de lectura: {dato}")
                detener.set()
                return
            ultima = instante
            recibidas += 1
            mostrar(dato, elementos, recibidas)

        animacion = FuncAnimation(figura, actualizar, interval=100, cache_frame_data=False)
        print(f"Graficando {nombre}. Cierre la ventana o use Ctrl+C para terminar.")
        plt.show()
        del animacion
    except KeyboardInterrupt:
        pass
    except (ImportError, RuntimeError) as exc:
        parser.exit(1, f"No se pudo abrir la ventana: {exc}\n"
                       "En Arch Linux instale Tk (sudo pacman -S --needed tk) "
                       "y ejecute desde el escritorio sin sudo.\n")
    finally:
        detener.set()
        if hilo is not None:
            hilo.join(timeout=1)
        try:
            puerto.write(b"t")
        except (serial.SerialException, OSError):
            pass
        puerto.close()


if __name__ == "__main__":
    main()
