"""Ejercita la herramienta real con un puerto fragmentado; no acredita hardware."""
from pathlib import Path
import json
import sys

import numpy as np
import pytest

FIRMWARE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(FIRMWARE / "tools"))
from pc import protocolo
from pc.cliente import Cliente
from pc.archivos import abrir_sesion
from pc.terminal import configuracion_inicial


class PuertoSimulado:
    """Modelo de transporte y respuestas, sin reemplazar las pruebas del DSP C."""

    def __init__(self, fallo=None):
        """Inicia contadores y una cola con fragmentacion deliberada de respuestas."""
        self.cola = bytearray()
        self.secuencia = 0
        self.sesion = 0
        self.longitud = 0
        self.fallo = fallo
        self.operaciones = []
        self.audio_recibido = bytearray()

    @property
    def in_waiting(self):
        """Limita cada lectura para ejercitar ensamblado de tramas parciales."""
        return min(len(self.cola), 37)

    def reset_input_buffer(self):
        """Simula descartar bytes viejos antes de HELLO."""
        self.cola.clear()

    def read(self, cantidad):
        """Entrega como maximo los bytes solicitados."""
        datos = bytes(self.cola[:cantidad])
        del self.cola[:cantidad]
        return datos

    def publicar(self, tipo, datos=b"", indice=0, canal=0):
        """Codifica respuestas utilizando el mismo contrato que el firmware."""
        self.cola.extend(protocolo.codificar(protocolo.Paquete(tipo, self.sesion, self.secuencia, indice, canal, datos)))
        self.secuencia += 1

    def write(self, trama):
        """Responde a comandos y archivos; permite inyectar desconexion y saltos."""
        if trama == b"\0":
            return 1
        paquete = protocolo.decodificar(trama[:-1])
        self.sesion = paquete.sesion
        if paquete.tipo == protocolo.COMANDO:
            orden = paquete.datos.decode().split()
            self.operaciones.append(orden[0])
            if orden[0] in ("HELLO", "LINK_OK", "STOP"):
                self.publicar(protocolo.ACK, b"ASM2 enlace=1" if orden[0] == "HELLO" else orden[0].encode())
            elif orden[0] == "EVALUATE":
                self.longitud = int(orden[1])
                self.publicar(protocolo.ACK, b"INICIO")
            elif orden[0] == "PLAY":
                self.longitud = int(orden[1])
                self.audio_recibido.clear()
                self.publicar(protocolo.ACK, b"AUDIO ventana=2 bloque=1536")
        elif paquete.tipo == protocolo.ENTRADA:
            if self.fallo == "desconexion":
                raise OSError("USB desconectado")
            if self.fallo == "salto":
                self.secuencia += 1
            mezcla = np.frombuffer(paquete.datos, dtype="<i2").reshape(-1, 2)[:, 0].tobytes()
            for canal in (1, 2, 3):
                self.publicar(protocolo.SALIDA, mezcla, paquete.indice, canal)
            self.publicar(protocolo.ACK, b"BLOQUE")
            if paquete.indice + 256 == self.longitud:
                informe = {"muestras": self.longitud, "calculo_max_us": 100,
                           "fir": {"mse": 0}, "espectral": {"mse": 0}}
                self.publicar(protocolo.RESULTADO, json.dumps(informe).encode())
                self.publicar(protocolo.FIN)
        elif paquete.tipo == protocolo.AUDIO:
            assert paquete.indice * 2 == len(self.audio_recibido)
            self.audio_recibido.extend(paquete.datos)
            self.publicar(protocolo.ACK, b"BLOQUE_AUDIO")
            if len(self.audio_recibido) == self.longitud * 2:
                self.publicar(protocolo.RESULTADO, json.dumps({"muestras_reproducidas": self.longitud}).encode())
                self.publicar(protocolo.FIN)
        return len(trama)


def test_evaluar_y_reproducir_sin_refiltrar(tmp_path):
    """La reproduccion envia el WAV existente y conserva sus bytes tras repetirla."""
    puerto = PuertoSimulado()
    cliente = Cliente(puerto)
    cliente.enlace_comprobado = True
    mezcla = np.arange(4096, dtype="<i2")
    ruta, _ = cliente.registrar(tmp_path, configuracion_inicial(), mezcla, mezcla, 1, "archivo")
    assert abrir_sesion(ruta)[1]["estado"] == "completa"
    original = (ruta / "fir.wav").read_bytes()
    for _ in range(2):
        assert cliente.reproducir(ruta, "fir", 1)["muestras_reproducidas"] == 4096
        assert puerto.audio_recibido == mezcla.tobytes()
        assert (ruta / "fir.wav").read_bytes() == original
    assert puerto.operaciones.count("EVALUATE") == 1
    assert puerto.operaciones.count("PLAY") == 2


@pytest.mark.parametrize("fallo", ["desconexion", "salto"])
def test_fallo_no_declara_completa(tmp_path, fallo):
    """Desconexion o discontinuidad invalidan toda la captura y dejan evidencia."""
    cliente = Cliente(PuertoSimulado(fallo))
    mezcla = np.zeros(256, dtype="<i2")
    with pytest.raises(RuntimeError):
        cliente.registrar(tmp_path, configuracion_inicial(), mezcla, mezcla, 1, "archivo")
    carpetas = list(tmp_path.iterdir())
    assert len(carpetas) == 1
    assert json.loads((carpetas[0] / "sesion.json").read_text())["estado"] == "incompleta"


def test_cancelacion_envia_stop():
    """La cancelacion es explicita y no dispara una reproduccion ni otra captura."""
    puerto = PuertoSimulado()
    cliente = Cliente(puerto)
    cliente.cancelar()
    assert cliente.cancelado.is_set() and puerto.operaciones == ["STOP"]
