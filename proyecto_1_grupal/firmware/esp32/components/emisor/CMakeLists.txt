idf_component_register(
    SRCS "emisor_config.c" "generador_senales.c"
    INCLUDE_DIRS "include"
)

target_compile_features(${COMPONENT_LIB} PUBLIC c_std_11)
target_link_libraries(${COMPONENT_LIB} PUBLIC m)
