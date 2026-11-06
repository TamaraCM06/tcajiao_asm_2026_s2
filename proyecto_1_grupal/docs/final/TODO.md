# 1. Trabajo pendiente para entregar

Fuente de verdad: [enunciado del proyecto](../references/ASM_Proyecto_Grupal1_v7.pdf).
La [matriz de la rubrica](RUBRICA_DEFENSA.md) relaciona los nueve rubros con evidencia
y explicaciones pendientes; las pruebas de software no equivalen a una nota funcional.
Los comandos estan en el [manual de usuario](MANUAL_USUARIO.md).
Este bloque prepara software y procedimientos; no programa placas ni crea commits.

## 1.1. Ejecutar y revisar los ensayos

| ID | Pendiente real | Como cerrarlo | Responsable |
|---|---|---|---|
| F1 | Programar la version nueva y comprobar adquisicion, sonido e integracion | Manual 1.2--1.4 y 1.12: captura Pico, tres WAV y escucha FIR/espectral; revisar Sat y cambios de Perd/Err/Rein en Pico. El flujo requiere ordenar reproduccion; no acredita aun cadena completa automatica ni adecuacion cuasi real | P1/P3 |
| F2 | P1--P5, tres ejecuciones nuevas por condicion y sonido | Manual 1.5: 15 evaluaciones CSV en ESP32 y tres capturas acusticas por condicion fisica utilizada. No copiar carpetas como repeticiones. Resumen con media y desviacion | Equipo |
| F3 | Prevencion de aliasing no demostrada, requisito PDF 2 | Manual 1.6: revisar cadencia y espectros; el montaje acustico actual no demuestra rechazo antes del ADC. Declarar la limitacion no satisface el requisito | P1/P3 |
| F4 | Obtener atenuacion regional en las corridas nuevas | Manual 1.7: evaluar selecciona region del caso y ESP32 calcula residuos; revisar estado y region_muestras. P3/P4 son banda ancha, no tono aislado | P3/P4 |
| F5 | Obtener costos, memoria y latencia digital de las sesiones nuevas | Manual 1.7: revisar tiempos por ruta, cola, evaluacion, publicacion, arranque y cierre; comparar calculo conjunto con criterio interno de 32000 us. No llamarlo latencia analogica | P3/P4 |
| F6 | Ensayar P6 y ajustes sin recompilar | Manual 1.8: CSV desconocido, referencia presente/ausente, region configurable y escucha. P6 real se completa en defensa | Todos |

Los ensayos del manual tienen herramientas disponibles. Esto no significa que
este acreditado todo el enunciado o el nivel excelente de la rubrica: siguen
abiertos la prevencion de aliasing y la integracion automatica/cuasi real completa.
Los resultados pueden revelar fallos que deban corregirse. No se cambia la
arquitectura ni se recuperan modos retirados por esta revision documental.

## 1.2. Documentacion, defensa y entrega

| ID | Pendiente | Cierre |
|---|---|---|
| F7 | Incorporar resultados y limites reales | Manual 1.9: seleccionar tablas/figuras, respuesta FIR, repeticiones, atenuacion regional y tiempos. Separar CSV en placa, captura acustica, simulacion y analogica |
| F8 | Terminar articulo y herramientas | Sustituir pendientes; compilar y revisar limites de cuatro y dos paginas, referencias y abstract |
| F9 | Ensayo y release del equipo | Defensa de hasta 15 min, todos participan y explican codigo; revisar diff, integracion y tag segun flujo acordado. No se hicieron commits en este bloque |

## 1.3. Limites aceptados y criterios internos

Aceptados como alcance de trabajo por el usuario; no implican excepciones a los
requisitos academicos ni aprobacion del profesor.

| Elemento | Tratamiento |
|---|---|
| Fuente fisica | Audio del notebook por parlante hacia microfono; volumen, distancia y observaciones en notas.txt |
| Referencia | Solo CSV controlados; no asignar el WAV limpio a una captura acustica sin sincronizacion |
| Antialiasing de entrada | No comprobado con el montaje y ensayos elegidos. Es una limitacion de cobertura, no un requisito cumplido |
| Latencia analogica | No medida. Los tiempos nuevos terminan en aceptacion UART dentro de ESP32; excluyen ADC, PC y DAC |
| Concordancia Python | Umbral interno conservado de 90 %, distinto de ruido eliminado |
| Calidad y calculo | Mantener criterios_finales.json, sin cambiar umbrales para aprobar resultados |
| Demo analogica adicional | Opcional para reconstruccion de salida; no valida antialias del ADC |
| Registros | Mantener originales utilizados localmente; seleccionar evidencias pequenas para Git |

## 1.4. Limpieza local pendiente por bloqueo de herramienta

La revisión automática rechazó la eliminación física por terminal con el motivo
blocked by policy, incluso para un único archivo. El editor permitió retirar código
y texto. No se considera completada la limpieza de estos grupos, ni se crearon respaldos.

| Grupo | Pendiente y límite |
|---|---|
| Datos binarios del banco retirado | Eliminar los tres archivos float32 que aún quedan en firmware/esp32/components/senales_embebidas/datos; no se compilan ni pertenecen a la entrega |
| Sesiones de diagnóstico no utilizadas | Eliminar todas salvo los originales 20261105T164053Z_77315ebc, 20261105T164327Z_614a343d, 20261105T165522Z_88f6f6f0 y la medición analógica 20261105T185714Z_80cf289c |
| Copias y cálculos temporales | Eliminar copias completas bajo evidencias/sesiones y evidencias/analogicas, resultados/verificacion_final_pc y resultados/entrega; preservar las seis evidencias seleccionadas |
| Cachés y herramientas duplicadas | Eliminar directorios python y python_directo, capturas PNG y logs de revisión bajo build/herramientas_tex; conservar tectonic.exe, fonts.conf y build/ruta_compilacion.txt |
| Otros residuos regenerables | Eliminar preescuchas Pn, cachés y carpetas vacías retiradas; conservar .venv, entregas anteriores y resultados históricos |

Las 21 carpetas (356.14 MiB) se eliminan desde el explorador; conservar
resultados/sesiones originales, evidencias seleccionadas, .venv y entregas anteriores.
No impide ejecutar el manual; no se declara espacio liberado.

## 1.5. Verificacion tecnica completada

| Comprobacion | Resultado observado |
|---|---|
| Suite Python y C portable | 195 aprobadas en 18.26 s, sin omisiones; energias C frente a NumPy, tiempos con reloj controlado, JSON real menor de 4096 bytes, notas y compatibilidad |
| Receptor C | GCC: ADC/DC/RMS, FFT frente a DFT, Hann, estimacion, CRC8 y trama SPI correctos |
| ESP32 | ESP-IDF 5.5.5: aplicacion unica compilada con instrumentacion; ruta_compilacion.txt apunta a esa copia |
| Preparacion sin CSV | Seis casos de 96000 muestras y seis juegos de audios generados desde cero; carga PCM16 sin recortes |
| Historia | 77 archivos protegidos con SHA256 identico; tres sesiones originales abiertas completas |
| Documentos | Articulo cuatro paginas; herramientas dos; sin referencias sin resolver |
| Limite | No se programaron placas ni se reprodujo audio. Borrado fisico rechazado por politica; sin commits ni respaldos |
