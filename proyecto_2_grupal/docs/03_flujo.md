# 1. Flujo del sistema

Cómo viaja un comando desde la PC hasta el disco y de vuelta a un CSV, y en qué orden leer los
archivos para entenderlo.

## 1.1. Bloques

Azul: comunicación con la PC. Naranja: actuación. Verde: medición (realimentación).

~~~mermaid
%%{init: {"flowchart": {"curve": "stepBefore", "nodeSpacing": 30, "rankSpacing": 50}}}%%
flowchart LR
    pc(["<b>PC</b><br/>consola.py<br/>guarda en datos/"])

    subgraph esp["ESP32"]
        direction LR
        ser["<b>protocolo_serial</b><br/>+ <b>comandos</b><br/>texto a comando"]
        sen["<b>sensor_optico</b><br/>hora de cada ranura"]
        est["<b>estimador_velocidad</b><br/>RPM por vuelta"]
        app["<b>aplicacion</b><br/>ensayo y registro<br/>cada 20 ms"]
        srv["<b>servo_freno</b><br/>PWM 50 Hz"]
        mot["<b>motor</b><br/>PWM 1 kHz"]
    end

    subgraph banco["Banco"]
        direction LR
        servo["<b>MG90S</b><br/>brazo con goma"]
        puente["<b>L298N</b><br/>puente H"]
        motorcd["<b>Motor CD</b>"]
        disco(("<b>Disco</b><br/>20 ranuras"))
        lm["<b>LM393</b><br/>horquilla óptica"]
    end

    pc <-->|"órdenes /<br/>filas y estado"| ser
    ser <-->|"comando /<br/>filas"| app
    sen -->|"intervalos"| est
    est -->|"RPM"| app
    app -->|"ángulo"| srv
    app -->|"% potencia"| mot
    srv -->|"pulso 1000–2200 µs"| servo
    mot -->|"PWM y sentido"| puente
    puente -->|"voltaje"| motorcd
    motorcd -->|"giro"| disco
    servo -->|"fricción"| disco
    disco -->|"ranuras"| lm
    lm -->|"pulso por ranura"| sen

    linkStyle 0,1 stroke:#1f6feb,stroke-width:1.8px
    linkStyle 4,5,6,7,8,9,10 stroke:#d1700a,stroke-width:1.8px
    linkStyle 2,3,11,12 stroke:#2e7d32,stroke-width:1.8px

    style esp fill:none,stroke:#8b949e,stroke-width:1px
    style banco fill:none,stroke:#8b949e,stroke-width:1px
~~~

## 1.2. Orden de lectura

1. **Cómo se corre todo**: [banco.py](../banco.py), de main hacia arriba (buscar_idf → entorno_idf →
   idf_py → detectar_puerto).
2. **Qué hardware cree el firmware que tiene**: [sdkconfig.defaults](../firmware/sdkconfig.defaults)
   (valores reales), luego [hardware.c](../firmware/src/hardware.c) (los carga y los valida).
3. **El corazón**: [aplicacion.c](../firmware/src/aplicacion.c), en este orden:
   1. app_main (al final): el bucle de 1 ms que vigila, muestrea y lee comandos.
   2. ejecutar_comando: qué hace cada comando y qué bloqueos de seguridad aplica.
   3. iniciar_ensayo_automatico y vigilar_ensayo_automatico: el ensayo (diagrama abajo).
   4. iniciar_registro → adquirir_muestra → terminar_registro → intentar_cierre: una captura.
4. **Cómo se mide la velocidad**: [sensor_optico.c](../firmware/src/sensor_optico.c)
   (interrupción por ranura) y [estimador_velocidad.c](../firmware/src/estimador_velocidad.c)
   (RPM con la última vuelta).
5. **Cómo se mueven los actuadores**: [servo_freno.c](../firmware/src/servo_freno.c) con
   [conversion_freno.c](../firmware/src/conversion_freno.c), y [motor.c](../firmware/src/motor.c).
6. **Cómo sale todo por la serie**: [protocolo_serial.c](../firmware/src/protocolo_serial.c).
7. **El lado de la PC**: [consola.py](../herramientas/consola.py), clase Banco: traducir
   (alias → comandos), leer (hilo que recibe), mensaje_json (qué hace con cada mensaje);
   luego Captura (escribe el CSV).
