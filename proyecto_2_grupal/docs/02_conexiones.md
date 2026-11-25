# Conexiones

ESP32 clásico (DevKit). Los pines y la calibración vigentes están en `firmware/sdkconfig.defaults`;
si se cambia un cable, cambiarlo también ahí.

## Cableado

| Desde | Hacia | Nota |
|---|---|---|
| Sensor **VCC** / **GND** | ESP32 **3V3** / **GND** | A 3,3 V la salida nunca supera el nivel del GPIO |
| Sensor **DO** | ESP32 **GPIO27** | Un flanco de bajada por marca; 20 marcas por vuelta |
| MG90S **naranja** (señal) | ESP32 **GPIO18** | PWM de 50 Hz |
| MG90S **rojo** / **café** | Fuente **5 V** del servo / **GND común** | Nunca a 3V3; el 5 V del USB no alcanza al frenar |
| L298N **ENA** | ESP32 **GPIO25** | Pin de entrada, sin jumper; PWM de 1 kHz |
| L298N **IN1** / **IN2** | ESP32 **GPIO26** / **GPIO33** | |
| L298N **+12V** / **GND** | Fuente del motor + / − y **GND común** | |
| L298N **OUT1 / OUT2** | Motor CD | Si gira al revés, intercambiarlos |
| ESP32 **USB** | PC | Alimentación y serie a 115200 baudios |

```text
             3V3 ─────────────── VCC  sensor
             GND ──┬──────────── GND
          GPIO27 ◄─┼──────────── DO
          GPIO18 ──┼──────────── señal MG90S ── +5 V fuente servo
                   ├──────────── GND MG90S ──── GND fuente servo
  ESP32   GPIO25 ──┼──────────── ENA (sin jumper)
          GPIO26 ──┼──────────── IN1        L298N ── OUT1/OUT2 ── motor CD
          GPIO33 ──┼──────────── IN2              ── +12V ──────── fuente motor +
             GND ──┴──────────── GND ──────────────────────────── fuente motor −
```

Todos los GND en un mismo punto: ESP32, L298N, fuente del motor, fuente del servo y sensor.

## Calibración vigente (25 nov 2026)

| Parámetro | Valor |
|---|---|
| Marcas por vuelta / promedio | 20 / 20 intervalos (una vuelta) |
| Rechazo de rebotes | Intervalos menores a 200 µs |
| Recorrido del servo | 1000..2200 µs = 45..153° (escala nominal 0..180° = 500..2500 µs) |
| Freno liberado | 1500 µs = 90° |
| Freno aplicado de referencia | 2194 µs ≈ 152,5° |
| Motor | Máximo 60 % durante 15 s continuos |

Para recalibrar el servo: [ejecución, sección 5](01_ejecucion.md#5-calibrar-el-servo).

## Antes de energizar

- ENA sin jumper y GPIO25 en el pin de entrada (no en el de +5 V).
- Servo con su fuente de 5 V; sensor a 3V3; ningún cable de 5 V o 12 V en un GPIO.
- GND común.
- Disco fijo y protegido; el primer arranque con el motor a baja potencia.

Pines que el firmware rechaza: 0, 2, 5, 12, 15 (arranque), 1, 3 (USB), 6..11 (flash), 16, 17
(PSRAM); 34..39 solo como entrada.
