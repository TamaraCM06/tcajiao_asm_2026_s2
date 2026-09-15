import numpy as np
import matplotlib.pyplot as plt
import time
import sys
import os

os.makedirs("outputs/ecos", exist_ok=True)

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from generacion_señales.generacion_señales import (
    generar_secuencia_pulsos,
    generar_chirp
)
from fft_dft.experimentos_fft import fft, ifft

# =========================================================
# CASO DE PRUEBA ANALIZADO
# Definido una sola vez y compartido por el experimento de detección y por la
# comparación de tiempos, de modo que ambos reporten siempre el mismo escenario.
#
# Se simulan dos reflexiones porque el haz acústico no viaja como un rayo: se
# abre al propagarse, de modo que una parte de la señal choca contra el objeto
# de interés y otra lo pasa de largo y rebota en la superficie que haya detrás.
# Ambas regresan al micrófono con retardos distintos y se superponen, que es el
# escenario que la correlación debe resolver.
# =========================================================
FS = 44100
DURACION_EMITIDA = 0.02    # 20 ms de señal transmitida
RETARDOS_MS = (4.0, 9.0)   # Retardos conocidos: objeto y superficie posterior
ATENUACIONES = (0.6, 0.3)  # El eco lejano regresa más débil
NIVEL_RUIDO = 0.4          # Amplitud del ruido blanco ambiental

# Generación de la señal recibida con ecos de retardo conocido
def simular_canal_ecos(s_t, Fs, retardos_ms, atenuaciones, nivel_ruido):
    """
    Uso unicamente en experimentos, no en aplicacion fisica.
    Construye la señal recibida r(t) superponiendo una copia retardada y
    atenuada de la señal emitida por cada reflexión, más ruido blanco ambiental.
    Los ecos se suman entre sí porque el medio se modela como un sistema LTI.

    Parametros:
        s_t: Señal emitida limpia.
        Fs: Frecuencia de muestreo en Hz.
        retardos_ms: Retardos conocidos de cada eco, en milisegundos.
        atenuaciones: Amplitud relativa de cada eco (0 a 1).
        nivel_ruido: Amplitud del ruido blanco ambiental.

    Retorna:
        t_captura: Vector de tiempo de la ventana de recepción.
        r_t: Señal recibida final (Ecos + Ruido).
    """
    # La ventana de recepción debe alcanzar a contener el eco más tardío completo
    duracion_captura = (max(retardos_ms) / 1000.0) + (len(s_t) / Fs)
    N_captura = int(Fs * duracion_captura)
    t_captura = np.linspace(0, duracion_captura, N_captura, endpoint=False)

    r_t = np.zeros(N_captura)

    for retardo_ms, atenuacion in zip(retardos_ms, atenuaciones):
        muestras_retardo = int(round((retardo_ms / 1000.0) * Fs))

        # El eco se suma (no reemplaza): varias reflexiones que coinciden en el
        # tiempo se superponen sobre el micrófono
        fin = min(muestras_retardo + len(s_t), N_captura)
        r_t[muestras_retardo:fin] += atenuacion * s_t[:fin - muestras_retardo]

    # Generación de ruido blanco gaussiano sobre toda la ventana
    r_t = r_t + nivel_ruido * np.random.normal(size=N_captura)

    return t_captura, r_t

# Correlación cruzada en el dominio del tiempo (implementación directa)
def correlacion_directa(s, r):
    """
    Correlación cruzada evaluada segun su definición: R[k] = sum_n s[n]*r[n+k].
    Para cada uno de los N+M-1 desplazamientos se desliza s sobre r y se acumula
    el producto con un ciclo explícito, de modo que el costo O(N*M) quede
    expuesto y no lo oculte una rutina vectorizada.

    Parametros:
        s: Señal emitida (referencia).
        r: Señal recibida.

    Retorna:
        lags: Vector de desplazamientos evaluados, en muestras.
        corr: Correlación asociada a cada desplazamiento.
    """
    N, M = len(s), len(r)
    lags = np.arange(-(N - 1), M)
    corr = np.zeros(len(lags))

    for i, k in enumerate(lags):
        acumulador = 0.0
        if k >= 0:
            n_max = min(N, M - k)
            for n in range(n_max):
                acumulador += s[n] * r[n + k]
        else:
            m0 = -k
            n_max = min(N - m0, M)
            for n in range(n_max):
                acumulador += s[m0 + n] * r[n]
        corr[i] = acumulador

    return lags, corr

