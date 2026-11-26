#!/usr/bin/env python3
"""Entrada unica del banco de frenado (ESP32). Pasos completos: docs/04_capturas_y_graficas.md

  python banco.py preparar             instala pyserial y pytest en el Python de ESP-IDF (una vez)
  python banco.py compilar             compila el firmware en salidas/firmware
  python banco.py flashear [-p PUERTO] compila y programa la placa
  python banco.py consola  [-p PUERTO] [--nombre escalon]   ensayos y capturas en datos/
  python banco.py monitor  [-p PUERTO] serie sin filtro (salir con Ctrl+])
  python banco.py menuconfig           cambio temporal; lo vigente va en firmware/sdkconfig.defaults
  python banco.py pruebas              pruebas del firmware en la PC (gcc + pytest)
  python banco.py limpiar              borra salidas/

Todo lo generado queda en salidas/. El puerto se detecta solo si hay una sola placa.
"""
import argparse
import glob
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

sys.dont_write_bytecode = True
RAIZ = Path(__file__).resolve().parent
FIRMWARE = RAIZ / "firmware"
SALIDAS = RAIZ / "salidas"
WINDOWS = os.name == "nt"
# Chips USB-serie de las placas ESP32 comunes: CP210x, CH340, FTDI y USB nativo de Espressif.
FABRICANTES_USB = {0x10C4, 0x1A86, 0x0403, 0x303A}


def fallar(mensaje):
    sys.exit(f"banco: {mensaje}")


def buscar_idf():
    """Devuelve (IDF_PATH, IDF_TOOLS_PATH, python del entorno de ESP-IDF) o None."""
    sdks = [os.environ.get("IDF_PATH"), Path.home() / "esp/esp-idf", "C:/Espressif/frameworks/esp-idf-v5.5.5"]
    herramientas = [os.environ.get("IDF_TOOLS_PATH"), Path.home() / ".espressif", "C:/Espressif"]
    sdk = next((Path(r) for r in sdks if r and (Path(r) / "tools/idf.py").is_file()), None)
    for base in (Path(r) for r in herramientas if r):
        binario = "Scripts/python.exe" if WINDOWS else "bin/python"
        pythons = sorted(glob.glob(str(base / "python_env" / "idf5.5_py*_env" / binario)))
        if sdk and pythons:
            return sdk, base, Path(pythons[-1])
    return None


def usar_python_idf(idf):
    """Reejecuta banco.py con el Python de ESP-IDF, que trae pyserial y esptool."""
    # Se compara el entorno, no el ejecutable: en Linux el python del venv es un enlace al del sistema.
    if idf and Path(sys.prefix).resolve() != idf[2].parent.parent.resolve():
        sys.exit(subprocess.run([str(idf[2]), __file__, *sys.argv[1:]]).returncode)


def entorno_idf(idf):
    """Equivale a export.sh/export.ps1, sin tener que activarlo en cada terminal."""
    sdk, herramientas, python = idf
    entorno = dict(os.environ, IDF_PATH=str(sdk), IDF_TOOLS_PATH=str(herramientas),
                   PYTHONUTF8="1", PYTHONDONTWRITEBYTECODE="1")
    salida = subprocess.run([str(python), str(sdk / "tools/idf_tools.py"), "export", "--format=key-value"],
                            env=entorno, capture_output=True, text=True)
    if salida.returncode:
        fallar(f"no se pudo activar ESP-IDF:\n{salida.stderr.strip()}")
    for linea in salida.stdout.splitlines():
        nombre, _, valor = linea.partition("=")
        if nombre and valor:
            entorno[nombre] = valor.replace("%PATH%", os.environ["PATH"]).replace("$PATH", os.environ["PATH"])
    temporal = entorno.pop("IDF_DEACTIVATE_FILE_PATH", None)
    if temporal:
        Path(temporal).unlink(missing_ok=True)
    return entorno


def rutas_firmware():
    """CMake de ESP-IDF falla con rutas no ASCII (visto en Windows): en ese caso compila una copia."""
    if str(RAIZ).isascii() and " " not in str(RAIZ):
        return FIRMWARE, SALIDAS / "firmware"
    copia = Path(tempfile.gettempdir()) / "asm2_banco"
    shutil.copytree(FIRMWARE, copia / "firmware", dirs_exist_ok=True,
                    ignore=shutil.ignore_patterns("build", "sdkconfig", "sdkconfig.old"))
    print(f"banco: la ruta del repo no es ASCII; se compila desde {copia}")
    return copia / "firmware", copia / "salidas"


