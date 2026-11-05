# TODO entrega final

Entrega y defensa: **6 de noviembre de 2026, 11:50 pm**. Enunciado: [ASM_Proyecto_Grupal1_v7.pdf](../references/ASM_Proyecto_Grupal1_v7.pdf).

Solo queda lo pendiente. Está dividido en lo que necesita las placas y lo que se hace
en la computadora sin hardware. Todo usa el montaje actual, sin reconectar nada.

## Cómo se relacionan nuestros casos con las pruebas del enunciado

Los tres casos usan la misma señal útil: tres tonos de 440, 880 y 1320 Hz.

- **caso_2** (ruido de banda 2.5–3.8 kHz, fuera de la banda útil) es exactamente **P2**:
  tres tonos con ruido de alta frecuencia.
- **caso_3** (ruido de banda 0.6–1.5 kHz, encima de los tonos) es exactamente **P5**:
  superposición parcial de señal y ruido.
- **caso_1** (interferencia sinusoidal de 4 kHz) tiene el ruido que pide **P1**, pero no
  su señal: P1 pide un solo tono y caso_1 tiene tres. Basta con dejarle un solo tono
  (440 Hz) para que sea P1.
- **Faltan P3** (audio o señal arbitraria con ruido de banda ancha) **y P4** (señal
  transitoria con ruido impulsivo).

---

## A. Con las placas

### A1. Repetir P1 a P5 tres veces
**Problema.** El enunciado (§4) pide al menos tres repeticiones por prueba, con promedio
y variabilidad. Hoy hay una sola corrida por caso.
**Solución.** Correrlas antes de la defensa, no durante ella: en la terminal,
`evaluar P1` tres veces, y lo mismo para P2 a P5. Cada sesión se copia a
`docs/final/evidencias/P1/rep_1/`, `rep_2/`, `rep_3/`, porque `resultados/` no se sube a
Git. Después, `python -m herramientas.resumen_pruebas docs/final/evidencias` genera
`resumen.csv` con media y desviación de cada métrica, y con eso se llena la tabla
pendiente del paper. En la defensa basta mostrar una corrida en vivo.

### A2. Respuesta del FIR medida
**Problema.** El enunciado (§3.3.5) pide comparar la respuesta calculada del FIR con la
medida. Lo medido es lo que la placa hace con los tonos reales.
**Solución.** No requiere una prueba nueva: se usa cualquier sesión de `evaluar` ya
grabada. Corre `python -m herramientas.respuesta_fir_medida resultados/sesiones/<id>`,
que mide en `entrada.wav` y `fir.wav` la amplitud de cada tono y la compara con la
respuesta calculada desde los coeficientes. El resultado se guarda en
`docs/final/evidencias/fir/` y se reporta en el paper: en banda de paso la diferencia
debería ser menor a 0.5 dB, y a 4 kHz la salida debería quedar en el piso de ruido.

### A3. Aliasing
**Qué es.** El aliasing es que una frecuencia mayor a la mitad de la frecuencia de
muestreo (8 kHz, porque la Pico muestrea a 16 kHz) se "dobla" y aparece disfrazada de
otra frecuencia más baja: un tono de 9 kHz se ve como uno de 16 − 9 = 7 kHz. Pasa al
muestrear, así que solo lo evita un filtro analógico antes del ADC, y entre el
micrófono y la Pico no tenemos uno.
**Problema.** El enunciado (§2) pide demostrar que el sistema evita el aliasing.
**Solución.** Poner un tono de 9 kHz desde un generador en el celular frente al
micrófono y mirar la columna **Pico** de la consola de la Pico, que muestra la
frecuencia dominante del bloque más fuerte. Si marca cerca de 7 kHz, hay aliasing y se
reporta como limitación. Si no aparece nada fuerte, el micrófono y su circuito ya
atenúan esas frecuencias, y esa es la evidencia. Se guarda una captura en
`evidencias/aliasing/` y se escribe una frase en el paper.

### A4. Enlace SPI de 60 s
**Problema.** Solo hay una captura de 6 s sin pérdidas. El enunciado (§5) pide detectar
errores e indicar pérdidas, y la guía pide 60 s.
**Solución.** No hace falta un test nuevo: el firmware ya revisa cada bloque y aborta si
uno llega mal. En la terminal, `configurar segundos=60` y `capturar`, tres veces. Si las
tres terminan, en el paper va "11250 bloques, 0 errores CRC, 0 pérdidas"; si alguna se
aborta, `eventos.log` dice por qué y se reporta.

