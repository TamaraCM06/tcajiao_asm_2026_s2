"""Archivos de evidencia y conversion PCM16 con escala fija por sesion."""
import csv
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from dataclasses import replace
import uuid
import wave

import numpy as np

NOMBRES = {1: "entrada", 2: "fir", 3: "espectral"}


def cuantizar(muestras, escala):
    """Usa el mismo redondeo que C y cuenta los recortes antes de limitar."""
    muestras = np.asarray(muestras)
    if not np.all(np.isfinite(muestras)) or not np.isfinite(escala) or escala <= 0:
        raise ValueError("Muestras o escala invalidas")
    valores = np.floor(muestras.astype(np.float64) / escala * 32768 + 0.5)
    recortes = int(np.count_nonzero((valores < -32768) | (valores > 32767)))
    return np.clip(valores, -32768, 32767).astype("<i2"), recortes


def cargar_csv(ruta):
    """Reutiliza el lector del notebook; tambien admite tiempo_s,contaminada sin referencia."""
    from src.datos.archivos import cargar_muestras_csv
    with Path(ruta).open(encoding="utf-8-sig", newline="") as archivo:
        encabezado = next(csv.reader(archivo), [])
    if encabezado == ["tiempo_s", "contaminada"]:
        valores = np.loadtxt(ruta, delimiter=",", skiprows=1, ndmin=2)
        if valores.shape[1] != 2 or not np.all(np.isfinite(valores)):
            raise ValueError("CSV sin referencia invalido")
        tiempos, mezcla, referencia = valores[:, 0], valores[:, 1], None
    else:
        datos = cargar_muestras_csv(ruta)
        tiempos, mezcla, referencia = datos["t"], datos["noisy"], datos["clean"]
    if not 256 <= len(mezcla) <= 960000 or len(mezcla) % 256:
        raise ValueError("Se requieren 256..960000 muestras, multiplo de 256")
    if not np.allclose(np.diff(tiempos), 1 / 16000, rtol=1e-6, atol=1e-10):
        raise ValueError("El CSV debe estar muestreado uniformemente a 16000 Hz")
    escala = max(1.0, float(np.max(np.abs(mezcla))),
                 0.0 if referencia is None else float(np.max(np.abs(referencia))))
    # El margen de un codigo evita recortar el extremo positivo exactamente igual a escala.
    escala = float(np.float32(escala * 32768 / 32767))
    if escala > 100:
        raise ValueError("La escala excede el limite admitido")
    mezcla_pcm, recortes = cuantizar(mezcla, escala)
    referencia_pcm = None
    if referencia is not None:
        referencia_pcm, recortes_referencia = cuantizar(referencia, escala)
        recortes += recortes_referencia
    return mezcla_pcm, referencia_pcm, escala, recortes


