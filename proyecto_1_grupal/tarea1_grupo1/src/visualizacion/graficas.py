"""Figuras del notebook. Cada función devuelve una figura sin exportarla."""

import numpy as np
import matplotlib.pyplot as plt

from ..senales.analisis_fourier import espectro_db

# ---------------------------------------------------------------------------
# Generación y ejemplo de Fourier
# ---------------------------------------------------------------------------


def graficar_generacion(t, clean, noisy, fs, titulo, noise=None):
    """Grafica señales en tiempo y frecuencia sin cambiar su escala.

    Con noise, separa limpia, ruido y mezcla en filas con límites comparables.
    Sin noise, conserva la vista superpuesta de referencia y mezcla.
    """
    view = min(len(t), int(0.05 * fs))
    if noise is not None:
        componentes = [(clean, 'Limpia', 'C0'), (noise, 'Ruido', 'C3'), (noisy, 'Mezcla', 'C1')]
        espectros = [espectro_db(senal, fs) for senal, _, _ in componentes]
        max_amplitud = max(float(np.max(np.abs(senal))) for senal, _, _ in componentes)
        limite_amplitud = 1.05 * max_amplitud if max_amplitud > 0 else 1.0
        max_db = max(float(np.max(magnitud)) for _, magnitud in espectros)
        limites_db = (max_db - 100, max_db + 5)
        fig, ax = plt.subplots(
            3, 2, figsize=(15, 10), sharex='col', sharey='col', layout='constrained'
        )
        fig.suptitle(
            f'{titulo}: señal limpia + ruido = mezcla\n'
            f'Simulación · espectros del registro completo (FFT de {len(t)} muestras)'
        )
        for fila, ((senal, etiqueta, color), (frecuencias, magnitud)) in enumerate(
            zip(componentes, espectros)
        ):
            ax[fila, 0].plot(t[:view] * 1000, senal[:view], color=color, lw=1)
            ax[fila, 0].set(
                xlabel='Tiempo (ms)',
                ylabel='Amplitud digital',
                title=f'{etiqueta}: primeros {1000 * view / fs:g} ms',
                ylim=(-limite_amplitud, limite_amplitud),
            )
            ax[fila, 1].plot(frecuencias, magnitud, color=color, lw=1)
            ax[fila, 1].set(
                xlabel='Frecuencia (Hz)',
                ylabel='Magnitud (dB)',
                title=f'{etiqueta}: frecuencias presentes',
                xlim=(0, fs / 2),
                ylim=limites_db,
            )
        return fig

    f1, m1 = espectro_db(clean, fs)
    f2, m2 = espectro_db(noisy, fs)
    fig, ax = plt.subplots(2, 1, figsize=(14, 8))
    ax[0].plot(t[:view] * 1000, clean[:view], label='Limpia', lw=1.5)
    ax[0].plot(t[:view] * 1000, noisy[:view], label='Contaminada', alpha=0.7, lw=1)
    ax[0].set(xlabel='Tiempo (ms)', ylabel='Amplitud', title=f'{titulo}: primeros 50 ms')
    ax[0].legend()
    ax[1].plot(f1, m1, label='Limpia')
    ax[1].plot(f2, m2, label='Contaminada', alpha=0.75)
    ax[1].set(
        xlim=(0, fs / 2),
        ylim=(max(-120, np.max(m2) - 100), np.max(m2) + 5),
        xlabel='Frecuencia (Hz)',
        ylabel='Magnitud (dB)',
        title='Espectro con ventana Hann',
    )
    ax[1].legend()
    fig.tight_layout()
    return fig


def graficar_ejemplo_fourier(t, x, frecuencias, amplitudes, fases, componentes):
    """Muestras y espectro unilateral; omite fases sin componente significativa."""
    fig, axs = plt.subplots(1, 3, figsize=(14, 4), layout="constrained")
    axs[0].stem(t * 1000, x, basefmt=" ")
    axs[0].set(xlabel="Tiempo (ms)", ylabel="Amplitud", title="Ocho muestras")
    axs[1].stem(frecuencias, amplitudes, basefmt=" ")
    axs[1].set(xlabel="Frecuencia (Hz)", ylabel="Amplitud unilateral", title="Magnitud normalizada")
    axs[2].stem(frecuencias[componentes], fases[componentes], basefmt=" ")
    axs[2].set(
        xlabel="Frecuencia (Hz)",
        ylabel="Fase (grados)",
        title="Fase de los tonos",
        ylim=(-105, 15),
        yticks=[-90, -45, 0],
    )
    return fig


