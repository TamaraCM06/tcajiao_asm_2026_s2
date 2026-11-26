# Ejecución

Todo se corre desde la carpeta `proyecto_2_grupal/` con un solo script, igual en Linux y Windows:

| Sistema | Cómo se llama | Puerto de la placa |
|---|---|---|
| Linux | `python banco.py <acción>` (en Debian/Ubuntu `python3`) | `/dev/ttyUSB0` o `/dev/ttyACM0` |
| Windows (PowerShell) | `py banco.py <acción>` | `COM3`, `COM5`… |

`banco.py` encuentra ESP-IDF solo y detecta el puerto si hay una sola placa conectada (si no,
`-p PUERTO`). Lo generado queda en `salidas/` y las capturas en `datos/`. En el resto de este
documento se escribe `python banco.py`; en Windows usar `py banco.py`.

## 1. Instalar (una vez por computadora)

### Linux

```bash
# Arch/CachyOS
sudo pacman -S --needed gcc git make flex bison gperf python cmake ninja ccache dfu-util libusb
sudo usermod -aG uucp $USER
# Debian/Ubuntu
sudo apt install git wget flex bison gperf python3 python3-pip python3-venv cmake ninja-build \
    ccache libffi-dev libssl-dev dfu-util libusb-1.0-0 gcc
sudo usermod -aG dialout $USER

# ESP-IDF 5.5.5 (cualquier distribución)
git clone --depth 1 --branch v5.5.5 --recursive --shallow-submodules \
    https://github.com/espressif/esp-idf.git ~/esp/esp-idf
~/esp/esp-idf/install.sh esp32
```

Cerrar sesión y volver a entrar para que valga el permiso del puerto. Después, desde `proyecto_2_grupal/`:

```bash
python banco.py preparar        # pyserial, pytest y prompt_toolkit en el Python de ESP-IDF
```

### Windows

1. Instalar [Python 3](https://www.python.org/downloads/) (deja el comando `py`).
2. Instalar ESP-IDF **5.5.5** con el *ESP-IDF Tools Installer* de Espressif, en la ruta que propone
   (`C:\Espressif`). Si se instala en otra ruta, crear la variable de entorno `IDF_PATH` con la
   carpeta de `esp-idf` e `IDF_TOOLS_PATH` con la carpeta de herramientas.
3. Instalar el driver USB de la placa: CP210x o CH340, según el chip que tenga junto al USB.
4. En PowerShell, desde `proyecto_2_grupal\`:

```powershell
py banco.py preparar            # pyserial, pytest y prompt_toolkit en el Python de ESP-IDF
```

No hace falta abrir la "ESP-IDF PowerShell" ni ejecutar `export` en ningún sistema.

## 2. Programar la placa

```bash
python banco.py flashear          # compila y programa (Windows: py banco.py flashear)
python banco.py flashear -p COM5  # si hay más de una placa
```

Pines y calibración vigentes: `firmware/sdkconfig.defaults`. Para cambiarlos, editar ese archivo y
volver a `flashear`. `python banco.py menuconfig` sirve para probar algo sin tocarlo.

## 3. Consola

```bash
python banco.py consola --nombre identificacion
```

Al conectar fija el registro (`CONFIG 20 10000 100`: una fila cada 20 ms, 10 s máximo, 0 RPM tras
100 ms sin ranuras) y libera el freno.

| Comando | Qué hace |
|---|---|
| `ensayo [motor%] [freno°]` | Acelera, corta el motor cuando la velocidad se estabiliza, graba y frena tras la espera. Sin números usa los ajustes |
| `ajustes` | Muestra los parámetros: motor (60 %), freno (máximo), espera (300 ms) y periodo (20 ms) |
| `ajustar <nombre> <valor>` | Cambia uno, validado contra los límites de la placa: `ajustar freno 130`, `ajustar periodo 50` |
| `motor <%>` | Gira el disco mostrando las RPM (`motor 0` lo detiene) |
| `parar` | Corta el motor, libera el freno y cierra la captura |
| `estado` | Placa, motor, freno y RPM |
| `ayuda` · `salir` | Tab completa; flechas para el historial |

Cada ensayo queda en `datos/<nombre>_m<motor>_f<freno>_NN.csv` (por ejemplo
`identificacion_m60_f140_01.csv`) con su `.json`; si la espera o el periodo no son los iniciales, el
nombre también los lleva (`_e500`, `_p50`). La captura se cierra sola cuando el disco lleva
1 s detenido, y la consola muestra un resumen: desaceleración antes y después del freno y tiempo
hasta detenerse. Usar un `--nombre` por serie (`identificacion`, `validacion`, `final`).

### Pruebas para el PID

`python banco.py pid` mide qué velocidad da cada % de motor, elige la velocidad alta y la baja, y
corre todos los ensayos de identificación, uno por Enter. Detalle y lista: [ensayos](04_ensayos.md).

## 4. Analizar

En MATLAB abrir `herramientas/visualizar_ensayo.m`, ejecutar y elegir el CSV en `datos/`.
Grafica el ensayo, ajusta `K` y `tau` y calcula la respuesta al impulso. Requiere exactamente un
cambio de freno en la captura (lo que produce `ensayo`).

## 5. Ajustar el freno

Solo si cambia el montaje del freno. Con el motor detenido, probar ángulos en la consola con
`FRENO <grados>` (en mayúsculas, va directo al firmware; dentro de 45..153°) hasta encontrar el
ángulo sin contacto y el de contacto. Escribir el liberado en `CONFIG_ASM_SERVO_LIBERADO_DEG` de
`firmware/sdkconfig.defaults` y volver a `flashear`. `parar` regresa el freno al liberado.

## 6. Pruebas en la PC

```bash
python banco.py pruebas           # firmware compilado con gcc contra dobles del SDK
```

Necesita `gcc` en el PATH. En Linux viene con los paquetes de arriba; en Windows, instalar
[MSYS2](https://www.msys2.org/), luego `pacman -S mingw-w64-ucrt-x86_64-gcc` en su terminal, y
agregar `C:\msys64\ucrt64\bin` al PATH.

## Problemas comunes

| Síntoma | Causa probable |
|---|---|
| `No se pudo abrir ...` | Otro programa tiene el puerto (monitor u otra consola). En Linux, falta el grupo `uucp`/`dialout` |
| `no se encontro la placa` | Cable USB solo de carga, o falta el driver CP210x/CH340 (Windows) |
| `no se encontro ESP-IDF` | ESP-IDF en otra ruta: definir `IDF_PATH` (ver instalación) |
| `falta pytest` o `No module named prompt_toolkit` | Correr `banco.py preparar` |
| La placa se reinicia al frenar (`La placa se reinicio`) | Servo alimentado desde el USB del ESP32: usar su fuente de 5 V |
| `El sensor no mide` | Disco detenido o sensor desalineado; ver [conexiones](02_conexiones.md) |
| `Placa no lista: ...` | Pines o calibración inválidos en `sdkconfig.defaults`; corregir y `flashear` |
| Algo raro en la consola | Cerrarla y abrir `python banco.py monitor`: muestra todo lo que envía la placa |

## Tarea 2 (entregada)

`tarea_2/compilar.sh` regenera el informe y `empaquetar.sh` el ZIP en `salidas/tarea_2/`, con los
programas del commit entregado (`6431b3b`). Son scripts de bash: en Windows, correrlos desde Git Bash.
