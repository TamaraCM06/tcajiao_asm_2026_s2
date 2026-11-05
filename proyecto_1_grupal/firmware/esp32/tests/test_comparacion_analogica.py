"""Pruebas de instrumentacion y porcentajes; las capturas sinteticas no acreditan hardware."""
import csv
from dataclasses import replace
import json
from pathlib import Path
from contextlib import contextmanager, nullcontext
import sys
import threading
import wave

import numpy as np
import pytest

PROYECTO = Path(__file__).resolve().parents[3]
FIRMWARE = PROYECTO / "firmware/esp32"
sys.path.insert(0, str(PROYECTO))
sys.path.insert(0, str(PROYECTO / "tarea1_grupo1"))
sys.path.insert(0, str(FIRMWARE / "tools"))
from herramientas.capturas_pico import Captura, LectorPico
from pc.analisis_analogico import amplitudes_componentes, comparar_respuesta, ganancia_teorica, resumir_capturas
from pc.concordancia import concordancia_modelo, validar_sesion
from pc.demo_analogica import cargar_modelo, pedir_conexion
from pc.archivos import SesionArchivos, cuantizar
from pc.protocolo import Paquete, SALIDA
from src.filtros.filtrado_espectral import filtrar_senal
from scipy.signal import lfilter


def capturas_sinteticas(frecuencias, ganancias, offset, cantidad=12):
    """Cuantiza bloques con fases distintas para verificar el ajuste sin concatenar huecos."""
    capturas = []
    amplitudes = np.array([0.3, 0.15, 0.1, 0.12]) * ganancias
    for numero in range(cantidad):
        tiempos = np.arange(256) / 16000
        voltios = np.full(256, offset)
        for frecuencia, amplitud in zip(frecuencias, amplitudes):
            voltios += amplitud * np.sin(2 * np.pi * frecuencia * tiempos + numero * 0.37)
        codigos = np.clip(np.floor(voltios / 3.3 * 4095 + 0.5), 0, 4095).astype(int)
        capturas.append(Captura(numero * 13, 16000, 3.3, 0, 0, 0, tuple(codigos)))
    return capturas


def test_respuesta_y_porcentajes_analogicos():
    """Recupera la respuesta ideal pese a fases libres y a cuantizacion ADC de 12 bits."""
    modelo, frecuencias = cargar_modelo(PROYECTO)
    ganancias = ganancia_teorica(frecuencias, modelo)
    np.testing.assert_allclose(ganancias, [0.499715, 0.495501, 0.478396, 0.168667], atol=0.0001)
    antes = resumir_capturas(capturas_sinteticas(frecuencias, np.ones(4), 1.65), frecuencias)
    despues = resumir_capturas(capturas_sinteticas(frecuencias, ganancias, .825), frecuencias)
    filas = comparar_respuesta(antes, despues, frecuencias, modelo)
    assert all(fila["cumple_criterio"] for fila in filas)
    assert min(fila["concordancia_teorica_pct"] for fila in filas) > 99
    # Medir el mismo punto dos veces debe descubrir que falta el filtro.
    incorrectas = comparar_respuesta(antes, antes, frecuencias, modelo)
    assert not any(fila["cumple_criterio"] for fila in incorrectas)


def test_saturacion_y_senal_debil_no_generan_accuracy():
    """Una lectura invalida no se presenta como porcentaje de confianza del filtro."""
    modelo, frecuencias = cargar_modelo(PROYECTO)
    antes = resumir_capturas(capturas_sinteticas(frecuencias, np.ones(4), 1.65), frecuencias)
    despues = dict(antes, saturadas=1)
    assert all(fila["concordancia_teorica_pct"] is None for fila in comparar_respuesta(antes, despues, frecuencias, modelo))
    silencio = [Captura(numero, 16000, 3.3, 0, 0, 0, (2048,) * 256) for numero in range(4)]
    debil = resumir_capturas(silencio, frecuencias)
    assert all(not fila["medida_valida"] for fila in comparar_respuesta(antes, debil, frecuencias, modelo))


def test_contadores_adc_y_frecuencias_invalidas():
    """La instrumentacion detecta errores de adquisicion y parametros incompatibles."""
    _, frecuencias = cargar_modelo(PROYECTO)
    capturas = capturas_sinteticas(frecuencias, np.ones(4), 1.65)
    capturas[-1] = replace(capturas[-1], errores=1)
    with pytest.raises(ValueError):
        resumir_capturas(capturas, frecuencias)
    with pytest.raises(ValueError):
        amplitudes_componentes(np.zeros(256), 16000, [8000])


