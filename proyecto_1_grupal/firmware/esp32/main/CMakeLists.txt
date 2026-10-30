idf_component_register(
    SRCS "app_main.c" "reproduccion_senal.c" "demostracion.c" "informe_consola.c"
    INCLUDE_DIRS "."
    PRIV_REQUIRES senales_embebidas salida_dac evaluacion_digital log esp_timer heap
)
