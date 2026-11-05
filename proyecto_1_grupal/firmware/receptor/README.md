# 1. Nodo de adquisicion Pico RP2040

## 1.1. Funcion y configuracion vigente

| Campo | Valor |
|---|---|
| Entrada | MAX4466 u otra fuente acondicionada a GPIO26/ADC0; rango 0 a 3.3 V |
| Muestreo | 16000 muestras/s; 256 muestras por bloque, 16 ms |
| Analisis | Quitar media DC; Hann y FFT sobre copia; resolucion 62.5 Hz |
| Transporte | Muestras en voltios sin DC y sin Hann; SPI maestro a 2 MHz, modo 1 |
| Integracion | Activar NODO1_HABILITAR_SPI=ON al compilar |
| USB | Tabla diagnostica; capturas ADC1 bajo demanda para visualizador |
| Responsable | Persona 1; la aplicacion ESP32 integra ambos filtros |

La ESP32 ya no es el emisor de entrada en el modo de sesiones PC. Su GPIO25
es la salida filtrada para el amplificador. No conectar esa salida a la entrada
Pico durante una prueba con microfono. El sistema completo se describe en la
[guia ESP32](../esp32/GUIA_SESIONES.md).

## 1.2. Cableado SPI

| Pico | ESP32 | Funcion |
|---|---|---|
| GP18, pin fisico 24 | GPIO18 | SCK |
| GP19, pin fisico 25 | GPIO23 | MOSI |
| GP17, pin fisico 22 | GPIO27 | CS, activo bajo |
| GP20, pin fisico 26 | GPIO21 | READY, desde ESP32 |
| GND | GND | Tierra comun; niveles de 3.3 V |

MISO no se utiliza. La Pico mantiene CS alto en reposo y espera READY. El receptor
baja READY al consumir una transferencia y lo sube al armar la siguiente.
El receptor de esta rama usa GPIO27 para CS; no usar el GPIO5 del plan anterior.

## 1.3. Compilar y cargar

Instalar Pico SDK con TinyUSB, compilador ARM, CMake y Ninja. Desde esta carpeta,
con PICO_SDK_PATH apuntando al SDK instalado:

| Paso | Comando o accion |
|---|---|
| Configurar integracion | cmake -S . -B build -G Ninja -DPICO_BOARD=pico -DNODO1_HABILITAR_SPI=ON |
| SDK por argumento si no hay variable | Agregar -DPICO_SDK_PATH=C:/ruta/pico-sdk al comando anterior |
| Compilar | cmake --build build |
| Cargar | Mantener BOOTSEL al conectar USB y copiar build/nodo1_receptor.uf2 a RPI-RP2 |
| Comprobar | Abrir USB CDC y verificar Fs=16000 y SPI=ON; despues cerrar si se usa el visualizador |
| Prueba aislada sin ESP32 | Compilar con -DNODO1_HABILITAR_SPI=OFF; no sirve para capturar en la herramienta ESP32 |

La Pico adquiere aunque no haya consola conectada. Sin ESP32 preparada, los
contadores sin_READY aumentan: eso no prueba una averia ADC. Para iniciar una
captura completa deben estar encendidas ambas placas y abierta la herramienta PC.
Las versiones antiguas de 10 kHz no son compatibles con esta integracion.

## 1.4. Entrada y diagnostico

| Indicador | Significado |
|---|---|
| DC | Nivel medio antes de quitar la media del bloque; MAX4466 suele estar cerca de media alimentacion |
| RMS / Max | Nivel eficaz medio y maximo por bloque; actividad no equivale a identificar voz |
| Pico Hz | Frecuencia dominante del bloque mas intenso; resolucion 62.5 Hz |
| Sat | Codigos ADC en extremos; revisar recorte y conexion |
| Perd/Err/Rein | Perdidas de cola, errores ADC y reinicios |
| Fs | Tasa estimada por bloques DMA; no sustituye calibracion del reloj |
| SPI emitidos | Transferencias realizadas, no confirmacion de CRC remoto |
| sin_READY / sin_consumo | Esperas sin permiso o sin confirmar final de transferencia |

La eliminacion de DC por bloques tambien modifica las componentes bajas.
El antialias debe limitar frecuencias fuera de la banda prevista antes del ADC;
Nyquist a 16 kHz es 8 kHz. Una entrada flotante puede mostrar actividad falsa.
La escala usa Vref nominal de 3.3 V y no es una medida calibrada.

## 1.5. Visualizador opcional

| Accion desde receptor | Comando |
|---|---|
| Dependencias | python -m pip install -r tools/requirements.txt |
| Windows | python tools/graficar_microfono.py --puerto COMx |
| Linux | python tools/graficar_microfono.py --puerto /dev/ttyACM0 |
| Pruebas | python -m unittest discover -s tests -p test_graficar.py |

El visualizador acepta ADC1 a 16 kHz y puede importarse en Windows sin grp.
Requiere un entorno de escritorio con Matplotlib y Tk. En Linux, si el puerto
requiere permisos, el programa identifica el grupo del dispositivo. En Windows,
comprobar el puerto y cerrar otras terminales que lo tengan abierto.

Muestra voltaje con DC y senal sin DC. Cada captura contiene 256 muestras, 16 ms;
se solicitan aproximadamente cinco por segundo y hay huecos entre ellas.
No usar esas capturas separadas como una grabacion continua. La herramienta de
sesiones recibe la grabacion continua desde ESP32 por otro puerto.

## 1.6. Contratos y comprobaciones

| Elemento | Formato |
|---|---|
| SPI | 1032 bytes: AA BB, id u32 LE, 256 float32 LE, CRC8, relleno |
| CRC | CRC-8/SMBUS, polinomio 0x07, inicio/XOR final 0; cubre bytes 0 a 1029 |
| Relleno | Byte final fuera del CRC; alinea DMA a cuatro bytes |
| Secuencia | ID por bloque adquirido; huecos indican datos omitidos |
| Espera READY | 2 ms antes y despues de cada transferencia; no retransmitir el mismo bloque |
| USB ADC1 | ADC1,id,Fs,Vref,perdidos,errores,reinicios,N,codigo0,...,codigo255 |
| Comandos USB | g solicita captura y pausa tabla; t restaura tabla; retorna sola tras 2 s |
| Codigo ADC | Enteros 0 a 4095; visualizador usa Vref/4095 y DSP conserva Vref/4096 |

El contrato SPI no incluye la tasa de muestreo en cada paquete: ambos programas
se construyen para 16 kHz. La nueva aplicacion ESP32 comprueba la cadencia
aproximada en capturas suficientemente largas. La compatibilidad del codec
no demuestra continuidad fisica ni ausencia de aliasing.

| Comprobacion | Estado que debe registrar el equipo |
|---|---|
| Pruebas C de metodos y codec | Ejecucion en PC; no acredita ADC/DMA/SPI fisicos |
| Compilacion Pico | Realizar con SDK instalado y SPI habilitado |
| Captura conjunta | Guardar contadores y sesion completa sin perdidas |
| Fuente y niveles | Medir antes de afirmar calibracion o calidad analogica |
