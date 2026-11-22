# Firmware Raspberry Pi Pico

Estado: módulos por implementar. Confirmar placa, sensor, actuador y asignación
de pines antes de escribir control de hardware. No hay aplicación compilable aún.

## Archivos previstos

| Archivo | Responsabilidad |
|---|---|
| `CMakeLists.txt` | Objetivo Pico SDK, fuentes y bibliotecas realmente usadas |
| `pico_sdk_import.cmake` | Importador oficial de la versión elegida del SDK |
| `include/config.h` | GPIO, Ts, pulsos/vuelta, unidades, límites y parámetros calibrados |
| `include/speed_sensor.h`, `src/speed_sensor.c` | Adquisición de pulsos, conversión a rad/s, timeout y ruido |
| `include/motor_driver.h`, `src/motor_driver.c` | Impulso inicial y corte/reducción controlada del motor |
| `include/brake_servo.h`, `src/brake_servo.c` | Mando del freno, calibración y saturación física |
| `include/pid_controller.h`, `src/pid_controller.c` | PID discreto, filtro derivativo, anti-windup y reinicio de estado |
| `include/reference.h`, `src/reference.c` | Trayectoria temporal decreciente y alcanzable |
| `include/telemetry.h`, `src/telemetry.c` | Registro de muestras y configuración según contrato de datos |
| `src/main.c` | Estados reposo, impulso, frenado, liberación y fallo; temporización |

Las interfaces se crearán con la implementación para evitar archivos vacíos que
aparenten funcionalidad. Registrar versión del SDK y toolchain cuando se agregue
la compilación; no copiar el SDK completo al repositorio.

## Criterios para implementar

- Definir la convención de signo del error y comprobar que un exceso de velocidad
  aumenta el frenado. El actuador solo desacelera.
- Ejecutar el control con Ts definido y medir sus tiempos reales. La transmisión
  no debe bloquear el muestreo; contabilizar muestras perdidas.
- Separar impulso del motor y maniobra de frenado según el protocolo experimental.
- Saturar el mando con límites calibrados y evitar acumulación integral. Definir
  la liberación, el reinicio del PID y el comportamiento ante pérdida del sensor.
- Registrar referencia, velocidad, error, mando aplicado y saturación tanto en
  acción fija como con PID; documentar la discretización y filtro elegidos.

Ver [contrato de datos](../experimentos/README.md) y
[decisiones pendientes](../docs/decisiones.md).
