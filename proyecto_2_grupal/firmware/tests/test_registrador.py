"""Comprueba fuentes C de produccion en PC; los dobles SDK no acreditan hardware."""
import json
from pathlib import Path
import re
import shutil
import subprocess

import pytest

FIRMWARE = Path(__file__).resolve().parents[1]


# Compila el estimador, conversion, parser, reloj, validacion y coordinador originales.
@pytest.fixture(scope="module")
def ejecutor(tmp_path_factory):
    directorio = tmp_path_factory.mktemp("asm2_host")
    fuente_hardware = (FIRMWARE / "src/hardware.c").read_text(encoding="utf-8")
    nombres = set(re.findall(r"CONFIG_ASM_[A-Z0-9_]+", fuente_hardware))
    nombres -= {"CONFIG_ASM_CONEXIONES_VERIFICADAS", "CONFIG_ASM_SENSOR_FLANCO_BAJADA"}
    (directorio / "sdkconfig.h").write_text("\n".join(f"#define {nombre} 0" for nombre in sorted(nombres)), encoding="ascii")
    salida = directorio / "registrador.exe"
    compilador = shutil.which("gcc")
    assert compilador, "Se requiere GCC para comprobar el mismo nucleo C."
    fuentes = [FIRMWARE / "src" / nombre for nombre in (
        "estimador_velocidad.c", "conversion_freno.c", "comandos.c", "reloj_registro.c", "hardware.c")]
    subprocess.run([compilador, "-std=c11", "-D__USE_MINGW_ANSI_STDIO=1", "-Wall", "-Wextra", "-Werror",
                    "-I", str(FIRMWARE / "include"), "-I", str(FIRMWARE / "tests/dobles"),
                    "-I", str(directorio), *(str(fuente) for fuente in fuentes),
                    str(FIRMWARE / "tests/pruebas_host.c"), "-lm", "-o", str(salida)], check=True)
    return salida


# Cada escenario ejecuta comportamientos observables y estados invalidos distintos.
@pytest.mark.parametrize("escenario", ["velocidad", "rechazo_pulsos", "timeout", "reloj_64bits", "conversion",
    "comandos", "configuracion", "temporizacion", "hardware", "inicio_bloqueado", "recorrido", "bloqueos",
    "cola_llena", "fallo_corte"])
def test_escenario_produccion(ejecutor, escenario):
    subprocess.run([str(ejecutor), escenario], check=True, capture_output=True, text=True)


# Verifica que los conteos del cierre corresponden a las filas reales del protocolo.
def test_trama_produccion(ejecutor):
    resultado = subprocess.run([str(ejecutor), "trama"], check=True, capture_output=True, text=True)
    lineas = resultado.stdout.splitlines()
    mensajes = [json.loads(linea[2:]) for linea in lineas if linea.startswith("# ")]
    filas = [linea.split(",") for linea in lineas if not linea.startswith("# ")]
    assert filas[0] == ["tiempo_ms", "freno_deg", "velocidad_rpm"]
    assert len(filas[1:]) == 3
    assert [float(fila[0]) for fila in filas[1:]] == [0, 20, 40]
    assert [float(fila[1]) for fila in filas[1:]] == [10, 40, 40]
    cierre = next(mensaje for mensaje in mensajes if mensaje["tipo"] == "fin")
    assert cierre["completo"] and cierre["enviadas"] == cierre["producidas"] == 3
    assert {mensaje["grupo"] for mensaje in mensajes if mensaje["tipo"] == "configuracion"} == {"ensayo", "sensor", "servo", "motor"}
    destino = FIRMWARE / "build/pruebas"
    destino.mkdir(parents=True, exist_ok=True)
    (destino / "trama_produccion.txt").write_text(resultado.stdout, encoding="utf-8")


# Enlaza los controladores PWM reales con dobles que solo registran sus ordenes.
@pytest.fixture(scope="module")
def ejecutor_actuadores(tmp_path_factory):
    salida = tmp_path_factory.mktemp("asm2_actuadores") / "actuadores.exe"
    fuentes = [FIRMWARE / "src" / nombre for nombre in ("motor.c", "servo_freno.c", "conversion_freno.c")]
    subprocess.run([shutil.which("gcc"), "-std=c11", "-Wall", "-Wextra", "-Werror",
        "-I", str(FIRMWARE / "include"), "-I", str(FIRMWARE / "tests/dobles"),
        *(str(fuente) for fuente in fuentes), str(FIRMWARE / "tests/pruebas_actuadores.c"),
        "-lm", "-o", str(salida)], check=True)
    return salida


# Comprueba limites y recuperacion sin confundir las ordenes simuladas con PWM medido.
@pytest.mark.parametrize("escenario", ["arranque", "limite_impulso", "limites", "fallo_pwm"])
def test_actuadores_produccion(ejecutor_actuadores, escenario):
    subprocess.run([str(ejecutor_actuadores), escenario], check=True, capture_output=True, text=True)