# Correlación cruzada en el dominio de la frecuencia (vía FFT)
def correlacion_fft(s, r):
    """
    Correlación cruzada calculada con la relación entre convolución y producto
    en frecuencia: convolucionar (o correlacionar) en el tiempo equivale a
    multiplicar los espectros, conjugando uno de ellos para que el sentido del
    desplazamiento corresponda a una correlación.
        R[k] = IFFT{ conj(S[f]) * R[f] }
    El producto resuelve todos los desplazamientos a la vez y la IFFT los
    devuelve al tiempo, donde el pico ya es legible como retardo.

    Se aplica Zero-Padding a la siguiente potencia de 2 mayor o igual a N+M-1:
    la cota N+M-1 evita que la correlación circular de la FFT solape los
    extremos, y la potencia de 2 es requisito del algoritmo Radix-2.
    Complejidad: O(N log N).

    Parametros:
        s: Señal emitida (referencia).
        r: Señal recibida.

    Retorna:
        lags: Vector de desplazamientos evaluados, en muestras.
        corr: Correlación asociada a cada desplazamiento.
    """
    N, M = len(s), len(r)
    N_fft = 1 << (N + M - 2).bit_length()

    s_padded = np.pad(s, (0, N_fft - N), mode='constant')
    r_padded = np.pad(r, (0, N_fft - M), mode='constant')

    S_f = np.array(fft(s_padded))
    R_f = np.array(fft(r_padded))

    corr_circular = np.real(ifft(np.conjugate(S_f) * R_f))

    # Reordenamiento de la salida circular al eje de desplazamientos lineal
    lags = np.arange(-(N - 1), M)
    corr = corr_circular[lags % N_fft]

    return lags, corr

# Estimación del retardo a partir de los picos de correlación
def estimar_retardos(lags, corr, Fs, n_ecos):
    """
    Localiza los n_ecos máximos de la correlación y los traduce a retardos.
    Solo se consideran desplazamientos no negativos, ya que un eco nunca puede
    llegar antes de haberse emitido la señal. Tras aceptar un pico se silencia
    su vecindad para que el siguiente corresponda a otro eco y no al mismo
    lóbulo principal.

    Parametros:
        lags: Vector de desplazamientos, en muestras.
        corr: Correlación asociada a cada desplazamiento.
        Fs: Frecuencia de muestreo en Hz.
        n_ecos: Cantidad de ecos que se desea detectar.

    Retorna:
        retardos_ms: Retardos estimados en milisegundos, ordenados.
    """
    validos = lags >= 0
    lags_validos = lags[validos]
    corr_trabajo = corr[validos].astype(float).copy()

    vecindad = int(0.001 * Fs)  # 1 ms alrededor del pico aceptado
    retardos_ms = []

    for _ in range(n_ecos):
        idx = int(np.argmax(corr_trabajo))
        retardos_ms.append(int(lags_validos[idx]) / Fs * 1000.0)
        corr_trabajo[max(0, idx - vecindad): idx + vecindad + 1] = -np.inf

    return sorted(retardos_ms)

