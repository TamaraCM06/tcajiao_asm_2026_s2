#ifndef ASM_ESTIMADOR_VELOCIDAD_H
#define ASM_ESTIMADOR_VELOCIDAD_H

#include <stdbool.h>
#include <stdint.h>

#define ESTIMADOR_VENTANA_MAXIMA 64

typedef struct {
    bool tiene_pulso;
    bool tiene_intervalo;
    int64_t ultimo_pulso_us;
    int64_t intervalo_us;
    int64_t intervalos_us[ESTIMADOR_VENTANA_MAXIMA]; /* Anillo de intervalos consecutivos */
    uint32_t siguiente_intervalo;
    uint32_t cantidad_intervalos;                    /* Validos desde la ultima pausa */
    uint32_t pulsos_aceptados;
    uint32_t pulsos_rechazados;
} estimador_velocidad_t;

typedef enum { VELOCIDAD_ESPERANDO, VELOCIDAD_VALIDA, VELOCIDAD_SIN_PULSOS } estado_velocidad_t;

typedef struct {
    estado_velocidad_t estado;
    int64_t tiempo_lectura_us;
    double velocidad_rpm;
    int64_t edad_pulso_us;
    uint32_t pulsos_aceptados;
    uint32_t pulsos_rechazados;
} lectura_velocidad_t;

/* Borra historial y contadores sin asignar una velocidad ficticia. */
void estimador_reiniciar(estimador_velocidad_t *estimador);

/* Incorpora un solo flanco; rechaza tiempos repetidos y pulsos demasiado proximos. */
void estimador_registrar(estimador_velocidad_t *estimador, int64_t tiempo_us,
    uint32_t intervalo_minimo_us, int64_t timeout_us);

/* Calcula RPM promediando hasta `ventana` intervalos; con ventana = pulsos por vuelta se
 * mide el tiempo de una vuelta completa y se cancela el espaciado desigual de las ranuras.
 * Cero por timeout es una inferencia. */
lectura_velocidad_t estimador_leer(const estimador_velocidad_t *estimador,
    int64_t tiempo_us, uint32_t pulsos_por_vuelta, uint32_t ventana, int64_t timeout_us);

#endif