### A5. Escuchar y ensayar P6
**Problema.** El enunciado pide revisar el sonido (§4) y resolver en vivo una prueba
desconocida cambiando parámetros sin recompilar (§6).
**Solución.** `reproducir entrada`, `fir` y `espectral` de P3, empezando con volumen
bajo. Para P6, alguien arma un CSV sorpresa y el resto lo resuelve con
`evaluar "ruta.csv"` y `configurar ...`. Lo que se cambió se anota en
`evidencias/P6_ensayo.md`.

### A6. Copiar la evidencia que ya existe
**Problema.** La demo analógica y las sesiones del 5 de noviembre están solo en la otra
computadora, dentro de `resultados/`, que no va a Git.
**Solución.** Copiar a `docs/final/evidencias/` la carpeta de `resultados/sesiones/analogicas/`
(con `comparacion_analogica.csv` y `respuesta_analogica.png`) y las dos sesiones del 5 de
noviembre. La demo no se vuelve a correr (no la pide el enunciado). Si el tono de 4 kHz
sale con más error que los demás, se justifica así: los escalones del DAC bajan cerca de
10 % la amplitud a 4 kHz, la sonda "después" (pin 7) lo ve y la "antes" (GPIO25) no, y el
modelo no lo incluye. No es un error del filtro.

### A7. Confirmar el umbral de concordancia
**Problema.** El paper fija una concordancia placa–Python de al menos 90 %, pero todavía
no vemos los valores reales.
**Solución.** Revisar `validacion_python.csv` de las sesiones. El caso 1 dio 29.9764 dB en
la placa contra 29.9760 dB en Python, así que se espera mucho más de 99 %. Si algo da
menos de 90 %, se investiga antes de entregar.

---

## B. En la computadora, sin placas

### B1. Crear P1, P3 y P4 y renombrar los casos (pendiente)
**Solución.** En `configuraciones.json`: caso_1 pasa a P1 con un solo tono de 440 Hz,
caso_2 pasa a P2, caso_3 pasa a P5, y se agregan P3 (audio propio con ruido de banda
ancha; si es voz, con permiso) y P4 (ráfaga o escalón con ruido impulsivo). Después hay
que regenerar las muestras y renombrar en el notebook, `prototipo.py`, el exportador, la
terminal (`terminal.py` y `demo_analogica.py`), los datos del firmware y los tests, con
un test nuevo `tarea1_grupo1/tests/test_casos_p.py`. Esto debe hacerse antes de A1.

### B2. Repeticiones automáticas en la terminal (opcional)
Si se quiere ahorrar tiempo en A1, se puede agregar a la terminal algo como
`evaluar P1 3`, que repita la evaluación y guarde las tres sesiones. No es obligatorio:
correr el comando tres veces da lo mismo.

### B3. Hecho en esta revisión
- El test del filtro analógico ahora espera 22 nF. Todas las pruebas pasan (153).
- El modelo analógico no se tocó: queda igual que cuando se corrió la demo.
- 🆕 `herramientas/respuesta_fir_medida.py` y 🆕 `herramientas/resumen_pruebas.py`, con
  sus pruebas en `firmware/esp32/tests/test_herramientas_resultados.py`.
- En el paper: las figuras 1 y 2 están en el anexo; la terminal de la PC queda declarada
  como interfaz local del nodo 3; y los criterios de aceptación incluyen el analógico
  (≤ 15 %) y la concordancia de al menos 90 %, con su justificación.

### B4. Al final
Quitar los pendientes en rojo del paper (aliasing, FIR medido, confirmar criterios y la
tabla P1–P5), revisar que tenga como máximo 4 páginas y herramientas como máximo 2,
hacer merge a `master` con su tag y ensayar la defensa.

**Ojo con el espacio del paper.** Hoy cuerpo y referencias llenan exactamente 3 páginas
y el anexo ocupa la 4. Cuando entre la tabla P1–P5 y los textos de aliasing y FIR medido,
habrá que recortar: por ejemplo, pasar la Tabla I (candidatos FIR/IIR) al anexo o
reemplazar la tabla del 30/10 por la de P1–P5.
