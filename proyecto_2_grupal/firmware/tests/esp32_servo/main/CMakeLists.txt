idf_component_register(
    SRCS "calibrar_servo.c" "../../../src/protocolo_serial.c"
         "../../../src/sensor_optico.c" "../../../src/estimador_velocidad.c"
    INCLUDE_DIRS "../../../include"
    REQUIRES esp_driver_gpio esp_driver_ledc esp_driver_uart esp_timer
)
