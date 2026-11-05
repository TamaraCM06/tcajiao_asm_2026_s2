# 1. Preparación de la entrega final

| Campo | Valor |
|---|---|
| Fuente de verdad | [ASM Proyecto Grupal 1 v7](../references/ASM_Proyecto_Grupal1_v7.pdf) |
| Plazo | 6 de noviembre de 2026, 23:50, Costa Rica |
| Estado | Software y evidencias parciales disponibles; entrega funcional todavía pendiente de los ensayos y límites identificados |
| Pendientes reales | [TODO](TODO.md) |
| Operación y pruebas | [Manual de usuario](MANUAL_USUARIO.md) |
| Responsable | Cada autor revisa su componente; P3 integra ESP32 y P4 consolida |

## 1.1. Qué se entrega según el PDF

| Elemento | Ubicación | Criterio |
|---|---|---|
| Sistema funcional y defensa | Placas y código del proyecto | Adquisición separada; dos rutas comparables; reproducción; P1–P6; todos participan en ≤15 min |
| Artículo | [Fuente](paper/main.tex), [PDF](paper/main.pdf) | LaTeX con formato establecido, ≤4 páginas incluyendo referencias; resultados y discusión reales |
| Herramientas | [Fuente](herramientas/herramientas.tex), [PDF](herramientas/herramientas.pdf) | ≤2 páginas; selección, aplicación y adaptación de lo efectivamente utilizado |
| Modelo reproducible | [Notebook](../../tarea1_grupo1/notebook.ipynb), [prototipo](../../prototipo.py) | Generar señales, DFT/FFT, candidatos FIR/IIR y figuras/tablas |
| Resultados seleccionados | [Índice](evidencias/README.md) | Tablas/figuras que respaldan el artículo; el PDF no obliga a publicar todos los registros crudos |
| Release | Ramas del equipo y etiqueta | Pendiente de revisión e integración; sin commits en este bloque |

## 1.2. Estado comprobado y límites

| Observación | Qué demuestra | Qué no demuestra |
|---|---|---|
| Captura física de 6 s: 96000 muestras, 375 bloques, sin pérdidas ni recortes | Una adquisición Pico → ESP32 → PC completa | Toda la matriz P1–P5, audio continuo ni prevención de aliasing |
| Evaluación del CSV histórico P2_tonal en ESP32 | Cálculo de ambos filtros y métricas con referencia | El paso físico por ADC; no equivale al tono único P1 |
| FIR calculado frente a WAV medido | Diferencia <0.0035 dB en tonos útiles; cota de rechazo a 4 kHz | Respuesta analógica después del DAC ni rechazo profundo exacto por debajo del piso PCM16 |
| Tres tonos útiles del filtro analógico | Concordancia con modelo nominal y retención DAC en esos puntos | Antialias antes del ADC; el punto de 4 kHz es inválido por variabilidad |
| Tiempos conjuntos 16.323 ms en captura y 25.694 ms en evaluación; estado DSP 80960 bytes | Costo de la versión observada en placa | Latencia física ni tiempos individuales actuales |

Los límites de desempeño son decisiones del equipo, no cifras impuestas por el
enunciado. Los [criterios internos](../../metadatos/criterios_finales.json) conservan
concordancia ≥90 %. El [modelo analógico](../../metadatos/filtro_analogico.json)
conserva 22 nF y sus criterios. Las limitaciones no se cierran con documentación sola.

## 1.3. Para qué sirve cada herramienta

| Herramienta | Función | Relación con el PDF |
|---|---|---|
| [preparar_casos](../../herramientas/preparar_casos.py) | Prepara entradas locales con el generador del notebook; no reescribe el JSON fuente | §2 y §3.2: señales reproducibles |
| [sesiones PC](../../firmware/esp32/tools/sesiones.py) | Configura, captura o evalúa en ESP32, guarda WAV/métricas y solicita reproducción | Operación, comparación y evidencia; captura y escucha son etapas separadas |
| [resumen_pruebas](../../herramientas/resumen_pruebas.py) | Lee las sesiones completas directamente y calcula media/desviación por condición y método | §4 exige tres repeticiones y estadísticas. No filtra, no necesita otra copia de las sesiones y no califica el sistema |
| [graficar_sesion](../../herramientas/graficar_sesion.py) | Muestra señales y espectros de los WAV de placa; opcionalmente mide atenuación de tonos presentes | Evidencia P1, P2, P4 y comparación de salidas |
| [respuesta_fir_medida](../../herramientas/respuesta_fir_medida.py) | Compara ganancias de tonos de una sesión con los coeficientes FIR | §3.3.5: respuesta calculada frente a medida |
| validar / concordancia | Compara con Python sobre el mismo PCM16 | Verificación independiente complementaria; no porcentaje de ruido eliminado |
| demo analogico | Pico como instrumento de amplitud antes/después del filtro de salida | Apoyo al §5.6, filtro de reconstrucción; no acredita el antialias del ADC |

## 1.4. Qué pertenece a Git y qué es local

| Grupo | Política |
|---|---|
| Código, tests, JSON de configuración, documentación y PDF de entrega | Se mantienen |
| Coeficientes FIR | Se mantienen en filtros_digitales; registros y exportador del banco flash retirados de la aplicación |
| CSV P1–P5/P2_tonal y WAV sintéticos de preescucha | Ignorados, regenerables; carga automática cuando falta el CSV |
| Sesiones completas, JSON de ejecución, WAV de placa, logs y cálculos intermedios | Locales bajo resultados; conservar para ensayar, revisar y respaldar mediciones |
| Copias completas previas bajo evidencias | Son residuos para eliminar; la eliminación física está pendiente por bloqueo de la herramienta. No son necesarias para compilar ni para entregar el código |
| Tablas/figuras seleccionadas del artículo | Se mantienen; ver [índice](evidencias/README.md) |
| Migración local de sesiones antiguas | consolidar_evidencias retirado; no forma parte de la aplicación |

Un JSON de configuración define el experimento o modelo: sí es fuente. Un
sesion.json registra una ejecución: es salida local. Su extensión no determina
por sí sola si debe estar en Git.

## 1.5. Revisión de este bloque

| Elemento | Cambio y verificación |
|---|---|
| Alcance | TODO y manual referidos a secciones concretas del PDF; se retiran obligaciones inventadas |
| Organización | Una aplicación PC, procesador finito y coeficientes reubicados; modos antiguos retirados del código. Cuatro originales y seis resultados seleccionados protegidos |
| Compatibilidad | Nombres P1–P5 y P2_tonal; alias históricos conservados. Las entradas faltantes se preparan automáticamente |
| Resumen | Separa configuraciones y origen; no mezcla ADC y CSV, no exige concordancia complementaria para calcular estadísticas |
| Pendiente experimental | F1–F6 del TODO; no se ejecuta hardware automáticamente ni se inventan resultados |
| Verificación de cierre | 175 pruebas aprobadas; receptor C OK; única aplicación PC compilada; PDF de 4 y 2 páginas. Limpieza física incompleta por bloqueo de la herramienta; [detalle](MANUAL_USUARIO.md#110-comprobaciones-realizadas-durante-la-preparación). No se ejecutaron placas ni commits |
