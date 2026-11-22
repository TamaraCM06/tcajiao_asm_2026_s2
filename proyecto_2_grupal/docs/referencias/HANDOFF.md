# HANDOFF — Tarea 2 + Proyecto Grupal 2 (ASM, CE 1110)

> Estado al **sábado 21 nov 2026**. Resume lo que ya decidimos para que cualquiera del grupo pueda continuar sin releer toda la conversación.
> Enunciados completos: [`tarea_2/ENUNCIADO_TAREA_2.md`](tarea_2/ENUNCIADO_TAREA_2.md) · [`proyecto_2/ENUNCIADO_PROYECTO_2.md`](proyecto_2/ENUNCIADO_PROYECTO_2.md)

## Fechas

| Entrega | Fecha | Cómo |
|---|---|---|
| **Tarea 2** | **Dom 22 nov 2026, 11:59 pm** (−1 punto por minuto tarde) | PDF en TEC-Digital (Word o LaTeX libre) + links YouTube no listados |
| **Proyecto Grupal 2** | **Mié 2 dic 2026** — defensa ese día, archivos 11:50 pm | Repo git + paper IEEE LaTeX ≤ 4 págs |

---

## 1. Qué es el sistema (entendimiento acordado)

Banco de frenado: un **disco** movido por un **motor DC**, un **freno de zapata accionado por servomotor**, un **encoder óptico** (marcas negras sobre la rueda café) y un **microcontrolador** con PID discreto.

**Flujo de un run:**

1. El motor lleva el disco a una velocidad inicial ω₀ **repetible**.
2. Se corta o reduce el motor y arranca la referencia ω_ref(t), que es decreciente.
3. Cada Ts el micro mide ω(k), calcula el error `e(k) = ω(k) − ω_ref(k)` y el PID ajusta el ángulo del servo:
   - si va **más rápido** que la curva → **aprieta** más;
   - si va **más lento** → **suelta**.
4. El run termina cuando ω llega a 0 o casi. No hace falta controlar fino cerca de cero.

**El PID controla el servo, no el motor.** El motor solo da la energía inicial.

### Roles de cada pieza (no mezclarlos)

| Pieza | Qué responde | Quién la define |
|---|---|---|
| **Referencia** ω_ref(t) | *Cómo queremos* que frene | Nosotros (decisión de diseño) |
| **Modelo** G(s)/G(z) | *Cómo responde* el disco al freno (ángulo servo → ω / desaceleración) | MATLAB, con datos de lazo abierto |
| **PID** | *Cuánto* mover el servo según el error | Diseñado con el modelo, ajustado en el banco |

- **Referencia elegida (propuesta):** una **rampa de desaceleración constante**, `ω_ref(t) = ω₀ − a·t`. No es obligatoria, pero es la más simple de justificar.
- **Restricción física:** el freno es **unilateral**: solo quita velocidad. La pendiente `a` tiene que cumplir:
  - **a mayor que** la desaceleración natural sin freno (solo fricción). Si no, el disco se queda atrás y el PID no puede hacer nada.
  - **a menor que** la desaceleración con el freno a tope. Si no, el servo se satura.
  - Ambos límites se miden en lazo abierto. El PID necesita **saturación + anti-windup**.
- **El modelo SÍ es obligatorio para diseñar el PID.** La sección 2.4 del proyecto pide Laplace/Z, la ecuación de control, los parámetros iniciales y los polos/ceros del controlador y del lazo cerrado *según el modelo obtenido*. Llegar solo con ganancias a prueba y error pierde puntos.

---

## 2. Decisiones técnicas

### Encoder (medición de velocidad)
- 12 marcas = 12 pulsos/vuelta contando solo negro→café. Contando ambos flancos son **24**, el doble de resolución sin costo.
- Las marcas tienen que estar **uniformes**. Si no, aparece ruido periódico en ω.
- **Lectura por interrupción** (`attachInterrupt` / input capture). La ISR guarda `micros()` en cada flanco, así **no se pierde ninguna marca** y no aplica Nyquist a la lectura.
- **ω por tiempo entre flancos:** `ω = (2π/N) / Δt`. **No contar flancos por ventana**: con N=12 y Ts=20 ms la resolución sería ≈ 26 rad/s, inservible a baja velocidad.
- **Timeout:** si pasa demasiado tiempo sin flanco → ω ≈ 0.
- **Chequeo a velocidad máxima:** p. ej. 3000 rpm × 12 = 600 flancos/s, uno cada 1,7 ms. Sin problema.

