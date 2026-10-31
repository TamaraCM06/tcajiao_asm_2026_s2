#pragma once
#include "banco_filtros.h"

/* Conserva solo el resumen de un metodo, sin guardar las muestras de la senal. */
typedef struct {
    const char *caso;
    const char *metodo;
    banco_resultado_t resultado;
    unsigned presupuesto_us;
} informe_resultado_t;

/* Imprime calidad y costo por metodo, diferenciando calculo de tiempo total de ejecucion. */
void informe_consola_publicar(const char *caso, const char *metodo,
    const banco_resultado_t *resultado, unsigned presupuesto_us);

/* Reune los resultados terminados en tablas de calidad y costo al final de la demostracion. */
void informe_consola_publicar_resumen(const informe_resultado_t *resultados,
                                    size_t cantidad_resultados);