def guardar_json(ruta, contenido):
    """Reemplaza solo los metadatos de la sesion y evita valores JSON no estandar."""
    temporal = ruta.with_suffix(".tmp")
    temporal.write_text(json.dumps(contenido, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    temporal.replace(ruta)


class SesionArchivos:
    """Escribe WAV incrementalmente y conserva las sesiones fallidas como incompletas."""

    def __init__(self, raiz, metadatos):
        """Crea una carpeta unica y marca incompleta antes de recibir la primera muestra."""
        identificador = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "_" + uuid.uuid4().hex[:8]
        self.ruta = Path(raiz) / identificador
        self.ruta.mkdir(parents=True, exist_ok=False)
        self.metadatos = dict(metadatos, estado="incompleta", formato="PCM16", frecuencia_hz=16000,
                              retardo_filtros_muestras=37, protocolo="ASM2/1")
        self.contadores = {canal: 0 for canal in NOMBRES}
        self.archivos = {}
        self.informe = None
        self.cerrada = False
        guardar_json(self.ruta / "sesion.json", self.metadatos)
        for canal, nombre in NOMBRES.items():
            archivo = wave.open(str(self.ruta / f"{nombre}.wav"), "wb")
            archivo.setparams((1, 2, 16000, 0, "NONE", "not compressed"))
            self.archivos[canal] = archivo
        self.evento("Inicio de sesion; resultados pendientes")

    def evento(self, texto):
        """Agrega evidencia textual sin reemplazar eventos anteriores."""
        with (self.ruta / "eventos.log").open("a", encoding="utf-8") as archivo:
            archivo.write(f"{datetime.now(timezone.utc).isoformat()} {texto}\n")

    def agregar(self, paquete):
        """Exige continuidad por canal; nunca une huecos como si fueran audio continuo."""
        if paquete.canal == 0:
            if not paquete.datos or len(paquete.datos) % 6:
                raise ValueError("Longitud invalida del paquete de tres rutas")
            if any(indice != paquete.indice for indice in self.contadores.values()):
                raise ValueError("Perdida o duplicacion de muestras en paquete agrupado")
            muestras = np.frombuffer(paquete.datos, dtype="<i2").reshape(-1, 3)
            if paquete.indice + len(muestras) > self.metadatos["muestras"]:
                raise ValueError("Salida mayor que el registro declarado")
            for columna, canal in enumerate(NOMBRES):
                self.agregar(replace(paquete, canal=canal, datos=muestras[:, columna].tobytes()))
            return
        if paquete.canal not in self.contadores or len(paquete.datos) % 2:
            raise ValueError("Canal o longitud de salida invalido")
        if paquete.indice != self.contadores[paquete.canal]:
            raise ValueError("Perdida o duplicacion de muestras")
        cantidad = len(paquete.datos) // 2
        if self.contadores[paquete.canal] + cantidad > self.metadatos["muestras"]:
            raise ValueError("Salida mayor que el registro declarado")
        self.archivos[paquete.canal].writeframesraw(paquete.datos)
        self.contadores[paquete.canal] += cantidad

    def guardar_referencia(self, muestras):
        """Conserva exactamente la referencia PCM16 enviada a la ESP32."""
        with wave.open(str(self.ruta / "referencia.wav"), "wb") as archivo:
            archivo.setparams((1, 2, 16000, 0, "NONE", "not compressed"))
            archivo.writeframes(muestras.astype("<i2").tobytes())

    def cerrar(self, completo=False, causa=None):
        """Solo declara completa una sesion con tres longitudes correctas y metricas recibidas."""
        if self.cerrada:
            return
        self.cerrada = True
        for archivo in self.archivos.values():
            archivo.close()
        valido = completo and self.informe is not None and all(
            cantidad == self.metadatos["muestras"] for cantidad in self.contadores.values())
        self.metadatos.update(estado="completa" if valido else "incompleta",
                              muestras_guardadas=self.contadores, causa=causa)
        self.metadatos["sha256"] = {nombre: hashlib.sha256((self.ruta / f"{nombre}.wav").read_bytes()).hexdigest()
                                     for nombre in NOMBRES.values()}
        if self.informe is not None:
            self.metadatos["resultado_esp32"] = self.informe
            filas = []
            comunes = {clave: valor for clave, valor in self.informe.items() if not isinstance(valor, dict)}
            for metodo in ("fir", "espectral"):
                filas.append(dict(comunes, metodo=metodo, **self.informe[metodo]))
            with (self.ruta / "metricas.csv").open("w", newline="", encoding="utf-8") as archivo:
                escritor = csv.DictWriter(archivo, fieldnames=list(filas[0]))
                escritor.writeheader()
                escritor.writerows(filas)
        else:
            (self.ruta / "metricas.csv").write_text("metodo,mse,snr_entrada_db,snr_salida_db\n", encoding="utf-8")
        guardar_json(self.ruta / "sesion.json", self.metadatos)
        self.evento("COMPLETA" if valido else f"INCOMPLETA: {causa or 'faltan muestras o metricas'}")
        if completo and not valido:
            raise ValueError("El firmware termino sin entregar todas las muestras y metricas")


def abrir_sesion(ruta):
    """Valida metadatos, integridad y longitudes antes de ofrecer reproduccion."""
    ruta = Path(ruta).resolve()
    metadatos = json.loads((ruta / "sesion.json").read_text(encoding="utf-8"))
    if metadatos.get("estado") != "completa" or metadatos.get("frecuencia_hz") != 16000:
        raise ValueError("La sesion no esta completa o tiene otro muestreo")
    for nombre in NOMBRES.values():
        archivo = ruta / f"{nombre}.wav"
        if hashlib.sha256(archivo.read_bytes()).hexdigest() != metadatos["sha256"][nombre]:
            raise ValueError(f"El archivo {nombre} cambio desde la captura")
        with wave.open(str(archivo), "rb") as audio:
            if (audio.getnchannels(), audio.getsampwidth(), audio.getframerate(), audio.getnframes()) != (
                    1, 2, 16000, metadatos["muestras"]):
                raise ValueError("WAV incompatible")
    return ruta, metadatos


# Guarda observaciones fuera de los metadatos y WAV que identifican la medicion original.
def anotar_sesion(ruta, texto):
    """Agrega una nota fechada, sin modificar hashes, metricas ni resultados ESP32."""
    ruta, _ = abrir_sesion(ruta)
    texto = texto.strip()
    if not texto or len(texto) > 2000:
        raise ValueError("Escriba una nota de 1 a 2000 caracteres")
    with (ruta / "notas.txt").open("a", encoding="utf-8") as archivo:
        archivo.write(f"{datetime.now(timezone.utc).isoformat()} {texto}\n")
    return ruta / "notas.txt"
