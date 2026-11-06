# 1. Manual de usuario

Comandos para operar el sistema. Los de PowerShell se ejecutan desde
`proyecto_1_grupal`; los de `asm>` dentro de la terminal del sistema. `COM12`
(ESP32) y `COM13` (Pico) son ejemplos.

| Quiero | Ir a |
|---|---|
| Arrancar el sistema | [1.1 Abrir la terminal](#11-abrir-la-terminal) |
| Capturar con micrófono y escuchar | [1.2 Captura con micrófono](#12-captura-con-micrófono) |
| Correr P1 a P5 | [1.3 Pruebas P1 a P5](#13-pruebas-p1-a-p5) |
| Ver qué está midiendo la Pico | [1.4 Consola de la Pico](#14-consola-de-la-pico) |
| Cambiar parámetros o cargar otro CSV (P6) | [1.5 Cambiar parámetros](#15-cambiar-parámetros-p6) |
| Saber qué guarda cada corrida | [1.6 Qué guarda cada corrida](#16-qué-guarda-cada-corrida) |
| Sacar tablas y figuras para el paper | [1.7 Resultados para la entrega](#17-resultados-para-la-entrega) |

## 1.1. Abrir la terminal

```powershell
# (lista los puertos y dice cuál es la ESP32 y cuál la Pico)
& '.venv/Scripts/python.exe' firmware/esp32/tools/sesiones.py --listar

# (abre la terminal asm>; las corridas se guardan en resultados/pruebas_finales)
& '.venv/Scripts/python.exe' firmware/esp32/tools/sesiones.py --puerto COM12 --salidas resultados/pruebas_finales

# (solo si hay que reprogramar la ESP32: compila y carga)
powershell.exe -NoProfile -ExecutionPolicy Bypass -File firmware/esp32/ejecutar_idf.ps1 -Accion build
powershell.exe -NoProfile -ExecutionPolicy Bypass -File firmware/esp32/ejecutar_idf.ps1 -Accion flash -Puerto COM12
```

```text
# (lista todos los comandos)
ayuda
# (muestra firmware, parámetros actuales y sesión seleccionada)
estado
# (deja los parámetros por defecto)
configurar segundos=6 minimo_hz=1600 ancho_hz=100 factor=0.1 umbral=0.05 ganancia=1
# (cancela la operación en curso)
detener
# (cierra el puerto y sale)
salir
```

No escribir otro comando mientras una operación esté activa, salvo `detener`.

## 1.2. Captura con micrófono

Poner la fuente frente al micrófono antes de `capturar`.

```text
# (graba 6 s por la Pico; la ESP32 filtra con FIR y espectral y la PC guarda las tres señales)
capturar
# (reproduce por el parlante la señal original capturada)
reproducir entrada
# (reproduce la salida del FIR)
reproducir fir
# (reproduce la salida del espectral)
reproducir espectral
# (guarda una observación en notas.txt de esa sesión)
nota volumen ...; FIR ...; espectral ...
```

Esperar `SESION COMPLETA` antes de reproducir.

## 1.3. Pruebas P1 a P5

| Prueba | Señal y ruido |
|---|---|
| P1 | Tono 440 Hz + interferencia 4 kHz |
| P2 | Tres tonos + ruido 2.5–3.8 kHz |
| P3 | Barrido 220–1320 Hz + ruido blanco |
| P4 | Transitorio 440 Hz + impulsos |
| P5 | Tres tonos + ruido 600–1500 Hz superpuesto |

Tres veces por prueba (P1 a P4 igual):

```text
# (manda el CSV de P1 a la ESP32, que filtra y calcula MSE, SNR, energía, atenuación y tiempos)
evaluar P1
# (escucha cada salida)
reproducir fir
reproducir espectral
# (anota la repetición y lo que se oyó)
nota P1 r1: FIR ...; espectral ...
```

P5:

```text
# (protege la señal útil solo bajo 600 Hz, porque el ruido cae encima)
configurar minimo_hz=600
evaluar P5
reproducir fir
reproducir espectral
nota P5 r1: ...
# (vuelve al valor normal)
configurar minimo_hz=1600
```

## 1.4. Consola de la Pico

Muestra lo que mide el nodo de adquisición, una fila por segundo. Sirve para
ver si llega señal, si satura y qué frecuencia domina.

```powershell
# (abre la salida USB de la Pico en otra ventana; Ctrl+] para cerrar)
& '.venv/Scripts/python.exe' -m serial.tools.miniterm COM13 115200
```

| Columna | Qué es |
|---|---|
| `Pico` | Frecuencia dominante del bloque más intenso (FFT de 256, resolución 62.5 Hz) |
| `RMS`, `Max` | Nivel de la señal en mV |
| `DC`, `Vpp` | Offset (≈ 1.65 V con el MAX4466) y rango |
| `Sat` | Muestras en los extremos del ADC: si sube, bajar el volumen |
| `Perd/Err/Rein` | Bloques perdidos, errores del ADC y reinicios |

## 1.5. Cambiar parámetros (P6)

Para cuando el profesor cambia la señal o el ruido. Todo se ajusta sin
recompilar, con el sistema detenido.

```text
# (frecuencia bajo la cual se protege la señal útil)
configurar minimo_hz=1200
# (ancho alrededor de cada componente de ruido que se atenúa)
configurar ancho_hz=150
# (cuánto se deja de cada bin de ruido: 0 lo borra, 1 no lo toca)
configurar factor=0.3
# (sensibilidad para marcar un bin como ruido; más bajo marca más bins)
configurar umbral=0.08
# (volumen de reproducción)
configurar ganancia=0.5
# (banda donde se mide la atenuación de la interferencia; auto la deduce del caso)
configurar interferencia_min_hz=2500 interferencia_max_hz=3800
configurar interferencia_min_hz=auto
# (procesa un CSV del profesor)
evaluar "C:/ruta/desconocida.csv"
```

| Límite | Valor |
|---|---|
| Frecuencia de muestreo | 16000 Hz |
| Bloques | Entrada 256, FFT 1024, salto 512 (fijos) |
| CSV | `tiempo_s,limpia,ruido,contaminada` con referencia, o `tiempo_s,contaminada` sin ella; 256 a 960000 muestras, múltiplo de 256 |
| `minimo_hz`, `ancho_hz` | 0–8000 Hz |
| `factor`, `umbral` | 0–1 y (0, 1] |

## 1.6. Qué guarda cada corrida

Cada sesión queda en `resultados/pruebas_finales/<id>/`:

| Archivo | Contenido |
|---|---|
| `entrada.wav`, `fir.wav`, `espectral.wav` | Las tres señales PCM16 |
| `metricas.csv` | Una fila por método: MSE, SNR entrada/salida, ΔSNR, energía útil, atenuación de interferencia (`atenuacion_interferencia_db`), costo por bloque (`ruta_medio_us`), latencia digital (`latencia_bloque_medio_us`) y memoria (`estado_dsp_bytes`) |
| `sesion.json` | Parámetros, versión de firmware, pérdidas y recortes |
| `notas.txt` | Lo escrito con `nota` |

Al terminar cada `capturar` o `evaluar`, la terminal compara con Python y
muestra las tablas sola. Para volver a ver una sesión:

```text
# (selecciona una sesión anterior por su carpeta)
abrir "resultados/pruebas_finales/<id>"
# (muestra de nuevo las métricas guardadas de la sesión seleccionada)
metricas
# (recalcula la comparación con el modelo Python; criterio ≥ 90 %)
validar
```

## 1.7. Resultados para la entrega

`resultados/` está en `.gitignore`: las sesiones no aparecen en Git. Se versiona
solo lo que se copia a `docs/final`.

```powershell
# (media y desviación de las 15 corridas: resumen.csv y tabla_pruebas.tex)
& '.venv/Scripts/python.exe' -m herramientas.resumen_pruebas resultados/pruebas_finales --salida resultados/entrega

# (señales y espectros de una sesión; RUTA_SESION es la ruta que imprimió la terminal)
& '.venv/Scripts/python.exe' -m herramientas.graficar_sesion RUTA_SESION --salida resultados/entrega/P1 --tonos 440 4000
& '.venv/Scripts/python.exe' -m herramientas.graficar_sesion RUTA_SESION --salida resultados/entrega/P4 --inicio 0.9 --duracion 0.3
& '.venv/Scripts/python.exe' -m herramientas.graficar_sesion RUTA_SESION --salida resultados/entrega/P2

# (copia lo seleccionado a las rutas que Git sí admite)
New-Item -ItemType Directory -Force docs/final/evidencias/pruebas
Copy-Item resultados/entrega/tabla_pruebas.tex docs/final/paper/tablas/pruebas_finales.tex
Copy-Item resultados/entrega/resumen.csv docs/final/evidencias/pruebas/resumen_final.csv
Copy-Item resultados/entrega/P1/senales_espectros.png docs/final/evidencias/pruebas/P1_senales_espectros.png
Copy-Item resultados/entrega/P1/atenuacion_tonos.csv docs/final/evidencias/pruebas/P1_atenuacion_tonos.csv
# (igual para P2–P5: Pn_senales_espectros.png)
```