# Insertar datos de prueba y ejecutar análisis
def ejecutar_deteccion_ecos(tipo_senal="chirp"):
    Fs = FS
    duracion = DURACION_EMITIDA
    retardos_ms = RETARDOS_MS
    atenuaciones = ATENUACIONES
    nivel_ruido = NIVEL_RUIDO

    # 1. Seleccionar la señal conocida a transmitir
    if tipo_senal == "chirp":
        t, s_t = generar_chirp(Fs, duracion, 1000, 5000)
        titulo_tipo = "Chirp Frecuencial (1 kHz a 5 kHz)"
    else:
        t, s_t = generar_secuencia_pulsos(Fs, duracion, 2000, 3)
        titulo_tipo = "Secuencia de Pulsos (2 kHz)"

    # 2. Simular la recepción con ecos de retardo conocido y ruido
    t_captura, r_t = simular_canal_ecos(s_t, Fs, retardos_ms, atenuaciones, nivel_ruido)

    # 3. Correlación en el dominio del tiempo (implementación directa)
    t0 = time.perf_counter()
    lags, corr_dir = correlacion_directa(s_t, r_t)
    t_directa = time.perf_counter() - t0
    estimados_dir = estimar_retardos(lags, corr_dir, Fs, len(retardos_ms))

    # 4. Correlación en el dominio de la frecuencia (vía FFT)
    t0 = time.perf_counter()
    lags, corr_fft = correlacion_fft(s_t, r_t)
    t_fft = time.perf_counter() - t0
    estimados_fft = estimar_retardos(lags, corr_fft, Fs, len(retardos_ms))

    # 5. Comparación entre ambas implementaciones
    print(f"\n=== Detección de Ecos — {titulo_tipo} ===")
    print(f"Retardos recuperados de una única señal con {len(retardos_ms)} ecos superpuestos:\n")
    print(f"{'Eco':<6} | {'Retardo real (ms)':<18} | {'Directa (ms)':<14} | "
          f"{'FFT (ms)':<12} | {'Error (ms)':<11}")
    print("-" * 74)
    for i, (real, est_dir, est_fft) in enumerate(zip(retardos_ms, estimados_dir, estimados_fft), 1):
        print(f"{i:<6} | {real:<18.3f} | {est_dir:<14.3f} | {est_fft:<12.3f} | "
              f"{abs(est_dir - real):<11.3f}")

    # Eje 1 de la comparación: ambas implementaciones deben dar el mismo resultado
    diferencia = np.max(np.abs(corr_dir - corr_fft))
    escala = np.max(np.abs(corr_dir))
    print(f"\n--- Comparación: implementación directa vs implementación vía FFT ---")
    print(f"¿Entregan el mismo resultado?")
    print(f"    Diferencia máxima entre ambas curvas : {diferencia:.2e}")
    print(f"    Altura del pico de correlación       : {escala:.2f}")
    print(f"    Diferencia relativa                  : {diferencia/escala:.1e}  "
          f"-> equivalentes (solo redondeo de punto flotante)")

    # Eje 2 de la comparación: el costo de obtener ese mismo resultado
    print(f"\n¿Cuál es más eficiente?")
    print(f"    Directa O(N^2)      : {t_directa*1000:8.1f} ms")
    print(f"    Vía FFT O(N log N)  : {t_fft*1000:8.1f} ms")
    print(f"    La FFT es {t_directa/t_fft:.1f} veces más rápida "
          f"(ahorra {(1 - t_fft/t_directa)*100:.1f}% del tiempo)")

    # =========================================================
    # VENTANA 4: SEÑAL EMITIDA Y SEÑAL RECIBIDA CON ECOS
    # =========================================================
    fig4, axs4 = plt.subplots(1, 2, figsize=(12, 4.5))
    fig4.suptitle(f"Ventana 4: Señal Emitida y Señal Recibida — ({titulo_tipo})", fontsize=13)

    # 1. Señal Emitida
    axs4[0].plot(t * 1000, s_t, color='blue')
    axs4[0].set_title("1. Señal Emitida s(t)")
    axs4[0].set_xlabel("Tiempo [ms]")
    axs4[0].set_ylabel("Amplitud")
    axs4[0].grid(True)

    # 2. Señal Recibida: los ecos quedan enmascarados por el ruido
    axs4[1].plot(t_captura * 1000, r_t, color='red', alpha=0.85)
    for retardo_ms in retardos_ms:
        axs4[1].axvline(retardo_ms, color='k', ls='--', lw=1)
    axs4[1].set_title("2. Señal Recibida r(t) [Ecos + Ruido]")
    axs4[1].set_xlabel("Tiempo [ms]")
    axs4[1].set_ylabel("Amplitud")
    axs4[1].grid(True)

    plt.tight_layout()
    plt.savefig(f"outputs/ecos/ventana4_senales_{tipo_senal}.png")

    # =========================================================
    # VENTANA 5: CORRELACIÓN DIRECTA VS CORRELACIÓN VÍA FFT
    # =========================================================
    fig5, axs5 = plt.subplots(1, 2, figsize=(12, 4.5))
    fig5.suptitle(f"Ventana 5: Correlación Directa vs vía FFT — ({titulo_tipo})", fontsize=13)

    lags_ms = lags / Fs * 1000

    # 1. Correlación Directa con los picos detectados
    axs5[0].plot(lags_ms, corr_dir, color='crimson')
    for retardo_ms in estimados_dir:
        axs5[0].axvline(retardo_ms, color='k', ls='--', lw=1, label=f"pico = {retardo_ms:.2f} ms")
    axs5[0].set_title(f"1. Correlación Directa — {t_directa*1000:.1f} ms de cómputo")
    axs5[0].set_xlabel("Retardo [ms]")
    axs5[0].set_ylabel("Correlación")
    axs5[0].legend(loc="upper right", fontsize=8)
    axs5[0].grid(True)

    # 2. Correlación vía FFT con los picos detectados
    axs5[1].plot(lags_ms, corr_fft, color='navy')
    for retardo_ms in estimados_fft:
        axs5[1].axvline(retardo_ms, color='k', ls='--', lw=1, label=f"pico = {retardo_ms:.2f} ms")
    axs5[1].set_title(f"2. Correlación vía FFT — {t_fft*1000:.1f} ms de cómputo")
    axs5[1].set_xlabel("Retardo [ms]")
    axs5[1].set_ylabel("Correlación")
    axs5[1].legend(loc="upper right", fontsize=8)
    axs5[1].grid(True)

    plt.tight_layout()
    plt.savefig(f"outputs/ecos/ventana5_correlaciones_{tipo_senal}.png")

    # Se devuelven los tiempos medidos para que la comparación de la Ventana 6
    # reutilice esta misma medición y no vuelva a cronometrar el mismo caso
    return t_directa, t_fft

