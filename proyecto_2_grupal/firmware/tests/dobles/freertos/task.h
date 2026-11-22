#ifndef PRUEBA_TASK_H
#define PRUEBA_TASK_H
#include <stdint.h>
typedef void *TaskHandle_t;
/* Doble sin planificador real. */
void xTaskNotifyGive(TaskHandle_t tarea);
/* Doble que permite recorrer la coordinacion sin tareas reales. */
uint32_t ulTaskNotifyTake(int limpiar, uint32_t espera);
/* Devuelve un identificador ficticio. */
TaskHandle_t xTaskGetCurrentTaskHandle(void);
/* No cambia prioridades en PC. */
void vTaskPrioritySet(TaskHandle_t tarea, unsigned prioridad);
/* No introduce esperas en los ensayos host. */
void vTaskDelay(unsigned tiempo);
#endif
