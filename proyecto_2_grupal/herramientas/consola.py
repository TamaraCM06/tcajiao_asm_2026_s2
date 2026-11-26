#!/usr/bin/env python3
"""Consola del banco de frenado. Se abre con: python banco.py consola [--nombre prefijo]

Al conectar fija el registro (CONFIG 20 10000 100: fila cada 20 ms, 10 s maximo, 0 RPM tras 100 ms
sin ranuras) y libera el freno. Cada ensayo se guarda en datos/<prefijo>_m<motor>_f<freno>_NN.csv
(tiempo_ms,freno_deg,velocidad_rpm) con su .json de configuracion y eventos. Los comandos del firmware en mayusculas pasan tal cual (FRENO 120, MOTOR 30).
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
from prompt_toolkit import PromptSession
from prompt_toolkit.completion import WordCompleter
from prompt_toolkit.patch_stdout import patch_stdout

DATOS = Path(__file__).resolve().parents[1] / "datos"
CABECERA = "tiempo_ms,freno_deg,velocidad_rpm"
DURACION_MS, TIMEOUT_MS = 10000, 100   # captura de 10 s como maximo; 0 RPM tras 100 ms sin ranuras
# Parametros de los ensayos; los del lazo cerrado (kp, ki, kd, rampa) se agregan aqui.
# freno None = el maximo calibrado de la placa.
AJUSTES_INICIALES = {"motor": 60, "freno": None, "espera": 300, "periodo": 20}
UNIDADES = {"motor": "%", "freno": "°", "espera": "ms", "periodo": "ms"}
PERIODO_PANTALLA_S = 0.5     # una linea de progreso cada medio segundo
CIERRE_DETENIDO_MS = 1000    # con 0 RPM durante 1 s la captura se cierra sola
PROMPT = "banco> "
GRIS, ROJO, AMARILLO, VERDE, CIAN, FIN = "\033[90m", "\033[91m", "\033[93m", "\033[92m", "\033[96m", "\033[0m"

AYUDA = """\
  ensayo [motor%] [freno°]   acelera, corta el motor al estabilizarse, graba y frena tras la espera;
                             sin numeros usa los ajustes
  ajustes                    muestra motor, freno, espera y periodo
  ajustar <nombre> <valor>   cambia un ajuste, p. ej. ajustar freno 130 (periodo: fila cada N ms)
  motor <%>                  gira el disco mostrando las RPM; motor 0 lo detiene
  parar                      corta el motor, libera el freno y cierra la captura
  estado                     placa, motor, freno y RPM
  salir                      tambien Ctrl+D"""
COMANDOS = ["ensayo", "ajustes", "ajustar", "motor", "parar", "estado", "ayuda", "salir", *AJUSTES_INICIALES]

# Motivos del firmware traducidos a una accion.
MOTIVOS = {
    "falta_CONFIG": "La placa no recibio CONFIG: salir y volver a abrir la consola",
    "ordenar_freno_liberado": "El freno no esta liberado: parar",
    "velocidad_no_disponible": "El sensor no mide: ¿gira el disco? ¿pasan las ranuras por la horquilla?",
    "ensayo_activo": "Hay un ensayo en curso: parar",
    "cierre_pendiente": "Cerrando la captura anterior; espera un momento",
    "motor_requiere_reposo_CONFIG_y_liberacion": "El motor no arranca durante una captura: parar",
    "cortar_motor_antes_de_frenar": "Primero motor 0",
    "mando_rechazado": "Valor fuera de los limites calibrados",
    "parametros_ENSAYO_invalidos": "Freno fuera del recorrido calibrado",
    "velocidad_maxima_no_alcanzada": "El motor se corto antes de estabilizar la velocidad (limite de impulso)",
    "CONFIG_requiere_reposo": "El periodo solo cambia con el motor detenido y sin captura",
    "comando_invalido": "Comando no reconocido: ayuda",
    "linea_descartada": "Linea demasiado larga o con caracteres invalidos",
    "transmision_ocupada": "Serie ocupada; reintenta",
    "fallo_uart_reiniciar": "Fallo serie en la placa: reiniciarla",
    "fallo_actuador": "Fallo al mover un actuador: revisar alimentacion",
}
EVENTOS = {
    "motor": lambda v: f"motor {v:g} %" if v else "motor cortado",
    "freno": lambda v: f"freno → {v:g}°",
    "velocidad_maxima": lambda v: f"velocidad estable en {v:.0f} RPM: corta el motor y graba",
    "limite_impulso_motor": lambda v: "motor cortado por el limite de impulso continuo",
}


def mostrar(texto, color=""):
    """Imprime una linea; patch_stdout la pone encima del prompt sin tocar lo que se esta tecleando."""
    print(f"{color}{texto}{FIN if color else ''}", flush=True)


def numero(texto):
    try:
        valor = float(texto)
    except ValueError:
        return None
    return valor if valor == valor else None


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
        return ["muy pocas filas para evaluar"]
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

    def pendiente(valor):
        return f"{valor:.1f} RPM/s" if valor == valor else "—"
    lineas.append(f"freno {freno[k - 1]:g}° → {freno[k]:g}° en t = {t0:.3f} s con {rpm[k]:.1f} RPM")
    lineas.append(f"desaceleracion antes {pendiente(pa)} · despues {pendiente(pd)}")
    lineas.append(f"se detuvo {parada - t0:.2f} s despues del freno" if parada is not None
                  else "el disco no llego a 0 RPM dentro de la captura")
    return lineas


class Captura:
    """Escribe el CSV crudo y el JSON de metadatos de una captura."""

    def __init__(self, nombre, numerar=True):
        """numerar: agrega _NN (consola). Sin numerar usa el nombre exacto y, si ya existe, _intentoN."""
        DATOS.mkdir(parents=True, exist_ok=True)
        if numerar:
            n = 1
            while (DATOS / f"{nombre}_{n:02d}.csv").exists():
                n += 1
            self.base = DATOS / f"{nombre}_{n:02d}"
        else:
            self.base, n = DATOS / nombre, 2
            while self.base.with_suffix(".csv").exists():
                self.base, n = DATOS / f"{nombre}_intento{n}", n + 1
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


class Banco:
    """Conexion con el ESP32: traduce los comandos, interpreta lo que llega y guarda las capturas."""

    def __init__(self, puerto, prefijo):
        self.puerto, self.prefijo = puerto, prefijo
        self.escritura = threading.Lock()
        self.activo = threading.Event()
        self.activo.set()
        self.config = {}
        self.ajustes = dict(AJUSTES_INICIALES)
        self.listo = False
        self.liberar_al_conectar = True
        self.captura = None
        self.ensayo_pedido = None     # (motor, freno) del ultimo ENSAYO, para nombrar el archivo
        self.acelerando_desde = None  # ensayo: el motor acelera antes de grabar
        self.girando = False          # motor manual
        self.sondeos = 0              # STATUS pedidos por sondear(), que no se imprimen enteros
        self.ultima_linea = 0.0
        self.cero_desde = None
        self.cierre_pedido = False

    def enviar(self, linea):
        with self.escritura:
            self.puerto.write((linea + "\n").encode("ascii", "replace"))

    def limite(self, grupo, campo):
        return self.config.get(grupo, {}).get(campo)

    def config_inicial(self):
        return f"CONFIG {self.ajustes['periodo']} {DURACION_MS} {TIMEOUT_MS}"

    def rangos(self):
        """Limites de cada ajuste; los del motor y el freno vienen de la placa."""
        return {"motor": (1, self.limite("motor", "maximo_porcentaje")),
                "freno": (self.limite("servo", "minimo_deg"), self.limite("servo", "maximo_deg")),
                "espera": (0, 10000), "periodo": (10, 100)}

    def valor(self, clave):
        if clave == "freno" and self.ajustes["freno"] is None:
            return self.limite("servo", "maximo_deg")
        return self.ajustes[clave]

    def mostrar_ajustes(self):
        mostrar("  " + "  ".join(f"{c} {self.valor(c):g}{'' if UNIDADES[c] == '°' else ' '}{UNIDADES[c]}"
                                 for c in self.ajustes if self.valor(c) is not None), CIAN)

    def ajustar(self, clave, texto):
        """Valida y guarda un ajuste; el periodo se aplica a la placa con CONFIG."""
        if clave not in self.ajustes or numero(texto) is None:
            mostrar("ajustar <" + "|".join(self.ajustes) + "> <valor>", ROJO)
            return None
        minimo, maximo = self.rangos()[clave]
        if minimo is None or maximo is None:
            mostrar("Aun no llega la configuracion de la placa: estado", ROJO)
            return None
        if clave == "periodo" and (self.captura or self.girando or self.acelerando_desde is not None):
            mostrar(MOTIVOS["CONFIG_requiere_reposo"], ROJO)
            return None
        valor = numero(texto)
        if clave in ("espera", "periodo"):
            valor = int(valor)
        if not minimo <= valor <= maximo:
            mostrar(f"{clave}: de {minimo:g} a {maximo:g} {UNIDADES[clave]}", ROJO)
            return None
        self.ajustes[clave] = valor
        self.mostrar_ajustes()
        return self.config_inicial() if clave == "periodo" else None

    def nombre_captura(self, motor, freno):
        """El archivo lleva motor y freno, y la espera o el periodo cuando no son los iniciales."""
        nombre = f"{self.prefijo}_m{motor:g}_f{freno:g}"
        if self.ajustes["espera"] != AJUSTES_INICIALES["espera"]:
            nombre += f"_e{self.ajustes['espera']}"
        if self.ajustes["periodo"] != AJUSTES_INICIALES["periodo"]:
            nombre += f"_p{self.ajustes['periodo']}"
        return nombre

    def traducir(self, linea):
        """Convierte un comando de la consola en la orden del firmware; None si no hay que enviar nada."""
        palabras = linea.split()
        orden, args = palabras[0].lower(), palabras[1:]
        if palabras[0].isupper():
            if orden == "ensayo":
                self.acelerando_desde = time.monotonic()
            return linea
        if orden == "ayuda":
            mostrar(AYUDA)
            return None
        if orden == "estado":
            return "STATUS"
        if orden == "ajustes":
            self.mostrar_ajustes()
            return None
        if orden == "ajustar" and len(args) == 2:
            return self.ajustar(args[0].lower(), args[1])
        if orden == "parar":
            self.girando, self.acelerando_desde = False, None
            return "STOP"
        if orden == "motor" and len(args) == 1 and numero(args[0]) is not None:
            potencia, maximo = numero(args[0]), self.limite("motor", "maximo_porcentaje")
            if maximo is not None and not 0 <= potencia <= maximo:
                mostrar(f"motor: de 0 a {maximo} %", ROJO)
                return None
            self.girando = potencia > 0
            return f"MOTOR {args[0]}"
        if orden == "ensayo" and len(args) <= 2:
            if not self.config.get("servo"):
                mostrar("Aun no llega la configuracion de la placa: estado", ROJO)
                return None
            valores = [numero(a) for a in args]
            if None in valores:
                mostrar("ensayo [motor%] [freno°], por ejemplo: ensayo 60 140", ROJO)
                return None
            motor = valores[0] if valores else self.valor("motor")
            freno = valores[1] if len(valores) > 1 else self.valor("freno")
            rangos = self.rangos()
            if not rangos["motor"][0] <= motor <= rangos["motor"][1] or \
                    not rangos["freno"][0] <= freno <= rangos["freno"][1]:
                mostrar("ensayo: motor de {:g} a {:g} %, freno de {:g} a {:g}°".format(
                    *rangos["motor"], *rangos["freno"]), ROJO)
                return None
            self.ensayo_pedido = self.nombre_captura(motor, freno)
            self.acelerando_desde = time.monotonic()
            return f"ENSAYO {motor:g} {freno:g} {self.ajustes['espera']}"
        mostrar(f"'{linea}' no es un comando: ayuda", ROJO)
        return None

    def al_conectar(self):
        self.enviar("STATUS")
        self.enviar(self.config_inicial())
        self.enviar("CONFIG")

    def progreso(self, texto):
        """Linea de avance limitada a una cada PERIODO_PANTALLA_S."""
        ahora = time.monotonic()
        if ahora - self.ultima_linea >= PERIODO_PANTALLA_S:
            self.ultima_linea = ahora
            mostrar(texto, CIAN)

    def mensaje_json(self, m):
        tipo = m.get("tipo")
        if tipo == "listo":
            mostrar(f"La placa se reinicio (firmware {m.get('firmware')})", AMARILLO)
            self.liberar_al_conectar = True
            self.al_conectar()
        elif tipo == "estado":
            self.listo = m.get("hardware_listo", False)
            rpm = m.get("velocidad_rpm")
            rpm_texto = f"{rpm:6.1f} RPM" if rpm is not None else "  sin medida"
            if self.sondeos:
                self.sondeos -= 1
                if self.acelerando_desde is not None and m.get("acelerando"):
                    self.progreso(f"  acelerando {time.monotonic() - self.acelerando_desde:4.1f} s  {rpm_texto}")
                elif self.girando and m.get("motor_porcentaje", 0) > 0:
                    self.progreso(f"  girando  {rpm_texto}")
                elif self.girando:
                    self.girando = False
                return
            if not self.listo:
                mostrar(MOTIVOS.get(m.get("motivo"), f"Placa no lista: {m.get('motivo')}"), ROJO)
                return
            freno = m.get("freno_deg")
            mostrar(f"placa lista · motor {m.get('motor_porcentaje', 0):g} % · freno "
                    f"{f'{freno:g}°' if freno is not None else 'sin orden'} · {rpm_texto.strip()}"
                    f"{' · grabando' if m.get('registrando') else ''}")
        elif tipo == "configuracion":
            self.config[m.get("grupo")] = m
            if self.captura:
                self.captura.meta["configuracion"][m.get("grupo")] = m
            elif m.get("grupo") == "motor" and self.liberar_al_conectar and self.listo:
                self.liberar_al_conectar = False
                self.enviar(f"FRENO {self.limite('servo', 'liberado_deg')}")
                mostrar("lista: freno liberado; escribe ayuda", VERDE)
        elif tipo == "ok" and m.get("comando") == "CONFIG" and self.config:
            mostrar(f"  periodo aplicado: una fila cada {self.ajustes['periodo']} ms", CIAN)
        elif tipo == "ok" and m.get("comando") == "STOP":
            mostrar("motor cortado, freno liberado", VERDE)
        elif tipo == "error":
            self.acelerando_desde, self.girando = None, False
            if self.captura:
                self.captura.meta["errores"].append(m)
            mostrar("✗ " + MOTIVOS.get(m.get("motivo"), m.get("motivo", "error")), ROJO)
        elif tipo == "evento":
            if self.captura:
                self.captura.meta["eventos"].append(m)
            texto = EVENTOS.get(m.get("evento"))
            if texto:
                momento = f"{m['tiempo_ms'] / 1000:5.2f} s  " if m.get("tiempo_ms", -1) >= 0 else ""
                mostrar(f"  {momento}{texto(m.get('valor', 0))}", AMARILLO)
        elif tipo == "inicio":
            self.acelerando_desde, self.girando = None, False
            self.cero_desde, self.cierre_pedido = None, False
            self.captura = Captura(self.ensayo_pedido or self.prefijo)
            self.ensayo_pedido = None
            self.captura.meta["inicio"] = m
            mostrar(f"▶ grabando → datos/{self.captura.base.name}.csv", VERDE)
        elif tipo == "fin" and self.captura:
            ruta = self.captura.cerrar(m)
            completa = self.captura.meta["completo"]
            mostrar(f"■ captura {'completa' if completa else 'INCOMPLETA (revisar el .json)'} → datos/{ruta.name}",
                    VERDE if completa else ROJO)
            for linea in resumir(self.captura.filas):
                mostrar("  " + linea, CIAN)
            self.captura = None

    def fila(self, t, freno, rpm):
        """Muestra el avance y cierra la captura cuando el disco ya se detuvo."""
        self.progreso(f"  {t / 1000:5.2f} s  {rpm:6.1f} RPM  freno {freno:g}°")
        if rpm != 0:
            self.cero_desde = None
        elif self.cero_desde is None:
            self.cero_desde = t
        elif t - self.cero_desde >= CIERRE_DETENIDO_MS and not self.cierre_pedido:
            self.cierre_pedido = True
            self.enviar("STOP")

    def leer(self):
        while self.activo.is_set():
            try:
                crudo = self.puerto.readline()
            except serial.SerialException as error:
                mostrar(f"Puerto perdido: {error}", ROJO)
                self.activo.clear()
                return
            texto = crudo.decode("utf-8", "replace").strip()
            if not texto:
                continue
            if texto.startswith("# "):
                try:
                    self.mensaje_json(json.loads(texto[2:]))
                except json.JSONDecodeError:
                    mostrar(texto, GRIS)
            elif self.captura:
                fila = self.captura.linea_datos(texto)
                if fila:
                    self.fila(*fila)
            else:
                mostrar(texto, GRIS)

    def sondear(self):
        """Mientras el motor gira sin grabar, pide STATUS para mostrar las RPM."""
        while self.activo.is_set():
            time.sleep(PERIODO_PANTALLA_S)
            if (self.acelerando_desde is not None or self.girando) and not self.captura:
                self.sondeos += 1
                self.enviar("STATUS")


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
    banco = Banco(puerto, opciones.nombre)
    sesion = PromptSession(completer=WordCompleter(COMANDOS, ignore_case=True))
    with patch_stdout(raw=True):  # lo que imprimen los hilos sale encima del prompt
        mostrar(f"Banco de frenado en {opciones.puerto} · capturas en "
                f"datos/{opciones.nombre}_m<motor>_f<freno>_NN.csv")
        mostrar(AYUDA)
        threading.Thread(target=banco.leer, daemon=True).start()
        threading.Thread(target=banco.sondear, daemon=True).start()
        banco.al_conectar()
        try:
            while banco.activo.is_set():
                linea = sesion.prompt(PROMPT).strip()
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
    if banco.captura or banco.girando:
        banco.enviar("STOP")
        time.sleep(0.3)
    puerto.close()
    print()


if __name__ == "__main__":
    main()
