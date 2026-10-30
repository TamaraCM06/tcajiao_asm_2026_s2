"""Ejecuta el prototipo de reducción de ruido sin abrir ni ejecutar un notebook.

Desde proyecto_1_grupal: .venv/bin/python prototipo.py --caso todos
Utiliza --salida para elegir un directorio final distinto. Las señales se generan
en memoria desde las semillas; se exportan figuras, WAV, muestras y tablas.
"""

import argparse
import json
import sys
import time
from importlib.metadata import version
from pathlib import Path

import matplotlib

matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
from scipy import signal

from tarea1_grupo1.src.datos import archivos
from tarea1_grupo1.src.filtros import diseno_temporal as dt
from tarea1_grupo1.src.filtros import filtrado_espectral as fe
from tarea1_grupo1.src.filtros import filtros_temporales as ft
from tarea1_grupo1.src.mediciones import evaluacion, metricas
from tarea1_grupo1.src.senales import analisis_fourier as af, generacion
from tarea1_grupo1.src.visualizacion import graficas

RAIZ = Path(__file__).resolve().parent


def guardar_figura(figura, ruta):
    """Guarda y cierra una figura, sin abrir ventanas ni alterar los datos."""
    figura.savefig(ruta)
    plt.close(figura)


def exportar_fourier(ajustes, salida, tolerancia):
    """Exporta el ejemplo independiente DFT/FFT/IFFT y verifica su reconstrucción."""
    fs, n = ajustes['fs_Hz'], ajustes['numero_muestras']
    f1, f2 = ajustes['frecuencias_Hz']
    a1, a2 = ajustes['amplitudes']
    t = np.arange(n) / fs
    x = a1 * np.cos(2 * np.pi * f1 * t) + a2 * np.sin(2 * np.pi * f2 * t)
    directa, fft = af.dft_directa(x), np.fft.fft(x)
    errores = [float(np.max(np.abs(directa - fft))), float(np.max(np.abs(np.fft.ifft(fft) - x)))]
    if max(errores) > tolerancia:
        raise ValueError('El ejemplo Fourier supera la tolerancia de reconstrucción.')
    frecuencias = np.fft.fftfreq(n, 1 / fs)
    filas = []
    for k in np.flatnonzero(np.abs(fft) > tolerancia):
        filas.append({'k': int(k), 'frecuencia_Hz': frecuencias[k],
                      'coeficiente_real': fft[k].real, 'coeficiente_imaginario': fft[k].imag,
                      'magnitud': abs(fft[k]), 'fase_grados': np.angle(fft[k], deg=True)})
    archivos.guardar_csv(salida / 'fourier_coeficientes.csv', filas)
    archivos.guardar_csv(salida / 'fourier_verificacion.csv', [
        {'comparacion': nombre, 'error_maximo': error, 'tolerancia': tolerancia}
        for nombre, error in zip(('DFT directa - FFT', 'IFFT - muestras'), errores)
    ])
    unilateral = fft[:n // 2 + 1]
    amplitudes = 2 * np.abs(unilateral) / n
    amplitudes[0] /= 2
    if n % 2 == 0:
        amplitudes[-1] /= 2
    componentes = np.abs(unilateral) > tolerancia
    amplitudes[~componentes] = 0
    guardar_figura(graficas.graficar_ejemplo_fourier(
        t, x, np.fft.rfftfreq(n, 1 / fs), amplitudes,
        np.angle(unilateral, deg=True), componentes,
    ), salida / 'figuras/analisis_fourier.png')


def disenar_filtro(casos, configs, ajustes, salida, tolerancia):
    """Diseña el FIR, compara candidatos IIR y verifica la implementación temporal."""
    nombre = next(iter(casos))
    fs = casos[nombre]['fs']
    if any(c['fs'] != fs for c in casos.values()):
        raise ValueError('Los casos de una ejecución deben compartir el muestreo.')
    paso, rechazo = ajustes['frecuencia_paso_Hz'], ajustes['frecuencia_rechazo_Hz']
    rizado_max, atenuacion_min = ajustes['rizado_maximo_dB'], ajustes['atenuacion_minima_dB']
    b, beta = dt.disenar_fir_kaiser(paso, rechazo, atenuacion_min, fs)
    retardo = (len(b) - 1) // 2
    limpia, mezcla = casos[nombre]['clean'], casos[nombre]['noisy']
    candidatos = dt.disenar_iir(paso, rechazo, rizado_max, atenuacion_min, fs)
    snr_fir, _ = metricas.snr_mejor_retardo(limpia, signal.lfilter(b, 1, mezcla))
    filas = [{'caso_evaluado': nombre, 'filtro': 'FIR Kaiser', 'orden': len(b) - 1,
              'mac_por_muestra': len(b), 'coeficientes': len(b),
              'retardo_grupo_muestras': f'{retardo} (constante)', 'snr_salida_dB': snr_fir}]
    for etiqueta, (orden, sos) in candidatos.items():
        bi, ai = signal.sos2tf(sos)
        gd = signal.group_delay((bi, ai), w=np.array(configs[nombre]['frecuencias_utiles_Hz']), fs=fs)[1]
        snr, _ = metricas.snr_mejor_retardo(limpia, signal.sosfilt(sos, mezcla))
        costo = 5 * int(np.ceil(orden / 2))
        filas.append({'caso_evaluado': nombre, 'filtro': f'IIR {etiqueta}', 'orden': orden,
                      'mac_por_muestra': costo, 'coeficientes': costo,
                      'retardo_grupo_muestras': f'{gd.min():.1f} – {gd.max():.1f}', 'snr_salida_dB': snr})
    archivos.guardar_csv(salida / 'filtro_temporal/comparacion_tipos_filtro.csv', filas)
    archivos.guardar_csv(salida / 'filtro_temporal/coeficientes_fir.csv',
                         [{'k': k, 'b_k': f'{v:.17g}'} for k, v in enumerate(b)])
    be, ae = signal.sos2tf(candidatos['Elíptico'][1])
    ceros, polos = dt.polos_ceros(b)
    ceros_e, polos_e = dt.polos_ceros(be, ae)
    guardar_figura(graficas.graficar_polos_ceros(ceros, polos, ceros_e, polos_e, len(b)),
                   salida / 'figuras/polos_ceros_fir_iir.png')
    f, _, magnitud, fase, gd = dt.respuesta_frecuencia(b, 1.0, fs)
    rizado, atenuacion = dt.medir_especificacion(b, 1.0, fs, paso, rechazo)
    guardar_figura(graficas.graficar_respuesta_temporal(
        f, magnitud, fase, gd, fs, paso, rechazo, rizado_max, atenuacion_min, retardo,
        [dict(id=k, **cfg) for k, cfg in configs.items()], rizado, atenuacion,
    ), salida / 'figuras/respuesta_fir.png')
    if rizado > rizado_max or atenuacion < atenuacion_min:
        raise ValueError('El FIR diseñado no cumple las especificaciones.')
    for c in casos.values():
        referencia = signal.lfilter(b, 1, c['noisy'])
        for y in (ft.ecuacion_diferencias(b, [1.0], c['noisy']),
                  ft.filtrar_por_bloques(b, c['noisy'], ajustes['tam_bloque'])):
            if np.max(np.abs(y - referencia)) > tolerancia:
                raise ValueError('La implementación FIR no coincide con SciPy.')
    if np.max(np.abs(ft.ecuacion_diferencias(be, ae, mezcla) - signal.lfilter(be, ae, mezcla))) > tolerancia:
        raise ValueError('La ecuación de diferencias IIR no coincide con SciPy.')
    return b, retardo, {'caso_diseno': nombre, 'fs_Hz': fs, 'beta': float(beta),
                        'numero_coeficientes': len(b), 'orden': len(b) - 1,
                        'coeficientes': b.tolist(), 'retardo_muestras': retardo,
                        'retardo_teorico_s': retardo / fs}


def evaluar_casos(casos, b, retardo, ajustes, salida):
    """Aplica ambas rutas a la misma entrada e intervalo y exporta sus salidas completas."""
    bloque = ajustes['fir']['tam_bloque']

    def filtrar(muestras):
        """Aplica un FIR causal nuevo con estado por bloques."""
        return ft.filtrar_por_bloques(b, muestras, bloque)

    filas, medidas_fir, medidas_espectrales = [], {}, {}
    salidas_fir, salidas_espectrales = {}, {}
    for nombre, c in casos.items():
        longitud = len(c['clean']) - retardo
        if longitud < 1:
            raise ValueError(f'{nombre}: la señal es más corta que el retardo FIR.')
        identidad = fe.filtrar_senal(c['noisy'], c['fs'], **{**ajustes['espectral'], 'factor': 1})
        if np.max(np.abs(identidad - c['noisy'])) > ajustes['tolerancia']:
            raise ValueError(f'{nombre}: falla la reconstrucción espectral sin atenuación.')
        mf = evaluacion.evaluar_temporal(c['clean'], c['noise'], filtrar, retardo)
        salidas_fir[nombre] = mf.pop('salida')
        completa = filtrar(c['noisy'])
        archivos.guardar_wav(salida / f'filtro_temporal/salidas/{nombre}_salida_fir.wav',
                             c['fs'], completa, verificar_rango=True)
        fir = ft.FIRPorBloques(b)
        bloques = [c['noisy'][i:i + bloque] for i in range(0, len(c['noisy']), bloque)]
        inicio = time.perf_counter()
        for muestras in bloques:
            fir.procesar(muestras)
        mf.update(tiempo_por_bloque_us=1e6 * (time.perf_counter() - inicio) / len(bloques),
                  tam_bloque=bloque, salto=bloque)
        me = fe.evaluar_filtro(c['clean'], c['noise'], c['fs'],
                              longitud_evaluacion=longitud, **ajustes['espectral'])
        y = me.pop('salida')
        if len(y) != len(c['clean']) or not np.all(np.isfinite(y)):
            raise ValueError(f'{nombre}: salida espectral inválida.')
        salidas_espectrales[nombre] = y
        archivos.guardar_wav(salida / f'filtro_espectral/salidas/{nombre}_salida_espectral.wav',
                             c['fs'], y, verificar_rango=True)
        medidas_fir[nombre], medidas_espectrales[nombre] = mf, me
        limpia, mezcla = c['clean'][:longitud], c['noisy'][:longitud]
        snr = metricas.snr_db(limpia, mezcla)
        entrada = {'snr_entrada_dB': snr, 'snr_salida_dB': snr, 'delta_snr_dB': 0.0,
                   'mse': np.mean((limpia - mezcla) ** 2), 'energia_util_conservada_pct': 100.0,
                   'atenuacion_ruido_dB': 0.0, 'atenuacion_interferencia_dB': 0.0}
        columnas = ('snr_entrada_dB', 'snr_salida_dB', 'delta_snr_dB', 'mse',
                    'energia_util_conservada_pct', 'atenuacion_ruido_dB', 'snr_distorsion_util_dB',
                    'tiempo_por_bloque_us', 'tam_bloque', 'salto', 'muestras_evaluadas',
                    'atenuacion_interferencia_dB', 'memoria_trabajo_bytes')
        for metodo, valores in (('sin_filtrar', entrada), (f'fir_kaiser_{len(b)}', mf), ('espectral_umbral', me)):
            fila = {'caso': nombre, 'metodo': metodo}
            fila.update({clave: valores.get(clave, '') for clave in columnas})
            fila['muestras_evaluadas'] = longitud
            filas.append(fila)
    archivos.guardar_csv(salida / 'metricas.csv', filas)
    guardar_figura(graficas.graficar_filtrado(casos, salidas_fir, medidas_fir, 'Salida FIR (alineada)'),
                   salida / 'figuras/resultados_fir.png')
    guardar_figura(graficas.graficar_filtrado(casos, salidas_espectrales, medidas_espectrales, 'Salida espectral'),
                   salida / 'figuras/resultados_espectral.png')
    return filas, medidas_espectrales


def exportar_compromiso(casos, retardo, ajustes, salida):
    """Exporta las variantes de superposición solo si su caso está seleccionado."""
    cfg = ajustes['compromiso']
    nombre = cfg['caso']
    resultados = []
    if nombre not in casos:
        return resultados
    c = casos[nombre]
    for factor in cfg['factores']:
        parametros = {**ajustes['espectral'], 'frecuencia_minima': cfg['frecuencia_minima'], 'factor': factor}
        m = fe.evaluar_filtro(c['clean'], c['noise'], c['fs'],
                              longitud_evaluacion=len(c['clean']) - retardo, **parametros)
        m.pop('salida')
        resultados.append({'caso': nombre, 'factor': factor,
                           'frecuencia_minima': cfg['frecuencia_minima'], **m})
    archivos.guardar_csv(salida / 'filtro_espectral/compromiso_ruido_distorsion.csv', resultados)
    guardar_figura(graficas.graficar_compromiso(resultados),
                   salida / 'figuras/ruido_vs_distorsion.png')
    return resultados


def guardar_ficha(ajustes, configs, casos, diseno, medidas, compromiso, seleccion, salida):
    """Registra los ajustes efectivos en JSON y una tabla CSV de la misma información."""
    ficha = {
        'ejecucion': {'tipo_evidencia': 'simulacion', 'entrada': 'prototipo.py',
                      'seleccion': seleccion, 'casos_filtrados': list(casos)},
        'entorno': {'python': sys.version.split()[0], 'numpy': version('numpy'),
                    'scipy': version('scipy'), 'matplotlib': version('matplotlib')},
        'generacion': {'fade_ms': ajustes['fade_ms'], 'escala': 'amplitud_digital_normalizada',
                       'normalizacion': 'ganancia_comun_para_limpia_ruido_y_mezcla'},
        'fir': {**ajustes['fir'], **diseno, 'tam_bloque_muestras': ajustes['fir']['tam_bloque']},
        'espectral': {
            'ventana': 'hann',
            'tam_bloque_muestras': ajustes['espectral']['tam_bloque'],
            'frecuencia_minima_Hz': ajustes['espectral']['frecuencia_minima'],
            'ancho_Hz': ajustes['espectral']['ancho_hz'],
            'factor_amplitud': ajustes['espectral']['factor'],
            'umbral_relativo_energia': ajustes['espectral']['umbral_relativo'],
        },
        'validacion': {'tolerancia': ajustes['tolerancia']},
        'comparacion': {'retardo_fir_compensado_muestras': diseno['retardo_muestras'],
                        'salida_fir_wav': 'causal_completa', 'salida_espectral_wav': 'completa_sin_desplazamiento',
                        'tiempos_y_memoria': 'prototipo_en_computadora'},
        'ejemplo_fourier': ajustes['ejemplo_fourier'],
    }
    for nombre, c in casos.items():
        ficha[nombre] = {**configs[nombre], 'numero_muestras': len(c['clean']),
                         'duracion_generada_s': len(c['clean']) / c['fs']}
        m = medidas[nombre]
        ficha[f'evaluacion_{nombre}'] = {
            'muestras_evaluadas': m['muestras_evaluadas'], 'fft_figuras_muestras': len(c['clean']),
            'fft_procesamiento_muestras': m['tam_bloque'], 'salto_espectral_muestras': m['salto'],
            'separacion_bins_Hz': c['fs'] / m['tam_bloque'],
            'duracion_bloque_espectral_s': m['tam_bloque'] / c['fs'],
            'intervalo_entre_bloques_espectrales_s': m['salto'] / c['fs'],
        }
    for i, m in enumerate(compromiso, start=1):
        ficha[f'compromiso_{i}'] = {**ficha['espectral'], 'caso': m['caso'],
                                   'frecuencia_minima_Hz': m['frecuencia_minima'], 'factor_amplitud': m['factor']}
    archivos.guardar_json(salida / 'configuracion_ejecutada.json', ficha)
    filas = []
    for grupo, parametros in ficha.items():
        for parametro, valor in parametros.items():
            if isinstance(valor, (list, bool)) or valor is None:
                valor = json.dumps(valor, ensure_ascii=False)
            filas.append({'grupo': grupo, 'parametro': parametro, 'valor': valor})
    archivos.guardar_csv(salida / 'configuracion.csv', filas)


def ejecutar_prototipo(ruta_config, seleccion, salida):
    """Genera y evalúa los casos solicitados sin usar resultados previos ni notebooks."""
    ruta_config = Path(ruta_config).resolve()
    ajustes = archivos.cargar_configuraciones(ruta_config)
    disponibles = archivos.cargar_configuraciones(ruta_config.parent / ajustes['archivo_casos'])
    if not disponibles:
        raise ValueError('El archivo de configuración no contiene casos.')
    nombres = list(disponibles) if seleccion == 'todos' else [seleccion]
    if any(nombre not in disponibles for nombre in nombres):
        raise ValueError(f'Caso desconocido: {seleccion}. Disponibles: {", ".join(disponibles)} o todos.')
    configs = {nombre: dict(disponibles[nombre]) for nombre in nombres}
    salida = Path(salida).resolve()
    (salida / 'figuras').mkdir(parents=True, exist_ok=True)
    plt.style.use('seaborn-v0_8-whitegrid')
    plt.rcParams.update({'savefig.dpi': 150, 'savefig.bbox': 'tight', 'font.size': 12})
    casos = {}
    for nombre, cfg in configs.items():
        c = generacion.generar_caso_configurado(cfg, ajustes['fade_ms'])
        casos[nombre] = c
        cfg.update(snr_obtenida_dB=float(c['snr']), ganancia_comun=float(c['gain']))
        for clave, archivo in (('clean', '01_referencia_limpia.wav'), ('noise', '02_ruido.wav'),
                               ('noisy', '03_entrada_contaminada.wav')):
            archivos.guardar_wav(salida / 'pruebas' / nombre / archivo, c['fs'], c[clave], verificar_rango=True)
        archivos.guardar_muestras(salida / f'muestras/{nombre}_muestras.csv', c)
        fig = graficas.graficar_generacion(c['t'], c['clean'], c['noisy'], c['fs'], nombre, noise=c['noise'])
        fig.savefig(salida / f'figuras/{nombre}_senales.png', dpi=300)
        plt.close(fig)
    archivos.guardar_json(salida / 'configuraciones.json', configs)
    exportar_fourier(ajustes['ejemplo_fourier'], salida, ajustes['tolerancia'])
    b, retardo, diseno = disenar_filtro(casos, configs, ajustes['fir'], salida, ajustes['tolerancia'])
    filas, medidas = evaluar_casos(casos, b, retardo, ajustes, salida)
    compromiso = exportar_compromiso(casos, retardo, ajustes, salida)
    guardar_ficha(ajustes, configs, casos, diseno, medidas, compromiso, seleccion, salida)
    print(f'Casos: {", ".join(nombres)}')
    for fila in filas:
        print(f"{fila['caso']} | {fila['metodo']} | SNR salida: {fila['snr_salida_dB']:.3f} dB")
    print(f'Resultados: {salida}')
    return filas


def main():
    """Lee los argumentos y ejecuta el prototipo desde cualquier directorio."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--caso', default='todos', help='Identificador del JSON o todos (predeterminado).')
    parser.add_argument('--config', type=Path, default=RAIZ / 'metadatos/prototipo.json')
    parser.add_argument('--salida', type=Path, help='Directorio final de salida; no añade subcarpetas de selección.')
    args = parser.parse_args()
    salida = args.salida or RAIZ / 'resultados/simulacion' / args.caso
    try:
        ejecutar_prototipo(args.config, args.caso, salida)
    except (ValueError, FileNotFoundError, KeyError) as error:
        parser.exit(2, f'Error de configuración o ejecución: {error}\n')


if __name__ == '__main__':
    main()
