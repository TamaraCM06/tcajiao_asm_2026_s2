idf_component_register(
    SRCS "salida_dac.c" "salida_dac_vivo.c"
    INCLUDE_DIRS "include"
    REQUIRES esp_driver_dac freertos
    PRIV_REQUIRES senales_embebidas
)

target_compile_features(${COMPONENT_LIB} PUBLIC c_std_11)
