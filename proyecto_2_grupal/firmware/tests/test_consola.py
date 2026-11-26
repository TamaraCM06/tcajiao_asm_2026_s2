"""Comprueba que la consola conserva las decisiones de estabilidad recibidas, sin placa."""
import pytest


# Las decisiones no se recortan por el reloj de pantalla ni se mezclan con el sondeo STATUS.
def test_decisiones_sin_recorte_ni_sondeo(consola, monkeypatch):
    lineas = []
    monkeypatch.setattr(consola, "mostrar", lambda texto, color="": lineas.append(texto))
    banco = consola.Banco(None, "prueba")
    mensaje = {"tipo": "estabilidad", "tiempo_ms": 500, "velocidad_rpm": 1050,
               "referencia_rpm": 1000, "minimo_rpm": 930, "maximo_rpm": 1070,
               "referencia_siguiente_rpm": 1000, "lecturas": 2, "requeridas": 5, "decision": "dentro"}
    banco.mensaje_json(mensaje)
    banco.mensaje_json(dict(mensaje, tiempo_ms=1000, velocidad_rpm=1100,
                            referencia_siguiente_rpm=1100, lecturas=1, decision="fuera"))
    assert len(lineas) == 2
    assert "0.50 s" in lineas[0] and "RPM 1050.0" in lineas[0] and "2/5" in lineas[0]
    assert "ref 1000.0" in lineas[1] and "[930.0, 1070.0]" in lineas[1]
    assert "1/5" in lineas[1] and "reinicio con ref 1100.0" in lineas[1]
    banco.acelerando_desde = 1
    banco.sondeos = 1
    banco.mensaje_json({"tipo": "estado", "hardware_listo": True, "acelerando": True, "velocidad_rpm": 9999})
    assert len(lineas) == 2 and banco.sondeos == 0


# Una perdida de lectura se muestra con contador cero y sin inventar valores numericos.
def test_diagnostico_sin_lectura(consola, monkeypatch):
    lineas = []
    monkeypatch.setattr(consola, "mostrar", lambda texto, color="": lineas.append(texto))
    banco = consola.Banco(None, "prueba")
    banco.mensaje_json({"tipo": "estabilidad", "tiempo_ms": 0, "velocidad_rpm": None,
                       "referencia_rpm": None, "minimo_rpm": None, "maximo_rpm": None,
                       "referencia_siguiente_rpm": None, "lecturas": 0, "requeridas": 5, "decision": "invalida"})
    assert len(lineas) == 1
    assert all(texto in lineas[0] for texto in ("sin medida", "sin referencia", "no disponible", "0/5", "reinicio"))


# El aviso de corte usa el limite informado por la placa y admite no haberlo recibido.
@pytest.mark.parametrize("limite_ms, esperado", [(30000, "limite de 30 s"), (None, "limite de impulso configurado")])
def test_limite_motor_informado(consola, monkeypatch, limite_ms, esperado):
    lineas = []
    monkeypatch.setattr(consola, "mostrar", lambda texto, color="": lineas.append(texto))
    banco = consola.Banco(None, "prueba")
    if limite_ms is not None:
        banco.config["motor"] = {"maximo_impulso_ms": limite_ms}
    banco.mensaje_json({"tipo": "evento", "evento": "limite_impulso_motor", "valor": 0})
    assert len(lineas) == 1 and esperado in lineas[0]
    assert "15 s" not in lineas[0]


# Una placa sin mensajes de estabilidad conserva la visualizacion anterior de aceleracion.
def test_estado_de_firmware_anterior(consola, monkeypatch):
    lineas = []
    monkeypatch.setattr(consola, "mostrar", lambda texto, color="": lineas.append(texto))
    monkeypatch.setattr(consola.time, "monotonic", lambda: 10)
    banco = consola.Banco(None, "prueba")
    banco.acelerando_desde = 9
    banco.sondeos = 1
    banco.mensaje_json({"tipo": "estado", "hardware_listo": True, "acelerando": True, "velocidad_rpm": 1234.5})
    assert len(lineas) == 1 and "acelerando" in lineas[0] and "1234.5 RPM" in lineas[0]
