# 1. Firmware del registrador ESP32

## 1.1. Estado

| Campo | Valor |
|---|---|
| Responsable | Santiago, Persona 3 |
| Plataforma | ESP32 clasico, ESP-IDF 5.5.5 |
| Alcance | Captura a lazo abierto con TCRT5000, MG90S y motor manual |
| Estado | Registrador integrado y receptor MATLAB implementado |
| Revision | Codigo, documentacion, diff, compilacion ESP-IDF y 19 pruebas C host |
| Pendiente fisico | GPIO, niveles, alimentacion, calibracion y montaje |

## 1.2. Configuracion y compilacion

El firmware no asigna GPIO ni posiciones fisicas por defecto. menuconfig exige
confirmar conexiones y completar la calibracion. Verificar el nivel electrico
del modulo TCRT5000: la ficha del fototransistor no describe su placa comparadora.

| Accion desde la raiz | Comando PowerShell |
|---|---|
| Configurar | powershell.exe -NoProfile -ExecutionPolicy Bypass -File proyecto_2_grupal/firmware/ejecutar_idf.ps1 -Accion menuconfig |
| Compilar al completar | powershell.exe -NoProfile -ExecutionPolicy Bypass -File proyecto_2_grupal/firmware/ejecutar_idf.ps1 -Accion build |
| Programar placa configurada | powershell.exe -NoProfile -ExecutionPolicy Bypass -File proyecto_2_grupal/firmware/ejecutar_idf.ps1 -Accion flash -Puerto COMx |
| Monitor | powershell.exe -NoProfile -ExecutionPolicy Bypass -File proyecto_2_grupal/firmware/ejecutar_idf.ps1 -Accion monitor -Puerto COMx |

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

| pid_controller | PID discreto portable de la Tarea 2; aun no esta en `src/CMakeLists.txt` |

Solo se crean interfaces al implementar su responsabilidad. El PID existe como
modulo portable probado en simulacion, pero todavia no se ejecuta en el
registrador; tampoco hay secuencia automatica de aceleracion.

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

## 1.5. Actuadores

El arranque mantiene ENA deshabilitado y el PWM del servo sin pulsos. El operador
debe ordenar la liberacion calibrada antes de impulsar. La conversion grados a
microsegundos admite sentido inverso; rechaza ordenes fuera de limites. No hay
lectura de posicion ni de fuerza. Los temporizadores PWM de servo y motor son
distintos. Cambiar el porcentaje de motor no reinicia el limite de impulso continuo.
El limite es software; no reemplaza una desconexion fisica de alimentacion.

## 1.6. Comandos y datos

| Linea ASCII terminada en LF | Efecto |
|---|---|
| CONFIG | Consulta los cuatro grupos de configuracion |
| CONFIG periodo_ms duracion_ms timeout_ms | Aplica tres enteros en reposo con motor cortado; reinicia el estimador |
| STATUS | Estado, motivo de bloqueo y mandos actuales |
| FRENO grados | Ordena un angulo calibrado; requiere motor cortado |
| MOTOR porcentaje | Impulso en un sentido; requiere CONFIG y liberacion ordenada; 0 corta |
| START | Exige dos pulsos recientes y freno liberado; corta motor y registra |
| STOP | Cierra registro, corta motor y libera el freno calibrado |
| ENSAYO porcentaje grados espera_ms | Automatico: impulsa el motor; cuando la velocidad lleva 0,5 s sin subir mas de 2 %, corta el motor y registra como START, y aplica FRENO grados tras espera_ms (0 a 10000). Requiere CONFIG y freno liberado |

| Parametro de ensayo | Intervalo admitido | Inicial |
|---|---|---|
| periodo_ms | Entero de 10 a 60000 ms | Sin configurar |
| duracion_ms | Entero desde periodo_ms hasta 3600000 ms | Sin configurar |
| timeout_ms | Entero de 1 a 60000 ms, mayor al rechazo minimo de pulso | Sin configurar |

El limite de 100 filas/s deja margen en UART de 115200 baudios para filas de
menos de 64 bytes y metadatos. No demuestra que 100 Hz sea adecuado para la
dinamica del montaje. Definir el periodo con mediciones; no son periodos de PID.

El protocolo 1 emite mensajes JSON precedidos por numeral y espacio. Un ensayo
contiene inicio, cuatro grupos de configuracion, cabecera CSV, filas y fin.
Los eventos de freno y estado optico se intercalan como metadatos. El receptor
los separa: el CSV conserva solo tiempo_ms,freno_deg,velocidad_rpm.

El tiempo se toma en ESP32 despues del corte aceptado del motor; no es tiempo
de llegada a la computadora. Se exporta con tres decimales de milisegundo.
La lectura sin intervalo valido es NaN; el cero por timeout es inferido. Los
estados opticos son 0 esperando, 1 valido y 2 sin pulsos. START exige estado 1.

Durante captura se rechazan CONFIG y motor positivo. Cada periodo admite una
sola muestra real. La cola transmite hasta 64 lineas de 512 bytes; si se llena,
se detiene el ensayo y se reintenta el cierre tras drenar las muestras previas.
El cierre informa producidas, enviadas, vencimientos perdidos e intervalos reales
minimo/maximo. La condicion completo describe integridad de captura; no valida
el montaje, la calibracion ni el modelo. No hay confirmacion individual UART:
MATLAB tambien debe comprobar los conteos y la presencia de fin.

## 1.7. Verificacion y siguiente bloque

Se revisaron codigo, documentacion y diff. La compilacion ESP-IDF y 19 pruebas
C host finalizaron correctamente; no equivalen a funcionamiento fisico. El
analizador MATLAB no reporta observaciones. Sus 10 pruebas de ejecucion quedan
pendientes porque MATLAB solicita activacion de licencia. Ver
[auditoria](../docs/verificacion_registrador.md) y [pruebas host](tests/README.md).
No se ha programado ni accionado hardware en este feature.
El siguiente bloque fisico es comprobar el montaje y adquirir un ensayo abierto;
despues corresponde identificar y validar el modelo antes de integrar PID.
