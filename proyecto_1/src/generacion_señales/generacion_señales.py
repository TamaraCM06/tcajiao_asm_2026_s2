import numpy as np
import matplotlib.pyplot as plt

def generar_secuencia_pulsos(Fs, duracion, f_corte, n_pulsos):
    """
    Genera una secuencia de pulsos senoidales modulados en amplitud.
    
    Parametros:
        Fs: Frecuencia de muestreo en Hz. (Audio)
        duracion: Ventana total de tiempo en segundos.
        f_corte: Frecuencia de la portadora del pulso (Hz).
        n_pulsos: Cantidad de pulsos dentro de la ventana.
        
    Retorna:
        t: Vector de tiempo.
        s_t: Señal de secuencia de pulsos original.
    """
    N = int(Fs * duracion)
    t = np.linspace(0, duracion, N, endpoint=False)
    
    # Envolvente rectangular para crear pulsos
    envolvente = np.zeros(N)
    ancho_pulso = N // (2 * n_pulsos)
    
    for i in range(n_pulsos):
        inicio = i * (N // n_pulsos)
        envolvente[inicio : inicio + ancho_pulso] = 1.0
        
    # Señal senoidal modulada por la envolvente de pulsos
    s_t = envolvente * np.sin(2 * np.pi * f_corte * t)
    return t, s_t


def generar_chirp(Fs, duracion, f0, f1):
    """
    Genera un chirp de frecuencia barrida linealmente desde f0 hasta f1.
    
    Parametros:
        Fs: Frecuencia de muestreo en Hz. (Audio)
        duracion: Duracion total del barrido en segundos.
        f0: Frecuencia inicial en Hz.
        f1: Frecuencia final en Hz.
        
    Retorna:
        t: Vector de tiempo.
        s_t: Señal chirp original.
    """
    N = int(Fs * duracion)
    t = np.linspace(0, duracion, N, endpoint=False)
    
    # Tasa de variación de frecuencia (k)
    k = (f1 - f0) / duracion
    
    # Fase instantánea
    fase = 2 * np.pi * (f0 * t + 0.5 * k * (t**2))
    s_t = np.sin(fase)
    return t, s_t


def simular_canal_recepcion(t, s_t, Fs=44100, retardo_ms=4.0, nivel_ruido=0.4):
    """
    Uso unicamente en experimentos, no en aplicacion fisica.
    Simula el canal de transmisión (aire) sumando atenuación, retardo y ruido blanco.
    
    Parametros:
        t: Vector de tiempo.
        s_t: Señal emitida limpia.
        Fs: Frecuencia de muestreo en Hz.
        retardo_ms: Tiempo de vuelo del eco en milisegundos.
        nivel_ruido: Amplitud del ruido blanco ambiental.
        
    Retorna:
        ruido: Señal de ruido aleatorio generada.
        r_t: Señal recibida final (Eco + Ruido).
    """
    N = len(s_t)
    muestras_retardo = int((retardo_ms / 1000.0) * Fs)
    
    # Retardo del eco
    s_retardada = np.roll(s_t, muestras_retardo)
    s_retardada[:muestras_retardo] = 0.0
    
    # Generación de ruido blanco gaussiano
    ruido = nivel_ruido * np.random.normal(size=N)
    
    # Señal recibida: Eco atenuado al 60% (alterable para experimentos) + Ruido
    r_t = (0.6 * s_retardada) + ruido
    return ruido, r_t


# Comparación de chirp y secuencia de pulsos
if __name__ == "__main__":
    Fs = 44100
    duracion = 0.02 # 20 ms
    
    t, pulso_s = generar_secuencia_pulsos(Fs, duracion, 1000, 3)
    _, chirp_s = generar_chirp(Fs, duracion, 500, 4000)
    
    fig, axs = plt.subplots(2, 1, figsize=(10, 6))
    fig.suptitle("Comparación: Secuencia de Pulsos vs. Chirp", fontsize=14)
    
    axs[0].plot(t * 1000, pulso_s, color='darkblue')
    axs[0].set_title("1. Secuencia de Pulsos Senoidales (Frecuencia Fija)")
    axs[0].set_xlabel("Tiempo [ms]")
    axs[0].set_ylabel("Amplitud")
    axs[0].grid(True)
    
    axs[1].plot(t * 1000, chirp_s, color='darkgreen')
    axs[1].set_title("2. Chirp Frecuencial (Barrido Lineal de Frecuencia)")
    axs[1].set_xlabel("Tiempo [ms]")
    axs[1].set_ylabel("Amplitud")
    axs[1].grid(True)
    
    plt.tight_layout()
    plt.savefig("comparacion_pulsos_vs_chirp.png")
    plt.show()