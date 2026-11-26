# Ensayos en el banco

Lista de ensayos de lazo abierto para identificar la planta (§2.2 y §2.3 del enunciado). Se corren
con un solo comando; cada archivo queda etiquetado con su condición. Instalación y flasheo:
[ejecución](01_ejecucion.md).

## Antes de empezar

- Firmware actual flasheado (`python banco.py flashear`).
- ENA del L298N sin jumper, servo con su fuente de 5 V, todos los GND unidos ([conexiones](02_conexiones.md)).
- Disco fijo y protegido; goma sin rozar en la posición liberada (girar el disco a mano).
- Ninguna otra consola o monitor abierto en el puerto.

## Un solo comando

```bash
python banco.py pid
```

1. **Barrido de velocidad.** Gira el disco a 30, 40, 50 y 60 % de motor; cada uno hasta que la
   velocidad se estabiliza (±3 % durante 1 s, con un máximo de 30 s). Muestra la meseta de cada uno.
2. **Elige las dos velocidades**: la alta es el mayor %, la baja es la meseta más cercana al 60 % de
   la alta. Enter acepta; también se pueden escribir otras (`60 35`). Quedan en `niveles.json`.
3. **Ensayos del plan.** Antes de cada uno espera a que el disco esté **detenido** y a que se
   presione **Enter** (`s` salta, `q` termina). Mientras corre, no tocar el banco.

Si se interrumpe, volver a correr `python banco.py pid`: reutiliza las velocidades elegidas y sigue
con los ensayos que faltan. Opciones: `--alto 60 --bajo 35` salta el barrido; `--nombre otra`
guarda en otra carpeta.

| Grupo | Velocidad | Freno | Repeticiones | Para qué |
|---|---|---|---|---|
| `caida_libre` | alta y baja | liberado | 3 c/u | Desaceleración solo por fricción |
| `freno_maximo` | alta y baja | máximo | 3 c/u | Desaceleración máxima del freno |
| `escalones` | alta | 95°, 100° | 2 c/u | Zona muerta: dónde empieza a frenar la goma |
| `escalones` | alta | 110°, 120°, 130°, 140° | 2 c/u | Modelo: ganancia y retardo por ángulo |
| `escalones` | baja | 110°, 130° | 2 c/u | Modelo a la otra velocidad |
| `validacion` | alta y baja | 115°, 135° | 1 c/u | **Validación**: no se usan para ajustar |

Son 32 ensayos; la mayoría dura pocos segundos (la captura se cierra cuando el disco lleva 1 s
detenido), las caídas libres pueden tardar hasta un minuto. El plan está en
`herramientas/plan_identificacion.csv`: para cambiar ángulos o repeticiones se edita ese archivo.

## Qué entregar

La carpeta completa `datos/identificacion/`:

```text
datos/identificacion/
├── indice.csv                                  un renglón por ensayo (todos los grupos)
├── niveles.json                                velocidades elegidas y meseta de cada %
├── velocidad/     vel_m40_r01.csv              barrido: tiempo_s,rpm
├── caida_libre/   caida_alto_m60_f90_r01.csv   + .json
├── freno_maximo/  fmax_bajo_m40_f153_r02.csv   + .json
├── escalones/     esc_alto_m60_f120_r01.csv    + .json
└── validacion/    val_bajo_m40_f135_r01.csv    + .json
```

Nombre: `<tipo>_<nivel>_m<motor>_f<freno>_r<repetición>`; nivel es `alto` o `bajo`, motor en % y
freno en grados. Un reintento no pisa el anterior: queda como `..._r01_intento2`.

| Archivo | Contenido |
|---|---|
| `*.csv` de los ensayos | `tiempo_ms,freno_deg,velocidad_rpm`, una fila cada 20 ms desde el corte del motor |
| `*.json` | Configuración de la placa, eventos y cierre de ese ensayo |
| `indice.csv` | Grupo, nivel, repetición, motor, freno, archivo, si quedó completo, RPM inicial y motivo |

## Modelo

Al terminar todos los ensayos, `banco.py pid` pregunta si construir el modelo; también se puede
correr después con `python banco.py modelo`. Necesita MATLAB (o GNU Octave) en esa computadora y
deja todo en `datos/identificacion/modelo/` (ver [ejecución](01_ejecucion.md#4-modelo-de-la-planta)).
Subirlo junto con los datos.

Agregar una nota con cualquier cosa rara (la goma se movió, la fuente se apagó, un ensayo repetido)
y subirlo con un commit propio (`datos: identificacion`). Si un ensayo queda `completo = no`, el
índice dice el motivo; volver a correr la campaña lo repite.