### Frecuencia de muestreo del PID
- **Propuesta: 50 Hz (Ts = 20 ms).**
- **Justificación:**
  1. Un servo de hobby se actualiza cada 20 ms (PWM a 50 Hz); ir más rápido no aporta.
  2. La regla Ts ≈ τ/10 a τ/20: con un frenado de 1–3 s, τ ≈ 0,2–1 s → Ts entre 10 y 100 ms.
  3. Un frenado de 2 s da unas 100 muestras para identificar en MATLAB.
- **Teoría:** Nyquist (2×) no alcanza en control porque el ZOH mete un retardo de ≈ Ts/2. La regla es muestrear 10–30× el ancho de banda del lazo cerrado.
- **Confirmar con τ real** de la respuesta al escalón: si τ < 0,2 s, bajar Ts a 10 ms para la medición.
- **Ts no depende de la velocidad máxima.** La velocidad máxima solo sirve para validar el encoder y las interrupciones.

### PID en el micro
- **Discretización:** Euler hacia atrás o Tustin.
  `u[k] = Kp·e[k] + Ki·Ts·Σe + Kd·(e[k] − e[k−1])/Ts`
  más **saturación** al rango del servo, **anti-windup** (clamping) y, de preferencia, **filtro en el derivativo**.
- **Periodo fijo SIN `delay()`:** timer o `millis()` no bloqueante.
- **Por qué no `delay()`:**
  - Bloquea el micro: no puede registrar datos por serial ni atender botones.
  - El periodo real queda en `delay` + tiempo de ejecución variable (jitter), y entonces deja de coincidir con el Ts que se usó para diseñar.

---

## 3. Plan — Tarea 2 (para MAÑANA)

| # | Pregunta | Peso | Responsable | Estado / notas |
|---|---|---|---|---|
| 1 | Impulso vs escalón, con ejemplo en el proyecto | 20 % | _compañero_ | Escalón = poner el servo en un ángulo fijo y medir ω(t). Impulso = un "toque" breve del freno. |
| 2 | Frecuencia de muestreo + propuesta | 15 % | **yo** | Borrador ya escrito (doc en Claude). Pasar al PDF con citas IEEE. |
| 3 | PID en micro, por qué no `delay`, código sin `delay` | 15 % | **yo** (texto) + compañero (código) | Coordinar: Ts = 20 ms con `millis()`/timer, ω desde ISR del encoder. |
| 4 | Diagrama de bloques + prosa continuo/discreto | 25 % | _por asignar_ | Continuo: motor, disco, fricción, zapata. Discreto: micro, PID, ZOH/PWM del servo, encoder muestreado. |
| 5 | Modelo matemático teórico + respuesta esperada sin controlador | 25 % | _por asignar_ | `J·dω/dt = −b·ω − T_freno(u) − T_c` → 1.er orden + retardo del servo. Esperado: caída tipo exponencial/rampa; extraer τ, ganancia K, retardo. |
| 6 | Construir la planta (fotos + video en lazo abierto) | +40 % | todos | Solo si da tiempo. |
| 7 | Respuesta al escalón en físico + MATLAB (un solo video) | +40 % | todos | Solo si da tiempo. |

**Entregable:** un PDF con todo referenciado, el listing del código y los links de YouTube no listados.

**Referencias base (IEEE):**
- [1] K. J. Åström y B. Wittenmark, *Computer-Controlled Systems: Theory and Design*, 3.ª ed. Prentice Hall, 1997.
- [2] G. F. Franklin, J. D. Powell y M. L. Workman, *Digital Control of Dynamic Systems*, 3.ª ed. Addison-Wesley, 1998.
- [3] K. Ogata, *Sistemas de control en tiempo discreto*, 2.ª ed. Prentice Hall, 1996.
- [4] K. J. Åström y T. Hägglund, *Advanced PID Control*. ISA, 2006.
- [5] Hoja de datos del servo que usemos (p. ej. SG90 / MG996R) para el periodo PWM de 20 ms.

