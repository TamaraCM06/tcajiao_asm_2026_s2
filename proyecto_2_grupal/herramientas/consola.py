#!/usr/bin/env python3
"""Consola del banco de frenado. Se abre con: python banco.py consola

Al conectar configura el registro (CONFIG 20 10000 100) y libera el freno. Comandos cortos en
minusculas (escribe `ayuda`); los del firmware en mayusculas pasan tal cual. Cada captura se guarda
en datos/<nombre>_NN.csv (tiempo_ms,freno_deg,velocidad_rpm) con su .json de configuracion y eventos.
"""
import argparse
import json
import os
import sys
import threading
import time
from datetime import datetime
from pathlib import Path

import serial

try:
    import readline
except ImportError:  # Windows sin pyreadline3: sin historial ni Tab, pero funciona
    readline = None

DATOS = Path(__file__).resolve().parents[1] / "datos"
CABECERA = "tiempo_ms,freno_deg,velocidad_rpm"
CONFIG_INICIAL = "CONFIG 20 10000 100"   # fila cada 20 ms, 10 s maximo, cero tras 100 ms sin pulsos
PROMPT = "banco> "
GRIS, ROJO, AMARILLO, VERDE, CIAN, NEGRITA, FIN = (
    "\033[90m", "\033[91m", "\033[93m", "\033[92m", "\033[96m", "\033[1m", "\033[0m")

AYUDA = """\
  liberar                 freno a la posicion liberada
  frenar [grados]         aplica el freno (por defecto el maximo calibrado)
  motor <porcentaje>      impulsa el disco; motor 0 lo corta
  ensayo [% grados ms]    acelera, corta el motor al llegar a la velocidad maxima, graba y frena
                          tras la espera (por defecto: 60 % · freno maximo · 300 ms)
  grabar                  graba ya (corta el motor); parar termina la captura
  parar                   corta motor, libera el freno y cierra la captura
  estado                  estado de la placa y velocidad actual
  config [p d t]          sin numeros muestra la configuracion; con numeros: periodo, duracion y timeout en ms
  cal                     calibracion del servo:
      cal pulso <us>          mueve el servo a ese pulso (dentro del recorrido calibrado)
      cal + | cal -           un paso (cal paso <grados> lo cambia, 2 por defecto)
      cal liberado            marca la posicion sin contacto
      cal contacto            marca donde la goma toca el disco (vuelve a liberado)
  crudo                   alterna ver todo lo que manda la placa (depuracion)
  salir                   Ctrl+D tambien"""

