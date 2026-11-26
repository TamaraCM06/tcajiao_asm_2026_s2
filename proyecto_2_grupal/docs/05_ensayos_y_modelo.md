# Ensayos en el banco y modelo de la planta

Ensayos de lazo abierto para identificar la planta (§2.2 y §2.3 del enunciado) y el modelo que sale
de ellos, con dos comandos: `banco.py pid` en el banco y `banco.py modelo` en la computadora con
MATLAB. Instalación y flasheo: [ejecución, capturas y gráficas](04_capturas_y_graficas.md).

## Antes de empezar

- Firmware actual flasheado (`python banco.py flashear`).
- ENA del L298N sin jumper, servo con su fuente de 5 V, todos los GND unidos ([conexiones](02_conexiones.md)).
- Disco fijo y protegido; goma sin rozar en la posición liberada (girar el disco a mano).
- Ninguna otra consola o monitor abierto en el puerto.

## 1. Campaña: `python banco.py pid`

1. **Barrido de velocidad.** Gira el disco a 30, 40, 50 y 60 % de motor. Cada uno se mantiene hasta
   cumplir **el mismo criterio de estabilidad que el ENSAYO del firmware**: 5 lecturas dentro de ±7 %
   de una referencia, una cada 500 ms (los valores se leen del CONFIG de la placa). Muestra la meseta
   de cada porcentaje; si alguno no se estabiliza antes del límite de impulso, lo marca.
2. **Elige las dos velocidades**: la alta es el mayor %, la baja es la meseta más cercana al 60 % de
   la alta. Enter acepta; también se pueden escribir otras (`60 35`). Quedan en `niveles.json`.
3. **Ensayos del plan.** Antes de cada uno espera a que el disco esté **detenido** y a que se
   presione **Enter** (`s` salta, `q` termina). Cada ENSAYO pasa por el detector de estabilidad del
   firmware antes de cortar el motor y grabar; se ve su avance (`estabilidad 3/5`). Al cerrar,
   muestra pendientes y tiempo de parada y guarda la gráfica PNG junto al CSV. No tocar el banco
   mientras corre.
4. **Al completar todos**, ofrece construir el modelo (paso 2).

Si se interrumpe, volver a correr `python banco.py pid`: reutiliza las velocidades elegidas y sigue
con los ensayos que faltan. Opciones: `--alto 60 --bajo 35` salta el barrido; `--nombre otra`
guarda en otra carpeta; `--plan archivo.csv` usa otro plan.

| Grupo | Velocidad | Freno | Repeticiones | Para qué |
|---|---|---|---|---|
| `caida_libre` | alta y baja | liberado | 3 c/u | Desaceleración solo por fricción |
| `freno_maximo` | alta y baja | máximo | 3 c/u | Desaceleración máxima del freno |
| `escalones` | alta | 95°, 100° | 2 c/u | Zona muerta: dónde empieza a frenar la goma |
| `escalones` | alta | 110°, 120°, 130°, 140° | 2 c/u | Modelo: ganancia y retardo por ángulo |
| `escalones` | baja | 110°, 130° | 2 c/u | Modelo a la otra velocidad |
| `validacion` | alta y baja | 115°, 135° | 1 c/u | **Validación**: no se usan para ajustar |

Son 32 ensayos; la mayoría dura pocos segundos (la captura se cierra cuando el disco lleva 1 s
detenido); las caídas libres desde la velocidad alta pueden tardar más de 20 s. El plan está en
`herramientas/plan_identificacion.csv`: para cambiar ángulos, repeticiones o duración se edita ese archivo.

```text
datos/identificacion/
├── indice.csv                                  un renglón por ensayo (todos los grupos)
├── niveles.json                                velocidades elegidas y meseta de cada %
├── velocidad/     vel_m40_r01.csv              barrido: tiempo_s,rpm
├── caida_libre/   caida_alto_m60_f90_r01.csv   + .json + .png
├── freno_maximo/  fmax_bajo_m40_f153_r02.csv   + .json + .png
├── escalones/     esc_alto_m60_f120_r01.csv    + .json + .png
├── validacion/    val_bajo_m40_f135_r01.csv    + .json + .png
└── modelo/        modelo.json, tablas y figuras (paso 2)
```

Nombre: `<tipo>_<nivel>_m<motor>_f<freno>_r<repetición>`; nivel es `alto` o `bajo`, motor en % y
freno en grados. Un reintento no pisa el anterior: queda como `..._r01_intento2`. El CSV y el JSON
tienen el mismo formato que los de la consola; `indice.csv` lleva grupo, nivel, repetición, motor,
freno, archivo, si quedó completo, RPM al cortar y motivo.

## 2. Modelo: `python banco.py modelo`

Corre `herramientas/modelo_planta.m` en MATLAB sin abrir la interfaz (si no hay MATLAB, en GNU
Octave) sobre `datos/identificacion` (`--nombre` para otra campaña). Desde MATLAB también se puede
ejecutar `modelo_planta` dentro de `herramientas/`. Solo usa funciones base, sin toolboxes.

```text
dw/dt = -(c + b·w) - k·max(0, θ - θ_contacto)      θ sigue la orden del servo con constante τ
```

| De | Sale |
|---|---|
| `caida_libre` | Fricción: c (RPM/s) y b (1/s) |
| `escalones` y `freno_maximo` | Desaceleración agregada y τ por ensayo; contra el ángulo, la ganancia k y el **ángulo de contacto** (zona muerta) |
| `validacion` | Predicción con el modelo final y su RMSE |
| Todo | Planta para el PID con u ∈ [0, 1]: `G(s) = -Ku / ((s + b)(τ s + 1))`; polos y cero discretos con Ts (ZOH); rango de rampas alcanzables desde cada velocidad |

Resultados en `datos/identificacion/modelo/`: `modelo.json`, `escalones.csv`, `validacion.csv`,
`planta.png`, `validacion.png` y `polos_ceros.png`.

## Qué entregar

La carpeta completa `datos/identificacion/` (con `modelo/`), una nota con cualquier cosa rara (la
goma se movió, la fuente se apagó, un ensayo repetido) y un commit propio (`datos: identificacion`).
Si un ensayo queda `completo = no`, el índice dice el motivo; volver a correr la campaña lo repite.
