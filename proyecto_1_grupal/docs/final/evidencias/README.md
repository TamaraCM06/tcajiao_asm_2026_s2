# 1. Resultados seleccionados para el artículo

| Campo | Valor |
|---|---|
| Fuente de requisitos | [Enunciado](../../references/ASM_Proyecto_Grupal1_v7.pdf), §3.3, §3.5, §4 y §8 |
| Responsable | Autores de cada medida; P4 selecciona para el artículo |
| Política | En Git solo tablas y figuras utilizadas; registros completos locales, sin borrar originales |
| Pendientes experimentales | [TODO](../TODO.md) |

## 1.1. Selección actual

| Archivo | Origen y uso | Límite |
|---|---|---|
| [Resultados observados](resultados_observados.csv) | Dos sesiones del 5/11: 20261105T164053Z_77315ebc, captura Pico, y 20261105T164327Z_614a343d, CSV P2_tonal procesado en ESP32 | No son las tres repeticiones de P1–P5; MSE/SNR de micrófono quedan vacíos |
| [FIR CSV](fir/respuesta_fir_medida.csv), [figura](fir/respuesta_fir_medida.png) | Comparación con coeficientes usando entrada.wav/fir.wav de la sesión 164327; 93 bloques, 74 muestras iniciales omitidas | Dominio digital antes del DAC; a 4 kHz solo se resuelve cota inferior de atenuación |
| [Analógica CSV](analogica/comparacion_analogica.csv), [figura](analogica/respuesta_analogica.png) | Medición 20261105T185714Z_80cf289c; reanálisis con divisor, 22 nF y retención DAC | Tres tonos útiles válidos; 4 kHz inválido por variabilidad 19.3 %. No mide antialias antes del ADC |
| [Polos y ceros](../paper/figuras/fir_polos_ceros.png) | FIR Kaiser frente al IIR elíptico de orden 6, generada por prototipo.py | Modelo, no medición |
| [Respuesta del FIR](../paper/figuras/fir_respuesta_frecuencia.png) | Magnitud, rizado de banda de paso, fase y retardo de grupo, generada por prototipo.py | Modelo, no medición |
| [Señales P2](../paper/figuras/caso_2_graficas.png) | Señales y espectros del caso histórico P2 en simulación | Modelo, no medición |

El firmware declarado por las dos sesiones es 0cbd2b2-dirty, ESP-IDF 5.5.5. No se
atribuyen a esta revisión. Sus originales siguen en resultados/sesiones. Las copias
completas anteriores y los intentos no utilizados se seleccionaron para eliminar;
su eliminación física está pendiente por bloqueo de la herramienta. No forman
parte del código ni de la selección de entrega.

## 1.2. Qué guardar de las pruebas nuevas

| Elemento | Dónde conservarlo | Uso |
|---|---|---|
| Sesiones utilizadas con WAV, sesion.json, metricas.csv y eventos | resultados/pruebas_finales, local; conservar el original sin duplicarlo en docs | Escucha y repetición del análisis |
| Validación Python | Junto a la sesión, local | Verificación independiente complementaria |
| Resumen CSV y tabla LaTeX | resultados/entrega, local al generarlos | Escoger las filas reales que se reportan |
| Tabla final del artículo | [pruebas_finales.tex](../paper/tablas/pruebas_finales.tex) | Sustituir el pendiente con estadísticas reales, identificando origen y condiciones |
| Figuras seleccionadas P1–P5 y atenuación P1 | evidencias/pruebas, solo las seleccionadas | Espacio de entrega permitido por gitignore; no copiar todo el árbol de sesiones |

El PDF exige reportar parámetros, promedios y variabilidad y demostrar sonido;
no exige versionar todos los registros. Mostrar una prueba en la defensa no
reemplaza el resumen de las repeticiones en el informe.

## 1.3. Criterios de interpretación

| Dato | Interpretación |
|---|---|
| Concordancia PC | Coincidencia entre implementaciones, no porcentaje de ruido eliminado |
| Atenuación del ruido total | Métrica existente en ESP32; no equivale siempre a la interferencia principal |
| Atenuación tonal medida en WAV | Evidencia digital de la componente solicitada; si cae bajo PCM16 se reporta cota |
| Cálculo máximo | Tiempo de ejecutar DSP; no es latencia física entrada/salida |
| Modelo analógico con sinc | Componente fundamental del DAC y filtro de reconstrucción; no incluye todas las imágenes aliasadas |
| Ensayo analógico opcional | Puede respaldar el filtro de salida; no sustituye la validación obligatoria de muestreo y banda de entrada |

Para generar y seleccionar las salidas, seguir el [manual](../MANUAL_USUARIO.md).
