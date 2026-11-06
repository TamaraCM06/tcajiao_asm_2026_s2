#include "fft_radix2.h"
#include <math.h>

/* Calcula cada giro directamente para evitar acumular error entre mariposas. */
void fft_preparar(fft_plan_t *plan)
{
    for (int indice = 0; indice < FFT_LONGITUD / 2; ++indice) {
        double angulo = -6.2831853071795864769 * indice / FFT_LONGITUD;
        plan->giros[indice] = (complejo_t){(float)cos(angulo), (float)sin(angulo)};
    }
}

/* Ejecuta Cooley-Tukey radix 2 con ordenamiento binario y escala inversa. */
void fft_transformar(const fft_plan_t *plan, complejo_t *valores, bool inversa)
{
    unsigned invertido = 0;
    for (unsigned indice = 1; indice < FFT_LONGITUD; ++indice) {
        unsigned mascara = FFT_LONGITUD >> 1;
        while (invertido & mascara) { invertido ^= mascara; mascara >>= 1; }
        invertido ^= mascara;
        if (indice < invertido) {
            complejo_t temporal = valores[indice];
            valores[indice] = valores[invertido];
            valores[invertido] = temporal;
        }
    }
    for (unsigned longitud = 2; longitud <= FFT_LONGITUD; longitud <<= 1) {
        unsigned mitad = longitud / 2;
        unsigned paso = FFT_LONGITUD / longitud;
        for (unsigned inicio = 0; inicio < FFT_LONGITUD; inicio += longitud) {
            for (unsigned desplazamiento = 0; desplazamiento < mitad; ++desplazamiento) {
                complejo_t giro = plan->giros[desplazamiento * paso];
                if (inversa) giro.imaginaria = -giro.imaginaria;
                complejo_t par = valores[inicio + desplazamiento];
                complejo_t impar = valores[inicio + desplazamiento + mitad];
                complejo_t rotado = {
                    giro.real * impar.real - giro.imaginaria * impar.imaginaria,
                    giro.real * impar.imaginaria + giro.imaginaria * impar.real};
                valores[inicio + desplazamiento] = (complejo_t){
                    par.real + rotado.real, par.imaginaria + rotado.imaginaria};
                valores[inicio + desplazamiento + mitad] = (complejo_t){
                    par.real - rotado.real, par.imaginaria - rotado.imaginaria};
            }
        }
    }
    if (inversa) {
        for (unsigned indice = 0; indice < FFT_LONGITUD; ++indice) {
            valores[indice].real /= FFT_LONGITUD;
            valores[indice].imaginaria /= FFT_LONGITUD;
        }
    }
}
