# 1. Firmware del registrador ESP32

## 1.1. Estado

| Campo | Valor |
|---|---|
| Responsable | Santiago, Persona 3 |
| Plataforma | ESP32 clasico, ESP-IDF 5.5.5 |
| Alcance | Captura a lazo abierto con TCRT5000, MG90S y motor manual |
| Estado | Base y captura optica implementadas; integracion en curso |
| Revision | Codigo, documentacion y diff; aun sin pruebas funcionales |
| Pendiente fisico | GPIO, niveles, alimentacion, calibracion y montaje |

## 1.2. Configuracion y compilacion

El firmware no asigna GPIO ni posiciones fisicas por defecto. menuconfig exige
confirmar conexiones y completar la calibracion. Verificar el nivel electrico
del modulo TCRT5000: la ficha del fototransistor no describe su placa comparadora.

| Accion desde la raiz | Comando PowerShell |
|---|---|
| Configurar | & proyecto_2_grupal/firmware/ejecutar_idf.ps1 -Accion menuconfig |
| Compilar al completar | & proyecto_2_grupal/firmware/ejecutar_idf.ps1 -Accion build |
| Programar placa configurada | & proyecto_2_grupal/firmware/ejecutar_idf.ps1 -Accion flash -Puerto COMx |
| Monitor | & proyecto_2_grupal/firmware/ejecutar_idf.ps1 -Accion monitor -Puerto COMx |

[ejecutar_idf.ps1](ejecutar_idf.ps1) usa una copia temporal ASCII por los problemas
de rutas acentuadas observados en el proyecto anterior. menuconfig conserva
sdkconfig local, ignorado en Git. Despues de cambiar fuentes o configuracion,
ejecutar build: flash utiliza la ultima copia compilada.

## 1.3. Arquitectura

| Modulo | Responsabilidad |
|---|---|
| hardware | Configuracion y validacion sin accionar perifericos |
| estimador_velocidad y sensor_optico | Calculo portable y captura |
| servo_freno y motor | Conversion calibrada y mando |
| protocolo_serial | Comandos y transmision desacoplada |
| aplicacion | Coordinacion y tiempo real |

Solo se crean interfaces al implementar su responsabilidad. No se incluye
todavia PID ni secuencia automatica de aceleracion.

## 1.4. Medicion optica

Se calcula RPM = 60000000 / (pulsos_por_vuelta por intervalo_us). Las 24 marcas
son una propuesta del montaje: comprobar un flanco por marca. Un primer pulso
no entrega velocidad. El calculo utiliza el ultimo intervalo aceptado, sin
suavizado; nuevas filas pueden reutilizar esa estimacion entre pulsos.

El rechazo de intervalos cortos es configurable y esta desactivado inicialmente.
No sustituye ajustar contraste y evitar oscilaciones del comparador. Tras una
pausa igual o mayor al timeout se necesitan dos pulsos nuevos. La ausencia de
pulsos produce cero estimado por timeout, no confirma integridad del sensor.
Las instantaneas se protegen frente a escrituras simultaneas de la interrupcion.
