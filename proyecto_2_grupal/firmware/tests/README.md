# 1. Verificacion host del registrador

## 1.1. Alcance y resultado

Responsable: Santiago. Se compilan las mismas fuentes de produccion con GCC.
Los dobles de SDK registran ordenes; no representan una ESP32, un sensor o PWM
fisico. Resultado del cierre del bloque: 19 pruebas aprobadas en PC.

| Grupo | Casos | Comprobacion |
|---|---|---|
| Nucleo, coordinador y protocolo formateado | 15 | RPM, flancos repetidos, timeout, tiempo de 64 bits, conversion, comandos, configuracion, huecos, GPIO, bloqueos, recorrido, cola llena y fallo de corte |
| Controladores de actuadores | 4 | Arranque sin movimiento, tiempo continuo de impulso, limites y corte alternativo ante fallo PWM |

## 1.2. Reproduccion

| Desde raiz, PowerShell | Comando |
|---|---|
| Pruebas C desde pytest | & proyecto_1_grupal/.venv/Scripts/python.exe -m pytest proyecto_2_grupal/firmware/tests -q |

Se requiere GCC y pytest. Los ejecutables y cabeceras de configuracion simuladas
se generan en temporales. La prueba de trama guarda una salida del coordinador
en build/pruebas/trama_produccion.txt, ignorada en Git, para contrastarla luego
con el receptor MATLAB. Los pines, frecuencias y angulos presentes en las pruebas
son valores simulados, no una configuracion recomendada para el banco.

## 1.3. Pendientes y continuidad

No se emulan el planificador RTOS, la forma de onda del sensor, UART fisico,
electromecanica ni alimentacion. Validar esos elementos con el montaje real.
Las pruebas de ejecucion MATLAB estan en
[tests del receptor](../../experimentos/tests/test_receptor.m); requieren licencia activa.
