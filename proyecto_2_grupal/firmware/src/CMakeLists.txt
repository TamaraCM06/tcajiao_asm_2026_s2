idf_component_register(SRCS "aplicacion.c" "hardware.c"
    INCLUDE_DIRS "../include"
    REQUIRES esp_driver_gpio esp_driver_ledc esp_driver_uart esp_timer esp_app_format)
