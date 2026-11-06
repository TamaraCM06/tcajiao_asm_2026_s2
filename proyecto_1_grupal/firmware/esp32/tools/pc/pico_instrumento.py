"""Capturas ADC1 durante una reproduccion; todo el DSP principal permanece en ESP32."""
import csv
import threading
import time

from herramientas.capturas_pico import LectorPico


def abrir_pico(nombre=None):
    """Abre una unica Pico identificada por USB; no cambia los pines ni reinicia el ADC."""
    import serial
    from serial.tools import list_ports
    if nombre is None:
        candidatos = [puerto.device for puerto in list_ports.comports() if puerto.vid == 0x2E8A and puerto.pid == 0x000A]
        if len(candidatos) != 1:
            raise ValueError("No se identifico una unica Pico; use --puerto-pico COMx al abrir la herramienta")
        nombre = candidatos[0]
    return serial.Serial(nombre, 115200, timeout=0.05, write_timeout=0.5)


def medir_punto(cliente, sesion_fuente, puerto_pico, ruta_csv, modelo):
    """Guarda bloques con indices locales; espera inicio DAC y descarta el transitorio inicial."""
    inicio_audio = threading.Event()
    resultado_audio, errores = [], []

    def reproducir():
        """Notifica inicio al primer bloque DAC aceptado y conserva cualquier fallo del transporte."""
        try:
            resultado_audio.append(cliente.reproducir(sesion_fuente, "entrada", 1, al_iniciar=inicio_audio.set))
        except Exception as error:
            errores.append(error)

    puerto_pico.reset_input_buffer()
    lector = LectorPico(puerto_pico)
    tarea = threading.Thread(target=reproducir, daemon=True)
    tarea.start()
    capturas = []
    try:
        limite = time.monotonic() + 15
        while not inicio_audio.wait(0.05):
            if errores:
                raise RuntimeError(f"No inicio la reproduccion: {errores[0]}")
            if time.monotonic() > limite:
                raise TimeoutError("No se confirmo el arranque del DAC")
        time.sleep(modelo["espera_estabilizacion_s"])
        campos = ["captura", "bloque_adc", "indice_en_bloque", "tiempo_en_bloque_s", "codigo_adc",
                  "voltaje_v", "frecuencia_muestreo_hz", "vref_v", "perdidos", "errores", "reinicios"]
        with ruta_csv.open("w", encoding="utf-8", newline="") as archivo:
            escritor = csv.DictWriter(archivo, fieldnames=campos)
            escritor.writeheader()
            proxima = time.monotonic()
            for numero in range(modelo["capturas_por_punto"]):
                if errores or not tarea.is_alive():
                    raise RuntimeError("La reproduccion termino antes de completar las mediciones")
                time.sleep(max(0, proxima - time.monotonic()))
                captura = lector.solicitar()
                capturas.append(captura)
                for indice, (codigo, voltaje) in enumerate(zip(captura.codigos, captura.voltios)):
                    escritor.writerow(dict(captura=numero, bloque_adc=captura.bloque, indice_en_bloque=indice,
                        tiempo_en_bloque_s=indice / captura.fs, codigo_adc=codigo, voltaje_v=voltaje,
                        frecuencia_muestreo_hz=captura.fs, vref_v=captura.vref, perdidos=captura.perdidos,
                        errores=captura.errores, reinicios=captura.reinicios))
                archivo.flush()
                proxima = time.monotonic() + modelo["intervalo_capturas_s"]
        tarea.join(timeout=10)
        if tarea.is_alive() or errores or not resultado_audio:
            raise RuntimeError(f"No se completo la reproduccion: {errores[0] if errores else 'sin confirmacion DAC'}")
        if resultado_audio[0].get("recortes_dac", 0):
            raise ValueError("Hubo recortes DAC; la comparacion analogica no es valida")
        return capturas, resultado_audio[0]
    except BaseException:
        try:
            cliente.cancelar()
        except (OSError, RuntimeError):
            pass
        tarea.join(timeout=4)
        raise
    finally:
        try:
            puerto_pico.write(b"t")
        except OSError:
            pass
