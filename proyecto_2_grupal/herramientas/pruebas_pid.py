#!/usr/bin/env python3
"""Pruebas en el banco para el PID: barrido de velocidad y ensayos del plan, con un solo comando.

Se abre con: python banco.py pid [--nombre identificacion] [--plan archivo.csv] [--alto 60 --bajo 40]
1. Barrido: gira el disco a cada % de motor hasta que la velocidad se estabiliza (±3 % durante 1 s)
   y guarda datos/<nombre>/velocidad/vel_m<motor>_r01.csv. Elige la velocidad alta (el mayor %) y la
   baja (la meseta mas cercana al 60 % de la alta); se aceptan con Enter o se escriben otras.
2. Ensayos del plan, uno por Enter con el disco detenido (s = saltar, q = terminar). Cada uno queda en
   datos/<nombre>/<grupo>/<tipo>_<nivel>_m<motor>_f<freno>_r<repeticion>.csv (+ .json) y en indice.csv.
Si se vuelve a correr con el mismo nombre, reutiliza las velocidades elegidas y sigue con lo que falta.
"""
import argparse
import csv
import json
import statistics
import sys
import time
from datetime import datetime
from pathlib import Path

import serial

sys.path.insert(0, str(Path(__file__).resolve().parent))
import consola  # noqa: E402  (Captura, resumir y los mensajes de error, iguales que en la consola)

PLAN_INICIAL = Path(__file__).resolve().parent / "plan_identificacion.csv"
CAMPOS_INDICE = ["fecha", "grupo", "nivel", "repeticion", "motor", "freno", "espera_ms", "archivo",
                 "completo", "rpm_inicial", "motivo"]
TIPO = {"caida_libre": "caida", "freno_maximo": "fmax", "escalones": "esc", "validacion": "val"}
BARRIDO = [30, 40, 50, 60]
ESTABLE_TOLERANCIA, ESTABLE_S = 0.03, 1.0   # mismo criterio de meseta que el ensayo
FRACCION_BAJA = 0.6                          # la velocidad baja busca el 60 % de la alta


class Placa:
    """Comandos y mensajes JSON por el puerto serie; las filas CSV se devuelven aparte."""

    def __init__(self, puerto):
        self.serie = serial.Serial()
        self.serie.port, self.serie.baudrate, self.serie.timeout = puerto, 115200, 0.05
        self.serie.dtr = self.serie.rts = False  # abrir sin reiniciar la placa
        self.serie.open()

    def enviar(self, linea):
        self.serie.write((linea + "\n").encode("ascii"))

    def linea(self):
        """('json', mensaje), ('fila', texto) o (None, None) si no llego nada."""
        texto = self.serie.readline().decode("utf-8", "replace").strip()
        if texto.startswith("# "):
            try:
                return "json", json.loads(texto[2:])
            except json.JSONDecodeError:
                return None, None
        return ("fila", texto) if texto else (None, None)

    def esperar(self, tipo, segundos=1.0):
        fin = time.monotonic() + segundos
        while time.monotonic() < fin:
            clase, mensaje = self.linea()
            if clase == "json" and mensaje.get("tipo") in (tipo, "error"):
                return mensaje
        return None

    def configuracion(self):
        self.enviar("CONFIG")
        grupos = {}
        while len(grupos) < 4:
            mensaje = self.esperar("configuracion")
            if not mensaje or mensaje.get("tipo") != "configuracion":
                break
            grupos[mensaje["grupo"]] = mensaje
        return grupos

    def velocidad(self):
        self.enviar("STATUS")
        estado = self.esperar("estado", 0.5)
        return estado.get("velocidad_rpm") if estado and estado.get("tipo") == "estado" else None


def leer_plan(ruta, valores):
    """Expande nivel (alto/bajo) a % de motor y LIBERADO/MAXIMO a grados; una entrada por repeticion."""
    ensayos = []
    with open(ruta, encoding="utf-8") as archivo:
        for fila in csv.DictReader(archivo):
            motor = float(valores[fila["nivel"]])
            freno = float(valores.get(fila["freno"], fila["freno"]))
            for repeticion in range(1, int(fila["repeticiones"]) + 1):
                nombre = f"{TIPO.get(fila['grupo'], fila['grupo'])}_{fila['nivel']}_m{motor:g}_f{freno:g}_r{repeticion:02d}"
                ensayos.append(dict(fila, motor=motor, freno=freno, repeticion=repeticion, nombre=nombre,
                                    espera_ms=int(fila["espera_ms"]), duracion_s=float(fila["duracion_s"])))
    return ensayos


