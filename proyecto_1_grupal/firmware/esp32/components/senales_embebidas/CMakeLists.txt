idf_component_register(
    SRCS "senales_embebidas.c" "datos/caso_1.c" "datos/caso_2.c" "datos/caso_3.c"
    INCLUDE_DIRS "include"
)
target_compile_features(${COMPONENT_LIB} PUBLIC c_std_11)
