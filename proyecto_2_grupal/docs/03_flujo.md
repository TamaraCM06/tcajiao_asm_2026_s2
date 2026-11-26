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
8. **De los ensayos al modelo**: [pruebas_pid.py](../herramientas/pruebas_pid.py) (barrido con el
   criterio de estabilidad del firmware, elección de velocidades y ensayos del
   [plan](../herramientas/plan_identificacion.csv)) y [modelo_planta.m](../herramientas/modelo_planta.m)
   (fricción, freno, zona muerta, validación y G(s) para el PID).
9. **Lo que viene**: [pid_controller.h](../firmware/include/pid_controller.h) y
   [pid_controller.c](../firmware/src/pid_controller.c).
10. **Cómo se prueba sin placa**: [test_registrador.py](../firmware/tests/test_registrador.py), [test_pruebas_pid.py](../firmware/tests/test_pruebas_pid.py)
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
    acel -->|"5 lecturas dentro de ±7 %<br/>una cada 500 ms"| grab
    grab -->|"t = 300 ms"| fren
    fren -->|"duración configurada o parar"| cierre
    cierre --> csv
    acel -.->|"límite de impulso<br/>sin estabilizar"| error

    linkStyle 0,1,2,3,4 stroke:#d1700a,stroke-width:1.8px
    linkStyle 5 stroke:#c62828,stroke-width:1.6px
    style esp fill:none,stroke:#8b949e,stroke-width:1px
~~~

El motor se corta cuando cinco lecturas consecutivas quedan dentro de una banda de ±7 %.
La primera lectura válida, finita y positiva fija la referencia y cuenta como lectura 1.
La referencia permanece fija mientras las lecturas aceptadas estén dentro de la banda;
ambos extremos están incluidos.

| Parámetro de estabilidad | Valor | Significado |
|---|---|---|
| Tolerancia relativa | ±7 % de la referencia | Por ejemplo, una referencia de 1000 RPM admite de 930 a 1070 RPM |
| Lecturas consecutivas | 5, incluida la referencia | Cuatro lecturas todavía no habilitan el registro |
| Separación mínima | 500 ms | Cadencia comparable al sondeo de la consola, independiente del bucle de 1 ms |
| Ventana mínima completa | 2 s entre primera y quinta lectura | Puede durar más si faltan lecturas; no hay una espera adicional de 3 s |
| Lectura nueva | Último pulso aceptado distinto del usado en la evaluación anterior | Consultar otra vez el mismo estado del sensor no aumenta el conteo |

| Situación durante la aceleración | Comportamiento |
|---|---|
| Lectura nueva dentro de ±7 %, al menos 500 ms después de la anterior | Aumenta el conteo, sin mover la referencia |
| Lectura evaluada fuera de la banda, por arriba o por abajo | Usa la velocidad actual como referencia y empieza otra cuenta desde 1 |
| Lectura inválida, no finita o no positiva | Descarta referencia y conteo; exige cinco lecturas nuevas tras recuperarse |
| Consulta demasiado rápida o sin pulso nuevo | No aumenta el conteo; tampoco reconstruye lecturas faltantes |
| Quinta lectura aceptada | Corta el motor, empieza a registrar y aplica el freno tras la espera |
| Motor cortado antes de estabilizar | Conserva el error velocidad_maxima_no_alcanzada; no empieza a registrar |

El límite de impulso continuo se toma de CONFIG_ASM_MOTOR_MAXIMO_IMPULSO_MS en
[sdkconfig.defaults](../firmware/sdkconfig.defaults). La estabilidad debe completarse antes
de agotarlo; esta modificación no cambia ese límite ni la duración configurada de la captura.
El evento velocidad_maxima conserva su nombre por compatibilidad y contiene la referencia
de la banda aceptada; no demuestra una velocidad máxima. La velocidad medida al comenzar
la captura queda en el CSV.

El estimador entrega ahora el tiempo del último pulso aceptado en ultimo_pulso_us,
además del tiempo de consulta. El coordinador usa ese campo interno para distinguir
lecturas nuevas. La captura y el protocolo conservan sus tres columnas.

