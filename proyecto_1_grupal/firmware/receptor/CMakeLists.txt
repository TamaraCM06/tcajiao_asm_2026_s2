cmake_minimum_required(VERSION 3.13)

# No descarga dependencias automáticamente: indicar un Pico SDK instalado.
if(NOT PICO_SDK_PATH AND DEFINED ENV{PICO_SDK_PATH})
    set(PICO_SDK_PATH "$ENV{PICO_SDK_PATH}")
endif()
if(NOT EXISTS "${PICO_SDK_PATH}/external/pico_sdk_import.cmake")
    message(FATAL_ERROR "Defina PICO_SDK_PATH con la ruta del Pico SDK (con TinyUSB).")
endif()
include("${PICO_SDK_PATH}/external/pico_sdk_import.cmake")
project(nodo1_receptor C CXX ASM)
set(CMAKE_C_STANDARD 11)
set(CMAKE_C_STANDARD_REQUIRED ON)
pico_sdk_init()

option(NODO1_HABILITAR_SPI "Enviar bloques al ESP32 esclavo por SPI" OFF)
set(NODO1_SPI_MODO 0 CACHE STRING "SPI 0 solicitado (experimental con DMA) o 1 recomendado")
set(NODO1_SPI_HZ 2000000 CACHE STRING "Reloj SPI solicitado, 1000000 a 10000000 Hz")
if(NOT NODO1_SPI_MODO MATCHES "^[01]$")
    message(FATAL_ERROR "NODO1_SPI_MODO debe ser 0 o 1")
endif()
if(NODO1_SPI_HZ LESS 1000000 OR NODO1_SPI_HZ GREATER 10000000)
    message(FATAL_ERROR "NODO1_SPI_HZ debe estar entre 1000000 y 10000000")
endif()
if(NODO1_HABILITAR_SPI AND NODO1_SPI_MODO EQUAL 0)
    message(WARNING "Modo 0 + DMA del ESP32 clasico: validar timing/CRC; modo 1 es la alternativa recomendada")
endif()
add_executable(nodo1_receptor main.c nodo1_metodos.c)
target_compile_options(nodo1_receptor PRIVATE -Wall -Wextra -Werror)
target_compile_definitions(nodo1_receptor PRIVATE
    NODO1_HABILITAR_SPI=$<BOOL:${NODO1_HABILITAR_SPI}>
    NODO1_SPI_MODO=${NODO1_SPI_MODO}
    NODO1_SPI_HZ=${NODO1_SPI_HZ}
    PICO_STDIO_USB_CONNECT_WAIT_TIMEOUT_MS=0
    PICO_STDIO_USB_STDOUT_TIMEOUT_US=1000
)
target_link_libraries(nodo1_receptor PRIVATE
    pico_stdlib pico_stdio_usb hardware_adc hardware_dma hardware_irq
    hardware_clocks hardware_sync hardware_spi m
)
pico_enable_stdio_usb(nodo1_receptor 1)
pico_enable_stdio_uart(nodo1_receptor 0)
pico_add_extra_outputs(nodo1_receptor)
