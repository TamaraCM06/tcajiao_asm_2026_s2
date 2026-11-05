idf_component_register(SRCS "protocolo_pc.c" "enlace_pc.c"
    INCLUDE_DIRS "include" REQUIRES esp_driver_uart freertos)