# ---------------------------------------------------------------------------
# Caracterización del filtro temporal
# ---------------------------------------------------------------------------


def graficar_polos_ceros(ceros, polos, ceros_e, polos_e, n_coef):
    """Construye la figura sin mostrarla ni escribir archivos."""
    fig, axs = plt.subplots(1, 2, figsize=(14, 6.5))
    for ax, z, p, titulo in [
        (axs[0], ceros, polos, f'FIR Kaiser ({n_coef} coeficientes)'),
        (axs[1], ceros_e, polos_e, 'IIR elíptico de orden 6 (comparación)'),
    ]:
        th = np.linspace(0, 2 * np.pi, 400)
        ax.plot(np.cos(th), np.sin(th), 'k--', lw=0.8, label='Círculo unitario')
        ax.plot(z.real, z.imag, 'o', mfc='none', ms=7, label=f'Ceros ({len(z)})')
        ax.plot(p.real, p.imag, 'x', ms=10, mew=2, color='C3', label=f'Polos ({len(p)})')
        ax.axhline(0, color='gray', lw=0.5)
        ax.axvline(0, color='gray', lw=0.5)
        lim = max(1.3, 1.1 * np.max(np.abs(np.concatenate([z, p]))))
        ax.set(
            xlim=(-lim, lim),
            ylim=(-lim, lim),
            aspect='equal',
            xlabel='Re{z}',
            ylabel='Im{z}',
            title=titulo,
        )
        ax.legend(loc='upper right', fontsize=9)
    axs[0].annotate(
        f'{len(polos)} polos en z = 0', (0, 0), xytext=(-0.8, 0.3), arrowprops={'arrowstyle': '->'}
    )
    fig.tight_layout()
    return fig


def graficar_respuesta_temporal(
    f,
    mag_db,
    fase,
    gd,
    fs,
    f_paso,
    f_rechazo,
    rizado_max_db,
    atenuacion_min_db,
    retardo,
    casos,
    rizado,
    atenuacion,
):
    """Grafica la respuesta y las componentes de los casos recibidos.

    Combina las frecuencias útiles sin depender del orden de los casos y marca
    el ruido según su tipo. Devuelve la figura sin mostrarla ni escribirla.
    """
    frecuencias_utiles = set()
    for caso in casos:
        frecuencias_utiles.update(caso['frecuencias_utiles_Hz'])

    fig, axs = plt.subplots(2, 2, figsize=(15, 9))
    ax = axs[0, 0]
    ax.plot(f, mag_db)
    ax.axvspan(0, f_paso, color='C2', alpha=0.08, label='Banda de paso')
    ax.fill_between(
        [f_rechazo, fs / 2], -atenuacion_min_db, 10, color='C3', alpha=0.12, label='Zona prohibida'
    )
    ax.axhline(-atenuacion_min_db, color='C3', ls='--', lw=1)
    for fu in sorted(frecuencias_utiles):
        ax.axvline(fu, color='C2', ls=':', lw=1)
    for caso in casos:
        nombre = caso.get('id', caso.get('nombre_prueba', 'Caso'))
        if caso['tipo_ruido'] in ('banda', 'mixto'):
            ax.axvspan(
                *caso['banda_ruido_Hz'], color='C1', alpha=0.15, label=f'Ruido de banda ({nombre})'
            )
        if caso['tipo_ruido'] in ('tonal', 'mixto'):
            ax.axvline(
                caso['frecuencia_interferencia_Hz'],
                color='C4',
                ls='--',
                lw=1,
                label=f'Interferencia tonal ({nombre})',
            )
        elif caso['tipo_ruido'] == 'red_60hz':
            # El generador suma los cuatro primeros armónicos de la red de 60 Hz.
            for armonico in range(1, 5):
                ax.axvline(
                    60 * armonico,
                    color='C4',
                    ls='--',
                    lw=1,
                    label=f'Ruido de red ({nombre})' if armonico == 1 else '_nolegend_',
                )
    ax.set(
        xlim=(0, fs / 2),
        ylim=(-120, 5),
        xlabel='Frecuencia (Hz)',
        ylabel='|H| (dB)',
        title=f'Magnitud: atenuación mínima {atenuacion:.1f} dB para f ≥ {f_rechazo:.0f} Hz',
    )
    ax.legend(loc='upper right', fontsize=9)

    ax = axs[0, 1]
    sel = f <= f_paso * 1.1
    ax.plot(f[sel], mag_db[sel])
    ax.axhspan(
        -rizado_max_db / 2,
        rizado_max_db / 2,
        color='C2',
        alpha=0.1,
        label='±0.05 dB (especificación)',
    )
    for fu in sorted(frecuencias_utiles):
        ax.axvline(fu, color='C2', ls=':', lw=1)
    ax.axvline(f_paso, color='k', ls='--', lw=0.8)
    ax.set(
        ylim=(-0.08, 0.08),
        xlabel='Frecuencia (Hz)',
        ylabel='|H| (dB)',
        title=f'Detalle de la banda de paso: rizado {rizado:.4f} dB pico a pico',
    )
    ax.legend(loc='lower left', fontsize=9)

    ax = axs[1, 0]
    ax.plot(f, fase / np.pi)
    ax.set(
        xlim=(0, fs / 2),
        xlabel='Frecuencia (Hz)',
        ylabel='Fase (π rad)',
        title='Fase desenvuelta (lineal en la banda de paso; saltos de π en los ceros)',
    )

    ax = axs[1, 1]
    ax.plot(f, gd)
    ax.axhline(
        retardo,
        color='C3',
        ls='--',
        lw=1,
        label=f'(N−1)/2 = {retardo} muestras = {1000*retardo/fs:.2f} ms',
    )
    ax.set(
        xlim=(0, fs / 2),
        ylim=(0, 2 * retardo),
        xlabel='Frecuencia (Hz)',
        ylabel='Retardo de grupo (muestras)',
        title='Retardo de grupo (no definido donde |H| < −40 dB)',
    )
    ax.legend(loc='upper right')
    fig.tight_layout()
    return fig