8. **Lo que viene**: [pid_controller.h](../firmware/include/pid_controller.h) y
   [pid_controller.c](../firmware/src/pid_controller.c).
9. **Cómo se prueba sin placa**: [test_registrador.py](../firmware/tests/test_registrador.py)
   y los escenarios de [pruebas_host.c](../firmware/tests/pruebas_host.c), que describen el
   comportamiento esperado de cada comando.

## 1.3. Ensayo automático

~~~mermaid
%%{init: {"flowchart": {"curve": "stepBefore", "nodeSpacing": 30, "rankSpacing": 50}}}%%
flowchart LR
    orden(["<b>ensayo</b><br/>motor 60 %<br/>freno 153°<br/>espera 300 ms"])

    subgraph esp["ESP32"]
        direction LR
        acel["<b>Acelerando</b><br/>motor al 60 %"]
        grab["<b>Grabando</b><br/>motor cortado<br/>(t = 0)<br/>fila cada 20 ms"]
        fren["<b>Frenando</b><br/>freno a 153°"]
        cierre["<b>Cierre</b><br/>libera el freno"]
    end

    csv(["<b>datos/ensayo_NN.csv</b><br/>y resumen en la consola"])
    error(["<b>error</b><br/>no graba nada"])

    orden -->|"freno liberado"| acel
    acel -->|"3 s dentro de ±3 %<br/>de una referencia fija"| grab
    grab -->|"t = 300 ms"| fren
    fren -->|"10 s o parar"| cierre
    cierre --> csv
    acel -.->|"15 s sin<br/>estabilizar"| error

    linkStyle 0,1,2,3,4 stroke:#d1700a,stroke-width:1.8px
    linkStyle 5 stroke:#c62828,stroke-width:1.6px
    style esp fill:none,stroke:#8b949e,stroke-width:1px
~~~

El motor se corta cuando la velocidad medida permanece dentro de una banda de ±3 %
durante 3 segundos completos. Los extremos de la banda están incluidos. La referencia
se fija con la primera lectura válida, finita y positiva; permanece fija dentro de la banda.

| Situación durante la aceleración | Comportamiento |
|---|---|
| Lectura dentro de ±3 % de la referencia | Continúa el conteo, sin mover la referencia |
| Lectura fuera de la banda, por arriba o por abajo | Usa la velocidad actual como referencia y reinicia los 3 s |
| Lectura inválida, no finita o no positiva | Descarta referencia y conteo; exige otros 3 s desde la siguiente lectura válida |
| Tres segundos completos dentro de la banda | Corta el motor, empieza a registrar y aplica el freno tras la espera |
| Motor cortado antes de estabilizar | Conserva el error velocidad_maxima_no_alcanzada; no empieza a registrar |

El límite de impulso continuo sigue siendo 15 s con la configuración vigente: la estabilidad
debe completarse antes de que se agote. El evento velocidad_maxima conserva su nombre por
compatibilidad y contiene la referencia de la banda aceptada; no demuestra una velocidad máxima.
La velocidad medida al comenzar la captura queda en el CSV.

El mismo porcentaje de motor puede producir distintas RPM entre repeticiones. Este criterio
comprueba estabilidad aproximada; para comparar ensayos todavía hay que verificar que las
velocidades iniciales medidas estén dentro de la tolerancia elegida para cada condición.

## 1.4. Estado de la modificación

| Campo | Estado |
|---|---|
| Responsable | Santiago; corrección del criterio de inicio del ensayo |
| Implementado | Banda simétrica de ±3 % durante 3 s; reinicio ante cambios o lecturas inválidas |
| Compatibilidad | Mismos comandos, CSV, eventos y espera de freno; sin cambios de pines ni calibración |
| Revisión | Código, documentación, enlaces locales y diff revisados |
| Verificación en PC | 25 pruebas aprobadas con python banco.py pruebas; compilación ESP32 aprobada con python banco.py compilar y ESP-IDF v5.5.5 |
| Pendiente físico | Cargar el firmware y comprobar estabilidad y tiempos de preparación sobre el banco real |
| Siguiente bloque | Consolidar trazabilidad y velocidades iniciales repetibles del roadmap |
