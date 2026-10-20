# Release 1c: Cấu Trúc Thư Mục Mã Nguồn C++ & Cấu Hình CMake Chuẩn

> **Layer:** Implementation Layer (`docs/implementation/release-1c/guidec/02-cmake-conan-project-structure.md`)  
> **Release:** Release 1c (C/C++ Native Edge Capture & Perception Pipeline)  
> **Status:** Approved Baseline — Practical Engineering Standard  

---

## 1. Bản Đồ Thư Mục Dịch Vụ C++ (`services/pi_capture_agent_cpp/`)

Mã nguồn C++ của tác tử thu nhận hình ảnh được tổ chức theo cấu trúc chuẩn Clean C++ Architecture, phân tách rõ ràng giữa giao diện (Interfaces/Headers) và cài đặt (Implementation/Source). Toàn bộ mã nguồn loại bỏ triệt để các module resize/downscale, khóa cứng chuẩn gốc $1280 \times 720$:

```text
services/pi_capture_agent_cpp/
├── CMakeLists.txt                     # Cấu hình biên dịch chính của CMake
├── conanfile.txt                      # Khai báo gói phụ thuộc (libjpeg-turbo, yaml-cpp...)
├── README.md                          # Hướng dẫn build và chạy độc lập
│
├── include/                           # [TẦNG GIAO DIỆN & HEADERS]
│   ├── camera/
│   │   ├── camera_interface.hpp       # Lớp trừu tượng thuần túy ICameraDriver
│   │   └── v4l2_camera.hpp            # Cài đặt chi tiết Linux V4L2 ioctl & MMAP (1280x720)
│   ├── imu/
│   │   ├── imu_interface.hpp          # Lớp trừu tượng IImuDriver
│   │   └── mpu6050.hpp                # Giao tiếp thanh ghi qua Linux I2C ioctl
│   ├── jpeg/
│   │   ├── jpeg_interface.hpp         # Lớp trừu tượng IJpegEncoder
│   │   └── turbojpeg_encoder.hpp      # Trình nén libjpeg-turbo C API + ARM NEON 720p
│   ├── net/
│   │   ├── packed_header.hpp          # Struct PackedFrameHeader 40 bytes (#pragma pack)
│   │   └── tcp_streamer.hpp           # Socket Client POSIX, TCP_NODELAY, Drop-Stale
│   ├── concurrency/
│   │   └── ring_buffer.hpp            # Hàng đợi đa luồng thread-safe bounded buffer
│   └── config/
│       └── config_loader.hpp          # Đọc tệp cấu hình configs/capture_pi.yaml
│
├── src/                               # [TẦNG CÀI ĐẶT CHI TIẾT (IMPLEMENTATION)]
│   ├── main.cpp                       # Điểm vào chính: Phân luồng thực thi & CLI flags
│   ├── camera/
│   │   └── v4l2_camera.cpp            # Xử lý VIDIOC_REQBUFS, mmap, DQBUF/QBUF (Zero-Resize)
│   ├── imu/
│   │   └── mpu6050.cpp                # Gửi nhận byte qua /dev/i2c-1
│   ├── jpeg/
│   │   └── turbojpeg_encoder.cpp      # Khởi tạo tjInitCompress và gọi tjCompress2
│   ├── net/
│   │   └── tcp_streamer.cpp           # Quản lý socket POSIX, auto-reconnect backoff
│   └── config/
│       └── config_loader.cpp          # Phân tích YAML cấu hình sang C++ struct
│
└── tests/                             # [UNIT TESTS VÀ KIỂM THỬ CỤC BỘ]
    ├── test_header_packing.cpp        # Kiểm tra kích thước 40 bytes và endianness
    └── test_turbojpeg_synthetic.cpp   # Kiểm tra nén buffer nhân tạo 720p đo thời gian
```

---

## 2. Đặc Tả Tệp `CMakeLists.txt` Tối Ưu Cho Raspberry Pi 3

Tệp `CMakeLists.txt` được cấu hình để tích hợp tự động với `conan_toolchain.cmake`, bật cờ tối ưu hóa kiến trúc vi xử lý ARM Cortex-A53 và kiểm soát chặt chẽ các cảnh báo:

```cmake
cmake_minimum_required(VERSION 3.20)
project(pi_capture_agent_cpp VERSION 1.0.0 LANGUAGES C CXX)

# Bắt buộc chuẩn C++17
set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)

# Cờ biên dịch tối ưu hóa phần cứng ARM Cortex-A53
if(CMAKE_SYSTEM_PROCESSOR MATCHES "aarch64" OR CMAKE_SYSTEM_PROCESSOR MATCHES "arm64")
    # Raspberry Pi OS 64-bit: Tối ưu ARMv8-A + NEON
    add_compile_options(-O3 -mcpu=cortex-a53 -pipe -Wall -Wextra)
elseif(CMAKE_SYSTEM_PROCESSOR MATCHES "arm.*")
    # Raspberry Pi OS 32-bit: Tối ưu ARMv7-A + NEON VFPv4
    add_compile_options(-O3 -march=armv7-a -mfpu=neon-vfpv4 -mfloat-abi=hard -pipe -Wall -Wextra)
else()
    # Môi trường x86_64 dev/test trên máy tính
    add_compile_options(-O3 -Wall -Wextra)
endif()

# Tìm các gói thư viện do Conan quản lý
find_package(libjpeg-turbo REQUIRED)
find_package(yaml-cpp REQUIRED)
find_package(nlohmann_json REQUIRED)
find_package(Threads REQUIRED)

# Thư mục chứa Headers
include_directories(
    ${CMAKE_CURRENT_SOURCE_DIR}/include
)

# Danh sách mã nguồn
set(SOURCES
    src/main.cpp
    src/camera/v4l2_camera.cpp
    src/imu/mpu6050.cpp
    src/jpeg/turbojpeg_encoder.cpp
    src/net/tcp_streamer.cpp
    src/config/config_loader.cpp
)

# Tạo file thực thi binary
add_executable(pi_capture_agent_cpp ${SOURCES})

# Liên kết thư viện
target_link_libraries(pi_capture_agent_cpp PRIVATE
    libjpeg-turbo::turbojpeg
    yaml-cpp::yaml-cpp
    nlohmann_json::nlohmann_json
    Threads::Threads
)

# Chỉ định thư mục xuất binary
set_target_properties(pi_capture_agent_cpp PROPERTIES
    RUNTIME_OUTPUT_DIRECTORY "${CMAKE_BINARY_DIR}/bin"
)

# (Tùy chọn) Xây dựng Unit Tests
enable_testing()
add_executable(test_header_packing tests/test_header_packing.cpp)
target_link_libraries(test_header_packing PRIVATE Threads::Threads)
add_test(NAME TestHeaderPacking COMMAND test_header_packing)
```

---

## 3. Quy Trình Biên Dịch & Chạy Mẫu

Sau khi đã nạp toolchain từ Conan theo hướng dẫn tại [01-pi3-c-environment-and-conan-setup.md](file:///E:/UIT/monocular-spatial-vision/docs/implementation/release-1c/guidec/01-pi3-c-environment-and-conan-setup.md), quy trình build diễn ra vô cùng nhanh chóng:

```bash
# 1. Cấu hình build
cmake -B build -DCMAKE_TOOLCHAIN_FILE=build/Release/generators/conan_toolchain.cmake -DCMAKE_BUILD_TYPE=Release

# 2. Biên dịch (chỉ tốn ~20-40 giây trên Pi 3 với -j2)
cmake --build build -j2

# 3. Chạy unit test kiểm tra tính toàn vẹn
ctest --test-dir build --output-on-failure
```