def test_lector_usb_fragmentado():
    """Acepta un ADC1 dividido en muchas lecturas e ignora lineas de consola."""
    class Puerto:
        """Puerto de prueba sin placa ni dependencias serie."""
        def __init__(self):
            """Prepara una respuesta con saltos de linea y un bloque de 256 codigos."""
            self.datos = bytearray(("tabla\r\nADC1,17,16000,3.3,0,0,0,256," + ",".join(["2048"] * 256) + "\r\n").encode())
        @property
        def in_waiting(self):
            """Fuerza fragmentacion dentro de campos y codigos."""
            return min(7, len(self.datos))
        def write(self, datos):
            """Acepta la peticion g."""
            return len(datos)
        def read(self, cantidad):
            """Entrega una parte de la linea sin perder el resto."""
            salida = bytes(self.datos[:cantidad])
            del self.datos[:cantidad]
            return salida
    captura = LectorPico(Puerto()).solicitar()
    assert captura.bloque == 17 and len(captura.codigos) == 256


def test_definicion_concordancia():
    """La concordancia mide cercania al modelo y maneja el silencio sin dividir por cero."""
    assert concordancia_modelo([1, -1], [1, -1])["concordancia_modelo_python_pct"] == 100
    assert concordancia_modelo([.9, -.9], [1, -1])["concordancia_modelo_python_pct"] == pytest.approx(90)
    assert concordancia_modelo([0, 0], [0, 0])["concordancia_modelo_python_pct"] == 100
    assert concordancia_modelo([1, 0], [0, 0])["concordancia_modelo_python_pct"] is None


def test_validacion_sesion_y_archivos(tmp_path):
    """Agrega porcentajes sin cambiar WAV ni reemplazar las metricas de la ESP32."""
    tiempos = np.arange(768) / 16000
    entrada_pcm, _ = cuantizar(.3 * np.sin(2 * np.pi * 440 * tiempos), 1)
    entrada = entrada_pcm.astype(np.float32) / 32768
    coeficientes = np.loadtxt(PROYECTO / "tarea1_grupo1/resultados/filtro_temporal/coeficientes_fir.csv",
                             delimiter=",", skiprows=1)[:, 1].astype(np.float32)
    temporal, _ = cuantizar(lfilter(coeficientes, [1], entrada), 1)
    espectral = filtrar_senal(entrada.astype(float), 16000)
    espectral_pcm, _ = cuantizar(np.r_[np.zeros(37), espectral[:-37]], 1)
    sesion = SesionArchivos(tmp_path, dict(muestras=768, escala=1, unidad="normalizada",
        minimo_hz=1600, ancho_hz=100, factor=.1, umbral=.05))
    for canal, muestras in enumerate((entrada_pcm, temporal, espectral_pcm), 1):
        sesion.agregar(Paquete(SALIDA, 1, canal=canal, datos=muestras.tobytes()))
    sesion.informe = {"fir": {"mse": .01}, "espectral": {"mse": .02}}
    sesion.cerrar(completo=True)
    originales = {nombre: (sesion.ruta / f"{nombre}.wav").read_bytes() for nombre in ("entrada", "fir", "espectral")}
    resultados = validar_sesion(sesion.ruta, PROYECTO)
    assert all(resultado["concordancia_modelo_python_pct"] == 100 for resultado in resultados.values())
    for nombre, contenido in originales.items():
        assert (sesion.ruta / f"{nombre}.wav").read_bytes() == contenido
    with (sesion.ruta / "metricas.csv").open() as archivo:
        filas = list(csv.DictReader(archivo))
    assert filas[0]["mse"] == "0.01" and float(filas[0]["concordancia_modelo_python_pct"]) == 100
    assert json.loads((sesion.ruta / "validacion_python.json").read_text())["origen"] == "validacion_independiente_PC"


def test_cancelar_conexion_guiada():
    """Cancelar el cambio de sonda impide comenzar una medicion fisica."""
    with pytest.raises(RuntimeError):
        pedir_conexion("Mover sonda", lambda _: "cancelar")