def hechos(indice):
    """Nombres (grupo/tipo_nivel_m_f_r) ya completos en una corrida anterior; los reintentos cuentan."""
    if not indice.exists():
        return set()
    with open(indice, encoding="utf-8") as archivo:
        return {f["archivo"].rsplit("_intento", 1)[0].removesuffix(".csv")
                for f in csv.DictReader(archivo) if f["completo"] == "si"}


def clave(ensayo):
    return f"{ensayo['grupo']}/{ensayo['nombre']}"


def anotar(indice, fila):
    nuevo = not indice.exists()
    with open(indice, "a", newline="", encoding="utf-8") as archivo:
        escritor = csv.DictWriter(archivo, fieldnames=CAMPOS_INDICE)
        if nuevo:
            escritor.writeheader()
        escritor.writerow(fila)


def esperar_detenido(placa):
    """No deja empezar mientras el disco siga girando."""
    while True:
        rpm = placa.velocidad()
        if rpm is None or rpm == 0:
            print("\r\033[K  disco detenido")
            return
        print(f"\r\033[K  esperando a que el disco se detenga: {rpm:7.1f} RPM", end="", flush=True)
        time.sleep(0.5)


def girar_hasta_meseta(placa, motor, limite_s, liberado):
    """Gira hasta que la velocidad se mantenga ±3 % durante 1 s; devuelve (filas, meseta, estable)."""
    placa.enviar(f"FRENO {liberado}")
    placa.enviar(f"MOTOR {motor:g}")
    filas, inicio, referencia, desde = [], time.monotonic(), None, 0.0
    while time.monotonic() - inicio < limite_s:
        placa.enviar("STATUS")
        estado = placa.esperar("estado", 0.5)
        t = time.monotonic() - inicio
        if not estado or estado.get("tipo") != "estado":
            continue
        if estado.get("motor_porcentaje", 0) <= 0:
            break  # la placa corto el motor (limite de impulso)
        rpm = estado.get("velocidad_rpm")
        filas.append((t, rpm if rpm is not None else float("nan")))
        print(f"\r\033[K  motor {motor:g} %  {t:5.1f} s  {filas[-1][1]:7.1f} RPM", end="", flush=True)
        if not rpm:
            referencia = None
        elif referencia is None or abs(rpm - referencia) > ESTABLE_TOLERANCIA * referencia:
            referencia, desde = rpm, t
        elif t - desde >= ESTABLE_S:
            placa.enviar("MOTOR 0")
            print()
            return filas, statistics.mean(r for tt, r in filas if tt >= desde and r == r), True
        time.sleep(0.1)
    placa.enviar("MOTOR 0")
    print()
    ultimos = [r for tt, r in filas if r == r and tt >= (filas[-1][0] - 2 if filas else 0)]
    return filas, statistics.mean(ultimos) if ultimos else float("nan"), False


def barrido(placa, carpeta, porcentajes, limite_s, liberado):
    """Meseta de cada % de motor; guarda velocidad/vel_m<motor>_r01.csv."""
    mesetas = {}
    destino = carpeta / "velocidad"
    destino.mkdir(parents=True, exist_ok=True)
    for motor in porcentajes:
        esperar_detenido(placa)
        filas, meseta, estable = girar_hasta_meseta(placa, motor, limite_s, liberado)
        ruta, n = destino / f"vel_m{motor:g}_r01.csv", 2
        while ruta.exists():
            ruta, n = destino / f"vel_m{motor:g}_r{n:02d}.csv", n + 1
        ruta.write_text("tiempo_s,rpm\n" + "".join(f"{t:.3f},{r:.1f}\n" for t, r in filas), encoding="utf-8")
        mesetas[motor] = meseta
        print(f"  motor {motor:g} %: meseta {meseta:.0f} RPM{'' if estable else ' (no se estabilizo)'}"
              f" → {ruta.relative_to(carpeta.parent).as_posix()}")
    return mesetas


