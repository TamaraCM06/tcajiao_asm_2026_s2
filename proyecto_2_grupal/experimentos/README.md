# 1. Captura manual de ensayos

## 1.1. Estado y responsabilidad

| Campo | Valor |
|---|---|
| Responsable de este bloque | Santiago, Persona 3 |
| Implementado | Receptor serial minimo para ESP32; CSV y metadatos JSON |
| Analisis del companero | Consume el CSV; no se modifica ni se replica h(t) |
| Plataforma PC | MATLAB R2025b localizado; utiliza serialport, sin toolbox de identificacion |
| Verificacion | mlint sin observaciones; 10 pruebas preparadas, ejecucion pendiente por licencia |
| Hardware | Requiere configuracion y calibracion del firmware |

## 1.2. Entrada y operaciones

[ejecutar_caso.m](ejecutar_caso.m) es la unica entrada de captura. Resuelve rutas
desde su archivo y guarda en datos, sin depender del directorio de trabajo.
Agregar esta carpeta al path de MATLAB antes de llamar a la funcion.

| Paso | Expresion MATLAB | Significado |
|---|---|---|
| Crear parametros | parametros = struct('periodo_ms', periodo_elegido, 'duracion_ms', duracion_elegida, 'timeout_ms', timeout_elegido, 'calibracion_id', 'identificador_real'); | Tiempos enteros en ms; elegir con el montaje |
| Abrir sesion | sesion = ejecutar_caso("COMx", "ensayo_01", parametros); | Reserva CSV y JSON nuevos, conecta y envia CONFIG |
| Liberar | sesion.enviar("FRENO " + string(angulo_liberado)); | Angulo calibrado de menuconfig |
| Impulsar | sesion.enviar("MOTOR " + string(porcentaje_elegido)); | Dentro del maximo calibrado |
| Iniciar | sesion.enviar("START"); | Corta motor e inicia el origen de tiempo |
| Aplicar freno | sesion.enviar("FRENO " + string(angulo_elegido)); | La respuesta incluye instante de aplicacion |
| Consultar | sesion.enviar("STATUS"); | Estado del microcontrolador |
| Finalizar antes del limite | sesion.enviar("STOP"); | La duracion configurada tambien finaliza automaticamente |
| Ver resultado | resultado = sesion.estado(); | Rutas y metadatos; revisar completo |
| Cerrar conexion | sesion.cerrar(); | Solicita STOP y libera puerto y timer |

La funcion devuelve operaciones inmediatamente; el callback serial sigue
recibiendo mientras se usan los comandos en la consola MATLAB. Cerrar idf monitor
u otro programa que tenga abierto el mismo puerto. Usar un nombre distinto
por ensayo; despues de fin, cerrar y abrir una sesion nueva. No enviar START
de nuevo con los mismos archivos. Cerrar expresamente la sesion antes de
eliminar su variable del workspace.

## 1.3. Contrato de datos

Cabecera exacta: tiempo_ms,freno_deg,velocidad_rpm. Coma separadora y punto decimal.

| Campo | Unidad | Interpretacion |
|---|---|---|
| tiempo_ms | ms, tres decimales | Reloj ESP32 desde corte del motor |
| freno_deg | grados | Orden al MG90S; no mide posicion o fuerza |
| velocidad_rpm | vueltas/minuto | Ultimo intervalo valido entre marcas; NaN si falta intervalo |
| cero por timeout | vueltas/minuto | Inferencia por ausencia de pulsos; no diagnostica sensor sano |

Cada JSON conserva parametros solicitados, configuracion efectiva recibida,
revision del firmware, eventos con tiempo ESP32 y resumen de cierre. No hay
filtrado ni remuestreo en PC. El timeout del receptor solicita STOP si no llega
fin cinco segundos despues del tiempo configurado y conserva captura incompleta
si el cierre sigue ausente tres segundos mas. No sobrescribir ni corregir datos
crudos para mejorar el ajuste.

Si START no recibe inicio en cinco segundos, el receptor solicita STOP y conserva
el ensayo como incompleto. Un error explicito del firmware permite corregir la
orden y reintentar antes de comenzar el registro.

## 1.4. Compatibilidad y continuidad

[casos.json](casos.json) conserva las plantillas deshabilitadas del futuro PID.
Este receptor manual recibe una estructura de parametros y no ejecuta ese JSON.
[registro_ensayos.csv](datos/registro_ensayos.csv) sigue siendo el inventario
general del equipo; el receptor no inventa velocidades objetivo, fase o validez
experimental para rellenarlo. Registrar esos datos cuando se hagan mediciones.

El anterior esquema de nueve columnas era una propuesta para PID, sin capturas
ni consumidores implementados en esta rama. El esquema vigente de este bloque
tiene tres columnas; el formato final con referencia y error se coordinara al
integrar el controlador.

## 1.5. Fundamento y limites

Se identificara la relacion entre orden de freno y velocidad bajo condiciones
controladas; los grados no equivalen directamente a par. Fijar velocidad inicial,
corte del motor, referencia temporal del ensayo, calibracion y condiciones
mecanicas antes de comparar. El modelo debe validarse con corridas independientes.

Fuente de comunicacion: [serialport de MathWorks](https://www.mathworks.com/help/matlab/ref/serialport.html).
El codigo de analisis h(t) del companero aun no esta en esta rama; confirmar con
el sus unidades y convencion de entrada antes de interpretar un modelo.

## 1.6. Pruebas del receptor

| Accion MATLAB con licencia activa | Expresion |
|---|---|
| Ejecutar las 10 pruebas | resultados = runtests('proyecto_2_grupal/experimentos/tests'); assertSuccess(resultados); |

Las pruebas usan archivos temporales y no abren puertos. Cubren columnas,
conteos, tiempos repetidos, NaN, cierre ausente, texto intercalado, configuracion
incompleta, inicio duplicado y no sobrescritura. La prueba con trama C requiere
ejecutar primero las [pruebas host](../firmware/tests/README.md).