# Motivos del firmware traducidos a una accion clara.
MOTIVOS = {
    "conexiones_no_verificadas": "Firmware sin configurar: revisar firmware/sdkconfig.defaults y volver a flashear",
    "falta_CONFIG": "Falta CONFIG: escribe config 20 10000 100",
    "ordenar_freno_liberado": "Primero: liberar",
    "velocidad_no_disponible": "El sensor no mide velocidad: ¿gira el disco? ¿sensor alineado con las marcas?",
    "ensayo_activo": "Hay un ensayo en curso: parar",
    "cierre_pendiente": "Cerrando la captura anterior; espera un momento",
    "motor_requiere_reposo_CONFIG_y_liberacion": "Motor bloqueado: libera el freno y espera a que termine la captura",
    "cortar_motor_antes_de_frenar": "Corta el motor antes de frenar: motor 0",
    "mando_rechazado": "Valor fuera de los limites calibrados",
    "parametros_ENSAYO_invalidos": "ensayo: freno dentro del recorrido calibrado y espera de 0 a 10000 ms",
    "velocidad_maxima_no_alcanzada": "El motor se corto (limite de 15 s o parar) antes de estabilizar la velocidad",
    "CONFIG_requiere_reposo": "CONFIG solo con el motor detenido y sin captura",
    "tiempos_CONFIG_invalidos": "config: periodo 10-60000 ms, duracion >= periodo, timeout 1-60000 ms",
    "comando_invalido": "Comando no reconocido: ayuda",
    "linea_descartada": "Linea demasiado larga o con caracteres invalidos",
    "transmision_ocupada": "Serie ocupada; reintenta",
    "CAL_requiere_reposo": "cal solo con el motor detenido y sin captura",
    "CAL_PULSO_primero": "Primero: cal pulso <us>",
    "CAL_PULSO_entero": "cal pulso: microsegundos enteros",
    "CAL_PASO_0.5_a_10": "cal paso: de 0.5 a 10 grados",
    "CAL_limite": "Limite del recorrido calibrado",
    "CAL_fuera_de_limites": "Fuera del recorrido calibrado",
    "CAL_LIBERADO_primero": "Marca primero cal liberado en otra posicion",
    "fallo_uart_reiniciar": "Fallo serie en la placa: reiniciarla",
    "fallo_actuador": "Fallo al mover un actuador: revisar alimentacion",
}
EVENTOS = {
    "freno": lambda v: f"freno → {v:g}°",
    "motor": lambda v: f"motor {v:g} %",
    "velocidad_maxima": lambda v: f"velocidad maxima {v:.0f} RPM: motor cortado, grabando",
    "limite_impulso_motor": lambda v: "motor cortado por el limite de impulso continuo",
    "servo_apagado": lambda v: "servo sin fuerza (15 s sin ordenes cal)",
    "estado_sensor": lambda v: {0: "sensor esperando pulsos", 1: "sensor midiendo", 2: "sin pulsos: disco detenido"}[int(v)],
}
COMANDOS = ["liberar", "frenar", "motor", "ensayo", "grabar", "parar", "estado", "config", "cal",
            "crudo", "ayuda", "salir"]
SUBCOMANDOS_CAL = ["pulso", "paso", "+", "-", "liberado", "contacto"]


def recta(t, y):
    """Pendiente por minimos cuadrados (y por segundo)."""
    n = len(t)
    if n < 2:
        return float("nan")
    mt, my = sum(t) / n, sum(y) / n
    den = sum((a - mt) ** 2 for a in t)
    return sum((a - mt) * (b - my) for a, b in zip(t, y)) / den if den else float("nan")


def resumir(filas):
    """Resumen rapido del ensayo, con los mismos tramos de 300 ms que visualizar_ensayo.m."""
    if len(filas) < 3:
        return ["Muy pocas filas para evaluar."]
    t = [f[0] / 1000 for f in filas]
    freno = [f[1] for f in filas]
    rpm = [f[2] for f in filas]
    validas = [r for r in rpm if r == r]
    lineas = [f"{len(filas)} filas · {t[-1]:.2f} s · RPM max {max(validas, default=float('nan')):.1f}"]
    cambios = [i for i in range(1, len(freno)) if freno[i] != freno[i - 1]]
    if len(cambios) != 1:
        lineas.append(f"{len(cambios)} cambios de freno (visualizar_ensayo.m necesita exactamente 1)")
        return lineas
    k = cambios[0]
    t0 = t[k]
    antes = [(a, b) for a, b in zip(t, rpm) if t0 - 0.3 <= a < t0 and b == b and b > 0]
    despues = [(a, b) for a, b in zip(t, rpm) if t0 <= a <= t0 + 0.3 and b == b and b > 0]
    pa = recta([a for a, _ in antes], [b for _, b in antes])
    pd = recta([a for a, _ in despues], [b for _, b in despues])
    parada = next((a for a, b in zip(t, rpm) if a >= t0 and b == 0), None)
    lineas.append(f"freno {freno[k - 1]:g}° → {freno[k]:g}° en t = {t0:.3f} s con {rpm[k]:.1f} RPM")
    def pendiente(valor):
        return f"{valor:.1f} RPM/s" if valor == valor else "—"
    lineas.append(f"desaceleracion antes {pendiente(pa)} · despues {pendiente(pd)}")
    if len(antes) < 2:
        lineas.append("faltan muestras de giro libre antes del freno: usa una espera >= 100 ms")
    lineas.append(f"se detuvo {parada - t0:.2f} s despues del freno" if parada is not None
                  else "el disco no llego a 0 RPM dentro de la captura")
    return lineas


