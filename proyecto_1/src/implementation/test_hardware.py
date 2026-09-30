"""
Banco de calibracion - Radar acustico
CE1110 Analisis de Senales Mixtas - Proyecto 1

Herramientas para poner a punto el hardware y verificar que lo que mide el radar
corresponde con la realidad. Estan ordenadas como una escalera de diagnostico:
cada una responde una sola pregunta, y solo tiene sentido pasar a la siguiente
cuando la anterior da bien.

    1. Tono continuo      -> emite el transmisor de forma estable?   (con el oido)
    2. Reposo continuo    -> el microfono mantiene su referencia?    (con el oido
                             no se puede, se vigila el nivel de reposo)
    3. Muestreo y fidelidad -> se muestrea bien y la onda vuelve parecida?
    4. Calibrar ganancia  -> el directo ocupa la fraccion correcta del ADC?
    5. Respuesta en frecuencia -> donde responde mejor el par transductor?
    6. Validar distancia  -> lo que mide coincide con la regla?
    7. Volcar captura     -> sacar los datos crudos para analizarlos fuera

El procesamiento no se duplica aqui: se importa de main, de modo que lo que se
calibra es exactamente lo que despues mide.

Uso:
    El radar debe estar en la placa como main.py (no como code.py, o el import
    fallaria). Ejecutar este archivo desde Thonny con el Pico conectado.
"""

import math
import time
from array import array

import main
from main import Radar, RANGO_MIN_M

ESCALA_ADC = 65535     # CircuitPython escala los 12 bits reales a 16 bits
LSB = 16               # 1 escalon real del ADC de 12 bits, en la escala de 16 bits
FREC_TONO = 3000       # Tono de referencia, a mitad de la banda del chirp
PICO_OBJETIVO = 0.65   # Fraccion del rango del ADC que debe alcanzar el directo
PISO_MINIMO_LSB = 3.0  # Por debajo, el ruido del conversor tapa las senales debiles

# Pausa entre apagar el tono y medir el silencio. El sonido no se corta cuando se
# apaga el PWM: el cono tarda en frenar y la sala reverbera despues. Sin esta
# espera, la ventana de silencio recoge la cola del tono anterior, su nivel sube y
# el contraste medido sale menor del real.
ESPERA_SILENCIO_S = 0.12


# =============================================================================
# MEDICION
# =============================================================================

def _medir_ventana(mic, duracion_s):
    """
    Muestrea el microfono durante una ventana y resume la actividad observada.

    Se reporta el valor eficaz de la componente alterna y no el pico a pico: el
    pico a pico se queda con las dos muestras extremas de varios miles, de modo que
    un unico valor espurio define el resultado, mientras que el RMS promedia sobre
    toda la ventana y es proporcional a la energia de la senal.

    Retorna:
        media: Nivel de reposo de la ventana.
        rms: Valor eficaz de la componente alterna.
        val_min, val_max: Extremos observados, para detectar saturacion.
    """
    suma = 0
    suma_cuad = 0
    val_min = ESCALA_ADC
    val_max = 0
    n = 0

    t0 = time.monotonic()
    while (time.monotonic() - t0) < duracion_s:
        lectura = mic.value
        suma += lectura
        suma_cuad += lectura * lectura
        if lectura > val_max:
            val_max = lectura
        if lectura < val_min:
            val_min = lectura
        n += 1

    if n == 0:
        return 0.0, 0.0, 0, 0
    media = suma / n
    # Varianza en aritmetica entera exacta: restar dos flotantes grandes y casi
    # iguales perderia casi toda la precision justo cuando la senal es debil.
    varianza = (n * suma_cuad - suma * suma) / (n * n)
    if varianza < 0:
        varianza = 0.0
    return media, math.sqrt(varianza), val_min, val_max


