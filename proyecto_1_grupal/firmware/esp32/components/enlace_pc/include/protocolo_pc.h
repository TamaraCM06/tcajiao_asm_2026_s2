/** Contrato ASM2: cabecera explicita little-endian, CRC32 ISO-HDLC y COBS. */
#pragma once
#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>
enum { PC_PAYLOAD_MAX = 4096, PC_TRAMA_MAX = 4144 };
enum { PC_COMANDO = 1, PC_ACK, PC_ENTRADA, PC_SALIDA, PC_RESULTADO,
       PC_ERROR, PC_AUDIO, PC_SONDA, PC_FIN };
typedef struct {
    uint8_t tipo;
    uint16_t canal;
    uint32_t sesion, secuencia, indice, longitud;
    uint8_t datos[PC_PAYLOAD_MAX];
} pc_paquete_t;
/** Calcula CRC32 compatible con zlib.crc32, incluso para un contenido vacio. */
uint32_t pc_crc32(const uint8_t *datos, size_t cantidad);
/** Serializa y agrega el delimitador 0; devuelve cero ante argumentos invalidos. */
size_t pc_codificar(const pc_paquete_t *paquete, uint8_t salida[PC_TRAMA_MAX]);
/** Valida una trama COBS sin delimitador y no publica contenido parcial. */
bool pc_decodificar(const uint8_t *datos, size_t cantidad, pc_paquete_t *paquete);
/** Convierte con escala fija y redondeo; cuenta saturaciones de transporte. */
int16_t pc_cuantizar(float muestra, float escala, uint32_t *recortes);
