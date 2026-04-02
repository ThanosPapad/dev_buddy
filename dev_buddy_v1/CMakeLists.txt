# Generated Cmake Pico project file

cmake_minimum_required(VERSION 3.13)

set(CMAKE_C_STANDARD 11)
set(CMAKE_CXX_STANDARD 17)
set(CMAKE_EXPORT_COMPILE_COMMANDS ON)

# Initialise pico_sdk from installed location
# (note this can come from environment, CMake cache etc)

# == DO NOT EDIT THE FOLLOWING LINES for the Raspberry Pi Pico VS Code Extension to work ==
if(WIN32)
    set(USERHOME $ENV{USERPROFILE})
else()
    set(USERHOME $ENV{HOME})
endif()
set(sdkVersion 2.2.0)
set(toolchainVersion 14_2_Rel1)
set(picotoolVersion 2.2.0-a4)
set(picoVscode ${USERHOME}/.pico-sdk/cmake/pico-vscode.cmake)
if (EXISTS ${picoVscode})
    include(${picoVscode})
endif()
# ====================================================================================
# Build system will be determined by Pico SDK

set(PICO_BOARD pico2 CACHE STRING "Board type")

# Pull in Raspberry Pi Pico SDK (must be before project)
include(pico_sdk_import.cmake)

project(dev_buddy_v1 C CXX ASM)

# Initialise the Raspberry Pi Pico SDK
pico_sdk_init()



# Add executable. Default name is the project name, version 0.1

add_executable(dev_buddy_v1
        main.c
        src/uart_coms.c
        src/in_out_ctrl.c
        src/timer_handler.c
        src/i2c_drive.c
        src/usb_descriptors.c
)

target_include_directories(dev_buddy_v1 PRIVATE
        ${CMAKE_CURRENT_LIST_DIR}/inc
        ${CMAKE_CURRENT_SOURCE_DIR}
)

# pull in common dependencies
target_link_libraries(dev_buddy_v1 
                pico_stdlib 
                pico_unique_id 
                hardware_dma 
                pico_multicore 
                hardware_adc
                hardware_i2c
                tinyusb_device
                tinyusb_board
                )

# create map/bin/hex/uf2 file etc.
pico_add_extra_outputs(dev_buddy_v1)

# call pico_set_program_url to set path to example on github, so users can find the source for an example via picotool