def _goertzel(muestras, n, frecuencia, fs):
    """
    Estima la amplitud de una unica componente de frecuencia de la captura.

    Equivale a evaluar un solo termino de la DFT, es decir a correlacionar la senal
    contra una exponencial compleja de esa frecuencia. Por la ortogonalidad de las
    exponenciales, los aportes de las demas se cancelan y solo sobrevive la que se
    mide. Eso es lo que un medidor de energia de banda ancha no puede hacer: el RMS
    suma el ruido de todo el espectro junto con la senal, y en una habitacion ese
    ruido varia mas que el efecto del ajuste que se intenta observar.

    Se usa la recurrencia de Goertzel en lugar de evaluar senos y cosenos muestra a
    muestra: cuesta una multiplicacion y dos sumas por muestra en vez de dos
    llamadas trigonometricas.
    """
    suma = 0
    for i in range(n):
        suma += muestras[i]
    media = suma / n

    coeficiente = 2.0 * math.cos(2.0 * math.pi * frecuencia / fs)
    s1 = 0.0
    s2 = 0.0
    for i in range(n):
        s = (muestras[i] - media) + coeficiente * s1 - s2
        s2 = s1
        s1 = s

    potencia = s1 * s1 + s2 * s2 - coeficiente * s1 * s2
    if potencia <= 0:
        return 0.0
    return 2.0 * math.sqrt(potencia) / n


def _medir_selectivo(radar, frecuencia, con_tono, n=800):
    """
    Captura una ventana y devuelve su nivel de banda ancha y el de una sola frecuencia.

    La captura se separa del procesamiento para muestrear a la maxima velocidad:
    dentro del lazo no ocurre nada mas que leer y guardar.

    Retorna:
        rms: Valor eficaz de toda la ventana, util para vigilar la saturacion.
        bin_amplitud: Amplitud estimada en la frecuencia pedida.
        val_min, val_max: Extremos, para detectar recorte.
    """
    n = min(n, len(radar.datos))
    if con_tono:
        radar.emisor.tono(frecuencia)
    try:
        t0 = time.monotonic_ns()
        for i in range(n):
            radar.datos[i] = radar.mic.value
        fs = n / ((time.monotonic_ns() - t0) / 1e9)
    finally:
        radar.emisor.silencio()

    suma = 0
    suma_cuad = 0
    val_min = ESCALA_ADC
    val_max = 0
    for i in range(n):
        v = radar.datos[i]
        suma += v
        suma_cuad += v * v
        if v > val_max:
            val_max = v
        if v < val_min:
            val_min = v
    varianza = (n * suma_cuad - suma * suma) / (n * n)
    rms = math.sqrt(varianza) if varianza > 0 else 0.0

    return rms, _goertzel(radar.datos, n, frecuencia, fs), val_min, val_max


def _parecido(referencia, tramo):
    """
    Coeficiente de correlacion normalizado entre dos secuencias del mismo largo.

    Vale 1 cuando una es copia exacta de la otra salvo un factor de escala, y 0
    cuando no guardan relacion. Al normalizar por las energias, el resultado no
    depende del volumen ni de la ganancia: mide solo el parecido de la forma, que
    es de lo que depende la correlacion para funcionar.
    """
    n = min(len(referencia), len(tramo))
    producto = 0.0
    energia_a = 0.0
    energia_b = 0.0
    for i in range(n):
        a = referencia[i]
        b = tramo[i]
        producto += a * b
        energia_a += a * a
        energia_b += b * b
    if energia_a <= 0 or energia_b <= 0:
        return 0.0
    return abs(producto) / math.sqrt(energia_a * energia_b)


def _db(relacion):
    """
    Expresa una relacion de amplitudes en decibeles.

    Se aplica cambio de base sobre math.log porque varias compilaciones de
    CircuitPython omiten math.log10.
    """
    if relacion <= 0:
        return float("-inf")
    return 20.0 * (math.log(relacion) / math.log(10))


# =============================================================================
# 1 y 2 - LOS DOS ESCALONES SIMPLES
# =============================================================================

