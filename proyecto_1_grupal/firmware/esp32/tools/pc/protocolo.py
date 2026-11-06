"""Codec ASM2 independiente del puerto serie y compatible con el firmware C."""
from dataclasses import dataclass
import struct
import zlib

COMANDO, ACK, ENTRADA, SALIDA, RESULTADO, ERROR, AUDIO, SONDA, FIN = range(1, 10)
CABECERA = struct.Struct("<4sBBHIIII")
PAYLOAD_MAX = 4096
TRAMA_MAX = 4144


@dataclass(frozen=True)
class Paquete:
    """Contenido logico, sin padding del compilador ni dependencia del equipo."""
    tipo: int
    sesion: int
    secuencia: int = 0
    indice: int = 0
    canal: int = 0
    datos: bytes = b""


def codificar(paquete):
    """Serializa campos, CRC32 y COBS, incluido delimitador final."""
    if len(paquete.datos) > PAYLOAD_MAX:
        raise ValueError("Paquete demasiado grande")
    crudo = CABECERA.pack(b"ASM2", 1, paquete.tipo, paquete.canal, paquete.sesion,
                         paquete.secuencia, paquete.indice, len(paquete.datos)) + paquete.datos
    crudo += struct.pack("<I", zlib.crc32(crudo))
    salida = bytearray([0])
    posicion_codigo = 0
    codigo = 1
    for valor in crudo:
        if valor == 0:
            salida[posicion_codigo] = codigo
            posicion_codigo = len(salida)
            salida.append(0)
            codigo = 1
        else:
            salida.append(valor)
            codigo += 1
            if codigo == 255:
                salida[posicion_codigo] = codigo
                posicion_codigo = len(salida)
                salida.append(0)
                codigo = 1
    salida[posicion_codigo] = codigo
    salida.append(0)
    return bytes(salida)


def decodificar(trama):
    """Rechaza corrupcion, versiones incompatibles y longitudes falsas."""
    if not trama or len(trama) >= TRAMA_MAX or 0 in trama:
        raise ValueError("Trama COBS invalida")
    crudo = bytearray()
    posicion = 0
    while posicion < len(trama):
        codigo = trama[posicion]
        posicion += 1
        if posicion + codigo - 1 > len(trama):
            raise ValueError("Trama truncada")
        crudo.extend(trama[posicion:posicion + codigo - 1])
        posicion += codigo - 1
        if codigo < 255 and posicion < len(trama):
            crudo.append(0)
    if len(crudo) < 28:
        raise ValueError("Cabecera incompleta")
    marca, version, tipo, canal, sesion, secuencia, indice, longitud = CABECERA.unpack_from(crudo)
    if marca != b"ASM2" or version != 1 or longitud > PAYLOAD_MAX or len(crudo) != longitud + 28:
        raise ValueError("Contrato ASM2 incompatible")
    if zlib.crc32(crudo[:-4]) != struct.unpack_from("<I", crudo, len(crudo) - 4)[0]:
        raise ValueError("CRC incorrecto")
    return Paquete(tipo, sesion, secuencia, indice, canal, bytes(crudo[24:-4]))
