idf_component_register(
    SRCS "app_main.c" "reproduccion_senal.c"
    INCLUDE_DIRS "."
    PRIV_REQUIRES senales_embebidas salida_dac log
)
