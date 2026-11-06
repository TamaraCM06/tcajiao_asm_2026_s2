idf_component_register(
    SRCS "procesamiento_registro.c" "tiempos_registro.c"
    INCLUDE_DIRS "include"
    REQUIRES filtros_digitales evaluacion_digital
)
target_compile_features(${COMPONENT_LIB} PUBLIC c_std_11)
