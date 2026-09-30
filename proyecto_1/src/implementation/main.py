"""
Radar acustico para estimacion de distancia
CE1110 Analisis de Senales Mixtas - Proyecto 1

Emite un chirp, captura la ventana con el microfono, estima el retardo del eco por
correlacion via FFT y reporta la distancia al objeto.

Corresponde a las ocho operaciones de la etapa 4 del enunciado:
    a) generacion de una senal conocida  -> generar_muestras_chirp
    b) reproduccion por parlante         -> capturar
    c) adquisicion mediante ADC          -> capturar
    d) procesamiento mediante FFT        -> fft / ifft
    e) identificacion del eco            -> correlacion_fft
    f) estimacion del tiempo de vuelo    -> detectar_eco
    g) calculo de la distancia           -> distancia_desde_retardo
    h) visualizacion del resultado       -> main

Los nombres siguen los de los modulos de simulacion (src/fft_dft y
src/deteccion_ecos) para que el paso de la simulacion al hardware sea trazable.
Aqui no hay numpy: la FFT opera sobre pares de arreglos de flotantes en lugar de
listas de complejos, porque cada complejo de Python es un objeto en el monticulo y
varios miles no caben en la memoria del Pico.

Uso:
    Copiar al CIRCUITPY como main.py y reiniciar con Ctrl-D. Debe llamarse asi,
    no code.py, porque test_hardware.py lo importa por ese nombre. Conviene
    ejecutarlo desde la placa y no desde el editor: enviarlo por el puerto serie
    mantiene el codigo fuente en memoria ademas del programa.
"""

import board
import analogio
import pwmio
import gc
import math
import supervisor
import sys
import time
from array import array

# --- HARDWARE ---
PIN_PARLANTE = board.GP22    # PWM  -> INPUT L del amplificador
PIN_MICROFONO = board.GP26   # ADC0 <- OUT del MAX4466

# --- SENAL EMITIDA ---
CHIRP_F_INICIAL = 2000
CHIRP_F_FINAL = 7000
# La duracion no la fija solo el procesamiento. Un parlante tiene inercia
# mecanica y tarda algunos milisegundos en alcanzar su excursion completa, de modo
# que una emision demasiado corta termina antes de que el cono arranque y radia una
# fraccion de lo que podria. Con 6 ms la emision era apenas audible. Veinte
# milisegundos dan tiempo al transductor y ademas elevan el producto B*T, del que
# depende la ganancia de la correlacion.
# Seis milisegundos, no doce. Con doce la plantilla ocupaba del orden de 300
# muestras de las 512 de la transformada, no quedaba sitio para la ventana de
# escucha y el clamp de n_proc la reducia a 8 muestras: rango_max caia a unos
# 5 cm y el sistema no detectaba nada, con el lazo del ADC entre 22 y 30 kHz.
# Se paga con la mitad del producto B*T (30 en vez de 60), unos 3 dB menos de
# ganancia de correlacion. La nota anterior sobre que 6 ms era apenas audible se
# midio emitiendo por reconfiguracion del PWM; con audiopwmio la forma de onda
# se precalcula y sale completa, de modo que ese argumento ya no aplica.
CHIRP_DURACION_MS = 6
# Cada escalon debe durar varios ciclos de su propia frecuencia. El PWM reinicia
# su contador al cambiar de frecuencia, de modo que si el escalon es mas corto que
# un periodo el parlante recibe fragmentos de onda y apenas se mueve. Con 48 pasos
# sobre 20 ms cada escalon duraba 0.375 ms, menos de un ciclo a 2 kHz, y la
# emision resultaba casi inaudible. Con 16 pasos dura 1.25 ms: entre 2 y 9 ciclos
# segun la frecuencia.
CHIRP_PASOS = 8

# --- MEDICION ---
RANGO_MIN_M = 0.15
RANGO_MAX_M = 0.40
PROMEDIOS = 8           # Capturas por medicion: +10*log10(N) dB de mejora
UMBRAL_DETECCION = 3.5  # Respaldo si la calibracion automatica no se ejecuta
CALIBRACIONES = 4       # Mediciones sobre las que se aprende el umbral
PERCENTIL_UMBRAL = 0.95  # Del perfil de fondo; por encima solo quedan ecos
MARGEN_UMBRAL = 1.5     # Cuanto se eleva el umbral sobre ese percentil
# El umbral aprendido se acota. El margen entre el fondo y el eco mas debil del
# rango es estrecho, de modo que una estimacion libre puede caer fuera si la
# escena de calibracion no es representativa. Los limites garantizan que el valor
# adoptado siga siendo utilizable aunque la calibracion se haya hecho mal.
# El minimo se bajo de 4.5 a 3.0. Sobre hardware real el eco vuelve bastante mas
# debil que en simulacion, y un piso alto convierte cada medicion en un cero sin
# que haya nada mal en el procesamiento. Mas vale un umbral permisivo, con la razon
# a la vista para juzgar cada lectura, que un sistema que nunca afirma nada.
UMBRAL_MINIMO = 3.0
UMBRAL_MAXIMO = 7.0
CFAR_CELDAS = 12        # Muestras a cada lado que estiman el nivel de fondo
CFAR_GUARDA = 3         # Muestras contiguas excluidas: el pico ocupa varias

# --- CONSTANTES ---
DUTY_50 = 32768
VELOCIDAD_SONIDO = 343.0
# Cuantas veces la frecuencia maxima del chirp debe cubrir la tasa ya decimada.
# Decimar de mas hunde Nyquist por debajo del chirp y su parte alta se pliega;
# decimar de menos alarga la FFT sin aportar informacion. Con 2.2 queda margen
# suficiente sobre Nyquist y la transformada se mantiene en 1024 puntos aun con
# el chirp largo.
SOBREMUESTREO_MIN = 2.2
# Tope de la transformada. En el Pico una FFT de 2048 puntos con ulab agota el
# monticulo a medio calculo, cae al respaldo en Python y la medicion pasa de
# decimas de segundo a varios segundos.
# Con 1024 puntos ulab no arranca: pide 4096 bytes por arreglo y la asignacion
# falla sobre esta placa. El tope real es 512, y la forma de caber en el no es
# recortar la ventana de escucha sino acortar la emision, porque la correlacion
# necesita n_plantilla + n_escucha - 1 puntos y la plantilla es el termino que
# mas pesa.
FFT_MAX = 512


