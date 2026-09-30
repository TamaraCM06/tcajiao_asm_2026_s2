"""
Radar acustico monostatico - chirp lineal + correlacion cruzada por FFT (ulab)
CircuitPython / Raspberry Pi Pico (RP2040)

Metodo (igual al original):  R[k] = IFFT{ conj(S[f]) * R[f] }
"""
import board
import pwmio
import analogio
import time
import gc
from array import array
from ulab import numpy as np

# ---------------- HARDWARE ----------------
pwm = pwmio.PWMOut(board.GP22, frequency=2000, duty_cycle=0, variable_frequency=True)
mic = analogio.AnalogIn(board.GP26)

# ---------------- PARAMETROS ----------------
CHIRP_F_INICIAL = 2000          # Hz
CHIRP_F_FINAL = 4500            # Hz
VELOCIDAD_SONIDO_M_S = 343.0    # ~20 C  (v = 331.3 + 0.606*T[C])
DUTY_ON = 32768

N_MUESTRAS = 1024               # potencia de 2 (baje memoria: 2048 -> 1024)
MUESTRAS_CHIRP = 256            # muestras durante las que suena el chirp

GUARDA_DIRECTO_S = 0.002        # ventana donde se busca el pico directo parlante->mic
GUARDA_ECO_S = 0.0015           # separacion minima entre pico directo y eco (~26 cm)
UMBRAL_DETECCION = 6.0          # pico / media de |corr|; ajustelo experimentalmente
PERIODO_MEDICION_S = 3.0
MOSTRAR_BARRA = False           # True = barra de nivel del microfono entre mediciones

# ---------------- BUFFERS (compactos) ----------------
BUFFER = array('H', [0] * N_MUESTRAS)

# Tabla de frecuencias del chirp. Se extiende a N_MUESTRAS repitiendo la rampa,
# asi el bucle de escucha ejecuta EXACTAMENTE el mismo trabajo por muestra que
# el bucle de emision (con duty=0 no suena) y el periodo de muestreo es uniforme.
_df = (CHIRP_F_FINAL - CHIRP_F_INICIAL) / MUESTRAS_CHIRP
TABLA_F = array('H', [int(CHIRP_F_INICIAL + (i % MUESTRAS_CHIRP) * _df)
                      for i in range(N_MUESTRAS)])


def adquirir(emitir=True):
    """Emite el chirp y captura N_MUESTRAS con el ADC. Mismo costo por muestra en ambas fases."""
    buf = BUFFER
    tabla = TABLA_F
    p = pwm
    adc = mic
    m = MUESTRAS_CHIRP

    p.frequency = tabla[0]
    if emitir:
        p.duty_cycle = DUTY_ON
    for i in range(m):                  # fase 1: chirp sonando
        p.frequency = tabla[i]
        buf[i] = adc.value
    p.duty_cycle = 0
    for i in range(m, N_MUESTRAS):      # fase 2: solo escucha
        p.frequency = tabla[i]
        buf[i] = adc.value


def calibrar_fs(repeticiones=20):
    """
    Fs real = muestras totales / tiempo total, promediando muchas capturas SILENCIOSAS.
    (time.monotonic() tiene ~1 ms de resolucion; medir una sola captura da error de ~2 %.)
    """
    adquirir(emitir=False)
    t0 = time.monotonic_ns()
    for _ in range(repeticiones):
        adquirir(emitir=False)
    dt = (time.monotonic_ns() - t0) / 1e9
    return repeticiones * N_MUESTRAS / dt


def generar_referencia(N, fs, m, f0, f1):
    """Chirp lineal ideal (con ventana Hann para bajar lobulos laterales) -> conj(FFT)."""
    T = m / fs
    n = np.arange(m)
    t = n / fs
    f_t = t * ((f1 - f0) / (2 * T)) + f0          # f(t)=f0 + k*t/2 -> fase = 2*pi*f(t)*t
    patron = np.sin(t * f_t * (2 * np.pi))
    w = np.sin(n * (np.pi / (m - 1)))
    patron = patron * (w * w)
    s = np.zeros(N)
    s[:m] = patron
    S_re, S_im = np.fft.fft(s)
    return S_re, -S_im                            # conjugado


