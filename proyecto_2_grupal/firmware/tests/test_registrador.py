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
@pytest.mark.parametrize("escenario", ["velocidad", "promedio", "rechazo_pulsos", "timeout", "reloj_64bits", "conversion",
    "comandos", "configuracion", "temporizacion", "hardware", "inicio_bloqueado", "recorrido", "bloqueos",
    "ensayo_automatico", "estabilidad_bajada", "estabilidad_subida", "estabilidad_limites",
    "estabilidad_lecturas_invalidas", "estabilidad_cadencia", "diagnostico_invalido_sostenido",
    "cola_llena", "fallo_corte"])
def test_escenario_produccion(ejecutor, escenario):
    subprocess.run([str(ejecutor), escenario], check=True, capture_output=True, text=True)


# Reproduce las cuatro trazas del usuario en el coordinador C, sin inventar pulsos intermedios.
def test_estabilidad_mediciones_observadas(ejecutor):
    mediciones = FIRMWARE / "tests/datos/estabilidad_observada.csv"
    subprocess.run([str(ejecutor), "estabilidad_observada", str(mediciones)],
                   check=True, capture_output=True, text=True)


# Contrasta el diagnostico emitido con las lecturas inyectadas, sus reinicios y el inicio del CSV.
def test_diagnostico_estabilidad_produccion(ejecutor):
    resultado = subprocess.run([str(ejecutor), "diagnostico_estabilidad"],
                               check=True, capture_output=True, text=True)
    mensajes = [json.loads(linea[2:]) for linea in resultado.stdout.splitlines() if linea.startswith("# ")]
    diagnosticos = [mensaje for mensaje in mensajes if mensaje["tipo"] == "estabilidad"]
    assert [mensaje["decision"] for mensaje in diagnosticos] == [
        "referencia", "dentro", "fuera", "invalida", "referencia", "dentro", "dentro", "dentro", "aceptada"]
    assert [mensaje["lecturas"] for mensaje in diagnosticos] == [1, 2, 1, 0, 1, 2, 3, 4, 5]
    assert [mensaje["tiempo_ms"] for mensaje in diagnosticos] == [0, 500, 1000, 1001, 1500, 2000, 2500, 3000, 3500]
    assert all(mensaje["requeridas"] == 5 for mensaje in diagnosticos)
    assert diagnosticos[1]["velocidad_rpm"] == 1070
    assert diagnosticos[2]["referencia_rpm"] == 1000
    assert diagnosticos[2]["minimo_rpm"] == 930 and diagnosticos[2]["maximo_rpm"] == 1070
    assert diagnosticos[2]["referencia_siguiente_rpm"] == 1100
    assert diagnosticos[3]["velocidad_rpm"] is None and diagnosticos[3]["referencia_siguiente_rpm"] is None
    assert mensajes.index(diagnosticos[-1]) < next(indice for indice, mensaje in enumerate(mensajes)
                                                 if mensaje["tipo"] == "inicio")
    parametros = next(mensaje for mensaje in mensajes if mensaje.get("grupo") == "ensayo")
    assert parametros["estabilidad_tolerancia_porcentaje"] == 7
    assert parametros["estabilidad_lecturas"] == 5 and parametros["estabilidad_periodo_ms"] == 500


# Comprueba que el error y la confirmacion contienen los parametros efectivos del coordinador C.
def test_error_y_config_informan_parametros_efectivos(ejecutor):
    resultado = subprocess.run([str(ejecutor), "errores_parametros"], check=True, capture_output=True, text=True)
    mensajes = [json.loads(linea[2:]) for linea in resultado.stdout.splitlines() if linea.startswith("# ")]
    error = next(mensaje for mensaje in mensajes if mensaje["tipo"] == "error")
    assert error["motivo"] == "parametros_ENSAYO_invalidos"
    assert error["parametros"]["motor_maximo_porcentaje"] == 30
    assert error["parametros"]["motor_maximo_impulso_ms"] == 15000
    assert error["parametros"]["servo_minimo_deg"] == 10 and error["parametros"]["servo_maximo_deg"] == 90
    assert error["parametros"]["estabilidad_tolerancia_porcentaje"] == 7
    assert error["parametros"]["espera_maxima_ms"] == 10000
    respuesta = next(mensaje for mensaje in mensajes if mensaje.get("comando") == "CONFIG")
    assert [respuesta[campo] for campo in ("periodo_ms", "duracion_ms", "timeout_ms")] == [25, 5000, 150]


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
    estado = next(mensaje for mensaje in mensajes if mensaje["tipo"] == "estado")
    assert estado["velocidad_rpm"] == 1000 and estado["acelerando"] is False
    cierre = next(mensaje for mensaje in mensajes if mensaje["tipo"] == "fin")
    assert cierre["completo"] and cierre["enviadas"] == cierre["producidas"] == 3
    assert {mensaje["grupo"] for mensaje in mensajes if mensaje["tipo"] == "configuracion"} == {"ensayo", "sensor", "servo", "motor"}


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