class Captura:
    """Escribe el CSV crudo y el JSON de metadatos de una captura."""

    def __init__(self, nombre):
        DATOS.mkdir(parents=True, exist_ok=True)
        n = 1
        while (DATOS / f"{nombre}_{n:02d}.csv").exists():
            n += 1
        self.base = DATOS / f"{nombre}_{n:02d}"
        self.csv = open(self.base.with_suffix(".csv"), "w", encoding="utf-8")
        self.meta = {"protocolo": 1, "fecha_pc": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                     "receptor": "herramientas/consola.py", "configuracion": {}, "eventos": [], "errores": []}
        self.filas, self.cabecera, self.invalidas = [], False, 0

    def linea_datos(self, texto):
        """Guarda una fila valida y la devuelve; las invalidas solo se cuentan."""
        if texto == CABECERA:
            if not self.cabecera:
                self.cabecera = True
                self.csv.write(texto + "\n")
            return None
        partes = texto.split(",")
        try:
            t, f, r = (float(p) for p in partes)
        except ValueError:
            self.invalidas += 1
            return None
        if not self.cabecera or (self.filas and t <= self.filas[-1][0]):
            self.invalidas += 1
            return None
        self.csv.write(texto + "\n")
        self.filas.append((t, f, r))
        return t, f, r

    def cerrar(self, fin):
        self.csv.close()
        self.meta.update(fin=fin, muestras_recibidas=len(self.filas), filas_invalidas=self.invalidas,
                         completo=bool(fin and fin.get("completo")) and self.invalidas == 0
                         and fin.get("enviadas") == len(self.filas))
        self.base.with_suffix(".json").write_text(json.dumps(self.meta, indent=2, ensure_ascii=False) + "\n",
                                                  encoding="utf-8")
        return self.base.with_suffix(".csv")


class Pantalla:
    """Mensajes encima del prompt y una linea viva (velocidad) que se reescribe en su lugar."""

    def __init__(self):
        self.bloqueo = threading.Lock()
        self.viva = None
        self.ultima_viva = 0.0

    def _pintar(self, mensaje=None, subir=True):
        escrito = readline.get_line_buffer() if readline else ""
        salida = "\r\033[K"
        if self.viva is not None and subir:
            salida += "\033[1A\r\033[K"
        if mensaje is not None:
            salida += mensaje + "\n"
        if self.viva is not None:
            salida += self.viva + "\n"
        sys.stdout.write(salida + PROMPT + escrito)
        sys.stdout.flush()

    def mensaje(self, texto, color=""):
        with self.bloqueo:
            self._pintar(f"{color}{texto}{FIN if color else ''}")

    def vivo(self, texto, forzar=False):
        """Actualiza la linea viva como maximo 10 veces por segundo."""
        ahora = time.monotonic()
        if not forzar and self.viva is not None and ahora - self.ultima_viva < 0.1:
            return
        with self.bloqueo:
            nueva = self.viva is None
            self.viva = f"{CIAN}{texto}{FIN}"
            self.ultima_viva = ahora
            self._pintar(subir=not nueva)

    def fin_vivo(self):
        """Borra la linea viva; los mensajes siguientes vuelven a ser normales."""
        with self.bloqueo:
            if self.viva is not None:
                sys.stdout.write("\r\033[K\033[1A\r\033[K" + PROMPT + (readline.get_line_buffer() if readline else ""))
                sys.stdout.flush()
            self.viva = None


