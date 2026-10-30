idf_component_register(
    SRCS "senales_embebidas.c" "datos_digitales.c" "lectura_float32.c" "datos/coeficientes_fir.c"
         "datos/caso_1.c" "datos/caso_2.c" "datos/caso_3.c"
    INCLUDE_DIRS "include"
    EMBED_FILES "datos/caso_1.f32" "datos/caso_2.f32" "datos/caso_3.f32"
)
target_compile_features(${COMPONENT_LIB} PUBLIC c_std_11)
