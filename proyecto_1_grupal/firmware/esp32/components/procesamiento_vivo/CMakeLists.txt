idf_component_register(
    SRCS "procesamiento_vivo.c"
    INCLUDE_DIRS "include"
    REQUIRES filtros_digitales senales_embebidas
)

target_compile_features(${COMPONENT_LIB} PUBLIC c_std_11)