---

## 4. Plan — Proyecto Grupal 2 (hasta 2 dic)

| Semana | Fechas | Sección del enunciado | Trabajo concreto | Entregables |
|---|---|---|---|---|
| 1 | 11–22 nov | 2.1, 2.2 | Revisión literaria (≤ 1 pág.), armar banco, encoder funcionando, ω₀ repetible | Planta, materiales, esquema eléctrico, registro de ω |
| 2 | 23–26 nov | 2.3 | Escalones en lazo abierto con varios ángulos fijos de servo. Medir retardo del servo, zona muerta, saturación, decel. natural y máxima. Ajustar G(s) local en MATLAB. Validar con datos no usados en el ajuste | Datos, G(s)/G(z), polos/ceros, Ts justificado |
| 3 | 27–29 nov | 2.4, 2.5 | Diseñar PID con el modelo (Ziegler-Nichols / PID Tuner / cancelación de polos), polos de lazo cerrado en Z, simular seguimiento de la rampa. Ajustar Kp, Ki, Kd en el banco y documentar efecto de cada uno | Ecuación de control, ganancias, gráficas intermedias |
| 4 | 30 nov – 2 dic | 2.6 + paper | Lazo abierto (acción fija) vs PID: **≥ 3 repeticiones × 2 velocidades iniciales**. Registrar ref, ω, e, u. Comparar IAE/RMSE, tiempo, oscilaciones, saturación, variabilidad | Resultados + paper IEEE ≤ 4 págs |

### Requisitos mínimos de la demo en vivo
1. Giro estable y medición de ω.
2. Frenado controlable.
3. Registro de señales.
4. PID real corriendo.
5. Seguimiento de ≥ 1 referencia decreciente realizable.
6. Comparación lazo abierto vs cerrado.
7. Saber explicar el modelo, el muestreo y las ganancias.

Además: proteger las partes móviles y limitar la velocidad.

**Para la defensa:** frenar más rápido **no** prueba un mejor control. Lo que importa es el error de seguimiento y la repetibilidad. Un ABS real busca evitar el bloqueo, no frenar en menos tiempo.

### Puntos extra (máx. +15, solo si lo básico funciona)
Ordenados por facilidad dado lo que ya tenemos:
- **Comparación de dos Ts** (+3): p. ej. 20 ms vs 50 ms. Casi gratis.
- **Gain scheduling** por velocidad (+3).
- **Antibloqueo simplificado** (+5).
- **Perturbación** (+2).
- **Identificación semiautomática** (+2).

---

## 5. Git (obligatorio — si no se cumple, la parte funcional vale 0)

- Repo `<inicial><apellido>_asm_2026_s1`. Si es privado, dar acceso a `luchazam`.
- Ramas fijas: `master` y `development`. Se trabaja en `feature/<tarea|proyecto>-<tema>` creada desde `development`, se hace merge a `development` y, al cerrar el entregable, merge a `master` + **tag** (p. ej. `tarea2-v1.0`, `proyecto2-v1.0`).
- **Commits pequeños y frecuentes, de todos.** Se revisan las estadísticas semanales y el trabajo en equipo.
- **Estructura en `master`:**
  ```
  tarea_2/       ENUNCIADO_TAREA_2.md, informe, código
  proyecto_2/    ENUNCIADO_PROYECTO_2.md, firmware/, matlab/, datos/, paper/
  HANDOFF.md
  ```

```bash
git checkout development && git pull
git checkout -b feature/tarea2-muestreo-pid
git add . && git commit -m "Agrega enunciados en md y handoff"
git push -u origin feature/tarea2-muestreo-pid
```

---

## 6. Preguntas abiertas para el profesor

1. Tarea 2, punto 7: pide "respuesta al escalón" pero dice "use la respuesta al impulso de Matlab". ¿Cuál de las dos?
2. ¿Hay una referencia ω_ref(t) específica, o basta con una rampa lineal justificada?
3. El pie de página del enunciado del proyecto dice "control de un ascensor". Confirmar que es solo un resto de la versión anterior.
