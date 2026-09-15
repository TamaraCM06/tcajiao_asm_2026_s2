import numpy as np
from cmath import exp, pi
import matplotlib.pyplot as plt
import time
import sys
import os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from generacion_señales.generacion_señales import (
    generar_secuencia_pulsos,
    generar_chirp,
    simular_canal_recepcion
)

# Algoritmos DFT y FFT
def dft(x):
    # Calcula la Transformada Discreta de Fourier de forma directa O(N^2).
    N = len(x)
    n = np.arange(N)
    k = n.reshape((N, 1))
    e = np.exp(-1j * ((2 * np.pi) / N) * k * n)
    return np.dot(e, x)

def fft(x):
    """
    Algoritmo de Transformada Rápida de Fourier (FFT) recursivo Cooley-Tukey.
    Basado en la especificación de Rosetta Code.
    Complejidad: O(N log N)
    """
    N = len(x)
    
    if N <= 1:
        return x
    
    if N % 2 != 0:
        raise ValueError("El tamaño de la señal (N) debe ser una potencia de 2.")
    
    even = fft(x[0::2])
    odd  = fft(x[1::2])
    
    T = [exp(-2j * pi * k / N) * odd[k] for k in range(N // 2)]
    
    return [even[k] + T[k] for k in range(N // 2)] + \
           [even[k] - T[k] for k in range(N // 2)]

# Insertar datos de prueba y ejecutar análisis
def ejecutar_analisis_fourier(tipo_senal="chirp"):
    Fs = 44100
    duracion = 0.02  # 20 ms
    
    # 1. Seleccionar la señal original a transmitir
    if tipo_senal == "chirp":
        t, s_t = generar_chirp(Fs, duracion, 1000, 5000)
        titulo_tipo = "Chirp Frecuencial (1 kHz a 5 kHz)"
    else:
        t, s_t = generar_secuencia_pulsos(Fs, duracion, 2000, 3)
        titulo_tipo = "Secuencia de Pulsos (2 kHz)"
        
    # 2. Simular recepción con ruido y eco
    ruido, r_t = simular_canal_recepcion(t, s_t, Fs, 4.0, 0.4)
    N_original = len(t)
    
    # Zero-Padding a la siguiente potencia de 2 (882 -> 1024) (FFT requiere potencia de 2)
    N_fft = 2**int(np.ceil(np.log2(N_original)))
    s_t_padded = np.pad(s_t, (0, N_fft - N_original), mode='constant')
    r_t_padded = np.pad(r_t, (0, N_fft - N_original), mode='constant')
    
    # 3. FFT sobre los vectores con Zero-Padding
    S_f = fft(s_t_padded)
    R_f = fft(r_t_padded)

    # 4. Preparar frecuencias y magnitudes para graficar
    frecuencias = np.fft.fftfreq(N_fft, 1/Fs)
    mitad = N_fft // 2
    frec_pos = frecuencias[:mitad]
    
    # Magnitudes y Fases normalizadas
    mag_S = (2.0 / N_original) * np.abs(S_f[:mitad])
    mag_R = (2.0 / N_original) * np.abs(R_f[:mitad])
    fase_S = np.angle(S_f[:mitad])
    fase_R = np.angle(R_f[:mitad])

    # =========================================================
    # VENTANA 1: CARACTERIZACIÓN DE LA SEÑAL TRANSMITIDA Y RUIDO
    # =========================================================
    fig1, axs1 = plt.subplots(2, 2, figsize=(12, 8))
    fig1.suptitle(f"Ventana 1: Señal Transmitida Original y Ruido Blanco — ({titulo_tipo})", fontsize=13)

    # 1. Señal Transmitida
    axs1[0, 0].plot(t * 1000, s_t, color='blue')
    axs1[0, 0].set_title("1. Señal Transmitida s(t) [Original]")
    axs1[0, 0].set_xlabel("Tiempo [ms]")
    axs1[0, 0].set_ylabel("Amplitud")
    axs1[0, 0].grid(True)

    # 2. Ruido Ambiental Aislado
    axs1[0, 1].plot(t * 1000, ruido, color='gray', alpha=0.7)
    axs1[0, 1].set_title("2. Componente de Ruido Blanco Ambiental")
    axs1[0, 1].set_xlabel("Tiempo [ms]")
    axs1[0, 1].set_ylabel("Amplitud")
    axs1[0, 1].grid(True)

    # 3. Espectro de Magnitud Original
    axs1[1, 0].plot(frec_pos, mag_S, color='blue')
    axs1[1, 0].set_title("3. Espectro de Magnitud |S(f)| Original")
    axs1[1, 0].set_xlabel("Frecuencia [Hz]")
    axs1[1, 0].set_ylabel("Magnitud")
    axs1[1, 0].set_xlim([0, 8000])
    axs1[1, 0].grid(True)

    # 4. Espectro de Fase Original
    axs1[1, 1].plot(frec_pos, fase_S, color='navy')
    axs1[1, 1].set_title("4. Espectro de Fase ∠S(f) Original")
    axs1[1, 1].set_xlabel("Frecuencia [Hz]")
    axs1[1, 1].set_ylabel("Fase [rad]")
    axs1[1, 1].set_xlim([0, 8000])
    axs1[1, 1].grid(True)

    plt.tight_layout()
    plt.savefig(f"ventana1_original_{tipo_senal}.png")

    # =========================================================
    # VENTANA 2: ANÁLISIS DE LA SEÑAL RECIBIDA (ECO + RUIDO)
    # =========================================================
    fig2, axs2 = plt.subplots(2, 2, figsize=(12, 8))
    fig2.suptitle(f"Ventana 2: Señal Recibida en el Micrófono — ({titulo_tipo})", fontsize=13)

    # 1. Comparación Temporal (Original vs Recibida)
    axs2[0, 0].plot(t * 1000, s_t, color='blue', alpha=0.4, label="s(t) Original")
    axs2[0, 0].set_title("1. Señal Transmitida s(t) [Original]")
    axs2[0, 0].set_xlabel("Tiempo [ms]")
    axs2[0, 0].set_ylabel("Amplitud")
    axs2[0, 0].legend(loc="upper right")
    axs2[0, 0].grid(True)

    # 2. Señal Recibida Aislada
    axs2[0, 1].plot(t * 1000, r_t, color='red', alpha=0.85)
    axs2[0, 1].set_title("2. Señal Recibida r(t) [Eco Retardado + Ruido]")
    axs2[0, 1].set_xlabel("Tiempo [ms]")
    axs2[0, 1].set_ylabel("Amplitud")
    axs2[0, 1].grid(True)

    # 3. Espectro de Magnitud Recibida
    axs2[1, 0].plot(frec_pos, mag_R, color='crimson')
    axs2[1, 0].set_title("3. Espectro de Magnitud |R(f)| Recibida")
    axs2[1, 0].set_xlabel("Frecuencia [Hz]")
    axs2[1, 0].set_ylabel("Magnitud")
    axs2[1, 0].set_xlim([0, 8000])
    axs2[1, 0].grid(True)

    # 4. Espectro de Fase Recibida
    axs2[1, 1].plot(frec_pos, fase_R, color='darkgreen')
    axs2[1, 1].set_title("4. Espectro de Fase ∠R(f) Recibida")
    axs2[1, 1].set_xlabel("Frecuencia [Hz]")
    axs2[1, 1].set_ylabel("Fase [rad]")
    axs2[1, 1].set_xlim([0, 8000])
    axs2[1, 1].grid(True)

    plt.tight_layout()
    plt.savefig(f"ventana2_recibida_{tipo_senal}.png")
    
    # Mostrar ventanas de señal
    plt.show()

# Comparación de tiempos de ejecución entre DFT y FFT
def comparar_tiempos_ejecucion():
    tamanos_N = [2**k for k in range(4, 11)] # N = 16 a 1024
    t_dft_list, t_fft_list = [], []
    num_repeticiones = 5 # Promedio de corridas

    print(f"\n{'N (Muestras)':<12} | {'DFT Manual (s)':<18} | {'FFT Rosetta (s)':<18}")
    print("-" * 52)

    for N in tamanos_N:
        t_dft_acum, t_fft_acum = 0.0, 0.0

        for _ in range(num_repeticiones):
            x = np.random.randn(N)

            t0 = time.perf_counter()
            _ = dft(x)
            t_dft_acum += (time.perf_counter() - t0)

            t0 = time.perf_counter()
            _ = fft(x)
            t_fft_acum += (time.perf_counter() - t0)

        t_dft_prom = t_dft_acum / num_repeticiones
        t_fft_prom = t_fft_acum / num_repeticiones

        t_dft_list.append(t_dft_prom)
        t_fft_list.append(t_fft_prom)

        print(f"{N:<12} | {t_dft_prom:<18.6f} | {t_fft_prom:<18.6f}")

    # =========================================================
    # VENTANA 3: GRÁFICA COMPARATIVA DE TIEMPOS DE EJECUCIÓN
    # =========================================================
    plt.figure(figsize=(8, 4.5))
    plt.plot(tamanos_N, t_dft_list, 'o-', label='DFT Directa $O(N^2)$', color='crimson')
    plt.plot(tamanos_N, t_fft_list, 's-', label='FFT Rosetta $O(N \\log N)$', color='navy')
    plt.yscale('log')
    plt.xlabel('Número de Muestras (N)')
    plt.ylabel('Tiempo de Ejecución Promedio [s] (Escala Log)')
    plt.title('Ventana 3: Comparación de Tiempo de Ejecución (DFT Directa vs FFT Rosetta)')
    plt.grid(True, which="both", ls="--")
    plt.legend()
    plt.tight_layout()
    plt.savefig("ventana3_comparacion_tiempos.png")
    plt.show()

if __name__ == "__main__":
    ejecutar_analisis_fourier(tipo_senal="chirp")
    comparar_tiempos_ejecucion()