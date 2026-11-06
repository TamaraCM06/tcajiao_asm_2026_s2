#include "protocolo_pc.h"
#include <math.h>
#include <string.h>

/** Lee campos de 32 bits sin depender de alineacion ni padding. */
static uint32_t leer_entero(const uint8_t *datos)
{
    return (uint32_t)datos[0] | (uint32_t)datos[1] << 8 |
           (uint32_t)datos[2] << 16 | (uint32_t)datos[3] << 24;
}
/** Escribe un campo en orden little-endian. */
static void escribir_entero(uint8_t *datos, uint32_t valor)
{
    for (unsigned posicion = 0; posicion < 4; ++posicion) datos[posicion] = valor >> (8 * posicion);
}
/** Implementa CRC32 ISO-HDLC sin tablas ni dependencias del microcontrolador. */
uint32_t pc_crc32(const uint8_t *datos, size_t cantidad)
{
    uint32_t crc = UINT32_MAX;
    for (size_t posicion = 0; posicion < cantidad; ++posicion) {
        crc ^= datos[posicion];
        for (unsigned bit = 0; bit < 8; ++bit)
            crc = (crc >> 1) ^ ((crc & 1) ? UINT32_C(0xedb88320) : 0);
    }
    return crc ^ UINT32_MAX;
}
/** Codifica cabecera y contenido sin transmitir estructuras C. */
size_t pc_codificar(const pc_paquete_t *paquete, uint8_t salida[PC_TRAMA_MAX])
{
    if (!paquete || !salida || paquete->longitud > PC_PAYLOAD_MAX) return 0;
    uint8_t crudo[PC_PAYLOAD_MAX + 28];
    memcpy(crudo, "ASM2", 4);
    crudo[4] = 1; crudo[5] = paquete->tipo;
    crudo[6] = paquete->canal; crudo[7] = paquete->canal >> 8;
    escribir_entero(crudo + 8, paquete->sesion);
    escribir_entero(crudo + 12, paquete->secuencia);
    escribir_entero(crudo + 16, paquete->indice);
    escribir_entero(crudo + 20, paquete->longitud);
    memcpy(crudo + 24, paquete->datos, paquete->longitud);
    escribir_entero(crudo + 24 + paquete->longitud, pc_crc32(crudo, 24 + paquete->longitud));
    size_t escritura = 1, codigo_posicion = 0;
    uint8_t codigo = 1;
    for (size_t posicion = 0; posicion < paquete->longitud + 28; ++posicion) {
        if (crudo[posicion] == 0) {
            salida[codigo_posicion] = codigo;
            codigo_posicion = escritura++; codigo = 1;
        } else {
            salida[escritura++] = crudo[posicion];
            if (++codigo == 255) {
                salida[codigo_posicion] = codigo;
                codigo_posicion = escritura++; codigo = 1;
            }
        }
    }
    salida[codigo_posicion] = codigo;
    salida[escritura++] = 0;
    return escritura;
}
/** Comprueba COBS, longitud, version y CRC antes de copiar al destino. */
bool pc_decodificar(const uint8_t *datos, size_t cantidad, pc_paquete_t *paquete)
{
    if (!datos || !paquete || !cantidad || cantidad >= PC_TRAMA_MAX) return false;
    uint8_t crudo[PC_PAYLOAD_MAX + 28];
    size_t lectura = 0, escritura = 0;
    while (lectura < cantidad) {
        const unsigned codigo = datos[lectura++];
        if (!codigo || lectura + codigo - 1 > cantidad) return false;
        for (unsigned posicion = 1; posicion < codigo; ++posicion) {
            if (escritura >= sizeof(crudo) || datos[lectura] == 0) return false;
            crudo[escritura++] = datos[lectura++];
        }
        if (codigo != 255 && lectura < cantidad) {
            if (escritura >= sizeof(crudo)) return false;
            crudo[escritura++] = 0;
        }
    }
    if (escritura < 28 || memcmp(crudo, "ASM2", 4) || crudo[4] != 1) return false;
    const uint32_t longitud = leer_entero(crudo + 20);
    if (longitud > PC_PAYLOAD_MAX || escritura != longitud + 28 ||
        pc_crc32(crudo, escritura - 4) != leer_entero(crudo + escritura - 4)) return false;
    paquete->tipo = crudo[5]; paquete->canal = crudo[6] | (uint16_t)crudo[7] << 8;
    paquete->sesion = leer_entero(crudo + 8); paquete->secuencia = leer_entero(crudo + 12);
    paquete->indice = leer_entero(crudo + 16); paquete->longitud = longitud;
    memcpy(paquete->datos, crudo + 24, longitud);
    return true;
}
/** Mantiene la escala comun de las tres rutas, sin normalizar por bloque. */
int16_t pc_cuantizar(float muestra, float escala, uint32_t *recortes)
{
    const double valor = floor((double)muestra / escala * 32768.0 + 0.5);
    if (!isfinite(valor) || valor < -32768 || valor > 32767) {
        if (recortes) ++*recortes;
        return !isfinite(valor) ? 0 : valor < 0 ? INT16_MIN : INT16_MAX;
    }
    return (int16_t)valor;
}
