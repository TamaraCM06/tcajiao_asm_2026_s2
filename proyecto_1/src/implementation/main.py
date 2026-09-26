import board
import pwmio
import analogio
import time
import supervisor
import sys

# --- CONFIGURACIÓN DE HARDWARE ---
pwm = pwmio.PWMOut(board.GP22, frequency=1000, duty_cycle=0, variable_frequency=True)
mic = analogio.AnalogIn(board.GP26)

# --- PARÁMETROS DEL CHIRP ---
CHIRP_F_INICIAL = 2000
CHIRP_F_FINAL = 4500
CHIRP_DURACION_MS = 200

# Control de velocidad de refresco (15 FPS ~ 66 ms)
INTERVALO_PANTALLA_S = 0.066
ultimo_refresco = time.monotonic()

val_max = 0
val_min = 65535

def emitir_chirp_con_escucha():
    global val_max, val_min, ultimo_refresco
    
    pasos = 30
    tiempo_paso_s = (CHIRP_DURACION_MS / 1000.0) / pasos
    delta_f = (CHIRP_F_FINAL - CHIRP_F_INICIAL) / pasos
    
    pwm.duty_cycle = 32768  # 50% volumen
    frecuencia_actual = CHIRP_F_INICIAL
    
    for _ in range(pasos):
        pwm.frequency = int(frecuencia_actual)
        frecuencia_actual += delta_f
        
        # Muestreo activo mientras suena el tono
        t_paso = time.monotonic()
        while (time.monotonic() - t_paso) < tiempo_paso_s:
            lectura = mic.value
            if lectura > val_max:
                val_max = lectura
            if lectura < val_min:
                val_min = lectura
                
            if (time.monotonic() - ultimo_refresco) >= INTERVALO_PANTALLA_S:
                imprimir_barra()

    pwm.duty_cycle = 0  # Apagar PWM

def imprimir_barra():
    global val_max, val_min, ultimo_refresco
    
    amplitud = val_max - val_min
    largo_barra = int(amplitud / 500)
    barra = "█" * min(largo_barra, 50)
    
    if not barra:
        barra = "▏"
        
    print(barra)
    
    # Reiniciar métricas para la siguiente ventana
    val_max = 0
    val_min = 65535
    ultimo_refresco = time.monotonic()

print("--- MONITOR DE AUDIO CONTINUO (PRESIONA ENTER PARA CHIRP) ---")
time.sleep(1)

while True:
    # 1. Detección NO BLOQUEANTE de teclas
    if supervisor.runtime.serial_bytes_available:
        # Leemos los caracteres pendientes sin usar input() para evitar que se congele
        _ = sys.stdin.read(supervisor.runtime.serial_bytes_available)
        emitir_chirp_con_escucha()

    # 2. Muestreo continuo del micrófono MAX4466
    lectura = mic.value
    if lectura > val_max:
        val_max = lectura
    if lectura < val_min:
        val_min = lectura

    # 3. Imprimir barra gráfica cada 66 ms sin interrumpir el bucle
    if (time.monotonic() - ultimo_refresco) >= INTERVALO_PANTALLA_S:
        imprimir_barra()

    time.sleep(0.001)