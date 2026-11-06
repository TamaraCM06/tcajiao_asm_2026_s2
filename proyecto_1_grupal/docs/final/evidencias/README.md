# 1. Resultados seleccionados para el artículo

En Git solo van las tablas y figuras que respaldan el artículo. Las sesiones
completas (WAV, `sesion.json`, `metricas.csv`) quedan locales en `resultados/`.

## 1.1. Pruebas P1–P5 en placa (6/11)

| Archivo | Contenido |
|---|---|
| [resumen_final.csv](pruebas/resumen_final.csv) | Media y desviación por prueba y método de las 14 evaluaciones completas en la ESP32 (firmware 50c161c): calidad, tiempos, memoria e integridad |
| [P1](pruebas/P1_senales_espectros.png), [P2](pruebas/P2_senales_espectros.png), [P3](pruebas/P3_senales_espectros.png), [P4](pruebas/P4_senales_espectros.png), [P5](pruebas/P5_senales_espectros.png) | Señales y espectros de entrada, FIR y espectral de una sesión por prueba |
| [P1_atenuacion_tonos.csv](pruebas/P1_atenuacion_tonos.csv) | Tono útil de 440 Hz intacto; interferencia de 4 kHz atenuada ≥ 57.8 dB (FIR, cota por PCM16) y 20.0 dB (espectral) |

La Tabla II del artículo se resume de `resumen_final.csv`. Tres intentos se
abortaron por tramas USB truncadas detectadas y se repitieron; no se incluyen.

## 1.2. Mediciones anteriores (5/11)

| Archivo | Contenido | Límite |
|---|---|---|
| [resultados_observados.csv](resultados_observados.csv) | Captura física con micrófono (375 bloques, sin pérdidas) y CSV P2_tonal en la ESP32 | Firmware 0cbd2b2; sin MSE/SNR en la captura |
| [FIR CSV](fir/respuesta_fir_medida.csv), [figura](fir/respuesta_fir_medida.png) | Ganancia del FIR calculada frente a la medida en WAV | Dominio digital, antes del DAC |
| [Analógica CSV](analogica/comparacion_analogica.csv), [figura](analogica/respuesta_analogica.png) | Sallen-Key de 22 nF medido con la Pico como instrumento | 4 kHz inválido por variabilidad de 19.3 % |

## 1.3. Figuras del modelo

| Archivo | Contenido |
|---|---|
| [Polos y ceros](../paper/figuras/fir_polos_ceros.png) | FIR Kaiser frente al IIR elíptico de orden 6 |
| [Respuesta del FIR](../paper/figuras/fir_respuesta_frecuencia.png) | Magnitud, rizado, fase y retardo de grupo |
| [Señales P2](../paper/figuras/caso_2_graficas.png) | Señales y espectros de P2 en simulación |
| [Compromiso P5](../paper/figuras/espectral_compromiso_ruido_distorsion.png) | Ruido eliminado frente a energía útil conservada |

Las genera `prototipo.py`. Los comandos para producir y copiar resultados están
en el [manual](../MANUAL_USUARIO.md#17-resultados-para-la-entrega).
