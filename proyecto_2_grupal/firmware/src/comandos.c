#include "comandos.h"
#include <ctype.h>
#include <errno.h>
#include <math.h>
#include <stdlib.h>
#include <string.h>

/* Convierte un token completo a numero finito; rechaza texto sobrante y desbordes. */
static bool leer_numero(const char *texto, double *valor)
{
    errno = 0;
    char *final;
    *valor = strtod(texto, &final);
    return final != texto && !*final && errno != ERANGE && isfinite(*valor);
}

/* CAL, CAL + | - | LIBERADO | CONTACTO, CAL PULSO us, CAL PASO grados. */
static comando_t interpretar_calibracion(char **palabras, unsigned cantidad)
{
    comando_t comando = {.tipo = COMANDO_INVALIDO};
    if (cantidad == 1) comando.tipo = COMANDO_CAL_CONSULTA;
    if (cantidad == 2 && !strcmp(palabras[1], "+")) comando.tipo = COMANDO_CAL_MAS;
    if (cantidad == 2 && !strcmp(palabras[1], "-")) comando.tipo = COMANDO_CAL_MENOS;
    if (cantidad == 2 && !strcmp(palabras[1], "LIBERADO")) comando.tipo = COMANDO_CAL_LIBERADO;
    if (cantidad == 2 && !strcmp(palabras[1], "CONTACTO")) comando.tipo = COMANDO_CAL_CONTACTO;
    if (cantidad == 3 && (!strcmp(palabras[1], "PULSO") || !strcmp(palabras[1], "PASO"))) {
        if (!leer_numero(palabras[2], &comando.valores[0])) return comando;
        comando.tipo = !strcmp(palabras[1], "PULSO") ? COMANDO_CAL_PULSO : COMANDO_CAL_PASO;
    }
    return comando;
}

/* Separa tokens en una copia acotada y rechaza tanto exceso como truncamiento. */
comando_t comando_interpretar(const char *linea)
{
    comando_t comando = {.tipo = COMANDO_INVALIDO};
    if (strlen(linea) >= COMANDO_LONGITUD_MAXIMA) return comando;
    char copia[COMANDO_LONGITUD_MAXIMA];
    strcpy(copia, linea);
    char *palabras[5];
    unsigned cantidad = 0;
    char *posicion = copia;
    while (*posicion) {
        while (isspace((unsigned char)*posicion)) ++posicion;
        if (!*posicion) break;
        if (cantidad == 5) return comando;
        palabras[cantidad++] = posicion;
        while (*posicion && !isspace((unsigned char)*posicion)) ++posicion;
        if (*posicion) *posicion++ = '\0';
    }
    if (cantidad == 0) return comando;
    if (!strcmp(palabras[0], "CAL")) return interpretar_calibracion(palabras, cantidad);
    if (cantidad == 1) {
        if (!strcmp(palabras[0], "CONFIG")) comando.tipo = COMANDO_CONFIG_CONSULTA;
        if (!strcmp(palabras[0], "START")) comando.tipo = COMANDO_START;
        if (!strcmp(palabras[0], "STOP")) comando.tipo = COMANDO_STOP;
        if (!strcmp(palabras[0], "STATUS")) comando.tipo = COMANDO_STATUS;
        return comando;
    }
    if (cantidad == 4 && !strcmp(palabras[0], "CONFIG")) comando.tipo = COMANDO_CONFIG;
    if (cantidad == 4 && !strcmp(palabras[0], "ENSAYO")) comando.tipo = COMANDO_ENSAYO;
    if (cantidad == 2 && !strcmp(palabras[0], "MOTOR")) comando.tipo = COMANDO_MOTOR;
    if (cantidad == 2 && !strcmp(palabras[0], "FRENO")) comando.tipo = COMANDO_FRENO;
    if (comando.tipo == COMANDO_INVALIDO) return comando;
    for (unsigned indice_valor = 1; indice_valor < cantidad; ++indice_valor) {
        if (!leer_numero(palabras[indice_valor], &comando.valores[indice_valor - 1])) {
            comando.tipo = COMANDO_INVALIDO;
            return comando;
        }
    }
    return comando;
}

/* Limita el registro a 100 Hz por presupuesto UART y a una hora por ensayo. */
bool comando_configuracion(const comando_t *comando, uint32_t minimo_pulso_us,
    configuracion_ensayo_t *parametros)
{
    if (comando->tipo != COMANDO_CONFIG) return false;
    for (unsigned indice_valor = 0; indice_valor < 3; ++indice_valor) {
        double valor = comando->valores[indice_valor];
        if (!isfinite(valor) || valor <= 0 || valor > 3600000 || floor(valor) != valor) return false;
    }
    if (comando->valores[0] < 10 || comando->valores[0] > 60000 ||
        comando->valores[1] < comando->valores[0] || comando->valores[2] > 60000 ||
        comando->valores[2] * 1000 <= minimo_pulso_us) return false;
    *parametros = (configuracion_ensayo_t){(uint32_t)comando->valores[0],
        (uint32_t)comando->valores[1], (uint32_t)comando->valores[2]};
    return true;
}