El mismo porcentaje de motor puede producir distintas RPM entre repeticiones. Este criterio
comprueba estabilidad aproximada; para comparar ensayos todavía hay que verificar que las
velocidades iniciales medidas estén dentro de la tolerancia elegida para cada condición.

## 1.4. Diagnóstico del inicio de captura

El firmware envía un mensaje de tipo estabilidad por cada lectura que cuenta para la decisión.
La consola muestra esos mensajes directamente, sin aplicar el límite de refresco de pantalla.
Tras recibir el primero, deja de imprimir el sondeo de aceleración que consultaba el sensor
en otro instante. El comando estado y la visualización del motor manual continúan disponibles.

| Dato mostrado | Significado |
|---|---|
| detector, tiempo en segundos | Tiempo de la ESP32 desde que aceptó el comando ENSAYO |
| RPM | Lectura usada por el detector, sin sustituirla por otro sondeo de la consola |
| ref | Referencia contra la que se comparó esa lectura |
| banda | Extremos inclusivos calculados con ±7 % de esa referencia |
| Conteo, por ejemplo 3/5 | Número de lecturas aceptadas de la cuenta vigente |
| referencia inicial | La lectura fija una referencia nueva y cuenta como 1 |
| dentro de banda | Mantiene la referencia y aumenta el conteo |
| fuera de banda: reinicio con ref | Muestra la banda anterior y la nueva referencia; el conteo vuelve a 1 |
| lectura invalida: reinicio | El conteo pasa a 0 y se descarta la referencia |
| estable: cumple criterio | La quinta lectura cumple la condición; después se intenta cortar el motor e iniciar el registro |

Ejemplo de dos decisiones consecutivas:

~~~text
detector  0.50 s · RPM 1050.0 · ref 1000.0 · banda [930.0, 1070.0] RPM · 2/5 · dentro de banda
detector  1.00 s · RPM 1100.0 · ref 1000.0 · banda [930.0, 1070.0] RPM · 1/5 · fuera de banda: reinicio con ref 1100.0
~~~

La segunda línea explica por qué se reinició: 1100 RPM supera el máximo anterior de 1070 RPM.
La siguiente comparación usará 1100 RPM como referencia. Los valores de pantalla se redondean;
los mensajes estructurados llevan tres decimales y el cálculo conserva la precisión del estimador.

Una lectura inválida reinicia inmediatamente la cuenta. Se informa esa pérdida al ocurrir;
si persiste, se repite el aviso como máximo cada 500 ms. La recuperación conserva la separación
mínima desde la última lectura evaluada, de modo que alternar estados no acelera el conteo.
Los mensajes con valores no finitos usan null para conservar JSON válido.

| Interfaz | Compatibilidad y alcance |
|---|---|
| Mensaje estabilidad | Añade tiempo_ms, velocidad_rpm, referencia_rpm, minimo_rpm, maximo_rpm, referencia_siguiente_rpm, lecturas, requeridas y decision |
| Configuración de ensayo | Añade estabilidad_tolerancia_porcentaje, estabilidad_lecturas y estabilidad_periodo_ms; se conservan en el JSON de cada captura |
| CSV | Conserva tiempo_ms, freno_deg y velocidad_rpm; los diagnósticos previos se muestran en consola y no se añaden al CSV |
| Consola con firmware anterior | Conserva el progreso de aceleración mientras no reciba mensajes de estabilidad |
| Aviso del límite de motor | Usa maximo_impulso_ms recibido de la placa; si falta, muestra un aviso sin inventar la duración |

## 1.5. Fundamento con las mediciones del banco

El usuario compartió cuatro aceleraciones, dos al 40 %, una al 30 % y una al 20 %.
Las 215 lecturas mostradas por la consola se conservan, incluidos ceros y lecturas
sin medida, en [estabilidad_observada.csv](../firmware/tests/datos/estabilidad_observada.csv).
Cada número de traza corresponde al orden de los ensayos originales. Los tiempos
proceden de la consola y tienen redondeo y saltos; no son un registro de todos los pulsos.

La tolerancia anterior de ±6 % se eligió porque, con la misma referencia fija, cinco lecturas
y ±5 %, el ensayo al 30 % no completaba la cuenta. El usuario autorizó ampliar a ±7 % como
ajuste experimental y mostrar las lecturas reales del detector, tras observar nuevos cortes
por tiempo y diferencias entre el sondeo de consola y la decisión. La reproducción sobre
el coordinador C de las mismas cuatro trazas produce:

| Traza | Motor original | Aceptación anterior ±6 % | Aceptación actual ±7 % | Referencia actual | RPM en la quinta lectura |
|---|---|---|---|---|---|
| 1 | 40 % | 15,0 s | 15,0 s | 1959,4 RPM | 1858,9 RPM |
| 2 | 40 % | 28,5 s | 21,5 s | 2110,0 RPM | 1990,2 RPM |
| 3 | 30 % | 17,4 s | 12,9 s | 1072,4 RPM | 1137,9 RPM |
| 4 | 20 % | 20,8 s | 20,8 s | 414,4 RPM | 428,8 RPM |

Estos son resultados de reproducción de lecturas, no nuevos ensayos físicos. No permiten
asegurar los mismos tiempos en placa: el firmware consulta con otra fase y dispone de
estados del sensor entre las líneas mostradas por la consola. Las trazas continúan subiendo
después de algunas ventanas, especialmente al 20 %, donde alcanzan 525,1 RPM al final.
El criterio acepta una meseta local y todavía debe contrastarse con el objetivo de la prueba.

Las trazas históricas mencionaban un límite fijo de 15 s, aunque llegaban aproximadamente
a 30 s. El aviso actual usa el límite informado por la ESP32. La tabla reproduce el criterio
de estabilidad; completar cada ensayo exige que su aceptación ocurra antes del límite de
impulso configurado. Un límite de 30 s deja margen para las cuatro aceptaciones calculadas.

## 1.6. Cierre, muestras y gráfica del CSV

La consola muestra filas de captura cada 100 ms aproximadamente, sin cambiar el período
del CSV, inicialmente de 20 ms. Al cerrar, un trabajador independiente lee el CSV completo,
imprime estadísticas y una tabla de filas originales y genera el PNG junto al CSV y JSON.
La figura muestra velocidad y orden del servo en ejes separados; conserva picos y huecos,
marca el cambio de freno y el primer cero y declara la integridad reportada en el JSON.

| Módulo de PC | Responsabilidad |
|---|---|
| [analisis_captura.py](../herramientas/analisis_captura.py) | Leer el CSV, calcular extremos, pendientes y tiempos observados y seleccionar filas reales para el resumen |
| [graficas_captura.py](../herramientas/graficas_captura.py) | Exportar el PNG con Matplotlib y abrir la imagen ya generada |
| [mensajes_banco.py](../herramientas/mensajes_banco.py) | Traducir errores con los parámetros efectivos incluidos por la placa |
| [consola.py](../herramientas/consola.py) | Recibir, guardar y coordinar el cierre y el postproceso sin bloquear UART |

Los errores de firmware añaden parametros con límites de motor, servo, espera y estabilidad.
La confirmación de CONFIG incluye período, duración y timeout aplicados. La consola prioriza
los datos de la respuesta y no atribuye un corte externo al límite temporal por suposición.
El protocolo mantiene las tres columnas del CSV y conserva los motivos existentes.

La [guía de capturas y gráficas](04_capturas_y_graficas.md) documenta comandos, interpretación,
las tres capturas conservadas y la separación entre orden de servo, velocidad estimada y medición física.

## 1.7. Estado de la modificación

| Campo | Estado |
|---|---|
| Responsable | Santiago; corrección del criterio de inicio del ensayo |
| Implementado | Estabilidad en ±7 %, diagnóstico, resumen del CSV, PNG automático y errores con parámetros efectivos |
| Compatibilidad | Conserva comandos seriales, CSV y espera de freno; añade campos de error y CONFIG, y la acción graficar en PC |
| Revisión | Código, documentación, enlaces locales y diff revisados |
| Verificación en PC | 51 pruebas aprobadas con python banco.py pruebas; compilación ESP32 aprobada con ESP-IDF v5.5.5; gráficas de capturas existentes 08, 09 y 10 generadas |
| Pendiente físico | Cargar el firmware y confirmar mensajes, cierre y apertura del visor durante otra captura real |
| Siguiente bloque | Consolidar trazabilidad y velocidades iniciales repetibles del roadmap |
