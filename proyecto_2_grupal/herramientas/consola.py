#!/usr/bin/env python3
"""Consola del banco de frenado (ESP32) con prompt visible y registro de ensayos.

- Escribes los comandos del firmware (STATUS, CONFIG, FRENO, MOTOR, START, STOP, ENSAYO)
  en un prompt normal: ves lo que tecleas, con flechas e historial.
- Cada captura (de "inicio" a "fin") se guarda en experimentos/datos/<nombre>_<n>.csv,
  con el mismo formato que el receptor MATLAB, mas un .json con configuracion y eventos.
- Al terminar cada captura muestra un resumen para evaluar el ensayo.

Uso:  python consola_banco.py [--nombre escalon] [--puerto /dev/ttyUSB0] [--reiniciar]
Requiere pyserial (incluido en el entorno Python de ESP-IDF). Salir: Ctrl+D o "salir".
"""
import argparse
import json
import readline  # noqa: F401  (activa edicion de linea e historial en input())
import sys
import threading
import time
from datetime import datetime
from pathlib import Path

import serial

DATOS = Path(__file__).resolve().parent / "datos"
CABECERA = "tiempo_ms,freno_deg,velocidad_rpm"
PROMPT = "banco> "
GRIS, ROJO, AMARILLO, VERDE, CIAN, FIN = "\033[90m", "\033[91m", "\033[93m", "\033[92m", "\033[96m", "\033[0m"
bloqueo = threading.Lock()


def mostrar(texto, color=""):
    """Imprime encima del prompt sin borrar lo que el usuario esta escribiendo."""
    with bloqueo:
        escrito = readline.get_line_buffer()
        sys.stdout.write(f"\r\033[K{color}{texto}{FIN if color else ''}\n{PROMPT}{escrito}")
        sys.stdout.flush()


def recta(t, y):
    """Pendiente por minimos cuadrados (y por segundo)."""
    n = len(t)
    if n < 2:
        return float("nan")
    mt, my = sum(t) / n, sum(y) / n
    den = sum((a - mt) ** 2 for a in t)
    return sum((a - mt) * (b - my) for a, b in zip(t, y)) / den if den else float("nan")


def resumir(filas, eventos):
    """Resumen rapido del ensayo, con los mismos tramos de 300 ms que visualizar_ensayo.m."""
    if len(filas) < 3:
        return ["Muy pocas filas para evaluar."]
    t = [f[0] / 1000 for f in filas]
    freno = [f[1] for f in filas]
    rpm = [f[2] for f in filas]
    validas = [r for r in rpm if r == r]
    lineas = [f"Filas: {len(filas)} | duración: {t[-1]:.2f} s | RPM máx: {max(validas, default=float('nan')):.1f}"]
    cambios = [i for i in range(1, len(freno)) if freno[i] != freno[i - 1]]
    if len(cambios) != 1:
        lineas.append(f"Cambios de freno en la captura: {len(cambios)} (visualizar_ensayo.m exige exactamente 1).")
        return lineas
    k = cambios[0]
    t0 = t[k]
    antes = [(a, b) for a, b in zip(t, rpm) if t0 - 0.3 <= a < t0 and b == b and b > 0]
    despues = [(a, b) for a, b in zip(t, rpm) if t0 <= a <= t0 + 0.3 and b == b and b > 0]
    pa = recta([a for a, _ in antes], [b for _, b in antes])
    pd = recta([a for a, _ in despues], [b for _, b in despues])
    parada = next((a for a, b in zip(t, rpm) if a >= t0 and b == 0), None)
    lineas.append(f"Freno {freno[k - 1]:.0f}° → {freno[k]:.0f}° a t = {t0:.3f} s, con {rpm[k]:.1f} RPM")
    lineas.append(f"Desaceleración antes: {pa:.1f} RPM/s ({len(antes)} muestras) | después: {pd:.1f} RPM/s ({len(despues)})")
    if len(antes) < 2:
        lineas.append("Faltan muestras de giro libre antes del freno: usa espera_ms ≥ 100 en ENSAYO.")
    lineas.append(f"Tiempo hasta detenerse tras el freno: {parada - t0:.2f} s" if parada is not None
                  else "El disco no llegó a 0 RPM dentro de la captura.")
    return lineas


