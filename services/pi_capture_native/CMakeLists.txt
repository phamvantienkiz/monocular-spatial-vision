cmake_minimum_required(VERSION 3.10)
project(pi_capture_native VERSION 1.0.0 LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)
set(CMAKE_EXPORT_COMPILE_COMMANDS ON)

# ── ARM Cortex-A53 & NEON Optimization Flags (auto-detected) ────────
# Pi 3 (32-bit armhf/armv7l): requires explicit -mfpu=neon-vfpv4
# Pi 3 (64-bit aarch64): NEON is enabled by default on ARMv8-A
if(CMAKE_SYSTEM_PROCESSOR MATCHES "^arm")
    add_compile_options(-O3 -mfpu=neon-vfpv4 -mfloat-abi=hard -ftree-vectorize -Wall -Wextra)
    message(STATUS "ARM 32-bit detected — enabling NEON via -mfpu=neon-vfpv4")
elseif(CMAKE_SYSTEM_PROCESSOR MATCHES "aarch64|arm64")
    add_compile_options(-O3 -mcpu=cortex-a53 -ftree-vectorize -Wall -Wextra)
    message(STATUS "ARM 64-bit detected — NEON enabled by default (-mcpu=cortex-a53)")
else()
    add_compile_options(-O3 -Wall -Wextra)
    message(STATUS "Host architecture (${CMAKE_SYSTEM_PROCESSOR}) — building with scalar fallback")
endif()

# ── Dependencies (Conan or System libturbojpeg) ─────────────────────
find_package(Threads REQUIRED)
find_package(libjpeg-turbo QUIET)

if(libjpeg-turbo_FOUND)
    set(TURBOJPEG_TARGET libjpeg-turbo::turbojpeg)
    message(STATUS "Using Conan/CMake package: libjpeg-turbo::turbojpeg")
else()
    find_library(TURBOJPEG_LIB turbojpeg REQUIRED)
    set(TURBOJPEG_TARGET ${TURBOJPEG_LIB})
    message(STATUS "libturbojpeg found: ${TURBOJPEG_LIB}")
endif()

# ── Core Library Target (shared between main binary and unit tests) ─
set(CORE_SOURCES
    src/v4l2_camera.cpp
    src/jpeg_encoder.cpp
    src/socket_streamer.cpp
    src/frame_packer.cpp
    src/imu_reader.cpp
)

add_executable(pi_capture_native
    ${CORE_SOURCES}
    src/main.cpp
)

target_include_directories(pi_capture_native PRIVATE
    ${CMAKE_CURRENT_SOURCE_DIR}/include
)

target_link_libraries(pi_capture_native PRIVATE
    ${TURBOJPEG_TARGET}
    Threads::Threads
)

# Also create alias copy in build/bin/pi_capture_agent_cpp for Release 1c doc compatibility
add_custom_command(TARGET pi_capture_native POST_BUILD
    COMMAND ${CMAKE_COMMAND} -E make_directory "${CMAKE_BINARY_DIR}/bin"
    COMMAND ${CMAKE_COMMAND} -E copy_if_different
        "$<TARGET_FILE:pi_capture_native>"
        "${CMAKE_BINARY_DIR}/bin/pi_capture_agent_cpp"
    COMMENT "Creating compatibility binary bin/pi_capture_agent_cpp"
)

# ── Unit Tests (CTest) ──────────────────────────────────────────────
enable_testing()
add_executable(test_native
    tests/test_native.cpp
    src/frame_packer.cpp
    src/jpeg_encoder.cpp
)
target_include_directories(test_native PRIVATE
    ${CMAKE_CURRENT_SOURCE_DIR}/include
)
target_link_libraries(test_native PRIVATE
    ${TURBOJPEG_TARGET}
    Threads::Threads
)
add_test(NAME TestNativePackerAndJpeg COMMAND test_native)
