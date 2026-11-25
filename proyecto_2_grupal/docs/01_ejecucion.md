# Ejecución

Todo se corre desde `proyecto_2_grupal/` con `python banco.py <acción>`. Lo generado queda en
`salidas/` (se borra con `python banco.py limpiar`); las capturas quedan en `datos/`.

## 1. Instalar (una vez)

**Linux** (Arch/CachyOS; en Debian/Ubuntu el grupo es `dialout` y los paquetes van con `apt`):

```bash
sudo pacman -S --needed gcc git make flex bison gperf python cmake ninja ccache dfu-util libusb
sudo usermod -aG uucp $USER                 # permiso del puerto; cerrar sesión y volver a entrar
git clone --depth 1 --branch v5.5.5 --recursive --shallow-submodules \
    https://github.com/espressif/esp-idf.git ~/esp/esp-idf
~/esp/esp-idf/install.sh esp32
python banco.py preparar                    # pyserial y pytest en el Python de ESP-IDF
```

**Windows:** instalar ESP-IDF 5.5.5 con el *ESP-IDF Tools Installer* en `C:\Espressif`, el
driver de la placa (CP210x o CH340) y luego `python banco.py preparar`.

`banco.py` busca ESP-IDF en `$IDF_PATH`, `~/esp/esp-idf` o `C:/Espressif/frameworks/esp-idf-v5.5.5`;
no hace falta activar `export.sh` en cada terminal.

## 2. Programar la placa

```bash
python banco.py flashear                    # compila y programa; -p PUERTO si hay varias placas
```

La configuración vigente (pines y calibración) está en `firmware/sdkconfig.defaults`.
`python banco.py menuconfig` sirve para probar cambios; para dejarlos, editar ese archivo.

## 3. Consola

```bash
python banco.py consola --nombre escalon    # capturas en datos/escalon_NN.csv
```

Al conectar configura el registro (fila cada 20 ms, 10 s máximo) y libera el freno.

| Comando | Qué hace |
|---|---|
| `ensayo [% grados ms]` | Acelera, corta el motor al estabilizar la velocidad, graba y frena tras la espera. Por defecto `60 %`, freno máximo, `300 ms` |
| `liberar` / `frenar [grados]` | Freno a la posición liberada / aplicado (máximo si no se indica) |
| `motor <%>` · `grabar` · `parar` | Ensayo manual: impulsar, cortar motor y grabar, terminar |
| `estado` · `config` | Estado y velocidad actual · configuración de la placa |
| `cal ...` | Calibración del servo (sección 5) |
| `crudo` | Muestra todo lo que envía la placa (depuración) |
| `ayuda` · `salir` | Tab completa los comandos |

Al cerrar cada captura se imprime un resumen: desaceleración antes y después del freno y tiempo
hasta detenerse. Usar un `--nombre` por serie de ensayos (por ejemplo `pid_alta`).

## 4. Analizar

En MATLAB abrir `herramientas/visualizar_ensayo.m`, ejecutar y elegir el CSV en `datos/`.
Grafica el ensayo, ajusta `K` y `tau` y calcula la respuesta al impulso. Requiere exactamente un
cambio de freno en la captura (lo que produce `ensayo`).

## 5. Calibrar el servo

Con el motor detenido:

```text
cal pulso 1500        mover a un pulso conocido (dentro de 1000..2200 us)
cal + / cal -         pasos de 2 grados; cal paso 0.5 para afinar
cal liberado          marcar la posición sin contacto
cal contacto          marcar donde la goma toca el disco (vuelve a liberado)
```

La consola muestra los grados a copiar en `firmware/sdkconfig.defaults`
(`CONFIG_ASM_SERVO_LIBERADO_DEG`, límites). Después: `python banco.py flashear`. Si el servo queda
15 s sin órdenes `cal`, se le corta el PWM; `liberar` lo reactiva.

## 6. Pruebas en la PC

```bash
python banco.py pruebas                     # firmware compilado con gcc contra dobles del SDK
python banco.py diagramas                   # docs/diagramas/src -> svg (Node.js; Graphviz para conexiones)
```

## Problemas comunes

| Síntoma | Causa probable |
|---|---|
| `No se pudo abrir /dev/ttyUSB0` | Otro programa tiene el puerto (monitor) o falta el grupo `uucp`/`dialout` |
| La placa se reinicia al frenar (`Placa reiniciada`) | Servo alimentado desde el USB del ESP32: usar su fuente de 5 V |
| `El sensor no mide velocidad` | Disco detenido o sensor desalineado; ver [conexiones](02_conexiones.md) |
| `Firmware sin configurar` | `sdkconfig.defaults` incompleto; corregir y `flashear` |
| Algo raro en la consola | `crudo` muestra la salida sin filtrar; `python banco.py monitor` abre el monitor serie |

## Tarea 2 (entregada)

`tarea_2/compilar.sh` regenera el informe y `empaquetar.sh` el ZIP en `salidas/tarea_2/`
con los programas del commit entregado (`6431b3b`).
