# 1. Trabajo pendiente para entregar

Fuente de verdad: [enunciado del proyecto](../references/ASM_Proyecto_Grupal1_v7.pdf).
Solo aparecen acciones pendientes; los procedimientos están en el
[manual de usuario y pruebas](MANUAL_USUARIO.md). No se hacen commits en este bloque.

## 1.1. Funcionalidad que todavía debe comprobarse o completarse

| ID | Requisito del PDF | Qué falta realmente | Cómo cerrarlo y qué conservar | Responsable |
|---|---|---|---|---|
| F1 | §1–1.1: adquisición separada, dos rutas y salida reproducible en tiempo real o cuasi real | Se observó una captura de 6 s, pero falta comprobar integralmente adquisición, filtrado y escucha de ambas rutas mediante sesiones PC | Manual §1.3–1.4. Capturar la misma fuente, escuchar los dos WAV por DAC y anotar errores/colas/recortes. Medir y justificar el comportamiento temporal del flujo vigente; la reproducción es diferida y no se presenta como audio continuo | P1/P3 |
| F2 | §2 y §4: P1–P5, tres repeticiones por condición, sonido, parámetros, promedios y variabilidad | Faltan las corridas finales. Las pruebas CSV no comprueban la adquisición ADC ni todo el circuito | Manual §1.5: 15 sesiones digitales mínimas y ensayos físicos de las mismas señales. Guardar sesiones localmente; obtener resumen con media y desviación y seleccionar resultados para el artículo. Si falta una fuente física controlada, resolverla antes de declarar el sistema completo | Equipo |
| F3 | §2: justificar muestreo y demostrar que se evita aliasing en las condiciones previstas | Falta validar la banda de entrada antes del ADC. El Sallen-Key actual está después del DAC | Manual §1.6. Revisar acondicionamiento y limitación de banda de la fuente/entrada; verificar respuesta con estímulos conocidos. Un pico de 7 kHz al aplicar 9 kHz demuestra aliasing. La ausencia del pico por sí sola no demuestra que se evita. Reportar límites si no se resuelve | P1/P3 |
| F4 | §3.5: atenuación de la interferencia principal | El firmware informa atenuación del ruido total, que no equivale siempre a la principal | Manual §1.7. En P1 medir el tono de 4 kHz con las salidas de placa y conservar CSV/espectros; a rechazo profundo reportar una cota. Para ruido de banda/superposición definir y justificar la región de interferencia y completar su medida; no renombrar ruido total como principal | P3/P4 |
| F5 | §3.5: latencia por bloque, costo y memoria | Hay tiempos conjuntos de cálculo y memoria; falta caracterizar latencia por bloque y tiempos individuales actuales | Manual §1.7. Instrumentar marcas sincronizadas de llegada, procesamiento y publicación de cada bloque en sesiones PC; medir reproducción por separado. Separar cálculo, colas y espera voluntaria de escucha. No inferir latencia física de los WAV. Fijar y justificar el criterio antes de las corridas finales | P3/P4 |
| F6 | §4, §6: P6 desconocida y ajuste sin recompilar | Falta ensayo operativo y ejecución real que definirá el profesor | Manual §1.8. Ensayar carga de CSV desconocido y cambios de parámetros; comunicar límites 16 kHz, entrada 256, FFT 1024, salto 512. P6 real solo se completa en la defensa; no inventar referencia limpia si no existe | Todos |

## 1.2. Documento, defensa y entrega

| ID | Requisito del PDF | Acción pendiente | Cierre |
|---|---|---|---|
| F7 | §3.3.5 y §8: respuesta calculada frente a medida, resultados y análisis | La respuesta FIR digital medida ya está disponible; falta integrar las repeticiones finales, latencia, atenuación principal y resultado de antialias | Seleccionar tablas/figuras pequeñas, sustituir pendientes del artículo y distinguir ADC, CSV en placa y simulación. El rechazo a 4 kHz está limitado por PCM16; no llamarlo medición analógica |
| F8 | §8: artículo ≤4 páginas, abstract inglés 150–250 palabras, ≤6 palabras clave; herramientas ≤2 páginas | Compilar y revisar otra vez después de introducir los resultados finales | Manual §1.9. Referencias citadas, sin código fuente en los dos PDF; herramientas debe describir solo lo efectivamente utilizado |
| F9 | §6–8: defensa ≤15 min, todos participan, sonido, P6 y explicación del código; ramas y tag | Falta ensayo completo, revisión grupal y release | Manual §1.9. Poder justificar cada módulo entregado; revisar commits incrementales, integrar mediante el flujo del equipo y crear tag al cerrar. Esta revisión no ejecuta commits, merge ni publicación |

## 1.3. Qué no se añade como requisito

| Elemento | Alcance correcto |
|---|---|
| Capturas de 60 s, tres veces | Diagnóstico interno recomendado si hay dudas de continuidad; el PDF no fija esa duración ni esa repetición para el enlace |
| Demo analógica de cuatro tonos y error ≤15 % | Ayuda a documentar el filtro de reconstrucción, §5.6. El PDF no exige ese ensayo ni ese porcentaje. El punto de 4 kHz actual es inválido; repetirlo es opcional si se quiere usar como validación cuantitativa |
| Concordancia Python ≥90 % | Criterio interno conservado por decisión del usuario; no sustituye las métricas y ensayos físicos obligatorios |
| Copiar todos los WAV, JSON y logs a Git | No es requisito. Los registros completos se conservan localmente; en Git van fuentes, documentos y resultados seleccionados |
| Resumen estadístico | Sí responde al §4, pero es una ayuda: puede calcularse de otra manera. No aprueba el proyecto automáticamente ni exige validación Python para promediar |

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