def tono_continuo(radar):
    """
    Emite un tono constante, sin medir nada. La prueba se hace con el oido.

    Es el primer escalon del diagnostico y el unico que no depende del software.
    Las demas pruebas alternan emision y silencio, lo que vuelve confuso escuchar
    si el sonido se corta; aqui el tono no para nunca, de modo que cualquier
    interrupcion, crujido o cambio de volumen resulta evidente.

    Sirve para localizar una conexion intermitente meneando los cables mientras
    suena: el oido detecta el corte en el instante en que ocurre, sin promedios ni
    ventanas de por medio. Si el tono se mantiene estable durante un minuto, la
    cadena de transmision no es la que falla.
    """
    print("  Suena un tono continuo de {} Hz. Ctrl-C para parar.".format(FREC_TONO))
    print()
    print("  Escucha, y mientras suena mene un cable a la vez:")
    print("    1. GP22 al INPUT del amplificador")
    print("    2. POWER + y POWER - del amplificador")
    print("    3. Los dos cables del parlante")
    print("    4. Las patas del modulo amplificador")
    print()
    print("  Si el sonido se corta o cruje al tocar uno, ese es el cable.")
    print("  Si se mantiene perfecto, el transmisor no es el problema.")
    radar.emisor.tono(FREC_TONO)
    try:
        while True:
            time.sleep(0.5)
    except KeyboardInterrupt:
        print()
        print("  Estable -> el transmisor esta bien, seguir con la prueba 3.")
        print("  Se cortaba -> el cable que lo provocaba es el culpable.")
    finally:
        radar.emisor.silencio()