class Banco:
    """Conexion con la placa: traduce comandos cortos, interpreta el protocolo y guarda capturas."""

    def __init__(self, puerto, nombre):
        self.puerto, self.nombre = puerto, nombre
        self.pantalla = Pantalla()
        self.escritura = threading.Lock()
        self.activo = threading.Event()
        self.activo.set()
        self.captura = None
        self.config = {}
        self.listo = False
        self.crudo = False
        self.liberar_al_conectar = True
        self.acelerando_desde = None
        self.sondeos_pendientes = 0

    # --- envio -----------------------------------------------------------------------------
    def enviar(self, linea, mostrar=False):
        with self.escritura:
            self.puerto.write((linea + "\n").encode("ascii", "replace"))
        if mostrar or self.crudo:
            self.pantalla.mensaje(f"→ {linea}", GRIS)

    def servo(self, campo, defecto=None):
        return self.config.get("servo", {}).get(campo, defecto)

    def traducir(self, linea):
        """Convierte un comando corto en la orden del firmware; None si no hay nada que enviar."""
        palabras = linea.split()
        orden, args = palabras[0].lower(), palabras[1:]
        if palabras[0].isupper() and orden != "cal":
            if orden == "ensayo":
                self.acelerando_desde = time.monotonic()
            return linea                                    # comando del firmware tal cual
        if orden == "ayuda":
            self.pantalla.mensaje(AYUDA)
            return None
        if orden == "crudo":
            self.crudo = not self.crudo
            self.pantalla.mensaje(f"vista cruda {'activada' if self.crudo else 'desactivada'}", GRIS)
            return None
        if orden in ("liberar", "frenar", "ensayo") and self.servo("liberado_deg") is None:
            self.pantalla.mensaje("Aun no llega la configuracion de la placa: config", ROJO)
            return None
        if orden == "liberar":
            return f"FRENO {self.servo('liberado_deg')}"
        if orden == "frenar":
            return f"FRENO {args[0] if args else self.servo('maximo_deg')}"
        if orden == "motor" and len(args) == 1:
            return f"MOTOR {args[0]}"
        if orden == "ensayo":
            valores = args + [None] * (3 - len(args))
            motor = valores[0] or "60"
            freno = valores[1] or str(self.servo("maximo_deg"))
            espera = valores[2] or "300"
            self.acelerando_desde = time.monotonic()
            return f"ENSAYO {motor} {freno} {espera}"
        if orden == "grabar":
            return "START"
        if orden == "parar":
            return "STOP"
        if orden == "estado":
            return "STATUS"
        if orden == "config":
            return "CONFIG " + " ".join(args) if args else "CONFIG"
        if orden == "cal":
            return " ".join(["CAL", *(a.upper() for a in args)])
        self.pantalla.mensaje(f"'{linea}' no es un comando: ayuda", ROJO)
        return None

    # --- recepcion -------------------------------------------------------------------------
    def al_conectar(self):
        self.enviar("STATUS")
        self.enviar(CONFIG_INICIAL)
        self.enviar("CONFIG")

    def mensaje_json(self, m):
        tipo = m.get("tipo")
        if tipo == "listo":
            self.pantalla.mensaje(f"Placa reiniciada (firmware {m.get('firmware')})", VERDE)
            self.liberar_al_conectar = True
            self.al_conectar()
        elif tipo == "estado":
            self.listo = m.get("hardware_listo", False)
            sondeo = self.sondeos_pendientes > 0
            self.sondeos_pendientes = max(0, self.sondeos_pendientes - 1)
            if sondeo:  # respuesta al sondeo de la aceleracion: solo actualiza la linea viva
                rpm = m.get("velocidad_rpm")
                if self.acelerando_desde is not None and m.get("acelerando"):
                    self.pantalla.vivo(f"acelerando {time.monotonic() - self.acelerando_desde:4.1f} s | "
                                       f"{rpm if rpm is not None else '—':>6} RPM")
                return
            if not self.listo:
                self.pantalla.mensaje(MOTIVOS.get(m.get("motivo"), f"Placa no lista: {m.get('motivo')}"), ROJO)
                return
            rpm, freno = m.get("velocidad_rpm"), m.get("freno_deg")
            self.pantalla.mensaje(
                f"placa lista · motor {m.get('motor_porcentaje', 0):g} % · freno "
                f"{f'{freno:g}°' if freno is not None else 'sin orden'} · "
                f"{f'{rpm:.1f} RPM' if rpm is not None else 'sin velocidad'}"
                f"{' · grabando' if m.get('registrando') else ''}")
        elif tipo == "configuracion":
            self.config[m.get("grupo")] = m
            if self.captura:
                self.captura.meta["configuracion"][m.get("grupo")] = m
            elif m.get("grupo") == "motor":
                self.mostrar_configuracion()
        elif tipo == "calibracion":
            self.mostrar_calibracion(m)
        elif tipo == "ok":
            if m.get("comando") != "CONFIG" or self.crudo:
                self.pantalla.mensaje(f"✓ {m.get('comando')}", GRIS)
        elif tipo == "error":
            self.acelerando_desde = None
            self.pantalla.fin_vivo()
            if self.captura:
                self.captura.meta["errores"].append(m)
            self.pantalla.mensaje("✗ " + MOTIVOS.get(m.get("motivo"), m.get("motivo", "error")), ROJO)
        elif tipo == "evento":
            if self.captura:
                self.captura.meta["eventos"].append(m)
            texto = EVENTOS.get(m.get("evento"), lambda v: f"{m.get('evento')} {v}")(m.get("valor", 0))
            momento = f"{m['tiempo_ms'] / 1000:6.2f} s  " if m.get("tiempo_ms", -1) >= 0 else ""
            if m.get("evento") == "estado_sensor" and not self.captura:
                return
            self.pantalla.mensaje(f"{momento}{texto}", AMARILLO)
        elif tipo == "inicio":
            self.acelerando_desde = None
            self.pantalla.fin_vivo()
            self.captura = Captura(self.nombre)
            self.captura.meta["inicio"] = m
            self.pantalla.mensaje(f"▶ grabando → datos/{self.captura.base.name}.csv", VERDE)
        elif tipo == "fin" and self.captura:
            self.pantalla.fin_vivo()
            ruta = self.captura.cerrar(m)
            estado = "completa" if self.captura.meta["completo"] else "INCOMPLETA (revisar el .json)"
            self.pantalla.mensaje(f"■ captura {estado}, fin por {m.get('motivo')} → datos/{ruta.name}",
                                  VERDE if self.captura.meta["completo"] else ROJO)
            for linea in resumir(self.captura.filas):
                self.pantalla.mensaje("  " + linea, CIAN)
            self.captura = None

    def mostrar_configuracion(self):
        sensor, servo, motor = (self.config.get(g, {}) for g in ("sensor", "servo", "motor"))
        self.pantalla.mensaje(
            f"sensor {sensor.get('pulsos_por_vuelta')} marcas (promedio de {sensor.get('ventana_pulsos')}) · "
            f"freno {servo.get('minimo_deg')}..{servo.get('maximo_deg')}°, liberado {servo.get('liberado_deg')}° · "
            f"motor max {motor.get('maximo_porcentaje')} % / {motor.get('maximo_impulso_ms', 0) / 1000:g} s", GRIS)
        if self.liberar_al_conectar and self.listo and servo.get("liberado_deg") is not None:
            self.liberar_al_conectar = False
            self.enviar(f"FRENO {servo['liberado_deg']}")

    def mostrar_calibracion(self, m):
        def posicion(us, grados):
            return f"{us} us ({grados:g}°)" if us else "—"
        self.pantalla.mensaje(
            f"servo {posicion(m['pulso_us'], m['grados'])} · paso {m['paso_us']} us · "
            f"liberado {posicion(m['liberado_us'], m['liberado_deg'])} · "
            f"contacto {posicion(m['contacto_us'], m['contacto_deg'])} · "
            f"recorrido {m['minimo_us']}..{m['maximo_us']} us", CIAN)
        if m["liberado_us"] and m["contacto_us"]:
            self.pantalla.mensaje(
                f"  para fijarlo: CONFIG_ASM_SERVO_LIBERADO_DEG={round(m['liberado_deg'])} en firmware/sdkconfig.defaults; "
                f"la goma toca a {m['contacto_deg']:g}°: frenar por encima de ese angulo", GRIS)

    def leer(self):
        while self.activo.is_set():
            try:
                crudo = self.puerto.readline()
            except serial.SerialException as error:
                self.pantalla.mensaje(f"Puerto perdido: {error}", ROJO)
                self.activo.clear()
                return
            texto = crudo.decode("utf-8", "replace").strip()
            if not texto:
                continue
            if self.crudo:
                self.pantalla.mensaje(texto, GRIS)
            if texto.startswith("# "):
                try:
                    mensaje = json.loads(texto[2:])
                except json.JSONDecodeError:
                    if not self.crudo:
                        self.pantalla.mensaje(texto, GRIS)
                    continue
                self.mensaje_json(mensaje)
            elif self.captura:
                fila = self.captura.linea_datos(texto)
                if fila:
                    t, f, r = fila
                    self.pantalla.vivo(f"● {t / 1000:6.2f} s | {r:7.1f} RPM | freno {f:g}°")
            elif not self.crudo:
                self.pantalla.mensaje(texto, GRIS)

    def sondear(self):
        """Durante la aceleracion de ensayo pide STATUS para mostrar la velocidad en vivo."""
        while self.activo.is_set():
            time.sleep(0.3)
            if self.acelerando_desde is not None and not self.captura:
                self.sondeos_pendientes += 1
                self.enviar("STATUS")


