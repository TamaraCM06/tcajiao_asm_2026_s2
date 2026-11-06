"""Valida el JSON C real con cJSON de ESP-IDF instalado; no sustituye el serializador."""
import json
import os
from pathlib import Path
import shutil
import subprocess

import pytest

FIRMWARE = Path(__file__).resolve().parents[1]
COMPONENTES = FIRMWARE / "components"


# Usa la dependencia original del SDK, sin copiarla ni incorporarla al repositorio.
@pytest.fixture(scope="module")
def ejecutor_informe(tmp_path_factory):
    """Si no hay ESP-IDF, el resto de pruebas host sigue disponible."""
    sdk = Path(os.environ.get("IDF_PATH", "C:/Espressif/frameworks/esp-idf-v5.5.5"))
    biblioteca = sdk / "components/json/cJSON"
    if not (biblioteca / "cJSON.c").exists():
        pytest.skip("Se requiere cJSON del SDK para verificar el serializador de informes")
    carpeta = tmp_path_factory.mktemp("informe_c")
    cabeceras = {
        "esp_err.h": "#pragma once\ntypedef int esp_err_t;\n#define ESP_OK 0\n#define ESP_ERR_NO_MEM 1\n#define ESP_ERR_INVALID_SIZE 2\n",
        "esp_timer.h": "#pragma once\n#include <stdint.h>\nint64_t esp_timer_get_time(void);\n",
        "esp_heap_caps.h": "#pragma once\n#include <stddef.h>\n#define MALLOC_CAP_8BIT 1\nsize_t heap_caps_get_free_size(unsigned capacidad);\nsize_t heap_caps_get_minimum_free_size(unsigned capacidad);\n",
        "esp_app_desc.h": "#pragma once\ntypedef struct {char version[32], idf_ver[32];} esp_app_desc_t;\nconst esp_app_desc_t *esp_app_get_description(void);\n",
    }
    for nombre, contenido in cabeceras.items():
        (carpeta / nombre).write_text(contenido, encoding="utf-8")
    orden = [shutil.which("gcc"), "-std=c11", "-D__USE_MINGW_ANSI_STDIO=1", "-O2", "-Wall", "-Wextra", "-Werror",
             "-I", str(carpeta), "-I", str(biblioteca), "-I", str(COMPONENTES / "sesiones_pc")]
    for modulo in ("procesamiento_registro", "filtros_digitales", "evaluacion_digital", "enlace_pc", "recepcion_spi"):
        orden += ["-I", str(COMPONENTES / modulo / "include")]
    fuentes = [COMPONENTES / "sesiones_pc/informe_pc.c", biblioteca / "cJSON.c",
               *sorted((COMPONENTES / "evaluacion_digital").glob("*.c")),
               *sorted((COMPONENTES / "filtros_digitales").glob("*.c")),
               FIRMWARE / "tests/ejecutor_informe.c"]
    salida = carpeta / "informe.exe"
    subprocess.run([*orden, *map(str, fuentes), "-lm", "-o", str(salida)], check=True)
    return salida


# El limite se comprueba con el texto que produce C, incluidos nombres de version extensos.
@pytest.mark.parametrize("sin_referencia", [False, True])
def test_informe_completo_y_limite(ejecutor_informe, sin_referencia):
    """Mantiene campos no disponibles como null y la carga util debajo de 4096 bytes."""
    resultado = subprocess.run([str(ejecutor_informe), *(["sin_referencia"] if sin_referencia else [])],
                              capture_output=True, text=True, check=True)
    assert len(resultado.stdout.strip().encode("utf-8")) <= 4096
    informe = json.loads(resultado.stdout)
    assert informe["version_mediciones"] == 2
    assert informe["latencia_bloque_cantidad"] == 3750
    assert informe["heap_minimo_bytes"] == 98765
    for metodo in ("fir", "espectral"):
        assert informe[metodo]["ruta_max_us"] == 1234567
        if sin_referencia:
            assert informe[metodo]["mse"] is None
            assert informe[metodo]["atenuacion_interferencia_db"] is None
            assert informe[metodo]["estado_atenuacion_regional"] == "sin_referencia"
        else:
            assert informe[metodo]["estado_atenuacion_regional"] == "disponible"