# ---------------------------------------------------------------------------
# Resultados de ambos filtros
# ---------------------------------------------------------------------------


def graficar_filtrado(casos, salidas, metricas, etiqueta):
    """Compara referencia, entrada y salida con un panel temporal y otro espectral."""
    fig, axs = plt.subplots(len(casos), 2, figsize=(15, 4 * len(casos)), squeeze=False)
    for fila, (nombre, c) in enumerate(casos.items()):
        fs, y = c["fs"], salidas[nombre]
        i0, i1 = int(0.1 * fs), int(0.115 * fs)
        t_ms = c["t"][i0:i1] * 1000
        ax = axs[fila, 0]
        ax.plot(t_ms, c["noisy"][i0:i1], alpha=0.5, lw=1, label="Entrada contaminada")
        ax.plot(t_ms, c["clean"][i0:i1], lw=2.2, label="Referencia limpia")
        ax.plot(t_ms, y[i0:i1], "--", lw=1.4, color="k", label=etiqueta)
        ax.set(
            xlabel="Tiempo (ms)",
            ylabel="Amplitud",
            title=f"{nombre}: mejora SNR = {metricas[nombre]['delta_snr_dB']:.1f} dB",
        )
        ax.legend(loc="upper right", fontsize=11)
        ax = axs[fila, 1]
        for muestras, texto, estilo in [
            (c["noisy"], "Entrada", "-"),
            (c["clean"], "Referencia limpia", "-"),
            (y, etiqueta, "--"),
        ]:
            f, magnitud = espectro_db(muestras, fs)
            ax.plot(f, magnitud, estilo, lw=0.8, alpha=0.8, label=texto)
        ax.set(
            xlim=(0, fs / 2),
            ylim=(-150, 5),
            xlabel="Frecuencia (Hz)",
            ylabel="Magnitud (dB)",
            title=f"{nombre}: espectro antes y después",
        )
        ax.legend(loc="upper right", fontsize=11)
    fig.tight_layout()
    return fig


def graficar_compromiso(resultados):
    """Contrasta el ruido atenuado con la energía útil que conserva cada factor."""
    fig, axs = plt.subplots(1, 2, figsize=(14, 5))
    etiquetas = [f"factor = {m['factor']}" for m in resultados]
    for ax, clave, unidad, titulo in [
        (axs[0], "atenuacion_ruido_dB", "Atenuación (dB)", "Ruido eliminado"),
        (
            axs[1],
            "energia_util_conservada_pct",
            "Energía útil conservada (%)",
            "Señal útil conservada",
        ),
    ]:
        valores = [m[clave] for m in resultados]
        barras = ax.bar(etiquetas, valores, color=["C0", "C1"])
        ax.bar_label(barras, fmt="%.2f", padding=3, fontsize=12)
        ax.set(ylabel=unidad, title=titulo, ylim=(0, max(valores) * 1.2))
    fig.tight_layout()
    return fig
