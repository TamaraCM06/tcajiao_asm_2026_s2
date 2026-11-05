"""Sesion serial: un lector, envios sincronizados y ventanas de transferencia acotadas."""
import json
import threading
import time
import wave

import numpy as np

from . import protocolo as protocolo
from .archivos import SesionArchivos, abrir_sesion


class Cliente:
    """Transporta datos; no ejecuta ninguno de los filtros en la computadora."""

    def __init__(self, puerto):
        """Recibe un puerto compatible con PySerial para permitir pruebas sin hardware."""
        self.puerto = puerto
        self.bloqueo = threading.Lock()
        self.secuencia = 0
        self.ultima_secuencia = None
        self.buffer = bytearray()
        self.sesion = 0
        self.cancelado = threading.Event()
        self.enlace_comprobado = False

    def enviar(self, tipo, datos=b"", indice=0, canal=0):
        """Mantiene contiguos los bytes de cada paquete incluso al cancelar desde otro hilo."""
        with self.bloqueo:
            paquete = protocolo.Paquete(tipo, self.sesion, self.secuencia, indice, canal, datos)
            trama = protocolo.codificar(paquete)
            self.secuencia = (self.secuencia + 1) & 0xFFFFFFFF
            if self.puerto.write(trama) != len(trama):
                raise OSError("Escritura serie incompleta")

    def comando(self, texto):
        """Envia solo comandos ASCII; los archivos viajan en paquetes binarios."""
        self.enviar(protocolo.COMANDO, texto.encode("ascii"))

    def recibir(self, espera=3, sincronizando=False):
        """Ensambla fragmentos, valida CRC y exige secuencia sin huecos tras el saludo."""
        limite = time.monotonic() + espera
        while time.monotonic() < limite:
            if 0 in self.buffer:
                delimitador = self.buffer.index(0)
                trama = bytes(self.buffer[:delimitador])
                del self.buffer[:delimitador + 1]
                if not trama:
                    continue
                try:
                    paquete = protocolo.decodificar(trama)
                except ValueError:
                    if sincronizando:
                        continue
                    raise
                if sincronizando:
                    if paquete.sesion != self.sesion or paquete.tipo not in (protocolo.ACK, protocolo.ERROR):
                        continue
                elif self.ultima_secuencia is not None and paquete.secuencia != (self.ultima_secuencia + 1) & 0xFFFFFFFF:
                    raise ValueError("Se perdieron o duplicaron paquetes de la ESP32")
                self.ultima_secuencia = paquete.secuencia
                if paquete.sesion != self.sesion:
                    raise ValueError("Respuesta de otra sesion; reconectar")
                if paquete.tipo == protocolo.ERROR:
                    raise RuntimeError(paquete.datos.decode("utf-8", errors="replace"))
                return paquete
            fragmento = self.puerto.read(max(1, min(getattr(self.puerto, "in_waiting", 0), 8192)))
            self.buffer.extend(fragmento)
            if len(self.buffer) >= protocolo.TRAMA_MAX and 0 not in self.buffer:
                if sincronizando:
                    self.buffer.clear()
                else:
                    raise ValueError("Trama serie sin delimitador")
        raise TimeoutError("La ESP32 dejo de responder")

    def conectar(self):
        """Recupera comunicacion tras arranque o cancelacion; ignora solo el ruido inicial."""
        self.cancelado.clear()
        self.sesion = (time.time_ns() // 1000) & 0xFFFFFFFF
        self.buffer.clear()
        self.puerto.reset_input_buffer()
        self.puerto.write(b"\0")
        ultimo_error = None
        for _ in range(4):
            self.comando("HELLO")
            try:
                saludo = self.recibir(2, sincronizando=True).datos.decode()
                self.enlace_comprobado = self.enlace_comprobado and "enlace=1" in saludo
                return saludo
            except TimeoutError as error:
                ultimo_error = error
        raise TimeoutError(
            "No se recibio el saludo inicial ASM2 de la ESP32. "
            "Compruebe el firmware cargado, el puerto y la comunicacion USB-UART."
        ) from ultimo_error

    def comprobar_enlace(self):
        """Mide datos verificados y exige margen sobre los 96000 bytes/s de audio."""
        self.comando("PROBE")
        recibidos = 0
        inicio = time.monotonic()
        while True:
            paquete = self.recibir()
            if paquete.tipo == protocolo.FIN:
                break
            if paquete.tipo != protocolo.SONDA or paquete.indice != recibidos or len(paquete.datos) != 3072:
                raise ValueError("Prueba de enlace incompleta")
            numero = recibidos // 3072
            esperado = bytes((numero + posicion) % 251 for posicion in range(3072))
            if paquete.datos != esperado:
                raise ValueError("Contenido incorrecto en prueba de enlace")
            recibidos += len(paquete.datos)
        velocidad = recibidos / (time.monotonic() - inicio)
        if recibidos != 393216 or velocidad < 98000:
            raise RuntimeError(f"Enlace insuficiente: {velocidad:.0f} bytes/s; se requieren al menos 98000. Revisar cable/puente USB.")
        self.comando("LINK_OK")
        if self.recibir().tipo != protocolo.ACK:
            raise ValueError("Falta confirmacion del enlace")
        self.enlace_comprobado = True
        return velocidad

    def cancelar(self):
        """Solicita terminar sin confundir una operacion parcial con una sesion completa."""
        self.cancelado.set()
        self.comando("STOP")

    def registrar(self, raiz, configuracion, mezcla=None, referencia=None, escala=3.3, origen="pico", fuente=None):
        """Guarda las tres rutas por bloques mientras la ESP32 calcula sus resultados."""
        self.conectar()
        if origen == "pico" and not self.enlace_comprobado:
            self.comprobar_enlace()
        escala = float(np.float32(escala))
        longitud = configuracion["muestras"] if mezcla is None else len(mezcla)
        metadatos = dict(configuracion, muestras=longitud, duracion_s=longitud / 16000,
                         escala=escala, unidad="voltios" if origen == "pico" else "normalizada",
                         origen=origen, fuente=fuente, con_referencia=referencia is not None)
        archivos = SesionArchivos(raiz, metadatos)
        try:
            if referencia is not None:
                archivos.guardar_referencia(referencia)
            parametros = " ".join(str(configuracion[clave]) for clave in ("minimo_hz", "ancho_hz", "factor", "umbral"))
            orden = f"CAPTURE {longitud} {parametros}" if origen == "pico" else (
                f"EVALUATE {longitud} {int(referencia is not None)} {escala:.9g} {parametros}")
            self.comando(orden)
            enviados = 0
            ultimo_latido = 0.0
            while True:
                if origen == "pico" and not self.cancelado.is_set() and time.monotonic() - ultimo_latido >= 0.5:
                    self.comando("PING")
                    ultimo_latido = time.monotonic()
                paquete = self.recibir()
                if paquete.tipo == protocolo.SALIDA:
                    archivos.agregar(paquete)
                elif paquete.tipo == protocolo.RESULTADO:
                    archivos.informe = json.loads(paquete.datos)
                elif paquete.tipo == protocolo.ACK and mezcla is not None and enviados < longitud and not self.cancelado.is_set():
                    contenido = mezcla[enviados:enviados + 256]
                    if referencia is not None:
                        contenido = np.column_stack((contenido, referencia[enviados:enviados + 256]))
                    self.enviar(protocolo.ENTRADA, contenido.astype("<i2").tobytes(), indice=enviados)
                    enviados += 256
                elif paquete.tipo == protocolo.FIN:
                    if self.cancelado.is_set():
                        raise RuntimeError("Operacion cancelada")
                    archivos.cerrar(completo=True)
                    return archivos.ruta, archivos.informe
                elif paquete.tipo != protocolo.ACK:
                    raise ValueError("Respuesta inesperada durante captura")
        except BaseException as error:
            archivos.cerrar(causa=str(error))
            try:
                self.cancelar()
            except (OSError, ValueError):
                pass
            raise RuntimeError(f"{error}. Sesion incompleta conservada en {archivos.ruta}") from error

    def reproducir(self, ruta, nombre, ganancia, al_iniciar=None):
        """Reproduce un archivo inmutable con dos paquetes en vuelo; no vuelve a filtrarlo."""
        ruta, metadatos = abrir_sesion(ruta)
        if nombre not in ("entrada", "fir", "espectral"):
            raise ValueError("Elegir entrada, fir o espectral")
        self.conectar()
        if not self.enlace_comprobado:
            self.comprobar_enlace()
        longitud = metadatos["muestras"]
        self.comando(f"PLAY {longitud} {metadatos['escala']:.9g} {int(metadatos['unidad'] == 'voltios')} {ganancia}")
        enviados = 0
        pendientes = 0
        resultado = None
        inicio_notificado = False
        with wave.open(str(ruta / f"{nombre}.wav"), "rb") as audio:
            while True:
                paquete = self.recibir()
                if paquete.tipo == protocolo.ACK:
                    if paquete.datos == b"BLOQUE_AUDIO":
                        pendientes -= 1
                        if not inicio_notificado:
                            inicio_notificado = True
                            if al_iniciar is not None:
                                al_iniciar()
                    while pendientes < 2 and enviados < longitud and not self.cancelado.is_set():
                        cantidad = min(1536, longitud - enviados)
                        self.enviar(protocolo.AUDIO, audio.readframes(cantidad), indice=enviados)
                        enviados += cantidad
                        pendientes += 1
                elif paquete.tipo == protocolo.RESULTADO:
                    resultado = json.loads(paquete.datos)
                elif paquete.tipo == protocolo.FIN:
                    if self.cancelado.is_set() or resultado is None or resultado["muestras_reproducidas"] != longitud:
                        raise ValueError("Reproduccion incompleta")
                    return resultado
                else:
                    raise ValueError("Respuesta inesperada durante reproduccion")