class Captura:
    """Escribe el CSV y el JSON de una captura, igual que +captura/Registro.m."""

    def __init__(self, nombre):
        DATOS.mkdir(parents=True, exist_ok=True)
        n = 1
        while (DATOS / f"{nombre}_{n:02d}.csv").exists():
            n += 1
        self.base = DATOS / f"{nombre}_{n:02d}"
        self.csv = open(self.base.with_suffix(".csv"), "w", encoding="utf-8")
        self.meta = {"protocolo": 1, "fecha_pc": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                     "receptor": "consola_banco.py", "configuracion": {}, "eventos": [], "errores": []}
        self.filas, self.cabecera, self.invalidas = [], False, 0

    def linea_datos(self, texto):
        if texto == CABECERA:
            if not self.cabecera:
                self.cabecera = True
                self.csv.write(texto + "\n")
            return
        partes = texto.split(",")
        try:
            t, f, r = (float(p) for p in partes)
        except ValueError:
            self.invalidas += 1
            return
        if not self.cabecera or len(partes) != 3 or (self.filas and t <= self.filas[-1][0]):
            self.invalidas += 1
            return
        self.csv.write(texto + "\n")
        self.filas.append((t, f, r))

    def cerrar(self, fin):
        self.csv.close()
        self.meta.update(fin=fin, muestras_recibidas=len(self.filas), filas_invalidas=self.invalidas,
                         completo=bool(fin and fin.get("completo")) and self.invalidas == 0
                         and fin.get("enviadas") == len(self.filas))
        self.base.with_suffix(".json").write_text(json.dumps(self.meta, indent=2, ensure_ascii=False) + "\n")
        return self.base.with_suffix(".csv")


def leer(puerto, nombre, activo):
    captura = None
    contador = 0
    while activo.is_set():
        try:
            crudo = puerto.readline()
        except serial.SerialException as error:
            mostrar(f"Puerto perdido: {error}", ROJO)
            activo.clear()
            return
        if not crudo:
            continue
        texto = crudo.decode("utf-8", "replace").strip()
        if not texto:
            continue
        if texto.startswith("# "):
            try:
                mensaje = json.loads(texto[2:])
            except json.JSONDecodeError:
                mostrar(texto, GRIS)
                continue
            tipo = mensaje.get("tipo")
            if tipo == "inicio":
                captura = Captura(nombre)
                captura.meta["inicio"] = mensaje
                contador = 0
                mostrar(f"▶ Captura {mensaje.get('ensayo')} iniciada → {captura.base.name}.csv", VERDE)
                continue
            if captura and tipo == "configuracion":
                captura.meta["configuracion"][mensaje.get("grupo")] = mensaje
                continue
            if captura and tipo in ("evento", "error"):
                captura.meta["eventos" if tipo == "evento" else "errores"].append(mensaje)
            if tipo == "fin" and captura:
                ruta = captura.cerrar(mensaje)
                mostrar(f"■ Captura cerrada ({mensaje.get('motivo')}), completa: {captura.meta['completo']} → {ruta}", VERDE)
                for linea in resumir(captura.filas, captura.meta["eventos"]):
                    mostrar("  " + linea, CIAN)
                captura = None
                continue
            mostrar(texto, ROJO if tipo == "error" else AMARILLO if tipo == "evento" else "")
        elif captura:
            captura.linea_datos(texto)
            contador += 1
            if contador % 25 == 1:  # muestra ~2 filas por segundo a 20 ms
                mostrar(f"  {texto}", GRIS)
        else:
            mostrar(texto, GRIS)


def main():
    argumentos = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    argumentos.add_argument("--puerto", default="/dev/ttyUSB0")
    argumentos.add_argument("--nombre", default="escalon", help="prefijo de los archivos de captura")
    argumentos.add_argument("--reiniciar", action="store_true", help="reinicia la placa al conectar")
    opciones = argumentos.parse_args()

    puerto = serial.Serial()
    puerto.port, puerto.baudrate, puerto.timeout = opciones.puerto, 115200, 0.1
    puerto.dtr = puerto.rts = False  # abrir sin reiniciar ni entrar a modo descarga
    try:
        puerto.open()
    except serial.SerialException as error:
        sys.exit(f"No se pudo abrir {opciones.puerto}: {error}\n(¿monitor abierto en otra terminal o falta permiso?)")
    if opciones.reiniciar:
        puerto.rts = True
        time.sleep(0.1)
        puerto.rts = False

    activo = threading.Event()
    activo.set()
    threading.Thread(target=leer, args=(puerto, opciones.nombre, activo), daemon=True).start()
    print(f"Conectado a {opciones.puerto}. Capturas en {DATOS}/{opciones.nombre}_NN.csv")
    print("Comandos: STATUS, CONFIG p d t, FRENO g, MOTOR %, START, STOP, ENSAYO % g espera_ms. Salir: Ctrl+D")
    try:
        while activo.is_set():
            linea = input(PROMPT).strip()
            if linea.lower() in ("salir", "exit", "quit"):
                break
            if linea:
                puerto.write((linea + "\n").encode("ascii", "replace"))
    except (EOFError, KeyboardInterrupt):
        pass
    activo.clear()
    puerto.close()
    print()


if __name__ == "__main__":
    main()
