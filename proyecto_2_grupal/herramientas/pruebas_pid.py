#!/usr/bin/env python3
"""Pruebas en el banco para el PID: barrido de velocidad y ensayos del plan, con un solo comando.

Se abre con: python banco.py pid [--nombre identificacion] [--plan archivo.csv] [--alto 60 --bajo 40]
1. Barrido: gira el disco a cada % de motor hasta que la velocidad se estabiliza con el mismo
   criterio que el firmware usa en ENSAYO (por defecto 5 lecturas dentro de ±7 %, una cada 500 ms;
   se leen del CONFIG de la placa) y guarda datos/<nombre>/velocidad/vel_m<motor>_r01.csv. Elige la velocidad alta (el mayor %) y la
   baja (la meseta mas cercana al 60 % de la alta); se aceptan con Enter o se escriben otras.
2. Ensayos del plan, uno por Enter con el disco detenido (s = saltar, q = terminar). Cada uno queda en
   datos/<nombre>/<grupo>/<tipo>_<nivel>_m<motor>_f<freno>_r<repeticion>.csv (+ .json + .png) y en indice.csv.
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
import consola  # noqa: E402  (Captura y cierre automatico, iguales que en la consola)
from analisis_captura import analizar_filas, leer_csv  # noqa: E402
from mensajes_banco import describir_error  # noqa: E402

PLAN_INICIAL = Path(__file__).resolve().parent / "plan_identificacion.csv"
CAMPOS_INDICE = ["fecha", "grupo", "nivel", "repeticion", "motor", "freno", "espera_ms", "archivo",
                 "completo", "rpm_inicial", "motivo"]
TIPO = {"caida_libre": "caida", "freno_maximo": "fmax", "escalones": "esc", "validacion": "val"}
BARRIDO = [30, 40, 50, 60]
ESTABILIDAD_INICIAL = {"estabilidad_tolerancia_porcentaje": 7.0, "estabilidad_lecturas": 5,
                       "estabilidad_periodo_ms": 500}   # si el firmware no informa su criterio
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


def criterio_estabilidad(config):
    """(tolerancia relativa, lecturas, segundos entre lecturas) informados por la placa en CONFIG."""
    ensayo = dict(ESTABILIDAD_INICIAL, **{k: v for k, v in config.get("ensayo", {}).items() if k in ESTABILIDAD_INICIAL})
    return (ensayo["estabilidad_tolerancia_porcentaje"] / 100, int(ensayo["estabilidad_lecturas"]),
            ensayo["estabilidad_periodo_ms"] / 1000)


def girar_hasta_meseta(placa, motor, limite_s, liberado, criterio):
    """Gira hasta cumplir el criterio de ENSAYO: N lecturas, separadas un periodo, dentro de ±tolerancia
    de una referencia fija (una lectura fuera de la banda la reemplaza y reinicia la cuenta).
    Devuelve (filas, meseta = media de las lecturas aceptadas, estable)."""
    tolerancia, requeridas, periodo_s = criterio
    placa.enviar(f"FRENO {liberado}")
    placa.enviar(f"MOTOR {motor:g}")
    filas, inicio, referencia, aceptadas, ultima = [], time.monotonic(), None, [], -periodo_s
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
        print(f"\r\033[K  motor {motor:g} %  {t:5.1f} s  {filas[-1][1]:7.1f} RPM  "
              f"{len(aceptadas)}/{requeridas}", end="", flush=True)
        if not rpm:
            referencia, aceptadas = None, []
        elif t - ultima >= periodo_s:
            ultima = t
            if referencia is None or abs(rpm - referencia) > tolerancia * referencia:
                referencia, aceptadas = rpm, [rpm]
            else:
                aceptadas.append(rpm)
            if len(aceptadas) >= requeridas:
                placa.enviar("MOTOR 0")
                print()
                return filas, statistics.mean(aceptadas), True
        time.sleep(0.1)
    placa.enviar("MOTOR 0")
    print()
    ultimos = [r for tt, r in filas if r == r and tt >= (filas[-1][0] - 2 if filas else 0)]
    return filas, statistics.mean(ultimos) if ultimos else float("nan"), False


def barrido(placa, carpeta, porcentajes, limite_s, liberado, criterio):
    """Meseta de cada % de motor; guarda velocidad/vel_m<motor>_r01.csv."""
    mesetas = {}
    destino = carpeta / "velocidad"
    destino.mkdir(parents=True, exist_ok=True)
    for motor in porcentajes:
        esperar_detenido(placa)
        filas, meseta, estable = girar_hasta_meseta(placa, motor, limite_s, liberado, criterio)
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
    """Un ENSAYO completo; devuelve (captura o None, rpm inicial, motivo o mensaje de error)."""
    placa.serie.reset_input_buffer()
    placa.enviar(f"CONFIG 20 {int(ensayo['duracion_s'] * 1000)} 100")
    respuesta = placa.esperar("ok", 1.0)
    if not respuesta or respuesta.get("tipo") == "error":
        return None, None, respuesta or {"motivo": "sin_respuesta_CONFIG"}
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
                return captura, rpm_inicial, m
            if tipo == "estabilidad" and not captura:
                velocidad = m.get("velocidad_rpm")
                print(f"\r\033[K  estabilidad {m.get('lecturas', 0)}/{m.get('requeridas', '?')}  "
                      f"{velocidad if velocidad is not None else 0:7.1f} RPM  {m.get('decision', '')}", end="", flush=True)
                continue
            if tipo == "evento" and m.get("evento") == "velocidad_maxima":
                print()
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


def resumen_breve(ruta_csv):
    """Dos lineas: pendientes antes/despues del freno y tiempo hasta 0 RPM (de analisis_captura)."""
    filas = leer_csv(ruta_csv)
    a = analizar_filas(filas)
    lineas = [f"{len(filas)} filas · RPM al cortar {filas[0][2]:.0f}"]
    if len(a["cambios_freno"]) == 1:
        t_freno = filas[a["cambios_freno"][0]][0]
        pendientes = " · ".join(f"{nombre} {a[clave]:.0f} RPM/s" for nombre, clave in
                                (("antes", "pendiente_antes_rpm_s"), ("despues", "pendiente_despues_rpm_s"))
                                if a.get(clave) == a.get(clave) and a.get(clave) is not None)
        parada = (f"0 RPM a {(filas[a['indice_parada']][0] - t_freno) / 1000:.2f} s del freno"
                  if a["indice_parada"] is not None else "sin 0 RPM en la captura")
        lineas.append(f"pendiente {pendientes} · {parada}")
    return lineas


def guardar_grafica(ruta_csv):
    """PNG junto al CSV con graficas_captura (sin abrir el visor); un fallo no invalida el ensayo."""
    try:
        from graficas_captura import generar_grafica_csv
        return generar_grafica_csv(ruta_csv)
    except (ImportError, OSError, ValueError) as error:
        print(f"  (sin grafica: {error})")
        return None


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
            criterio = criterio_estabilidad(config)
            print(f"Criterio de estabilidad (el del ENSAYO): {criterio[1]} lecturas dentro de ±{criterio[0] * 100:g} %, "
                  f"una cada {criterio[2] * 1000:g} ms")
            niveles = elegir_niveles(barrido(placa, carpeta, porcentajes,
                                             config["motor"]["maximo_impulso_ms"] / 1000 - 0.5, liberado, criterio))
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
            if captura and captura.filas:
                ruta_csv = captura.base.with_suffix(".csv")
                try:
                    for linea in resumen_breve(ruta_csv):
                        print("  " + linea)
                except ValueError as error:
                    print(f"  (sin resumen: {error})")
                guardar_grafica(ruta_csv)
            if isinstance(motivo, dict):
                print(f"  ✗ {describir_error(motivo, config)}")
                motivo = motivo.get("motivo", "error")
            elif not completo:
                print(f"  ✗ ensayo no valido: {motivo}")
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
    return 0 if restantes == 0 else 3   # 0: campana completa (banco.py ofrece construir el modelo)


if __name__ == "__main__":
    sys.exit(main())