def completar(texto, estado):
    """Tab: comandos y subcomandos de cal."""
    if not readline:
        return None
    linea = readline.get_line_buffer().lstrip()
    opciones = SUBCOMANDOS_CAL if linea.lower().startswith("cal ") else COMANDOS
    coincidencias = [o + " " for o in opciones if o.startswith(texto.lower())]
    return coincidencias[estado] if estado < len(coincidencias) else None


def main():
    argumentos = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    argumentos.add_argument("--puerto", required=True)
    argumentos.add_argument("--nombre", default="ensayo", help="prefijo de las capturas en datos/")
    argumentos.add_argument("--reiniciar", action="store_true", help="reinicia la placa al conectar")
    opciones = argumentos.parse_args()
    if os.name == "nt":
        os.system("")  # activa los colores ANSI en la consola de Windows

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
    if readline:
        readline.set_completer(completar)
        readline.set_completer_delims(" ")
        readline.parse_and_bind("tab: complete")

    banco = Banco(puerto, opciones.nombre)
    print(f"{NEGRITA}Banco de frenado{FIN} en {opciones.puerto} · capturas en datos/{opciones.nombre}_NN.csv · "
          f"escribe {NEGRITA}ayuda{FIN}")
    threading.Thread(target=banco.leer, daemon=True).start()
    threading.Thread(target=banco.sondear, daemon=True).start()
    banco.al_conectar()
    try:
        while banco.activo.is_set():
            linea = input(PROMPT).strip()
            if not linea:
                continue
            if linea.lower() in ("salir", "exit", "quit"):
                break
            orden = banco.traducir(linea)
            if orden:
                banco.enviar(orden)
    except (EOFError, KeyboardInterrupt):
        pass
    banco.activo.clear()
    if banco.captura:
        banco.enviar("STOP")
        time.sleep(0.3)
    puerto.close()
    print()


if __name__ == "__main__":
    main()
