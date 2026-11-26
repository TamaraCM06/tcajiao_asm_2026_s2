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


# Los limites incluidos en el error prevalecen sobre una configuracion antigua almacenada en PC.
def test_error_usa_limites_del_mensaje(consola, monkeypatch):
    lineas = []
    monkeypatch.setattr(consola, "mostrar", lambda texto, color="": lineas.append(texto))
    banco = consola.Banco(None, "prueba")
    banco.config = {"motor": {"maximo_porcentaje": 60}, "servo": {"minimo_deg": 45, "maximo_deg": 153}}
    banco.mensaje_json({"tipo": "error", "motivo": "parametros_ENSAYO_invalidos",
                       "parametros": {"motor_maximo_porcentaje": 35, "servo_minimo_deg": 50,
                                      "servo_maximo_deg": 140, "espera_maxima_ms": 10000}})
    assert "0 a 35 %" in lineas[0] and "50 a 140 grados" in lineas[0] and "10000 ms" in lineas[0]
    assert "153" not in lineas[0] and "60 %" not in lineas[0]


# Una respuesta CONFIG confirma lo aplicado en la placa, aunque difiera del ajuste previo de PC.
def test_config_confirmado_por_placa(consola, monkeypatch):
    lineas = []
    monkeypatch.setattr(consola, "mostrar", lambda texto, color="": lineas.append(texto))
    banco = consola.Banco(None, "prueba")
    banco.mensaje_json({"tipo": "ok", "comando": "CONFIG", "periodo_ms": 40,
                       "duracion_ms": 12000, "timeout_ms": 250})
    assert banco.ajustes["periodo"] == 40 and banco.config["ensayo"]["duracion_ms"] == 12000
    assert all(texto in lineas[0] for texto in ("40 ms", "12000 ms", "250 ms"))


# No convierte tiempos fraccionarios en otro valor ni acepta valores no finitos del operador.
def test_ajustes_no_se_redondean_silenciosamente(consola, monkeypatch):
    lineas = []
    monkeypatch.setattr(consola, "mostrar", lambda texto, color="": lineas.append(texto))
    banco = consola.Banco(None, "prueba")
    assert banco.ajustar("periodo", "20.7") is None and banco.ajustes["periodo"] == 20
    assert "entero" in lineas[0]
    assert consola.numero("inf") is None and consola.numero("nan") is None


# Un error sin parametros conserva el motivo y muestra explicitamente lo no informado.
def test_error_sin_limites_no_inventa_valores(consola):
    texto = consola.describir_error({"motivo": "mando_rechazado"}, {})
    assert "no informado" in texto and "153" not in texto and "60 %" not in texto


# La captura muestra mas de una fila en medio segundo, conservando los tres decimales recibidos.
def test_captura_refresca_cada_cien_ms(consola, monkeypatch):
    lineas = []
    tiempos = iter([1.0, 1.11, 1.22, 1.33])
    monkeypatch.setattr(consola, "mostrar", lambda texto, color="": lineas.append(texto))
    monkeypatch.setattr(consola.time, "monotonic", lambda: next(tiempos))
    banco = consola.Banco(None, "prueba")
    for tiempo_ms in (0.549, 110.549, 220.549, 330.549):
        banco.fila(tiempo_ms, 90, 1821.107)
    assert len(lineas) == 4 and all("1821.107 RPM" in linea for linea in lineas)