def correlacion_por_fft(r, fs, S_re, S_im):
    """Correlacion cruzada por FFT. Devuelve (tof_s, dist_cm, razon_pico) o None."""
    N = len(r)
    r -= np.mean(r)                               # quitar offset DC (in-place)

    R_re, R_im = np.fft.fft(r)
    prod_re = S_re * R_re - S_im * R_im           # conj(S) * R
    prod_im = S_re * R_im + S_im * R_re
    del R_re, R_im
    corr, _im = np.fft.ifft(prod_re, prod_im)
    del prod_re, prod_im, _im
    gc.collect()

    c = np.sqrt(corr * corr)                      # |corr| (esta build de ulab no trae np.abs)
    del corr

    # 1) Pico directo (parlante -> microfono): referencia de tiempo cero
    n_dir = int(GUARDA_DIRECTO_S * fs)
    idx_dir = int(np.argmax(c[:n_dir]))

    # 2) Eco: se busca DESPUES del pico directo + guarda (el eco puede solaparse con el chirp)
    ini = idx_dir + int(GUARDA_ECO_S * fs)
    fin = N - MUESTRAS_CHIRP // 2                 # evita el envolvimiento circular
    if ini >= fin:
        return None
    zona = c[ini:fin]
    idx_rel = int(np.argmax(zona))
    pico = float(zona[idx_rel])
    razon = pico / (float(np.mean(zona)) + 1e-9)

    idx_eco = ini + idx_rel
    tof = (idx_eco - idx_dir) / fs                # el indice de correlacion YA es el retardo
    dist_cm = (VELOCIDAD_SONIDO_M_S * tof / 2.0) * 100.0
    return tof, dist_cm, razon


def medir():
    gc.collect()
    adquirir(emitir=True)
    r = np.array(BUFFER, dtype=np.float)
    res = correlacion_por_fft(r, FS, S_RE, S_IM)
    del r
    gc.collect()

    if res is None:
        print("Ventana de busqueda vacia")
        return
    tof, dist_cm, razon = res
    if razon < UMBRAL_DETECCION:
        print("Sin eco confiable (razon pico/media = %.1f < %.1f)" % (razon, UMBRAL_DETECCION))
    else:
        print("ToF = %.2f ms | Distancia = %.1f cm | razon = %.1f" % (tof * 1000, dist_cm, razon))


def esperar(seg):
    fin = time.monotonic() + seg
    vmax, vmin = 0, 65535
    ult = time.monotonic()
    while time.monotonic() < fin:
        if MOSTRAR_BARRA:
            v = mic.value
            vmax = max(vmax, v)
            vmin = min(vmin, v)
            if time.monotonic() - ult >= 0.066:
                print("█" * min(int((vmax - vmin) / 500), 50) or "▏")
                vmax, vmin, ult = 0, 65535, time.monotonic()
        time.sleep(0.001)


# ---------------- INICIALIZACION ----------------
print("Calibrando Fs...")
FS = calibrar_fs()
S_RE, S_IM = generar_referencia(N_MUESTRAS, FS, MUESTRAS_CHIRP, CHIRP_F_INICIAL, CHIRP_F_FINAL)
gc.collect()

B = CHIRP_F_FINAL - CHIRP_F_INICIAL
T_CHIRP = MUESTRAS_CHIRP / FS
print("=== Radar acustico (chirp + correlacion por FFT) ===")
print("Chirp: %d -> %d Hz | B = %d Hz | T = %.2f ms | T*B = %.1f" % (CHIRP_F_INICIAL, CHIRP_F_FINAL, B, T_CHIRP * 1000, T_CHIRP * B))
print("Fs = %d Hz | Nyquist = %d Hz | Fs/f_max = %.1f" % (FS, FS / 2, FS / CHIRP_F_FINAL))
if FS / 2 < CHIRP_F_FINAL:
    print("ADVERTENCIA: aliasing (Fs/2 < f_max)")
print("Resolucion en distancia ~ c/(2B) = %.1f cm" % (VELOCIDAD_SONIDO_M_S / (2 * B) * 100))
print("Distancia minima ~ %.0f cm | maxima ~ %.0f cm" % (
    VELOCIDAD_SONIDO_M_S * GUARDA_ECO_S / 2 * 100,
    VELOCIDAD_SONIDO_M_S * ((N_MUESTRAS - MUESTRAS_CHIRP // 2) / FS) / 2 * 100))

esperar(3.0)
while True:
    medir()
    esperar(PERIODO_MEDICION_S)
