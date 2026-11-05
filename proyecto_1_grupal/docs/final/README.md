# Entrega final: Proyecto Grupal 1

Enunciado: [ASM_Proyecto_Grupal1_v7.pdf](../references/ASM_Proyecto_Grupal1_v7.pdf).
Entrega y defensa: **6 de noviembre de 2026, 11:50 pm**. Defensa de 15 min con sonido.

## 1. Qué se entrega

| # | Entregable | Peso | Formato y límite | Ubicación |
|---|---|---|---|---|
| 1 | Artículo científico | 30 % | LaTeX, IEEE, ≤ 4 páginas con referencias; abstract en inglés 150–250 palabras; ≤ 6 palabras clave | [paper/](paper/) |
| 2 | Herramientas de ingeniería | 5 % | ≤ 2 páginas; a) selección, b) aplicación, c) adaptación; incluye IA usada | [herramientas/](herramientas/) |
| 3 | Código fuente | defensa 65 % | `master` con tag | `proyecto_1_grupal/` |
| 4 | Evidencias de pruebas | apoyo a 1 y a la defensa | P1–P5 × 3 repeticiones y mediciones | [evidencias/](evidencias/) |

Reglas de los documentos: sin código fuente (pseudocódigo o diagramas), toda
referencia citada en el texto y formato IEEE.

## 2. Requisitos del enunciado frente al estado actual

Leyenda: ✅ hecho · 🟡 parcial · ❌ falta

### 2.1. Sistema (secciones 1 y 5)

| Requisito | Estado | Dónde |
|---|---|---|
| Nodo 1 separado: ADC, quitar DC, ventana, FFT, estimar ruido, comunicar | ✅ | [receptor](../../firmware/receptor/) |
| Nodo 2: FIR, salida por DAC con filtro analógico | ✅ | [filtro_fir.c](../../firmware/esp32/components/filtros_digitales/filtro_fir.c); Sallen-Key en protoboard |
| Nodo 3: FFT/IFFT y métricas | ✅ | [filtro_espectral.c](../../firmware/esp32/components/filtros_digitales/filtro_espectral.c), [metricas_digitales.c](../../firmware/esp32/components/evaluacion_digital/metricas_digitales.c) |
| Nodo 3 muestra método, energía, MSE y SNR en interfaz local | ✅ | Terminal de la PC ([sesiones.py](../../firmware/esp32/tools/sesiones.py)), aceptada como interfaz local |
| Nodos 2 y 3 en un micro con dos rutas independientes | ✅ | [procesamiento_vivo.c](../../firmware/esp32/components/procesamiento_vivo/procesamiento_vivo.c) |
| Bloques potencia de dos | ✅ | 256 (entrada y FIR); 1024 con salto 512 (espectral) |
| Delimitación de bloques, detección de errores y pérdidas | ✅ | Trama SPI con cabecera, identificador y CRC-8; la captura aborta ante cualquier fallo |
| Ajustar parámetros sin recompilar | ✅ | Comando `configurar` |
| Justificar Fs, bloque, formato y tasa juntos | ✅ | Paper, sección III-A (SPI 2 MHz, USB 1 Mbaud) |
| Documentar el filtro de reconstrucción | ✅ | Paper III-D: divisor, seguidor y Sallen-Key con 22 nF, fc ≈ 2283 Hz |
| Demostrar que se evita el aliasing | ❌ | Prueba con tono de 9 kHz pendiente |

### 2.2. Señales y ruidos (sección 2)

| Requisito | Estado | Dónde |
|---|---|---|
| Tono sinusoidal | 🟡 | caso_1 tiene el ruido de P1 pero tres tonos; se pasa a un tono |
| Tres o más tonos | ✅ | caso_2 (P2) |
| Audio o señal arbitraria | ❌ | Caso P3 pendiente |
| Señal transitoria | ❌ | Caso P4 pendiente |
| ≥ 3 tipos de ruido | ✅ | Tonal 4 kHz, banda 2.5–3.8 kHz, banda superpuesta 0.6–1.5 kHz |
| Superposición parcial y compromiso ruido–distorsión | ✅ | caso_3 (P5) y [compromiso_ruido_distorsion.csv](../../tarea1_grupo1/resultados/filtro_espectral/compromiso_ruido_distorsion.csv) |