def idf_py(idf, *argumentos):
    fuente, compilacion = rutas_firmware()
    # ESP-IDF solo aplica sdkconfig.defaults al crear sdkconfig: si los defaults cambiaron despues,
    # se regenera para que la calibracion editada llegue al firmware (menuconfig dura hasta entonces).
    generado, defaults = compilacion / "sdkconfig", fuente / "sdkconfig.defaults"
    if generado.exists() and generado.stat().st_mtime < defaults.stat().st_mtime:
        generado.unlink()
        print("banco: sdkconfig.defaults cambio; se regenera salidas/firmware/sdkconfig")
    orden = [str(idf[2]), str(idf[0] / "tools/idf.py"), "-C", str(fuente), "-B", str(compilacion),
             "-D", f"SDKCONFIG={compilacion / 'sdkconfig'}", *argumentos]
    return subprocess.run(orden, env=entorno_idf(idf)).returncode


def detectar_puerto(pedido):
    if pedido:
        return pedido
    from serial.tools import list_ports
    placas = [p for p in list_ports.comports() if p.vid in FABRICANTES_USB
              or "ttyUSB" in p.device or "ttyACM" in p.device]
    if len(placas) == 1:
        return placas[0].device
    if not placas:
        fallar("no se encontro la placa; conectala o indica -p PUERTO (ej. /dev/ttyUSB0, COM5)")
    fallar("hay varias placas; indica -p con una de: " + ", ".join(p.device for p in placas))


def main():
    opciones = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    opciones.add_argument("accion", choices=["preparar", "compilar", "flashear", "consola", "monitor", "graficar",
                                             "menuconfig", "pruebas", "limpiar"])
    opciones.add_argument("-p", "--puerto")
    opciones.add_argument("--nombre", default="ensayo", help="prefijo de las capturas en datos/")
    opciones.add_argument("--archivo", type=Path, help="CSV para la accion graficar")
    opciones.add_argument("--sin-abrir-grafica", action="store_true", help="guarda el PNG sin abrir el visor")
    args = opciones.parse_args()

    if args.accion == "limpiar":
        shutil.rmtree(SALIDAS, ignore_errors=True)
        print("salidas/ borrada")
        return 0
    idf = buscar_idf()
    if not idf and args.accion not in ("pruebas", "graficar"):
        fallar("no se encontro ESP-IDF 5.5 ni su entorno de Python; revisar docs/04_capturas_y_graficas.md")
    usar_python_idf(idf)
    entorno = dict(os.environ, PYTHONDONTWRITEBYTECODE="1", PYTHONUTF8="1")

    if args.accion == "preparar":
        return subprocess.run([sys.executable, "-m", "pip", "install", "-r", str(RAIZ / "requirements.txt")]).returncode
    if args.accion == "compilar":
        return idf_py(idf, "build")
    if args.accion == "menuconfig":
        return idf_py(idf, "menuconfig")
    if args.accion == "flashear":
        return idf_py(idf, "-p", detectar_puerto(args.puerto), "flash")
    if args.accion == "monitor":
        _, compilacion = rutas_firmware()
        return subprocess.run([sys.executable, "-m", "esp_idf_monitor", "-p", detectar_puerto(args.puerto),
                               "--eol", "LF", str(compilacion / "asm2_registrador.elf")], env=entorno).returncode
    if args.accion == "consola":
        return subprocess.run([sys.executable, str(RAIZ / "herramientas/consola.py"), "--puerto",
                               detectar_puerto(args.puerto), "--nombre", args.nombre,
                               *(["--sin-abrir-grafica"] if args.sin_abrir_grafica else [])], env=entorno).returncode
    if args.accion == "graficar":
        if args.archivo is None:
            opciones.error("graficar requiere --archivo RUTA.csv")
        return subprocess.run([sys.executable, str(RAIZ / "herramientas/graficas_captura.py"),
                               str(args.archivo.resolve()), *([] if args.sin_abrir_grafica else ["--abrir"])],
                              env=entorno).returncode
    if args.accion == "pruebas":
        try:
            import pytest  # noqa: F401
        except ImportError:
            fallar("falta pytest: python banco.py preparar")
        return subprocess.run([sys.executable, "-m", "pytest", str(FIRMWARE / "tests"), "-q", "-p", "no:cacheprovider",
                               f"--basetemp={SALIDAS / 'pruebas'}"], env=entorno).returncode
    return 1


if __name__ == "__main__":
    sys.exit(main())
