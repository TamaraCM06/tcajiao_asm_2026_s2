# Avance 2: taller de la semana 12

Material del avance del taller de la semana 12.

| Archivo | Contenido |
|---|---|
| [informe.pdf](informe.pdf) | Informe: proceso de diseño, criterios, validación y discusión |
| [README_EJECUCION.txt](README_EJECUCION.txt) | Guía general para ejecutar el prototipo, las pruebas, el emisor y el receptor |
| [empaquetar_entrega.py](empaquetar_entrega.py) | Arma el ZIP de entrega con los archivos del repositorio |
| [diagramas](diagramas/) | Fuentes Mermaid y PNG de las figuras del informe |

Para generar el ZIP, desde la raíz del repositorio:

```bash
python proyecto_1_grupal/docs/avance2/empaquetar_entrega.py
```

El paquete contiene el informe y la guía en su raíz y, debajo, `proyecto_1_grupal/` con los
programas.

## Diagramas

| Diagrama | Figura del informe | Para qué sirve |
|---|---|---|
| `diagramas/1_sistema_completo` | 2.1 | Arquitectura: qué parte del proyecto cubre cada punto del taller y el enlace SPI entre nodos |
| `diagramas/2_emisor_esp32` | 3.4 | Emisor (punto 2): de las muestras de Python a la flash, el DAC en GPIO25 y la evaluación en la placa |
| `diagramas/3_receptor` | 3.5 | Receptor (punto 3): conexión ESP32 → RC → ADC de la Pico, captura por DMA y cadena DC → Hann → FFT → pico, según [firmware/receptor](../../firmware/receptor/) |
| `diagramas/4_decision_receptor` | 3.6 | Receptor (punto 3): qué se revisa en cada fila de la consola de la Pico y cuándo la recepción es correcta |

Los diagramas siguen la guía de diagramas de bloques del curso: ruta principal de datos de
izquierda a derecha, señales con nombre y formato, y elementos deshabilitados con borde
discontinuo. Para regenerar uno (requiere Node.js), desde `diagramas/`:

```bash
npx -p @mermaid-js/mermaid-cli mmdc -i 3_receptor.mmd -o 3_receptor.png -s 3 -b white
```
