/** Puente portable para comprobar el contrato C/Python con bytes reales. */
#include "protocolo_pc.h"
#include <stdio.h>
#include <string.h>
static pc_paquete_t paquete;
static uint8_t trama[PC_TRAMA_MAX];
/** Lee archivos para evitar traducciones de CRLF de stdout en Windows. */
int main(int cantidad_argumentos, char **argumentos)
{
    if (cantidad_argumentos != 4) return 1;
    FILE *entrada = fopen(argumentos[2], "rb"), *salida = fopen(argumentos[3], "wb");
    if (!entrada || !salida) return 2;
    if (!strcmp(argumentos[1], "codificar")) {
        paquete = (pc_paquete_t){.tipo=7, .canal=29, .sesion=13, .secuencia=19, .indice=23};
        paquete.longitud = fread(paquete.datos, 1, PC_PAYLOAD_MAX, entrada);
        const size_t longitud = pc_codificar(&paquete, trama);
        if (!longitud || fwrite(trama, 1, longitud, salida) != longitud) return 3;
    } else {
        const size_t longitud = fread(trama, 1, sizeof(trama), entrada);
        if (!longitud || trama[longitud-1] || !pc_decodificar(trama, longitud-1, &paquete)) return 4;
        if (fwrite(paquete.datos, 1, paquete.longitud, salida) != paquete.longitud) return 5;
    }
    fclose(entrada); fclose(salida);
    return 0;
}