def detectar_ulab():
    """
    Informa si la placa trae ulab con FFT utilizable.

    Se comprueba ejecutando una transformada y no solo importando el modulo,
    porque hay compilaciones que incluyen ulab sin habilitar el submodulo fft.
    """
    try:
        from ulab import numpy as unp
        unp.fft.fft(unp.zeros(4))
        return unp
    except Exception:
        return None


ULAB = detectar_ulab()


def detectar_audio():
    """
    Informa si la placa puede reproducir una forma de onda arbitraria por hardware.

    Con audiopwmio el chirp se precalcula en memoria y lo emite el hardware a tasa
    fija, sin que el interprete intervenga durante la emision. La alternativa, ir
    cambiando la frecuencia de un PWM escalon por escalon, reconfigura el divisor
    del periferico decenas de veces en pocos milisegundos y produce emisiones de
    amplitud irregular: sobre esta placa se midieron variaciones de dos a cuatro
    veces entre disparos identicos.
    """
    try:
        import audiocore
        import audiopwmio
        return audiocore, audiopwmio
    except ImportError:
        return None, None


AUDIOCORE, AUDIOPWMIO = detectar_audio()

# Tasa a la que se reproduce la forma de onda precalculada. No tiene relacion con
# la de captura: la fija el hardware de audio y es exacta.
# Cuanto mas alta, mas arriba queda la portadora del PWM y menos se cuela en la
# banda audible como turbiedad. La salida de audio por PWM es un tren de pulsos
# que idealmente se filtraria antes del amplificador; subir la tasa cumple una
# funcion parecida sin agregar componentes.
FS_EMISION = 44100


# =============================================================================
# TRANSFORMADA DE FOURIER
# =============================================================================

def siguiente_potencia_2(n):
    """Menor potencia de 2 mayor o igual que n (Ecuacion 12 del informe)."""
    potencia = 1
    while potencia < n:
        potencia <<= 1
    return potencia


def _invertir_bits(re, im):
    """
    Deja cada muestra en la posicion de su indice con los bits invertidos.

    Es el reordenamiento que la version recursiva de Cooley-Tukey consigue al
    separar pares e impares en cada nivel. Hacerlo de una vez permite recorrer
    despues el arreglo de forma iterativa y en sitio, sin listas intermedias.
    """
    n = len(re)
    j = 0
    for i in range(1, n):
        bit = n >> 1
        while j & bit:
            j ^= bit
            bit >>= 1
        j |= bit
        if i < j:
            re[i], re[j] = re[j], re[i]
            im[i], im[j] = im[j], im[i]


def fft(re, im, inversa=False):
    """
    Transformada rapida de Fourier de Cooley-Tukey, iterativa y en sitio.

    Aplica la descomposicion radix-2 descrita en el informe: las mitades par e
    impar se combinan con la operacion mariposa, de modo que un unico producto por
    el factor de giro produce dos salidas y el costo baja de O(N^2) a O(N log N).
    El factor de giro se actualiza por multiplicacion recurrente en vez de
    recalcular un coseno y un seno por mariposa.
    """
    n = len(re)
    if n <= 1:
        return
    _invertir_bits(re, im)

    longitud = 2
    while longitud <= n:
        angulo = (1.0 if inversa else -1.0) * 2.0 * math.pi / longitud
        paso_re = math.cos(angulo)
        paso_im = math.sin(angulo)
        mitad = longitud >> 1
        for inicio in range(0, n, longitud):
            giro_re = 1.0
            giro_im = 0.0
            for k in range(inicio, inicio + mitad):
                j = k + mitad
                t_re = re[j] * giro_re - im[j] * giro_im
                t_im = re[j] * giro_im + im[j] * giro_re
                re[j] = re[k] - t_re
                im[j] = im[k] - t_im
                re[k] += t_re
                im[k] += t_im
                nuevo = giro_re * paso_re - giro_im * paso_im
                giro_im = giro_re * paso_im + giro_im * paso_re
                giro_re = nuevo
        longitud <<= 1

    if inversa:
        for i in range(n):
            re[i] /= n
            im[i] /= n


def ifft(re, im):
    """Transformada inversa. Conserva los nombres usados en el informe."""
    fft(re, im, inversa=True)


