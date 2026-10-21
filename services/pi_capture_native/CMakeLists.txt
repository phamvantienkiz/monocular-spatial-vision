cmake_minimum_required(VERSION 3.10)
project(pi_capture_native LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_EXPORT_COMPILE_COMMANDS ON)

# ── ARM NEON flags (auto-detected) ──────────────────────────────────
# Pi 3 (32-bit armhf): needs explicit -mfpu=neon
# Pi 3 (64-bit aarch64): NEON is always available
if(CMAKE_SYSTEM_PROCESSOR MATCHES "^arm")
    add_compile_options(-mfpu=neon-vfpv4 -mfloat-abi=hard -ftree-vectorize)
    message(STATUS "ARM 32-bit detected — enabling NEON via -mfpu=neon-vfpv4")
elseif(CMAKE_SYSTEM_PROCESSOR MATCHES "aarch64")
    add_compile_options(-ftree-vectorize)
    message(STATUS "ARM 64-bit detected — NEON enabled by default")
endif()

# ── Sources ─────────────────────────────────────────────────────────
add_executable(pi_capture_native
    src/v4l2_camera.cpp
    src/jpeg_encoder.cpp
    src/socket_streamer.cpp
    src/frame_packer.cpp
    src/imu_reader.cpp
    src/main.cpp
)

target_include_directories(pi_capture_native PRIVATE include)

# ── Dependencies ────────────────────────────────────────────────────
# libturbojpeg (provided by libturbojpeg0-dev on Raspbian)
find_library(TURBOJPEG_LIB turbojpeg REQUIRED)
target_link_libraries(pi_capture_native PRIVATE ${TURBOJPEG_LIB} pthread)

message(STATUS "libturbojpeg found: ${TURBOJPEG_LIB}")
