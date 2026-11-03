idf_component_register(SRCS "app_main.c" "pantalla.c" INCLUDE_DIRS "."
    PRIV_REQUIRES audio_vivo esp_driver_spi esp_driver_gpio esp_timer heap log)