def reposo_continuo(radar):
    """
    Vigila el nivel de reposo del microfono en vivo, para cazar contactos marginales.

    Es el equivalente del tono continuo pero del lado receptor. El reposo del
    MAX4466 vale la mitad de su alimentacion y no depende de lo que suene, de modo
    que en condiciones sanas es un numero casi constante. Cualquier salto delata
    que el chip perdio momentaneamente alimentacion o referencia, que es justo lo
    que produce capturas buenas alternando con basura.

    Se compara contra la mediana de las ultimas lecturas y no contra la anterior:
    asi una sola lectura mala no desplaza la referencia y los saltos siguientes se
    siguen midiendo contra el valor sano.

    Las primeras lecturas se marcan como calentamiento y no se juzgan. El MAX4466
    lleva un condensador de acoplamiento que tarda algunos segundos en asentarse
    tras un encendido o una perturbacion, y esa deriva inicial es suave y normal,
    no un contacto defectuoso. Evaluarla daria un falso positivo justo al arrancar,
    que es cuando mas se mira.
    """
    print("  Vigilando el reposo del microfono. Ctrl-C para parar.")
    print()
    print("  Mene un cable a la vez del lado del MICROFONO:")
    print("    1. OUT  -> GP26 (pin 31)")
    print("    2. VCC  -> 3V3  (pin 36)")
    print("    3. GND  -> AGND (pin 33)")
    print("    4. Las patas del modulo MAX4466")
    print()
    print("  {:>9} {:>9} {:>7}  {}".format("reposo", "cambio", "V", "estado"))

    calentamiento = 15
    historial = []
    saltos = 0
    lectura = 0
    try:
        while True:
            lectura += 1
            media, _, _, _ = _medir_ventana(radar.mic, 0.1)
            historial.append(media)
            if len(historial) > 9:
                historial.pop(0)
            ordenados = sorted(historial)
            referencia = ordenados[len(ordenados) // 2]
            cambio = media - referencia

            if lectura <= calentamiento:
                print("  {:>9.0f} {:>+9.0f} {:>7.2f}  calentando".format(
                    media, cambio, media / ESCALA_ADC * 3.3))
                continue

            if abs(cambio) > 1500:
                estado_txt = "SALTO GRANDE <== ese cable"
                saltos += 1
            elif abs(cambio) > 400:
                estado_txt = "inestable"
                saltos += 1
            else:
                estado_txt = ""
            print("  {:>9.0f} {:>+9.0f} {:>7.2f}  {}".format(
                media, cambio, media / ESCALA_ADC * 3.3, estado_txt))
    except KeyboardInterrupt:
        print()
        if saltos:
            print("  Hubo {} lectura(s) inestable(s). Si coincidieron con tocar".format(
                saltos))
            print("  un cable concreto, ese es. Cambialo de agujero y repeti.")
        else:
            print("  Reposo estable: la conexion del microfono no es el problema.")
            print("  Seguir con la prueba 3.")


# =============================================================================
# 3 - MUESTREO Y FIDELIDAD
# =============================================================================

def fidelidad(radar):
    """
    Responde dos preguntas: si se muestrea bien y si lo recibido se parece a lo emitido.

    Son las dos condiciones de las que depende todo lo demas. El muestreo fija el
    techo del sistema: por debajo de Nyquist la parte alta del chirp se pliega, y un
    periodo irregular deforma el eje temporal sobre el que se mide el retardo. El
    parecido mide si la onda que vuelve conserva la forma de la que se emitio, que
    es lo unico que la correlacion puede reconocer.

    El parecido se expresa como coeficiente de correlacion normalizado, entre 0 y 1.
    Al dividir por las energias, el numero no depende del volumen ni de la ganancia:
    un eco debil pero fiel da un valor alto, y uno fuerte pero deformado da uno bajo.

    Se mide ademas la repetibilidad entre dos disparos consecutivos. Un sistema que
    emite igual cada vez da un valor cercano a uno; si baja, la emision no se repite
    y ningun ajuste de ganancia tiene sentido hasta resolverlo.
    """
    # La velocidad se mide con capturas reales, con la emision en curso. Un lazo
    # que solo lee resulta mas rapido, porque durante la emision el DMA de audio
    # roba ciclos al procesador. Comparar contra esa medida daria un desajuste
    # aparente que no existe: son dos condiciones distintas.
    tasas = []
    for _ in range(5):
        tasas.append(main.capturar(radar.emisor, radar.mic, radar.datos))
        time.sleep(0.03)
    tasas.sort()
    fs_cruda = tasas[len(tasas) // 2]

    # La dispersion entre capturas es lo que de verdad afecta a la correlacion: la
    # plantilla se construye una vez y debe seguir valiendo en las siguientes.
    dispersion = 100.0 * (tasas[-1] - tasas[0]) / fs_cruda

    fs_captura = fs_cruda / radar.decimacion
    desvio = 100.0 * abs(fs_captura - radar.fs) / radar.fs

    nyquist_ok = radar.fs / 2 > main.CHIRP_F_FINAL
    print("  MUESTREO  (medido sobre {} capturas reales)".format(len(tasas)))
    print("    fs cruda         : {:>8.0f} Hz".format(fs_cruda))
    print("    fs efectiva      : {:>8.0f} Hz  (decimacion {})".format(
        radar.fs, radar.decimacion))
    print("    Nyquist          : {:>8.0f} Hz  vs chirp {} Hz   {}".format(
        radar.fs / 2, main.CHIRP_F_FINAL, "OK" if nyquist_ok else "ALIASING"))
    print("    dispersion entre capturas: {:>5.2f} %             {}".format(
        dispersion, "OK" if dispersion < 0.5 else "alta"))
    print("    desvio de la plantilla   : {:>5.2f} %             {}".format(
        desvio, "OK" if desvio < 0.3 else "DESAJUSTADA"))
    print("    paso en distancia: {:>7.2f} cm por muestra".format(
        main.VELOCIDAD_SONIDO / (2 * radar.fs) * 100))

    # Capturas unicas, no promediadas: lo que se mide aqui es la fidelidad de un
    # disparo, y promediar varios la enmascararia.
    primera = array("f", bytes(4 * radar.n_proc))
    radar.capturar_una()
    main.realzar_altas(radar.ventana)
    main.quitar_continua(radar.ventana)
    for i in range(radar.n_proc):
        primera[i] = radar.ventana[i]

    radar.capturar_una()
    main.realzar_altas(radar.ventana)
    main.quitar_continua(radar.ventana)

    # El tramo se alinea con el pico del directo antes de comparar: un desfase de
    # unas pocas muestras bastaria para que dos senales identicas parecieran no
    # tener relacion, porque a estas frecuencias eso ya es medio ciclo.
    corr = main.correlacion_fft(radar.plantilla, primera, radar.fs)
    d = main.buscar_directo(corr)
    m = min(radar.n_emision_proc, radar.n_proc - d)
    tramo_a = [primera[d + i] for i in range(m)]
    tramo_b = [radar.ventana[d + i] for i in range(m)]
    plantilla = [radar.plantilla[i] for i in range(m)]

    rho_forma = _parecido(plantilla, tramo_a)
    rho_repite = _parecido(tramo_a, tramo_b)

    def juicio(valor):
        if valor > 0.7:
            return "BUENO"
        if valor > 0.4:
            return "regular"
        return "MALO"

    print()
    print("  FIDELIDAD DE LA ONDA")
    print("    pico directo en  : indice {}".format(d))
    print("    parecido con la plantilla    : {:.2f}   {}".format(
        rho_forma, juicio(rho_forma)))
    print("    repetibilidad entre disparos : {:.2f}   {}".format(
        rho_repite, juicio(rho_repite)))
    print()

    if not nyquist_ok:
        print("  Nyquist por debajo del chirp: la parte alta se pliega. Bajar")
        print("  CHIRP_F_FINAL o reducir la decimacion.")
    elif desvio > 0.3:
        print("  La plantilla se construyo con una velocidad distinta de la real.")
        print("  La fase acumulada se desvia a lo largo de la emision y arruina la")
        print("  correlacion. El margen es de unas tres decimas de por ciento:")
        print("  a 7 kHz durante 20 ms, medio por ciento ya desfasa media vuelta.")
        print("  Reiniciar la placa para que la plantilla se construya de nuevo.")
    elif rho_repite < 0.5:
        print("  La emision no se repite entre disparos. Si la prueba 1 sonaba")
        print("  estable, el problema esta en la captura y no en el cableado.")
    elif rho_forma < 0.4:
        print("  Lo que vuelve no se parece a lo emitido. Puede ser saturacion o")
        print("  que el parlante no reproduzca la banda: ver la prueba 5.")
    elif rho_forma > 0.7 and rho_repite > 0.7:
        print("  Muestreo y forma de onda correctos. Seguir con la prueba 6.")
    else:
        print("  Aceptable pero mejorable. Subir el volumen suele elevar las dos")
        print("  cifras, porque aleja la senal del ruido sin deformarla.")


# =============================================================================
# 4 y 5 - CALIBRACION
# =============================================================================

def calibrar_pico(radar):
    """
    Ajusta la ganancia por la amplitud del trayecto directo, en condiciones reales.

    No se cuentan vueltas del tornillo porque la ganancia por vuelta depende de las
    resistencias del modulo. Se mide la amplitud, que es lineal con la ganancia: al
    duplicar una se duplica la otra, de modo que basta una regla de tres para saber
    cuanto falta.

    El criterio acota por arriba y por abajo. Por arriba manda el trayecto directo,
    que es el sonido mas fuerte que el microfono recibe; se apunta a que su pico
    ocupe alrededor del 65 % del rango, porque el recorte es una no linealidad que
    rompe el modelo LTI sobre el que se apoya la correlacion. Por abajo manda el
    ruido propio del conversor: si el piso cae por debajo de unos 3 LSB, el ADC deja
    de resolver las senales debiles y el eco se pierde antes de poder medirlo.

    Se emite el chirp real, no un tono, y varias veces por linea. Con una sola
    captura no se puede distinguir una ganancia baja de una emision que fallo: las
    dos dan un pico chico. Comparando entre repeticiones, la dispersion lo delata.
    """
    print("  Parlante y microfono en su POSICION FINAL, volumen de trabajo.")
    print("  Gira el tornillo siguiendo la columna de accion. Ctrl-C para salir.")
    print()
    print("  {:>9} {:>8} {:>8} {:>7}  {:<26} {}".format(
        "piso LSB", "pico", "% rango", "disp", "accion", "barra"))

    escala = ESCALA_ADC / 2.0
    repeticiones = 5
    try:
        while True:
            time.sleep(ESPERA_SILENCIO_S)
            piso_rms, _, _, _ = _medir_selectivo(radar, FREC_TONO, False)

            picos = []
            recorta = False
            for _ in range(repeticiones):
                main.capturar(radar.emisor, radar.mic, radar.datos)
                suma = 0
                val_min = ESCALA_ADC
                val_max = 0
                n = len(radar.datos)
                for i in range(n):
                    v = radar.datos[i]
                    suma += v
                    if v > val_max:
                        val_max = v
                    if v < val_min:
                        val_min = v
                reposo = suma / n
                picos.append(max(val_max - reposo, reposo - val_min))
                if val_min <= LSB or val_max >= ESCALA_ADC - LSB:
                    recorta = True
                time.sleep(0.02)

            ordenados = sorted(picos)
            pico = ordenados[len(ordenados) // 2]
            dispersion = (ordenados[-1] / ordenados[0]) if ordenados[0] > 0 else 99.0
            fraccion = pico / escala
            piso_lsb = piso_rms / LSB
            factor = PICO_OBJETIVO / fraccion if fraccion > 0 else 99.0

            # La dispersion se juzga antes que el nivel: si la emision no se repite
            # igual, cualquier recomendacion de ganancia estaria calculada sobre un
            # numero que no representa nada estable.
            if dispersion > 2.0:
                accion = "INESTABLE x{:.0f}, ver prueba 1".format(dispersion)
            elif recorta:
                accion = "RECORTA, baja ya"
            elif fraccion > 0.80:
                accion = "BAJAR, x{:.2f}".format(factor)
            elif fraccion < 0.50:
                accion = "SUBIR, x{:.1f}".format(factor)
            elif piso_lsb < PISO_MINIMO_LSB:
                accion = "piso bajo ({:.1f} LSB), SUBIR".format(piso_lsb)
            else:
                accion = "<== LISTO, dejalo ahi"

            barra = "#" * int(30 * min(fraccion, 1.0))
            if fraccion > 0.80:
                barra += "!"
            print("  {:>9.1f} {:>8.0f} {:>7.0f}% {:>7.1f}  {:<26} {}".format(
                piso_lsb, pico, 100 * fraccion, dispersion, accion, barra))
    except KeyboardInterrupt:
        print()
        print("  Objetivo: pico entre 50 y 80 % del rango, dispersion bajo 2x,")
        print("  piso sobre {:.0f} LSB.".format(PISO_MINIMO_LSB))


def respuesta_frecuencia(radar):
    """
    Mide el contraste a lo largo de la banda audible util.

    Un parlante pequeno no responde parejo: su curva tiene picos y valles de decenas
    de decibeles, y el microfono agrega la suya. Medir un solo tono corre el riesgo
    de caer en un valle y concluir que la cadena no funciona.

    Cada punto se mide en su propia frecuencia y no en banda ancha: de otro modo el
    ruido de sala domina por igual en todas y la curva sale plana.

    El resultado define el diseno: conviene situar la banda del chirp donde el par
    transductor efectivamente responde, porque la ganancia de la correlacion no
    puede recuperar energia que nunca se emitio.
    """
    frecuencias = (1000, 1500, 2000, 2500, 3000, 4000, 5000, 6000, 7000, 8000)
    print("  {:>7} {:>9} {:>9} {:>8}  {}".format(
        "Hz", "ruido", "senal", "dB", "respuesta"))
    medidas = []
    for frecuencia in frecuencias:
        time.sleep(ESPERA_SILENCIO_S)
        _, off, min_off, max_off = _medir_selectivo(radar, frecuencia, False)
        _, on, min_on, max_on = _medir_selectivo(radar, frecuencia, True)
        val_min = min(min_off, min_on)
        val_max = max(max_off, max_on)
        db = _db(on / off) if off > 0 else 0.0
        medidas.append((frecuencia, db))
        nota = ("SATURADO" if val_min <= LSB or val_max >= ESCALA_ADC - LSB
                else "#" * min(max(int(db), 0), 34))
        print("  {:>7} {:>9.1f} {:>9.1f} {:>+8.1f}  {}".format(
            frecuencia, off, on, db, nota))

    mejor_f, mejor_db = max(medidas, key=lambda par: par[1])
    peor_db = min(db for _, db in medidas)
    utiles = [f for f, db in medidas if db >= mejor_db - 6.0]
    print()
    print("  Mejor: {} Hz con {:+.1f} dB   |   rango de la curva: {:.1f} dB".format(
        mejor_f, mejor_db, mejor_db - peor_db))
    if mejor_db < 10.0:
        print("  Ninguna frecuencia despega del ruido. El problema no es la banda")
        print("  sino la cadena de transmision o el nivel general.")
    else:
        print("  Banda util (dentro de 6 dB del maximo): {} a {} Hz.".format(
            min(utiles), max(utiles)))
        print("  Conviene que CHIRP_F_INICIAL y CHIRP_F_FINAL caigan ahi.")


# =============================================================================
# 6 y 7 - VALIDACION Y DATOS
# =============================================================================

def validar_distancia(radar):
    """
    Contrasta las lecturas del radar contra una distancia medida con regla.

    Separa dos cosas que suelen confundirse. El sesgo es cuanto se desvia la media
    de las lecturas respecto al valor real, y delata un error sistematico: una
    velocidad del sonido mal supuesta, o un origen de tiempos corrido. La dispersion
    es cuanto varian las lecturas entre si, y delata ruido. Un sesgo constante se
    corrige; una dispersion grande solo se reduce con mas senal o mas promediado.

    La tasa de deteccion importa tanto como la exactitud: un radar que acierta pero
    solo responde una de cada cinco veces no sirve para una defensa en vivo.
    """
    try:
        real = float(input("  Distancia real al objeto, en cm> ").strip())
    except ValueError:
        print("  Valor invalido.")
        return
    repeticiones = 10

    print("  Midiendo {} veces contra {:.1f} cm...".format(repeticiones, real))
    print("  {:>4} {:>9} {:>9} {:>9}".format("n", "razon", "cm", "error"))

    lecturas = []
    for i in range(repeticiones):
        distancia, _, _, razon = radar.medir()
        if distancia is None:
            print("  {:>4} {:>9.1f} {:>9} {:>9}".format(i + 1, razon, "---", "-"))
        else:
            lecturas.append(distancia)
            print("  {:>4} {:>9.1f} {:>9.1f} {:>+9.1f}".format(
                i + 1, razon, distancia, distancia - real))

    print()
    detectadas = len(lecturas)
    print("  Detecciones: {} de {}  ({:.0f}%)".format(
        detectadas, repeticiones, 100.0 * detectadas / repeticiones))
    if detectadas < 2:
        print("  Muy pocas lecturas para juzgar. Subir nivel con la prueba 4,")
        print("  acercar el objeto, o usar un reflector mas grande y plano.")
        return

    media = sum(lecturas) / detectadas
    varianza = sum((v - media) ** 2 for v in lecturas) / detectadas
    desviacion = math.sqrt(varianza)
    sesgo = media - real

    print("  Media       : {:.1f} cm".format(media))
    print("  Sesgo       : {:+.1f} cm   (error sistematico)".format(sesgo))
    print("  Dispersion  : {:.1f} cm   (desviacion tipica)".format(desviacion))
    print()

    if detectadas < repeticiones * 0.7:
        print("  Detecta de forma intermitente: hace falta mas senal antes de")
        print("  preocuparse por la exactitud.")
    elif desviacion > 5.0:
        print("  Lecturas dispersas: esta eligiendo picos distintos cada vez.")
        print("  Subir PROMEDIOS en main.py o mejorar el nivel acustico.")
    elif abs(sesgo) > 3.0:
        print("  Sesgo sistematico. Si se repite a varias distancias con el mismo")
        print("  signo y magnitud, es un corrimiento del origen de tiempos; si")
        print("  crece con la distancia, es la velocidad del sonido supuesta.")
    else:
        print("  Concuerda con la regla. Repetir a dos o tres distancias mas para")
        print("  confirmar que el acuerdo se mantiene en todo el rango.")


def volcar(radar):
    """
    Vuelca la ventana capturada por el puerto serie, para analizarla fuera de la placa.

    Con las muestras en la mano se puede probar cualquier variante del procesamiento
    sin volver a tocar el hardware. Conviene tomar dos volcados de la misma escena
    con el objeto en posiciones distintas: comparandolos se determina si el eco esta
    presente en los datos, que es la pregunta previa a cualquier ajuste.
    """
    etiqueta = input("  Etiqueta (ej. objeto_20cm)> ").strip() or "captura"
    radar.capturar_una()
    print("### {}".format(etiqueta))
    print("# fs={:.1f} decimacion={} n_emision={} n_ventana={}".format(
        radar.fs, radar.decimacion, radar.n_emision_proc, radar.n_proc))
    print("# chirp={}-{}Hz dur={}ms emision={} (captura unica)".format(
        main.CHIRP_F_INICIAL, main.CHIRP_F_FINAL,
        main.CHIRP_DURACION_MS, radar.modo_emision))
    linea = []
    for i in range(radar.n_proc):
        linea.append(str(int(radar.ventana[i])))
        if len(linea) == 16:
            print(",".join(linea))
            linea = []
    if linea:
        print(",".join(linea))
    print("### fin {}".format(etiqueta))


HERRAMIENTAS = (
    ("Tono continuo: escuchar si se corta (transmisor)", tono_continuo),
    ("Reposo continuo: vigilar el microfono (receptor)", reposo_continuo),
    ("Muestreo y fidelidad de la onda", fidelidad),
    ("Calibrar ganancia por amplitud del directo", calibrar_pico),
    ("Respuesta en frecuencia del par", respuesta_frecuencia),
    ("Validar contra una distancia conocida", validar_distancia),
    ("Volcar captura cruda", volcar),
)


def main_test():
    """Inicializa el radar una vez y ofrece las herramientas de calibracion."""
    print()
    print("=" * 56)
    print(" CALIBRACION - RADAR ACUSTICO")
    print("=" * 56)
    radar = Radar()
    print(" calibrando umbral...")
    radar.calibrar_umbral()
    print(" fs {:.0f} Hz | chirp {}-{} Hz | emision {} | rango {:.0f}-{:.0f} cm".format(
        radar.fs, main.CHIRP_F_INICIAL, main.CHIRP_F_FINAL,
        radar.modo_emision, RANGO_MIN_M * 100, radar.rango_max * 100))
    print(" umbral aprendido: {:.1f}".format(radar.umbral))

    try:
        while True:
            print()
            for i, (titulo, _) in enumerate(HERRAMIENTAS):
                print("  {}. {}".format(i + 1, titulo))
            print("  q. Salir")
            opcion = input(" > ").strip().lower()
            if opcion == "q":
                return
            if not opcion.isdigit() or not (1 <= int(opcion) <= len(HERRAMIENTAS)):
                print(" Opcion invalida.")
                continue
            titulo, funcion = HERRAMIENTAS[int(opcion) - 1]
            print()
            print("--- {} ---".format(titulo))
            try:
                funcion(radar)
            except KeyboardInterrupt:
                print()
            except Exception as error:
                print("  ERROR: {}: {}".format(type(error).__name__, error))
    finally:
        radar.liberar()


if __name__ == "__main__":
    main_test()
