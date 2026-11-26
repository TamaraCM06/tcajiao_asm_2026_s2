"""Comprueba la campana de banco.py pid sin placa: nombres, reanudacion, estabilidad y niveles."""
import importlib.util
from pathlib import Path

import pytest

HERRAMIENTAS = Path(__file__).resolve().parents[2] / "herramientas"


# Carga pruebas_pid.py con sus modulos locales, como lo hace banco.py.
@pytest.fixture(scope="module")
def pid():
    with pytest.MonkeyPatch.context() as ajustes:
        ajustes.syspath_prepend(str(HERRAMIENTAS))
        especificacion = importlib.util.spec_from_file_location("pruebas_pid", HERRAMIENTAS / "pruebas_pid.py")
        modulo = importlib.util.module_from_spec(especificacion)
        especificacion.loader.exec_module(modulo)
        yield modulo


VALORES = {"alto": 60, "bajo": 40, "LIBERADO": 90, "MAXIMO": 153}


# Cada ensayo del plan tiene un nombre unico que lleva grupo, nivel, motor, freno y repeticion.
def test_plan_y_nombres(pid):
    plan = pid.leer_plan(HERRAMIENTAS / "plan_identificacion.csv", VALORES)
    nombres = [pid.clave(e) for e in plan]
    assert len(plan) == 32 and len(set(nombres)) == 32
    assert nombres[0] == "caida_libre/caida_alto_m60_f90_r01"
    assert "freno_maximo/fmax_bajo_m40_f153_r03" in nombres
    assert "escalones/esc_alto_m60_f120_r02" in nombres
    assert "validacion/val_bajo_m40_f135_r01" in nombres
    assert {e["grupo"] for e in plan} == {"caida_libre", "freno_maximo", "escalones", "validacion"}


# Un reintento exitoso cuenta como hecho; un ensayo incompleto no.
def test_reanudacion(pid, tmp_path):
    indice = tmp_path / "indice.csv"
    comun = {"fecha": "x", "nivel": "alto", "repeticion": 1, "motor": 60, "espera_ms": 300,
             "rpm_inicial": "", "motivo": ""}
    pid.anotar(indice, dict(comun, grupo="escalones", freno=120, completo="no",
                            archivo="escalones/esc_alto_m60_f120_r01.csv"))
    pid.anotar(indice, dict(comun, grupo="escalones", freno=120, completo="si",
                            archivo="escalones/esc_alto_m60_f120_r01_intento2.csv"))
    pid.anotar(indice, dict(comun, grupo="escalones", freno=130, completo="no",
                            archivo="escalones/esc_alto_m60_f130_r01.csv"))
    assert pid.hechos(indice) == {"escalones/esc_alto_m60_f120_r01"}


# El barrido usa el criterio que la placa informa en CONFIG, o el del firmware si falta.
def test_criterio_estabilidad(pid):
    assert pid.criterio_estabilidad({}) == (0.07, 5, 0.5)
    informado = {"ensayo": {"periodo_ms": 20, "estabilidad_tolerancia_porcentaje": 5.0,
                            "estabilidad_lecturas": 4, "estabilidad_periodo_ms": 250}}
    assert pid.criterio_estabilidad(informado) == (0.05, 4, 0.25)


# La alta es el mayor %; la baja, la meseta mas cercana al 60 % de la alta; el operador puede cambiarlas.
def test_elegir_niveles(pid, monkeypatch):
    mesetas = {30: 980.0, 40: 1306.0, 50: 1633.0, 60: 1959.0}
    monkeypatch.setattr("builtins.input", lambda _: "")
    niveles = pid.elegir_niveles(mesetas)
    assert (niveles["alto"], niveles["bajo"]) == (60, 40)
    monkeypatch.setattr("builtins.input", lambda _: "60 35")
    assert (pid.elegir_niveles(mesetas)["alto"], pid.elegir_niveles(mesetas)["bajo"]) == (60, 35)


class PlacaFalsa:
    """Responde STATUS con una secuencia de RPM y registra las ordenes."""

    def __init__(self, rpm):
        self.rpm, self.ordenes = list(rpm), []

    def enviar(self, linea):
        self.ordenes.append(linea)

    def esperar(self, tipo, segundos=1.0):
        rpm = self.rpm.pop(0) if self.rpm else self.ultimo
        self.ultimo = rpm
        return {"tipo": "estado", "motor_porcentaje": 50, "velocidad_rpm": rpm}


class RelojFalso:
    """Cada sleep avanza el reloj; sin esperas reales."""

    def __init__(self):
        self.t = 0.0

    def monotonic(self):
        return self.t

    def sleep(self, segundos):
        self.t += max(segundos, 0.1)


# Misma regla que el firmware: N lecturas separadas un periodo dentro de la banda; salir de ella reinicia.
def test_meseta_como_el_firmware(pid, monkeypatch):
    reloj = RelojFalso()
    monkeypatch.setattr(pid, "time", reloj)
    subida = [200, 600, 1000, 1400, 1700, 1850]          # aceleracion: cada lectura sale de la banda
    caida = [1900, 1910, 1600]                            # una baja de mas del 7 % reinicia la cuenta
    estable = [1620, 1590, 1640, 1610, 1630, 1600] * 3
    placa = PlacaFalsa([r for r in subida + caida + estable for _ in range(5)])  # 5 STATUS por 0,5 s
    filas, meseta, ok = pid.girar_hasta_meseta(placa, 50, 30, 90, (0.07, 5, 0.5))
    assert ok and 1590 <= meseta <= 1640
    assert placa.ordenes[:2] == ["FRENO 90", "MOTOR 50"] and placa.ordenes[-1] == "MOTOR 0"
    assert filas[-1][0] >= 2.0 + len(subida + caida) * 0.5 - 0.6   # al menos 2 s estable tras el reinicio


# Sin estabilidad antes del limite devuelve la media de los ultimos 2 s y lo marca como no estable.
def test_meseta_no_alcanzada(pid, monkeypatch):
    monkeypatch.setattr(pid, "time", RelojFalso())
    placa = PlacaFalsa([100 * (i + 1) for i in range(200)])
    _, meseta, ok = pid.girar_hasta_meseta(placa, 50, 5, 90, (0.07, 5, 0.5))
    assert not ok and meseta > 0 and placa.ordenes[-1] == "MOTOR 0"