def test_demo_guiada_guarda_medidas_y_figura(tmp_path, monkeypatch):
    """Ejecuta el flujo completo con USB/DAC simulados, incluidos CSV crudos y figura real."""
    from pc import demo_analogica
    modelo, frecuencias = cargar_modelo(PROYECTO)
    modelo = dict(modelo, capturas_por_punto=3, espera_estabilizacion_s=0, intervalo_capturas_s=.1)
    # Cada punto incluye una captura de verificacion USB y tres de medicion.
    bloques = capturas_sinteticas(frecuencias, np.ones(4), 1.65, 4)
    bloques += capturas_sinteticas(frecuencias, ganancia_teorica(frecuencias, modelo), .825, 4)

    class Puerto:
        """Emite lineas ADC1 para dos posiciones de sonda conocidas."""
        port = "PICO_SIMULADA"
        def __init__(self):
            """Inicializa la cola de bytes y el evento de ultima captura."""
            self.datos = bytearray()
            self.numero = 0
            self.completo = threading.Event()
        def reset_input_buffer(self):
            """Descarta restos antes de cada posicion de sonda."""
            self.datos.clear()
        @property
        def in_waiting(self):
            """Fragmenta las lineas como un puerto serie real."""
            return min(23, len(self.datos))
        def write(self, datos):
            """Una peticion g entrega un bloque y t restaura la consola."""
            if datos == b"g":
                captura = bloques[self.numero]
                linea = f"ADC1,{captura.bloque},16000,3.3,0,0,0,256," + ",".join(map(str, captura.codigos)) + "\n"
                self.datos.extend(linea.encode())
                self.numero += 1
                if self.numero % 4 == 0:
                    self.completo.set()
            return len(datos)
        def read(self, cantidad):
            """Entrega bytes sin unir bloques en el tiempo."""
            salida = bytes(self.datos[:cantidad])
            del self.datos[:cantidad]
            return salida

    puerto = Puerto()

    class Reproductor:
        """Acredita una reproduccion despues de entregar los bloques del punto."""
        def reproducir(self, fuente, nombre, ganancia, al_iniciar):
            """Verifica que ambas medidas usen entrada y ganancia comun."""
            assert nombre == "entrada" and ganancia == 1
            puerto.completo.clear()
            al_iniciar()
            assert puerto.completo.wait(3)
            return dict(muestras_reproducidas=96000, recortes_dac=0)
        def cancelar(self):
            """Desbloquea el modelo si la prueba es cancelada."""
            puerto.completo.set()

    monkeypatch.setattr(demo_analogica, "cargar_modelo", lambda _: (modelo, frecuencias))
    monkeypatch.setattr(demo_analogica, "preparar_fuente", lambda *argumentos: tmp_path / "fuente")
    estado_puerto = dict(abierto=False, aperturas=0)

    @contextmanager
    def abrir_instrumento(_):
        """El puerto se abre despues de cada cambio de sonda y se cierra antes del siguiente."""
        assert not estado_puerto["abierto"]
        estado_puerto.update(abierto=True, aperturas=estado_puerto["aperturas"] + 1)
        try:
            yield puerto
        finally:
            estado_puerto["abierto"] = False

    def confirmar_conexion(_):
        """El usuario puede desconectar USB durante la pregunta sin dejar un handle abierto."""
        assert not estado_puerto["abierto"]
        return ""

    monkeypatch.setattr(demo_analogica, "abrir_pico", abrir_instrumento)
    mensajes = []
    carpeta, _ = demo_analogica.ejecutar_demo(Reproductor(), PROYECTO, tmp_path,
        {}, preguntar=confirmar_conexion, informar=mensajes.append)
    resumen = json.loads((carpeta / "medicion.json").read_text())
    assert resumen["estado"] == "completa" and resumen["cumple_criterio"]
    for punto in ("antes", "despues"):
        with (carpeta / f"medicion_{punto}.csv").open() as archivo:
            assert len(list(csv.DictReader(archivo))) == 3 * 256
    assert (carpeta / "respuesta_analogica.png").stat().st_size > 1000
    assert any("MEDICION GUARDADA" in mensaje for mensaje in mensajes)
    assert estado_puerto["aperturas"] == 2


def test_demo_identifica_fallo_usb_antes_del_audio(tmp_path, monkeypatch):
    """Un puerto invalido deja diagnostico con origen Pico y no inicia el DAC."""
    from pc import demo_analogica

    class PuertoDesconectado:
        """Reproduce el fallo WriteFile informado por Windows."""
        port = "COM13"
        def write(self, _):
            """Falla al solicitar la primera captura ADC1."""
            raise PermissionError(13, "The device does not recognize the command.")

    monkeypatch.setattr(demo_analogica, "preparar_fuente", lambda *argumentos: tmp_path / "fuente")
    monkeypatch.setattr(demo_analogica, "abrir_pico", lambda _: nullcontext(PuertoDesconectado()))
    with pytest.raises(ConnectionError, match="Pico en COM13"):
        demo_analogica.ejecutar_demo(object(), PROYECTO, tmp_path, {},
            preguntar=lambda _: "", informar=lambda _: None)
    carpeta = next((tmp_path / "analogicas").iterdir())
    datos = json.loads((carpeta / "medicion.json").read_text())
    assert datos["estado"] == "incompleta" and datos["etapa"] == "verificacion_usb_antes"
    assert "Pico en COM13" in (carpeta / "diagnostico_error.txt").read_text()
    assert not (carpeta / "medicion_antes.csv").exists()
