#pragma once
#include "banco_filtros.h"
/* Imprime calidad y costo por metodo, diferenciando calculo de tiempo total de ejecucion. */
void informe_consola_publicar(const char *caso, const char *metodo,
    const banco_resultado_t *resultado, unsigned presupuesto_us);
