cmake_minimum_required(VERSION 3.16)

# Este proyecto utiliza el ESP32 clásico del módulo ESP-32S.
set(IDF_TARGET "esp32")
include($ENV{IDF_PATH}/tools/cmake/project.cmake)
idf_build_set_property(MINIMAL_BUILD ON)
project(emisor_esp32)