### 2.3. Modelo y filtros (secciones 3.2–3.4)

| Requisito | Estado | Dónde |
|---|---|---|
| DFT directa frente a FFT | ✅ | [fourier_verificacion.csv](../../tarea1_grupo1/resultados/fourier_verificacion.csv) |
| FIR e IIR candidatos, polos, ceros, ROC y respuesta | ✅ | Tabla I del paper y figuras del anexo |
| Costo, memoria y latencia | ✅ | Paper, sección IV (tiempos en ESP32, 53 272 bytes) |
| Espectral adaptativo con simetría conjugada | ✅ | Umbral relativo por bloque |
| Respuesta FIR calculada frente a medida | 🟡 | Script listo: [respuesta_fir_medida.py](../../herramientas/respuesta_fir_medida.py); falta correrlo sobre una sesión |
| Representación numérica y saturación | ✅ | float32, PCM16 con saturación, DAC 8 bits |

### 2.4. Pruebas obligatorias (sección 4)

Cada P1–P5: 3 repeticiones con promedio y variabilidad
([resumen_pruebas.py](../../herramientas/resumen_pruebas.py)). P6 en la defensa.

| ID | Señal y condición | Caso actual | Estado |
|---|---|---|---|
| P1 | Tono + interferencia sinusoidal | caso_1 (pasar a un solo tono) | ❌ |
| P2 | Tres tonos + ruido de alta frecuencia | caso_2 | 🟡 una corrida |
| P3 | Audio + ruido de banda ancha | — | ❌ |
| P4 | Transitoria + ruido impulsivo | — | ❌ |
| P5 | Superposición parcial | caso_3 | 🟡 una corrida |
| P6 | Desconocida | `evaluar "archivo.csv"` y `configurar` | ensayar |

Criterios de aceptación (paper, sección IV): ΔSNR ≥ 10 dB y energía útil ≥ 90 % con
ruido fuera de banda; tiempo por bloque < 16 ms (FIR) y < 32 ms (espectral); cero
pérdidas; filtro analógico con error ≤ 15 % por tono; concordancia placa–Python ≥ 90 %.

### 2.5. Git (sección 7)

| Requisito | Estado |
|---|---|
| Ramas `master` y `development`, ramas de trabajo | ✅ |
| Merge final a `master` y tag | ❌ |
| Avance incremental, varios autores | ✅ |

## 3. Estado de los documentos

| Documento | Páginas | Pendiente (en rojo con `\pend{}`) |
|---|---|---|
| [paper/main.tex](paper/main.tex) | 4 / 4: cuerpo y referencias llenan 3 páginas exactas; el anexo con figuras ocupa la 4. **No queda espacio libre**: la tabla P1–P5 obliga a recortar texto o a mover tablas al anexo | Aliasing, respuesta FIR medida, confirmar criterios con datos reales, tabla P1–P5 |
| [herramientas/herramientas.tex](herramientas/herramientas.tex) | 2 / 2 | Nada |

Fuentes de los números: `tarea1_grupo1/resultados/*.csv`, la ejecución en ESP32 del
30/10/2026 y las sesiones del 5/11/2026 descritas en
[GUIA_SESIONES.md](../../firmware/esp32/GUIA_SESIONES.md) §1.9. Si cambian los
resultados, actualizar también el abstract. Las figuras del paper están copiadas en
[paper/figuras](paper/figuras/).

## 4. Scripts de evidencia

Desde `proyecto_1_grupal/`:

| Comando | Resultado |
|---|---|
| `python -m herramientas.respuesta_fir_medida resultados/sesiones/<id>` | Ganancia del FIR medida en la sesión frente a la calculada, por tono |
| `python -m herramientas.resumen_pruebas docs/final/evidencias` | `resumen.csv` con media y desviación de cada métrica por prueba |
| `python -m pytest tarea1_grupo1/tests firmware/esp32/tests -q` | 153 pruebas |

## 5. Compilar

```bash
cd proyecto_1_grupal/docs/final/paper && latexmk -pdf main.tex
cd ../herramientas && latexmk -pdf herramientas.tex
```
