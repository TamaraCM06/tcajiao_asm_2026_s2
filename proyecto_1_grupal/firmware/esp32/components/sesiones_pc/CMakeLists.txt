idf_component_register(SRCS "sesiones_pc.c" "captura_pico.c" "audio_pc.c" "informe_pc.c"
    INCLUDE_DIRS "include" PRIV_INCLUDE_DIRS "."
    REQUIRES enlace_pc procesamiento_vivo recepcion_spi salida_dac json esp_timer heap esp_app_format)