# Comparación de tiempos de ejecución entre correlación directa y correlación vía FFT
def comparar_tiempos_correlacion(tipo_senal="chirp", tiempos_caso=None):
    """
    Compara el costo de ambas implementaciones sobre el mismo problema de
    detección de ecos, escalando la duración de la señal emitida. No se usan
    vectores aleatorios: en cada punto se genera la señal acústica real y su
    recepción con ecos y ruido, de modo que los tiempos correspondan al caso
    práctico del radar y no a un caso sintético.

    Al alargar la señal emitida crece también la ventana de captura, por lo que
    ambas señales de entrada a la correlación aumentan de tamaño.

    Este barrido mide únicamente costo computacional: cronometra las dos
    correlaciones y no evalúa la calidad de la detección. Por eso las duraciones
    mayores son válidas como puntos de medición aunque en un sistema monostático
    real no serían operables: mientras el parlante sigue emitiendo, el micrófono
    no puede registrar ecos limpios, lo que impone una distancia mínima medible
    de vs*T/2 (3.4 m para T = 20 ms). La simulación no modela ese acoplamiento
    directo entre transductores.
    """
    Fs = FS
    retardos_ms = RETARDOS_MS
    atenuaciones = ATENUACIONES
    nivel_ruido = NIVEL_RUIDO

    # El barrido se construye duplicando la duración a partir del caso analizado:
    # tres duplicaciones hacia abajo y una hacia arriba. Así una de las filas es
    # exactamente el experimento ya reportado y el resto son ese mismo caso con
    # la señal más corta o más larga, en vez de tamaños elegidos al azar.
    duracion_caso_ms = DURACION_EMITIDA * 1000
    duraciones_ms = [duracion_caso_ms * factor for factor in (0.125, 0.25, 0.5, 1, 2)]

    tamanos_N, t_directa_list, t_fft_list = [], [], []
    num_repeticiones = 3  # Promedio de corridas

    print(f"\n{'Duración s(t)':<14} | {'N emitida':<10} | {'M recibida':<12} | {'N_fft':<7} | "
          f"{'Directa (s)':<13} | {'Vía FFT (s)':<13} | {'Aceleración':<12}")
    print("-" * 102)

    for duracion_ms in duraciones_ms:
        duracion = duracion_ms / 1000.0

        # Señal acústica real y su recepción con ecos superpuestos y ruido
        if tipo_senal == "chirp":
            _t, s_t = generar_chirp(Fs, duracion, 1000, 5000)
        else:
            _t, s_t = generar_secuencia_pulsos(Fs, duracion, 2000, 3)
        _t_captura, r_t = simular_canal_ecos(s_t, Fs, retardos_ms, atenuaciones, nivel_ruido)

        if duracion_ms == duracion_caso_ms and tiempos_caso is not None:
            # El caso analizado ya fue cronometrado en la Ventana 5: se reutiliza
            # esa medición en lugar de repetirla, para que ambas secciones
            # reporten exactamente el mismo número
            t_directa_prom, t_fft_prom = tiempos_caso
        else:
            t_directa_acum, t_fft_acum = 0.0, 0.0

            for _ in range(num_repeticiones):
                t0 = time.perf_counter()
                _ = correlacion_directa(s_t, r_t)
                t_directa_acum += (time.perf_counter() - t0)

                t0 = time.perf_counter()
                _ = correlacion_fft(s_t, r_t)
                t_fft_acum += (time.perf_counter() - t0)

            t_directa_prom = t_directa_acum / num_repeticiones
            t_fft_prom = t_fft_acum / num_repeticiones

        tamanos_N.append(len(s_t))
        t_directa_list.append(t_directa_prom)
        t_fft_list.append(t_fft_prom)

        # Tamaño al que se rellena con ceros: la FFT trabaja sobre este N, no
        # sobre el original, por lo que su costo se mantiene constante entre
        # potencias de 2 consecutivas
        N_fft = 1 << (len(s_t) + len(r_t) - 2).bit_length()

        aceleracion = f"{t_directa_prom/t_fft_prom:.1f}x"
        marca = "  <- caso analizado arriba" if duracion_ms == duracion_caso_ms else ""
        print(f"{duracion_ms:<14.1f} | {len(s_t):<10} | {len(r_t):<12} | {N_fft:<7} | "
              f"{t_directa_prom:<13.6f} | {t_fft_prom:<13.6f} | {aceleracion:<12}{marca}")

    # =========================================================
    # VENTANA 6: COSTO DE CADA IMPLEMENTACIÓN Y ACELERACIÓN OBTENIDA
    # =========================================================
    N_caso = int(FS * DURACION_EMITIDA)
    aceleraciones = [td / tf for td, tf in zip(t_directa_list, t_fft_list)]

    fig6, axs6 = plt.subplots(1, 2, figsize=(12, 4.5))
    fig6.suptitle("Ventana 6: Costo de la Detección de Ecos (Correlación Directa vs vía FFT)",
                  fontsize=13)

    # 1. Tiempo absoluto de cada implementación. Se usa escala logarítmica
    # porque los tiempos abarcan dos órdenes de magnitud y en escala lineal la
    # curva de la FFT quedaría aplastada contra el eje.
    axs6[0].plot(tamanos_N, t_directa_list, 'o-', color='crimson',
                 label='Correlación Directa $O(N^2)$')
    axs6[0].plot(tamanos_N, t_fft_list, 's-', color='navy',
                 label='Correlación vía FFT $O(N \\log N)$')
    axs6[0].axvline(N_caso, color='gray', ls=':', lw=1.5,
                    label=f'Caso analizado (N={N_caso})')
    axs6[0].set_yscale('log')
    axs6[0].set_title("1. Tiempo de Ejecución")
    axs6[0].set_xlabel("Muestras de la Señal Emitida (N)")
    axs6[0].set_ylabel("Tiempo Promedio [s] (Escala Log)")
    axs6[0].legend(fontsize=8)
    axs6[0].grid(True, which="both", ls="--")

    # 2. Cuántas veces más rápida resulta la FFT, en escala lineal para que la
    # razón se lea directamente del eje
    axs6[1].plot(tamanos_N, aceleraciones, 'D-', color='darkgreen')
    axs6[1].axhline(1, color='k', ls='-', lw=1)
    axs6[1].axvline(N_caso, color='gray', ls=':', lw=1.5)
    for N, aceleracion in zip(tamanos_N, aceleraciones):
        axs6[1].annotate(f"{aceleracion:.1f}x", xy=(N, aceleracion),
                         xytext=(0, 7), textcoords='offset points',
                         ha='center', fontsize=8, color='darkgreen')
    axs6[1].set_title("2. Aceleración de la FFT sobre la Directa")
    axs6[1].set_xlabel("Muestras de la Señal Emitida (N)")
    axs6[1].set_ylabel("Veces más rápida")
    axs6[1].set_ylim(0, max(aceleraciones) * 1.15)  # Margen para las etiquetas
    axs6[1].grid(True, ls="--")

    plt.tight_layout()
    plt.savefig("outputs/ecos/ventana6_comparacion_tiempos.png")

if __name__ == "__main__":
    tiempos_caso = ejecutar_deteccion_ecos(tipo_senal="chirp")
    comparar_tiempos_correlacion(tipo_senal="chirp", tiempos_caso=tiempos_caso)

    # Se entra al event loop una sola vez, con todas las ventanas ya construidas.
    # El backend macosx de matplotlib lanza "SystemError: NULL object passed to
    # Py_BuildValue" si se invoca plt.show() varias veces en el mismo proceso.
    plt.show()
