idf_component_register(
    SRCS "recepcion_spi.c" "trama_spi.c"
    INCLUDE_DIRS "include"
    REQUIRES esp_common
    PRIV_REQUIRES esp_driver_spi esp_driver_gpio esp_rom freertos soc
)

target_compile_features(${COMPONENT_LIB} PUBLIC c_std_11)
