"""Contrato ADC1 y lectura de bloques de diagnostico independientes de la interfaz."""
from dataclasses import dataclass
import math
import time


@dataclass(frozen=True)
class Captura:
    """Un bloque ADC consecutivo; bloques solicitados separados contienen huecos."""
    bloque: int
    fs: int
    vref: float
    perdidos: int
    errores: int
    reinicios: int
    codigos: tuple[int, ...]

    @property
    def voltios(self):
        """Convierte codigos a voltios con la misma convencion del visualizador."""
        return [codigo * self.vref / 4095 for codigo in self.codigos]


def decodificar(linea):
    """Rechaza tablas de texto, muestras invalidas y versiones ADC1 incompatibles."""
    try:
        campos = linea.decode("ascii").strip().split(",")
        if len(campos) < 8 or campos[0] != "ADC1":
            return None
        bloque, frecuencia = int(campos[1]), int(campos[2])
        referencia = float(campos[3])
        perdidos, errores, reinicios, cantidad = map(int, campos[4:8])
        if cantidad != 256 or len(campos) != 8 + cantidad or frecuencia != 16000:
            return None
        if not math.isfinite(referencia) or not 0 < referencia <= 5:
            return None
        if not all(0 <= valor <= 0xFFFFFFFF for valor in (bloque, perdidos, errores, reinicios)):
            return None
        codigos = tuple(map(int, campos[8:]))
        if any(codigo < 0 or codigo > 4095 for codigo in codigos):
            return None
        return Captura(bloque, frecuencia, referencia, perdidos, errores, reinicios, codigos)
    except (ValueError, UnicodeDecodeError):
        return None


class LectorPico:
    """Ensambla lineas parciales de USB y solicita un bloque fresco por vez."""

    def __init__(self, puerto):
        """Recibe un puerto abierto; no modifica la adquisicion ni el firmware."""
        self.puerto = puerto
        self.buffer = bytearray()
        self.ultimo_bloque = None

    def solicitar(self, espera_s=1.5):
        """Devuelve un bloque ADC1 nuevo sin confundir fragmentacion USB con truncamiento."""
        nombre = getattr(self.puerto, "port", "puerto USB Pico")
        try:
            self.puerto.write(b"g")
        except OSError as error:
            raise ConnectionError(
                f"Pico en {nombre}: fallo al solicitar ADC1 por USB. "
                "Si desconecto/reconecto la placa, confirme el puerto y repita la medicion. "
                f"Detalle: {error}"
            ) from error
        limite = time.monotonic() + espera_s
        while time.monotonic() < limite:
            while b"\n" in self.buffer:
                posicion = self.buffer.index(b"\n")
                linea = bytes(self.buffer[:posicion + 1])
                del self.buffer[:posicion + 1]
                captura = decodificar(linea)
                if captura is not None:
                    if self.ultimo_bloque is not None:
                        diferencia = (captura.bloque - self.ultimo_bloque) & 0xFFFFFFFF
                        if diferencia == 0:
                            continue
                        if diferencia >= 0x80000000:
                            raise RuntimeError("La Pico reinicio su secuencia durante la medicion")
                    self.ultimo_bloque = captura.bloque
                    return captura
            cantidad = max(1, min(getattr(self.puerto, "in_waiting", 0), 4096))
            try:
                self.buffer.extend(self.puerto.read(cantidad))
            except OSError as error:
                raise ConnectionError(f"Pico en {nombre}: se interrumpio la lectura USB: {error}") from error
            if len(self.buffer) > 8192:
                self.buffer.clear()
                raise ValueError("Respuesta USB Pico sin fin de linea")
        raise TimeoutError("La Pico no entrego ADC1. Cierre otras consolas y revise su puerto/firmware.")
