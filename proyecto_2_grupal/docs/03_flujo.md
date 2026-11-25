# Flujo del sistema

Cómo viaja un comando desde la PC hasta el disco y de vuelta a un CSV, y en qué orden leer los
archivos para entenderlo.

## Bloques

Azul: comunicación con la PC. Naranja: actuación. Verde: medición (realimentación).

```mermaid
%%{init: {"flowchart": {"curve": "stepBefore", "nodeSpacing": 30, "rankSpacing": 50}}}%%
flowchart LR
    pc(["<b>PC</b><br/>consola.py<br/>guarda en datos/"])

    subgraph esp["ESP32"]
        direction LR
        ser["<b>protocolo_serial</b><br/>+ <b>comandos</b><br/>texto a comando"]
        sen["<b>sensor_optico</b><br/>hora de cada ranura"]
        est["<b>estimador_velocidad</b><br/>RPM por vuelta"]
        app["<b>aplicacion</b><br/>ensayo, CAL y registro<br/>cada 20 ms"]
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
```

## Orden de lectura

1. **Cómo se corre todo**: `banco.py`, de `main` hacia arriba (`buscar_idf` → `entorno_idf` →
   `idf_py` → `detectar_puerto`).
2. **Qué hardware cree el firmware que tiene**: `firmware/sdkconfig.defaults` (valores reales), luego
   `firmware/src/hardware.c` (los carga y los valida).
3. **El corazón**: `firmware/src/aplicacion.c`, en este orden:
   1. `app_main` (al final): el bucle de 1 ms que vigila, muestrea y lee comandos.
   2. `ejecutar_comando`: qué hace cada comando y qué bloqueos de seguridad aplica.
   3. `iniciar_ensayo_automatico` y `vigilar_ensayo_automatico`: el ensayo (diagrama abajo).
   4. `iniciar_registro` → `adquirir_muestra` → `terminar_registro` → `intentar_cierre`: una captura.
   5. `ejecutar_calibracion` y `vigilar_calibracion`: los comandos `CAL`.
4. **Cómo se mide la velocidad**: `firmware/src/sensor_optico.c` (interrupción por ranura) y
   `firmware/src/estimador_velocidad.c` (RPM con la última vuelta).
5. **Cómo se mueven los actuadores**: `firmware/src/servo_freno.c` con `conversion_freno.c`, y
   `firmware/src/motor.c`.
6. **Cómo sale todo por la serie**: `firmware/src/protocolo_serial.c`.
7. **El lado de la PC**: `herramientas/consola.py`, clase `Banco`: `traducir` (alias → comandos),
   `leer` (hilo que recibe), `mensaje_json` (qué hace con cada mensaje); luego `Captura` (escribe el CSV).
8. **Lo que viene**: `firmware/include/pid_controller.h` y `firmware/src/pid_controller.c`.
9. **Cómo se prueba sin placa**: `firmware/tests/test_registrador.py` y los escenarios de
   `firmware/tests/pruebas_host.c`, que describen el comportamiento esperado de cada comando.

## Ensayo automático

```mermaid
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
    acel -->|"0,5 s sin subir<br/>más de 2 %"| grab
    grab -->|"t = 300 ms"| fren
    fren -->|"10 s o parar"| cierre
    cierre --> csv
    acel -.->|"15 s sin<br/>estabilizar"| error

    linkStyle 0,1,2,3,4 stroke:#d1700a,stroke-width:1.8px
    linkStyle 5 stroke:#c62828,stroke-width:1.6px
    style esp fill:none,stroke:#8b949e,stroke-width:1px
```

Con el mismo porcentaje de motor, cada repetición parte de la misma velocidad: el motor se corta
cuando la velocidad deja de subir, no a un tiempo fijo.
