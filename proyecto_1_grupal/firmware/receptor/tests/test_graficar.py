"""Pruebas del contrato USB y la conversion ADC, sin hardware ni pyserial."""

import math
import queue
import threading
import unittest

from tools.graficar_microfono import decodificar, recibir


def trama(codigos):
    return ("ADC1,42,10000,3.300000,1,2,3,256," + ",".join(map(str, codigos)) + "\r\n").encode()


class CapturasUSB(unittest.TestCase):
    def test_conversion_voltios_y_metadatos(self):
        captura = decodificar(trama([0, 4095] * 128))
        self.assertIsNotNone(captura)
        self.assertEqual((captura.bloque, captura.fs, captura.perdidos, captura.errores, captura.reinicios),
                         (42, 10000, 1, 2, 3))
        self.assertEqual(captura.voltios[:2], [0.0, 3.3])

    def test_rechaza_tabla_truncamiento_y_codigos_invalidos(self):
        valida = trama([2048] * 256)
        for linea in (b"| 1 | ACTIVIDAD |\n", valida[:100], b"\xff\n",
                      trama([4096] * 256), trama([-1] * 256),
                      valida.replace(b"3.300000", b"nan"),
                      valida.replace(b",256,", b",255,", 1),
                      valida.replace(b",10000,", b",0,", 1)):
            with self.subTest(linea=linea[:50]):
                self.assertIsNone(decodificar(linea))

    def test_tono_adc_conserva_nivel_y_offset(self):
        codigos = [round(2048 + 100 * math.sin(2 * math.pi * 16 * i / 256)) for i in range(256)]
        captura = decodificar(trama(codigos))
        voltios = captura.voltios
        dc = sum(voltios) / 256
        rms = math.sqrt(sum((v - dc) ** 2 for v in voltios) / 256)
        self.assertAlmostEqual(dc, 2048 * 3.3 / 4095, places=5)
        self.assertAlmostEqual(rms, 100 * 3.3 / 4095 / math.sqrt(2), delta=0.0005)

    def test_desconexion_no_bloquea_con_cola_llena(self):
        class PuertoDesconectado:
            def write(self, _):
                raise OSError("USB desconectado")

        ultimos = queue.Queue(maxsize=1)
        ultimos.put(("captura anterior", 0))
        recibir(PuertoDesconectado(), ultimos, threading.Event())
        self.assertEqual(ultimos.get_nowait()[0], "USB desconectado")


if __name__ == "__main__":
    unittest.main()