def elegir_niveles(mesetas):
    """Alta = mayor %; baja = la meseta mas cercana a FRACCION_BAJA de la alta. Se puede corregir."""
    validas = {m: r for m, r in mesetas.items() if r == r and r > 0}
    if len(validas) < 2:
        sys.exit("El barrido no dio dos velocidades validas: revisar el sensor y el motor")
    alto = max(validas)
    bajo = min((m for m in validas if m < alto), key=lambda m: abs(validas[m] - FRACCION_BAJA * validas[alto]))
    print(f"\nVelocidad alta: motor {alto:g} % ({validas[alto]:.0f} RPM) · "
          f"baja: motor {bajo:g} % ({validas[bajo]:.0f} RPM)")
    respuesta = input("Enter para aceptar, o escribir 'alto bajo' en % (p. ej. 60 35): ").strip().split()
    if len(respuesta) == 2:
        alto, bajo = float(respuesta[0]), float(respuesta[1])
    return {"alto": alto, "bajo": bajo, "mesetas_rpm": {f"{m:g}": r for m, r in mesetas.items()}}


def correr(placa, ensayo):
    """Un ENSAYO completo; devuelve (captura o None, rpm inicial, motivo)."""
    placa.serie.reset_input_buffer()
    placa.enviar(f"CONFIG 20 {int(ensayo['duracion_s'] * 1000)} 100")
    respuesta = placa.esperar("ok", 1.0)
    if not respuesta or respuesta.get("tipo") == "error":
        return None, None, (respuesta or {}).get("motivo", "sin_respuesta_CONFIG")
    placa.enviar(f"ENSAYO {ensayo['motor']:g} {ensayo['freno']:g} {ensayo['espera_ms']}")
    captura, rpm_inicial, cero_desde, cierre_pedido = None, None, None, False
    limite = time.monotonic() + 20 + ensayo["duracion_s"]
    ultima = 0.0
    while time.monotonic() < limite:
        clase, m = placa.linea()
        if clase == "json":
            tipo = m.get("tipo")
            if tipo == "error":
                placa.enviar("STOP")
                return captura, rpm_inicial, m.get("motivo")
            if tipo == "evento" and m.get("evento") == "velocidad_maxima":
                rpm_inicial = m.get("valor")
                print(f"  velocidad estable en {rpm_inicial:.0f} RPM: corta el motor y graba")
            if tipo == "inicio":
                captura = consola.Captura(ensayo["nombre"], numerar=False)
                captura.meta.update(inicio=m, plan=ensayo)
            elif captura and tipo == "configuracion":
                captura.meta["configuracion"][m.get("grupo")] = m
            elif captura and tipo == "evento":
                captura.meta["eventos"].append(m)
            elif captura and tipo == "fin":
                captura.cerrar(m)
                return captura, rpm_inicial, m.get("motivo")
        elif clase == "fila" and captura:
            fila = captura.linea_datos(m)
            if not fila:
                continue
            t, freno, rpm = fila
            if time.monotonic() - ultima >= 0.5:
                ultima = time.monotonic()
                print(f"\r\033[K  {t / 1000:6.2f} s  {rpm:7.1f} RPM  freno {freno:g}°", end="", flush=True)
            if rpm != 0:
                cero_desde = None
            elif cero_desde is None:
                cero_desde = t
            elif t - cero_desde >= consola.CIERRE_DETENIDO_MS and not cierre_pedido:
                cierre_pedido = True
                placa.enviar("STOP")
    placa.enviar("STOP")
    return captura, rpm_inicial, "sin_respuesta"


