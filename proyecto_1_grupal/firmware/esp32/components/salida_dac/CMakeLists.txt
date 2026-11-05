idf_component_register(
    SRCS "salida_dac.c"
    INCLUDE_DIRS "include"
    REQUIRES esp_driver_dac freertos
)

target_compile_features(${COMPONENT_LIB} PUBLIC c_std_11)