def correlacion_fft(plantilla, recibida, fs=None):
    """
    Correlacion cruzada calculada en el dominio de la frecuencia.

    Multiplica el conjugado del espectro emitido por el recibido y antitransforma
    (Ecuacion 11 del informe). Conjugar uno de los espectros hace que el sentido
    del desplazamiento corresponda a una correlacion y no a una convolucion. El
    relleno con ceros hasta la siguiente potencia de 2 mayor o igual a N+M-1 evita
    que la naturaleza circular de la FFT solape los extremos.

    Se devuelve la correlacion con su signo y no su magnitud: es una senal real que
    alterna de signo, y la cancelacion del trayecto directo consiste en restarle una
    copia escalada de la autocorrelacion, resta que solo es valida con signo.

    Retorna:
        Arreglo de longitud len(recibida). El indice es el desplazamiento en
        muestras respecto al inicio de la plantilla.
    """
    n_fft = siguiente_potencia_2(len(plantilla) + len(recibida) - 1)
    n_util = len(recibida)
    gc.collect()

    # Banda del chirp en indices de la transformada. Anular lo de afuera cuesta
    # cero porque el producto ya esta en frecuencia, y quita de golpe dos cosas
    # que ensucian el perfil: la deriva de la alimentacion, medida decenas de dB
    # por encima del chirp, y los armonicos que el PWM deja por arriba de la
    # banda util. El filtro adaptado ya atenua ambas, pero hacerlo explicito evita
    # que su fuga espectral se cuele en el residuo.
    if fs:
        k_bajo = int(CHIRP_F_INICIAL * n_fft / fs) - 1
        k_alto = int(CHIRP_F_FINAL * n_fft / fs) + 2
        if k_bajo < 1:
            k_bajo = 1
    else:
        k_bajo = 0
        k_alto = n_fft

    if ULAB is not None:
        try:
            s = ULAB.zeros(n_fft)
            r = ULAB.zeros(n_fft)
            for i in range(len(plantilla)):
                s[i] = plantilla[i]
            for i in range(n_util):
                r[i] = recibida[i]
            s_re, s_im = ULAB.fft.fft(s)
            del s
            r_re, r_im = ULAB.fft.fft(r)
            del r
            gc.collect()
            prod_re = s_re * r_re + s_im * r_im
            prod_im = s_re * r_im - s_im * r_re
            del s_re, s_im, r_re, r_im
            if k_bajo:
                # El espectro de una senal real es simetrico: hay que anular cada
                # banda y tambien su imagen en la mitad superior.
                for k in range(n_fft // 2 + 1):
                    if k < k_bajo or k > k_alto:
                        prod_re[k] = 0.0
                        prod_im[k] = 0.0
                        espejo = n_fft - k
                        if 0 < espejo < n_fft:
                            prod_re[espejo] = 0.0
                            prod_im[espejo] = 0.0
            gc.collect()
            corr_re, _ = ULAB.fft.ifft(prod_re, prod_im)
            del prod_re, prod_im
            salida = array("f", bytes(4 * n_util))
            for i in range(n_util):
                salida[i] = corr_re[i]
            return salida
        except Exception as error:
            print("  AVISO: ulab fallo -> {}: {}".format(
                type(error).__name__, error))
            print("         n_fft={} memoria libre={} bytes".format(
                n_fft, gc.mem_free()))
            print("         se usara la FFT en Python (mas lenta).")
            gc.collect()

    s_re = array("f", bytes(4 * n_fft))
    s_im = array("f", bytes(4 * n_fft))
    r_re = array("f", bytes(4 * n_fft))
    r_im = array("f", bytes(4 * n_fft))
    for i in range(len(plantilla)):
        s_re[i] = plantilla[i]
    for i in range(n_util):
        r_re[i] = recibida[i]
    fft(s_re, s_im)
    fft(r_re, r_im)
    for i in range(n_fft):
        sr, si, rr, ri = s_re[i], s_im[i], r_re[i], r_im[i]
        s_re[i] = sr * rr + si * ri
        s_im[i] = sr * ri - si * rr
    if k_bajo:
        for k in range(n_fft // 2 + 1):
            if k < k_bajo or k > k_alto:
                s_re[k] = 0.0
                s_im[k] = 0.0
                espejo = n_fft - k
                if 0 < espejo < n_fft:
                    s_re[espejo] = 0.0
                    s_im[espejo] = 0.0
    del r_re, r_im
    gc.collect()
    ifft(s_re, s_im)
    salida = array("f", bytes(4 * n_util))
    for i in range(n_util):
        salida[i] = s_re[i]
    return salida


# =============================================================================
# SENAL Y ADQUISICION
# =============================================================================

def tabla_chirp(n_pasos, f_inicial, f_final):
    """Secuencia de frecuencias del barrido lineal, en Hz."""
    if n_pasos < 2:
        return [f_inicial]
    delta = (f_final - f_inicial) / (n_pasos - 1)
    return [int(f_inicial + i * delta) for i in range(n_pasos)]


# Fraccion de la emision ocupada por los flancos de subida y bajada. Un chirp que
# arranca y corta de golpe tiene discontinuidades en los extremos: se oyen como un
# disparo seco y, en la correlacion, reparten energia en lobulos laterales que
# cubren todo el rango de busqueda y pueden superar al eco. Suavizar los bordes con
# medio ciclo de coseno quita las dos cosas. Se toma la cuarta parte a cada lado y
# no una campana completa porque el centro plano conserva la energia, que con una
# emision de 6 ms ya es escasa.
VENTANA_ALFA = 0.5


def factor_ventana(i, n, alfa=VENTANA_ALFA):
    """
    Peso de la ventana de Tukey en la muestra i de n.

    Vale uno en el centro y decae a cero en los extremos siguiendo medio ciclo de
    coseno. Debe aplicarse igual a la senal emitida y a la plantilla: la
    correlacion compara formas, de modo que enventanar solo una de las dos las
    vuelve distintas y baja el pico en lugar de subirlo.
    """
    if n < 2:
        return 1.0
    borde = alfa * (n - 1) / 2.0
    if borde <= 0:
        return 1.0
    if i < borde:
        return 0.5 * (1.0 - math.cos(math.pi * i / borde))
    if i > n - 1 - borde:
        return 0.5 * (1.0 - math.cos(math.pi * (n - 1 - i) / borde))
    return 1.0


def generar_muestras_chirp(fs, duracion_s, f_inicial, f_final, amplitud=32000):
    """
    Precalcula el chirp como muestras con signo, para reproducirlo por hardware.

    El barrido es lineal y continuo, sin escalones: la frecuencia instantanea pasa
    de f_inicial a f_final de forma suave, de modo que la fase no presenta los
    saltos que produce reconfigurar un PWM escalon por escalon. Esos saltos son
    discontinuidades en la onda, se oyen como chasquidos y contaminan la medicion
    del pico.

    La fase se integra muestra a muestra en lugar de evaluarse con la formula
    cerrada: acumular el incremento garantiza continuidad exacta entre muestras
    consecutivas aunque la frecuencia cambie.
    """
    n = int(fs * duracion_s)
    muestras = array("h", bytes(2 * n))
    pendiente = (f_final - f_inicial) / duracion_s
    fase = 0.0
    for i in range(n):
        frecuencia = f_inicial + pendiente * (i / fs)
        fase += 2.0 * math.pi * frecuencia / fs
        muestras[i] = int(amplitud * factor_ventana(i, n) * math.sin(fase))
    return muestras


def generar_plantilla_continua(fs, duracion_s, f_inicial, f_final):
    """
    Construye la plantilla de correlacion con el mismo barrido que se emite.

    Debe recorrer las mismas frecuencias en los mismos instantes que la senal
    emitida, pero muestreada a la tasa de captura y no a la de reproduccion. Son
    dos relojes distintos: el de audio, exacto y fijado por hardware, y el del lazo
    de muestreo, que depende de la velocidad del interprete.
    """
    n = int(fs * duracion_s)
    plantilla = array("f", bytes(4 * n))
    pendiente = (f_final - f_inicial) / duracion_s
    fase = 0.0
    for i in range(n):
        frecuencia = f_inicial + pendiente * (i / fs)
        fase += 2.0 * math.pi * frecuencia / fs
        plantilla[i] = factor_ventana(i, n) * math.sin(fase)
    return plantilla


def realzar_altas(muestras):
    """
    Suprime la deriva de baja frecuencia con una diferencia de primer orden.

    Durante la emision el amplificador consume corriente a rachas, la alimentacion
    cede y la polarizacion del microfono se desplaza. En capturas reales esa deriva
    alcanzo varios cientos de cuentas, casi un orden de magnitud sobre el chirp. La
    diferencia entre muestras consecutivas atenua 6 dB por octava hacia abajo y
    separa esa deriva de unos cientos de hercios del chirp de varios miles, a costa
    de una resta por muestra.
    """
    anterior = muestras[0]
    for i in range(len(muestras)):
        actual = muestras[i]
        muestras[i] = actual - anterior
        anterior = actual


def quitar_continua(muestras):
    """
    Resta el nivel de reposo para dejar solo la componente alterna.

    El MAX4466 entrega la senal centrada en la mitad de su alimentacion, no en cero.
    Esa componente continua no aporta informacion acustica y domina la correlacion.
    """
    media = sum(muestras) / len(muestras)
    for i in range(len(muestras)):
        muestras[i] -= media


def capturar(emisor, mic, datos):
    """
    Dispara la emision y captura la ventana completa.

    La emision no bloquea: el hardware de audio reproduce la forma de onda desde
    memoria mientras el lazo se dedica solo a leer el ADC. Eso separa por completo
    los dos relojes, y deja el lazo de captura sin mas trabajo que muestrear, que
    es lo que le da su maxima velocidad y su mayor uniformidad.

    Parametros:
        emisor: Objeto con metodo disparar(), que inicia la reproduccion.
        mic: AnalogIn sobre el pin del microfono.
        datos: Arreglo preasignado que se llena por completo.

    Retorna:
        La frecuencia de muestreo efectiva de esta captura, en Hz.
    """
    n_total = len(datos)
    t0 = time.monotonic_ns()
    emisor.disparar()
    for i in range(n_total):
        datos[i] = mic.value
    return n_total / ((time.monotonic_ns() - t0) / 1e9)


class EmisorAudio:
    """
    Reproduce el chirp precalculado por hardware, a tasa fija.

    El interprete no participa durante la emision: solo ordena el arranque. Asi la
    forma de onda emitida es identica en cada disparo, que es la condicion que el
    promediado y la correlacion necesitan y que el barrido por reconfiguracion del
    PWM no podia garantizar.
    """

    def __init__(self, pin, duracion_s):
        self.muestras = generar_muestras_chirp(
            FS_EMISION, duracion_s, CHIRP_F_INICIAL, CHIRP_F_FINAL)
        self.onda = AUDIOCORE.RawSample(self.muestras, sample_rate=FS_EMISION)
        self.salida = AUDIOPWMIO.PWMAudioOut(pin)
        self.duracion_s = duracion_s

    def disparar(self):
        """Inicia la reproduccion del chirp y regresa de inmediato."""
        self.salida.play(self.onda, loop=False)

    def tono(self, frecuencia):
        """
        Emite un tono sostenido, para las pruebas de calibracion.

        Se genera un solo ciclo completo y se reproduce en bucle. Al elegir una
        longitud que contenga un numero entero de ciclos, el empalme entre el final
        y el principio del bucle es continuo y no introduce el chasquido periodico
        que delataria un corte de fase.
        """
        ciclos = 32
        n = max(2, int(round(ciclos * FS_EMISION / frecuencia)))
        muestras = array("h", bytes(2 * n))
        for i in range(n):
            muestras[i] = int(32000 * math.sin(2.0 * math.pi * ciclos * i / n))
        self._tono = AUDIOCORE.RawSample(muestras, sample_rate=FS_EMISION)
        self.salida.play(self._tono, loop=True)

    def silencio(self):
        """Detiene cualquier emision en curso."""
        self.salida.stop()

    def liberar(self):
        self.salida.deinit()


class EmisorPWM:
    """
    Respaldo por escalones de frecuencia, para placas sin audiopwmio.

    Reconfigura el PWM en cada escalon del barrido. Funciona, pero la amplitud
    emitida varia entre disparos porque cada reconfiguracion puede caer en un punto
    distinto del ciclo en curso.
    """

    def __init__(self, pin, duracion_s, fs_estimada):
        self.pwm = pwmio.PWMOut(pin, frequency=CHIRP_F_INICIAL,
                                duty_cycle=0, variable_frequency=True)
        self.tabla = tabla_chirp(CHIRP_PASOS, CHIRP_F_INICIAL, CHIRP_F_FINAL)
        self.por_paso = max(1, int(fs_estimada * duracion_s) // CHIRP_PASOS)
        self.duracion_s = duracion_s

    def disparar(self):
        """Recorre el barrido. A diferencia del emisor por audio, esto bloquea."""
        paso_s = self.duracion_s / len(self.tabla)
        self.pwm.duty_cycle = DUTY_50
        for frecuencia in self.tabla:
            self.pwm.frequency = frecuencia
            t0 = time.monotonic()
            while (time.monotonic() - t0) < paso_s:
                pass
        self.pwm.duty_cycle = 0

    def tono(self, frecuencia):
        """Emite un tono sostenido fijando frecuencia y ciclo de trabajo."""
        self.pwm.frequency = frecuencia
        self.pwm.duty_cycle = DUTY_50

    def silencio(self):
        """Detiene la emision."""
        self.pwm.duty_cycle = 0

    def liberar(self):
        self.pwm.deinit()


# =============================================================================
# DETECCION
# =============================================================================

def buscar_directo(correlacion, fs=None):
    """
    Ubica el pico del trayecto directo, que fija el origen de tiempos.

    Se busca el maximo absoluto de todo el perfil, sin restringirlo a los primeros
    desplazamientos. El directo llega decenas de veces mas fuerte que cualquier
    eco, de modo que es siempre el maximo global y no hace falta acotar donde
    mirar. Restringir la busqueda seria ademas peligroso: el instante en que la
    salida de audio entrega su primera muestra no es inmediato, porque antes debe
    configurarse la transferencia por acceso directo a memoria, y ese retardo
    puede superar la ventana que se le reservaria. El pico caeria fuera, se
    alinearia contra ruido y todo el procesamiento posterior quedaria sin sentido.

    Medir el eco respecto a este pico y no respecto al instante en que el software
    ordena emitir cancela de golpe esa latencia de arranque, junto con la del
    amplificador y la del microfono.

    Se compara en valor absoluto porque el signo del pico depende de la polaridad
    de la cadena: invertir los cables del parlante basta para que el maximo pase a
    ser un minimo.
    """
    indice = 0
    valor = abs(correlacion[0])
    for i in range(1, len(correlacion)):
        actual = abs(correlacion[i])
        if actual > valor:
            valor = actual
            indice = i
    return indice


def cancelar_directo(correlacion, autocorrelacion, indice_directo):
    """
    Resta del perfil la huella que dejo el trayecto directo.

    El microfono esta a centimetros del parlante y el objeto a decenas, de modo que
    el directo llega decenas de veces mas fuerte. Al correlacionar no deja solo un
    pico sino la autocorrelacion completa de la plantilla, cuyos lobulos cubren todo
    el rango de busqueda. Como esa forma es conocida, basta estimar su amplitud en
    el pico y restarla desplazada a esa posicion.
    """
    if autocorrelacion[0] == 0:
        return correlacion
    escala = correlacion[indice_directo] / autocorrelacion[0]
    residuo = array("f", bytes(4 * len(correlacion)))
    n_auto = len(autocorrelacion)
    for i in range(len(correlacion)):
        k = i - indice_directo
        if 0 <= k < n_auto:
            residuo[i] = correlacion[i] - escala * autocorrelacion[k]
        else:
            residuo[i] = correlacion[i]
    return residuo


def perfil_cfar(residuo, fs, indice_directo, rango_max):
    """
    Calcula, para cada desplazamiento, cuantas veces supera al nivel de su vecindad.

    Comparar contra un nivel global no sirve: la cancelacion del directo nunca es
    perfecta sobre hardware real, y deja un residuo que decae desde el origen cuyo
    maximo cae siempre en el primer desplazamiento examinado. El sistema reportaria
    una y otra vez la misma distancia, haya objeto o no.

    Midiendo cada punto contra el promedio de sus vecinos, una rampa suave da razon
    cercana a uno en todas partes y solo destaca un maximo localizado, que es la
    forma que tiene un eco. Es el criterio de tasa de falsa alarma constante usado
    en radar. Las celdas de guarda contiguas se excluyen porque el pico comprimido
    ocupa varias muestras y de otro modo elevaria su propia referencia.

    Retorna:
        inicio: Indice del primer desplazamiento evaluado.
        razones: Lista con la razon de cada desplazamiento a partir de inicio.
    """
    inicio = indice_directo + int(fs * 2.0 * RANGO_MIN_M / VELOCIDAD_SONIDO)
    # Las dos muestras de holgura no son arbitrarias: una compensa el truncamiento
    # al convertir el rango a muestras y la otra que range() excluye su limite. Sin
    # ellas el eco que llega justo a RANGO_MAX_M cae fuera por una muestra y el
    # ultimo centimetro del rango declarado no se alcanza nunca.
    fin = min(indice_directo + int(fs * 2.0 * rango_max / VELOCIDAD_SONIDO) + 2,
              len(residuo) - 1)
    if inicio >= fin:
        return inicio, []

    n = len(residuo)
    razones = []
    for i in range(inicio, fin):
        suma = 0.0
        cuenta = 0
        for j in range(i - CFAR_CELDAS - CFAR_GUARDA,
                       i + CFAR_CELDAS + CFAR_GUARDA + 1):
            if j < 0 or j >= n or abs(j - i) <= CFAR_GUARDA:
                continue
            suma += abs(residuo[j])
            cuenta += 1
        nivel = suma / cuenta if cuenta else 0.0
        razones.append(abs(residuo[i]) / nivel if nivel > 0 else 0.0)
    return inicio, razones


def detectar_eco(residuo, fs, indice_directo, rango_max, umbral):
    """
    Localiza el eco y decide si el maximo supera el umbral de deteccion.

    El retardo se devuelve con precision de fraccion de muestra: la posicion del
    maximo se refina por interpolacion parabolica, de modo que la estimacion no
    queda limitada al paso de muestreo.

    Retorna:
        retardo_s: Tiempo de vuelo, o None si no supera el umbral.
        indice_pico: Posicion del maximo.
        razon: Cuantas veces el maximo supera el nivel de su vecindad.
    """
    inicio, razones = perfil_cfar(residuo, fs, indice_directo, rango_max)
    if not razones:
        return None, None, 0.0

    # Se toma el PRIMER maximo local que supera el umbral, no el de razon mas alta.
    # Un objeto no devuelve un solo eco: la onda rebota entre el objeto y el
    # microfono y deja replicas a dos y tres veces la distancia. Esas replicas
    # llegan mas debiles, pero caen en una parte del perfil donde ya no hay nada
    # mas, de modo que su vecindad es muy tranquila y su razon sale mas alta que la
    # del eco verdadero, que compite contra el residuo del trayecto directo.
    # Elegir por razon reportaba entonces el doble de la distancia real. El primer
    # eco es el del objeto; todo lo que viene despues es consecuencia suya.
    # Se localiza el primer tramo que cruza el umbral y, dentro de ese tramo, su
    # maximo. Quedarse con el cruce adelantaria la estimacion hasta el flanco de
    # subida: el enventanado ensancha el lobulo comprimido a una docena de muestras,
    # de modo que el flanco esta varias muestras antes del centro y la distancia
    # saldria corta por un par de centimetros de forma sistematica.
    mejor = None
    i = 0
    n_razones = len(razones)
    while i < n_razones:
        if razones[i] < umbral:
            i += 1
            continue
        mejor = i
        while i < n_razones and razones[i] >= umbral:
            if razones[i] > razones[mejor]:
                mejor = i
            i += 1
        break

    if mejor is None:
        # Nada supera el umbral. Se informa igual el maximo del perfil, porque su
        # posicion es el dato con el que se juzga si el sistema esta viendo el
        # objeto o eligiendo ruido.
        mejor = 0
        for i in range(1, len(razones)):
            if razones[i] > razones[mejor]:
                mejor = i
        return None, inicio + mejor, razones[mejor]

    indice_pico = inicio + mejor
    return ((_refinar(residuo, indice_pico) - indice_directo) / fs,
            indice_pico, razones[mejor])


def _refinar(residuo, indice):
    """
    Afina la posicion del maximo ajustando una parabola a el y sus dos vecinos.

    El maximo verdadero rara vez cae justo sobre una muestra. El vertice de la
    parabola que pasa por los tres puntos lo estima con una fraccion del paso de
    muestreo. Solo se acepta si la parabola es concava y el vertice cae entre las
    muestras vecinas; cualquier otro caso indica que el entorno no tiene forma de
    pico e interpolar inventaria precision.
    """
    if indice <= 0 or indice >= len(residuo) - 1:
        return float(indice)
    izq = abs(residuo[indice - 1])
    centro = abs(residuo[indice])
    der = abs(residuo[indice + 1])
    denominador = izq - 2.0 * centro + der
    if denominador >= 0:
        return float(indice)
    ajuste = 0.5 * (izq - der) / denominador
    if ajuste < -0.5 or ajuste > 0.5:
        return float(indice)
    return indice + ajuste


def distancia_desde_retardo(retardo_s):
    """
    Distancia para configuracion monostatica (Ecuacion 9 del informe).

    El factor dos recoge que el sonido recorre la ida y la vuelta, mientras que la
    distancia buscada es solo la de ida.
    """
    return VELOCIDAD_SONIDO * retardo_s / 2.0


# =============================================================================
# RADAR
# =============================================================================

class Radar:
    """Agrupa el hardware, los buffers y el ciclo de medicion."""

    def __init__(self):
        self.mic = analogio.AnalogIn(PIN_MICROFONO)
        self.duracion_emision = CHIRP_DURACION_MS / 1000.0

        fs_cruda = self._medir_velocidad()
        self.decimacion = max(1, int(fs_cruda /
                                     (SOBREMUESTREO_MIN * CHIRP_F_FINAL)))

        # La emision la temporiza el hardware de audio, asi que su duracion es
        # exacta y no depende de la velocidad del lazo. La ventana de captura, en
        # cambio, se dimensiona con la velocidad estimada del lazo.
        # Margen extra: la salida de audio tarda en entregar su primera muestra
        # mientras configura la transferencia por DMA. Ese retardo corre toda la
        # captura hacia adelante, de modo que sin holgura el final del rango
        # quedaria fuera de la ventana.
        margen_arranque = int(fs_cruda * 0.003)
        n_escucha = (int(fs_cruda * 2.0 * RANGO_MAX_M / VELOCIDAD_SONIDO)
                     + 24 + margen_arranque)
        self.n_emision = int(fs_cruda * self.duracion_emision)
        self.n_total = self.n_emision + n_escucha
        self.n_total -= self.n_total % self.decimacion
        self.n_proc = self.n_total // self.decimacion
        self.n_emision_proc = self.n_emision // self.decimacion

        n_proc_max = FFT_MAX - self.n_emision_proc + 1
        if self.n_proc > n_proc_max:
            self.n_proc = max(self.n_emision_proc + 8, n_proc_max)
            self.n_total = self.n_proc * self.decimacion

        self.fs = fs_cruda / self.decimacion
        self.indice_directo = 0
        self.directo_crudo = 0
        self.rango_max = min(
            RANGO_MAX_M,
            VELOCIDAD_SONIDO * (self.n_proc - self.n_emision_proc) / (2 * self.fs))

        gc.collect()
        self.datos = array("H", bytes(2 * self.n_total))
        self.ventana = array("f", bytes(4 * self.n_proc))
        self.acumulador = array("f", bytes(4 * self.n_proc))

        if AUDIOPWMIO is not None:
            self.emisor = EmisorAudio(PIN_PARLANTE, self.duracion_emision)
            self.modo_emision = "audio"
        else:
            self.emisor = EmisorPWM(PIN_PARLANTE, self.duracion_emision, fs_cruda)
            self.modo_emision = "pwm"

        # Una captura de descarte antes de construir la plantilla. La velocidad
        # estimada al principio proviene de un lazo que solo lee; la captura real
        # puede diferir, y la plantilla acumula fase como 2*pi*f/fs, de modo que
        # unas decimas de por ciento de error desplazan la fase decenas de grados
        # a lo largo de la emision. Medir con el mismo lazo lo evita.
        capturar(self.emisor, self.mic, self.datos)
        time.sleep(0.05)
        fs_real = capturar(self.emisor, self.mic, self.datos)
        self.fs = fs_real / self.decimacion

        self.plantilla = generar_plantilla_continua(
            self.fs, self.duracion_emision, CHIRP_F_INICIAL, CHIRP_F_FINAL)
        realzar_altas(self.plantilla)
        quitar_continua(self.plantilla)
        self.autocorrelacion = correlacion_fft(self.plantilla, self.plantilla,
                                               self.fs)
        self.umbral = UMBRAL_DETECCION
        gc.collect()

    def calibrar_umbral(self):
        """
        Aprende el umbral de deteccion a partir del perfil de este montaje.

        Un umbral fijo supone un nivel de fondo que cambia con la sala, la
        ganancia y la geometria. En su lugar se recogen las razones de todas las
        celdas del rango a lo largo de varias mediciones y se toma un percentil
        alto: ese valor representa lo mas alto que el fondo llega por si solo, y
        el umbral se fija con un margen por encima.

        El procedimiento tolera que haya un objeto presente durante la
        calibracion: un eco ocupa unas pocas celdas de un centenar y apenas mueve
        el percentil. Aun asi el resultado se acota entre dos limites, porque la
        separacion entre el fondo y el eco mas debil del rango es estrecha y una
        escena poco representativa podria llevar la estimacion fuera de ella.

        Retorna:
            El umbral adoptado.
        """
        todas = []
        for _ in range(CALIBRACIONES):
            residuo = self._perfil_medido()
            _, razones = perfil_cfar(residuo, self.fs, 0, self.rango_max)
            todas.extend(razones)
            gc.collect()

        if len(todas) < 20:
            self.umbral = UMBRAL_DETECCION
            return self.umbral

        todas.sort()
        percentil = todas[int(PERCENTIL_UMBRAL * (len(todas) - 1))]
        propuesto = percentil * MARGEN_UMBRAL
        if propuesto < UMBRAL_MINIMO:
            propuesto = UMBRAL_MINIMO
        elif propuesto > UMBRAL_MAXIMO:
            propuesto = UMBRAL_MAXIMO
        self.umbral = propuesto
        return self.umbral

    def _medir_velocidad(self, n=600):
        """
        Mide la velocidad del lazo de captura tal como va a correr.

        Se escribe en un arreglo dentro del lazo, igual que en la captura real. Un
        lazo que solo lee resulta mas rapido, y tomar ese numero lleva a decimar de
        mas, hundiendo Nyquist por debajo del chirp.
        """
        prueba = array("H", bytes(2 * n))
        t0 = time.monotonic_ns()
        for i in range(n):
            prueba[i] = self.mic.value
        return n / ((time.monotonic_ns() - t0) / 1e9)

    def liberar(self):
        """Devuelve los pines al sistema."""
        self.emisor.liberar()
        self.mic.deinit()

    def capturar_una(self):
        """
        Realiza una sola captura y deja el resultado decimado en self.ventana.

        La decimacion promedia grupos contiguos en vez de descartar muestras, de
        modo que actua como un filtro pasabajos elemental y el ruido de alta
        frecuencia no se pliega sobre la banda util.
        """
        fs_cruda = capturar(self.emisor, self.mic, self.datos)
        for i in range(self.n_proc):
            suma = 0.0
            base = i * self.decimacion
            for k in range(self.decimacion):
                suma += self.datos[base + k]
            self.ventana[i] = suma / self.decimacion
        self.fs = fs_cruda / self.decimacion

    def _perfil_medido(self):
        """
        Promedia varias correlaciones alineadas y devuelve el residuo sin el directo.

        Cada disparo se correlaciona por separado y las curvas se suman alineadas
        por su propio pico de trayecto directo. Ese pico es la referencia temporal
        de la captura, de modo que alinear por el absorbe cualquier diferencia en
        el instante de arranque. Sumar asi acumula el eco, que guarda posicion fija
        respecto al directo, mientras el ruido crece solo con la raiz del numero de
        disparos.
        """
        for i in range(self.n_proc):
            self.acumulador[i] = 0.0

        for _ in range(PROMEDIOS):
            self.capturar_una()
            realzar_altas(self.ventana)
            quitar_continua(self.ventana)

            gc.collect()
            correlacion = correlacion_fft(self.plantilla, self.ventana, self.fs)
            desplazamiento = buscar_directo(correlacion)
            self.directo_crudo = desplazamiento
            limite = len(correlacion) - desplazamiento
            if limite > self.n_proc:
                limite = self.n_proc
            for i in range(limite):
                self.acumulador[i] += correlacion[desplazamiento + i]
            del correlacion
            time.sleep(0.02)

        for i in range(self.n_proc):
            self.acumulador[i] /= PROMEDIOS

        gc.collect()
        self.indice_directo = 0
        return cancelar_directo(self.acumulador, self.autocorrelacion, 0)

    def medir(self):
        """
        Ejecuta una medicion completa promediando en el dominio de la correlacion.

        Cada disparo se correlaciona por separado y las curvas se suman alineadas
        por su propio pico de trayecto directo. Ese pico es la referencia temporal
        de la captura, de modo que alinear por el absorbe cualquier diferencia en
        el instante de arranque. Sumar asi acumula el eco, que guarda posicion fija
        respecto al directo, mientras el ruido crece solo con la raiz del numero de
        disparos.

        Retorna:
            distancia_cm: Distancia estimada, o None si no hubo deteccion.
            residuo: Perfil de correlacion sin el directo, para graficar.
            indice_pico: Posicion del maximo.
            razon: Cuantas veces el maximo supera su vecindad.
        """
        residuo = self._perfil_medido()
        retardo, indice_pico, razon = detectar_eco(
            residuo, self.fs, 0, self.rango_max, self.umbral)
        distancia_cm = None
        if retardo is not None:
            distancia_cm = distancia_desde_retardo(retardo) * 100.0
        return distancia_cm, residuo, indice_pico, razon


# =============================================================================
# MODOS
# =============================================================================

def perfil_ascii(residuo, fs, indice_directo, indice_pico, rango_max,
                 filas=16, ancho=38):
    """
    Dibuja el perfil de correlacion contra distancia.

    Cada fila abarca un intervalo y muestra su maximo, de modo que un pico estrecho
    no se diluya al agrupar. La forma dice tanto como el numero: un maximo aislado
    con valle a ambos lados es un objeto, mientras que una rampa que decrece desde
    la primera fila es residuo del trayecto directo mal cancelado.
    """
    inicio = indice_directo + int(fs * 2.0 * RANGO_MIN_M / VELOCIDAD_SONIDO)
    # Las dos muestras de holgura no son arbitrarias: una compensa el truncamiento
    # al convertir el rango a muestras y la otra que range() excluye su limite. Sin
    # ellas el eco que llega justo a RANGO_MAX_M cae fuera por una muestra y el
    # ultimo centimetro del rango declarado no se alcanza nunca.
    fin = min(indice_directo + int(fs * 2.0 * rango_max / VELOCIDAD_SONIDO) + 2,
              len(residuo) - 1)
    if inicio >= fin:
        print("   (rango vacio)")
        return

    por_fila = max(1, (fin - inicio) // filas)
    perfil = []
    for f in range(filas):
        desde = inicio + f * por_fila
        hasta = min(desde + por_fila, fin)
        if desde >= hasta:
            break
        perfil.append((desde, max(abs(residuo[i]) for i in range(desde, hasta))))

    maximo = max(v for _, v in perfil) or 1.0
    # Se imprime el nivel como numero y no como barra de caracteres. La barra
    # obligaba a contar simbolos para comparar dos filas, y en una consola serie
    # angosta se parte de linea y deja de significar nada.
    print("   dist(cm)   nivel")
    for desde, valor in perfil:
        distancia = distancia_desde_retardo((desde - indice_directo) / fs) * 100
        marca = "   pico" if (indice_pico is not None
                              and desde <= indice_pico < desde + por_fila) else ""
        print("   {:>7.1f}   {:>5.2f}{}".format(distancia, valor / maximo, marca))


def _tecla_pendiente():
    """Indica si llego algo por el puerto serie, sin bloquear la medicion."""
    if supervisor.runtime.serial_bytes_available:
        sys.stdin.read(supervisor.runtime.serial_bytes_available)
        return True
    return False


def main():
    """
    Mide en continuo e imprime razon de deteccion y distancia.

    La razon indica cuantas veces el maximo del perfil supera el nivel de su
    vecindad. Se imprime siempre, tambien cuando no alcanza el umbral, porque es lo
    que distingue una deteccion real de una casual: un valor alto y estable
    acompana a un objeto, mientras que uno que oscila entre dos y tres indica que
    se esta eligiendo un pico de ruido distinto en cada medicion.

    La distancia del maximo se imprime siempre, tambien cuando la razon no alcanza
    el umbral. El maximo existe en las dos situaciones, y su distancia es el unico
    dato que permite juzgar la medicion contra una regla: si sigue al objeto cuando
    se lo mueve, el procesamiento funciona y solo falta ajustar el umbral; si salta
    sin relacion con el objeto, lo que se esta eligiendo es ruido. Poner cero en esa
    columna borraba justo la informacion con la que se diagnostica.

    La columna det dice si esa lectura supero el umbral. Las cifras van primero y
    los rotulos al final porque el Plotter de Thonny (View -> Plot) toma los numeros
    de cada linea y los dibuja como series, ignorando el resto.

    Cualquier tecla pausa y muestra el perfil completo de la medicion en curso.
    """
    radar = Radar()
    print("calibrando umbral sobre el fondo de esta escena...")
    umbral = radar.calibrar_umbral()
    print("chirp {}-{} Hz {:.0f} ms | emision {} | fs {:.0f} Hz | {:.0f}-{:.0f} cm | {}".format(
        CHIRP_F_INICIAL, CHIRP_F_FINAL, CHIRP_DURACION_MS,
        radar.modo_emision, radar.fs,
        RANGO_MIN_M * 100, radar.rango_max * 100,
        "ulab" if ULAB is not None else "Python"))
    print("umbral aprendido: {:.1f}   banda del filtro: {}-{} Hz".format(
        umbral, CHIRP_F_INICIAL, CHIRP_F_FINAL))
    print("Enter pausa y muestra el perfil. Ctrl-C termina.")
    print("Abri View -> Plot para ver las columnas como grafica.")
    print("cm es la distancia del maximo; det dice si supero el umbral.")
    print()
    print("{:>7} {:>8} {:>5} {:>6}".format("razon", "cm", "det", "dir"))

    try:
        while True:
            distancia, residuo, pico, razon = radar.medir()
            if distancia is not None:
                cm = distancia
            elif pico is not None:
                # El umbral no se alcanzo, pero el maximo y su posicion existen.
                cm = distancia_desde_retardo(pico / radar.fs) * 100.0
            else:
                cm = 0.0
            print("{:>7.1f} {:>8.1f} {:>5} {:>6}".format(
                razon, cm, "si" if distancia is not None else "no",
                radar.directo_crudo))

            if _tecla_pendiente():
                print()
                perfil_ascii(residuo, radar.fs, radar.indice_directo,
                             pico, radar.rango_max)
                print()
                input(" pausado, Enter para seguir> ")
                print("{:>7} {:>8} {:>5} {:>6}".format("razon", "cm", "det", "dir"))
    except KeyboardInterrupt:
        print()
    finally:
        radar.liberar()


if __name__ == "__main__":
    main()