def main():
    opciones = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    opciones.add_argument("--puerto", required=True)
    opciones.add_argument("--plan", default=str(PLAN_INICIAL))
    opciones.add_argument("--nombre", default="identificacion", help="carpeta dentro de datos/")
    opciones.add_argument("--alto", type=float, help="%% de motor de la velocidad alta (omite el barrido)")
    opciones.add_argument("--bajo", type=float, help="%% de motor de la velocidad baja (omite el barrido)")
    opciones.add_argument("--motor", type=float, nargs="+", default=BARRIDO, help="%% del barrido")
    args = opciones.parse_args()

    carpeta = consola.DATOS / args.nombre
    carpeta.mkdir(parents=True, exist_ok=True)
    indice = carpeta / "indice.csv"

    try:
        placa = Placa(args.puerto)
    except serial.SerialException as error:
        sys.exit(f"No se pudo abrir {args.puerto}: {error}")
    config = placa.configuracion()
    if "servo" not in config or "motor" not in config:
        sys.exit("La placa no respondio la configuracion: ¿firmware flasheado?")
    maximo = config["motor"]["maximo_porcentaje"]
    liberado = config["servo"]["liberado_deg"]
    placa.enviar(f"FRENO {liberado}")
    archivo_niveles = carpeta / "niveles.json"
    try:
        if args.alto and args.bajo:
            niveles = {"alto": args.alto, "bajo": args.bajo}
        elif archivo_niveles.exists():
            niveles = json.loads(archivo_niveles.read_text(encoding="utf-8"))
            print(f"Velocidades ya elegidas: alta {niveles['alto']:g} %, baja {niveles['bajo']:g} % ({archivo_niveles.name})")
        else:
            porcentajes = [m for m in args.motor if 0 < m <= maximo]
            if len(porcentajes) < len(args.motor):
                print(f"La placa admite hasta {maximo} % de motor (CONFIG_ASM_MOTOR_MAXIMO_PORCENTAJE); se omite el resto")
            input(f"Barrido de velocidad a {', '.join(f'{m:g}' for m in porcentajes)} %. Enter para empezar: ")
            niveles = elegir_niveles(barrido(placa, carpeta, porcentajes,
                                             config["motor"]["maximo_impulso_ms"] / 1000 - 0.5, liberado))
        archivo_niveles.write_text(json.dumps(niveles, indent=2) + "\n", encoding="utf-8")
    except (KeyboardInterrupt, EOFError):
        placa.enviar("STOP")
        sys.exit("\nBarrido interrumpido")
    if max(niveles["alto"], niveles["bajo"]) > maximo:
        sys.exit(f"La placa admite hasta {maximo} % de motor (CONFIG_ASM_MOTOR_MAXIMO_PORCENTAJE)")
    valores = {"alto": niveles["alto"], "bajo": niveles["bajo"], "LIBERADO": liberado,
               "MAXIMO": config["servo"]["maximo_deg"]}

    plan = leer_plan(args.plan, valores)
    completos = hechos(indice)
    pendientes = [e for e in plan if clave(e) not in completos]
    print(f"Campana '{args.nombre}': {len(plan)} ensayos, {len(plan) - len(pendientes)} ya hechos, "
          f"{len(pendientes)} pendientes. Datos en {carpeta}")
    try:
        for n, ensayo in enumerate(pendientes, 1):
            print(f"\n[{n}/{len(pendientes)}] {clave(ensayo)}: {ensayo['descripcion']}")
            print(f"  motor {ensayo['motor']:g} %, freno {ensayo['freno']:g}°, espera {ensayo['espera_ms']} ms")
            esperar_detenido(placa)
            opcion = input("  Enter para empezar, s para saltar, q para terminar: ").strip().lower()
            if opcion == "q":
                break
            if opcion == "s":
                continue
            consola.DATOS = carpeta / ensayo["grupo"]  # Captura guarda en la carpeta del grupo
            captura, rpm_inicial, motivo = correr(placa, ensayo)
            print()
            completo = bool(captura and captura.meta.get("completo"))
            if captura:
                for linea in consola.resumir(captura.filas):
                    print("  " + linea)
            if not completo:
                print(f"  ✗ ensayo no valido: {consola.MOTIVOS.get(motivo, motivo)}")
            anotar(indice, {"fecha": datetime.now().isoformat(timespec="seconds"), "grupo": ensayo["grupo"],
                            "nivel": ensayo["nivel"], "repeticion": ensayo["repeticion"],
                            "motor": ensayo["motor"], "freno": ensayo["freno"], "espera_ms": ensayo["espera_ms"],
                            "archivo": f"{ensayo['grupo']}/{captura.base.name}.csv" if captura else "",
                            "completo": "si" if completo else "no",
                            "rpm_inicial": f"{rpm_inicial:.1f}" if rpm_inicial else "", "motivo": motivo or ""})
    except (KeyboardInterrupt, EOFError):
        print()
    finally:
        placa.enviar("STOP")
    restantes = len([e for e in plan if clave(e) not in hechos(indice)])
    print(f"\nFin. Pendientes: {restantes}. Indice: {indice}")


if __name__ == "__main__":
    main()
