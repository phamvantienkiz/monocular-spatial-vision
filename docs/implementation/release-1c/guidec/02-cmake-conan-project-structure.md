# Release 1c: Cấu Trúc Thư Mục Mã Nguồn C++ & Cấu Hình CMake Chuẩn

> **Layer:** Implementation Layer (`docs/implementation/release-1c/guidec/02-cmake-conan-project-structure.md`)  
> **Release:** Release 1c (C/C++ Native Edge Capture & Perception Pipeline)  
> **Status:** Approved Baseline — Practical Engineering Standard (Audit-Remediated)  

---

## 1. Bản Đồ Thư Mục Dịch Vụ C++ (`services/pi_capture_agent_cpp/`)

Mã nguồn C++ của tác tử thu nhận hình ảnh được tổ chức theo cấu trúc chuẩn Clean C++ Architecture, phân tách rõ ràng giữa giao diện (Interfaces/Headers) và cài đặt (Implementation/Source). Kiến trúc hỗ trợ đầy đủ cả **6 chế độ CLI** (`diag`, `snapshot`, `test-imu`, `preview`, `stream`, `test-perf`) và **2 giao thức truyền dẫn vật lý (Wi-Fi & Ethernet)**:

```text
services/pi_capture_agent_cpp/
├── CMakeLists.txt                     # Cấu hình biên dịch CMake (yêu cầu >= 3.18)
├── conanfile.txt                      # Khai báo gói phụ thuộc (libjpeg-turbo, yaml-cpp, nlohmann_json)
├── README.md                          # Hướng dẫn build và chạy độc lập
│
├── include/                           # [TẦNG GIAO DIỆN & HEADERS]
│   ├── camera/
│   │   ├── camera_interface.hpp       # Lớp trừu tượng thuần túy ICameraDriver
│   │   ├── v4l2_camera.hpp            # Điều khiển media-ctl, /dev/v4l-subdev0 & V4L2 MMAP
│   │   └── neon_yuv_convert.hpp       # Chỉ lệnh ARM NEON vld2_u8 tách UYVY -> YUV422P & giảm chiều Preview
│   ├── imu/
│   │   ├── imu_interface.hpp          # Lớp trừu tượng IImuDriver
│   │   └── mpu6050.hpp                # Giao tiếp thanh ghi qua Linux I2C ioctl (/dev/i2c-1)
│   ├── jpeg/
│   │   ├── jpeg_interface.hpp         # Lớp trừu tượng IJpegEncoder
│   │   └── turbojpeg_encoder.hpp      # Trình nén tjCompressFromYUV (YUV422P + ARM NEON SIMD)
│   ├── net/
│   │   ├── packed_header.hpp          # Struct PackedFrameHeader 40 bytes (Strict-Aliasing Safe)
│   │   ├── tcp_streamer.hpp           # Socket Client POSIX (:9876), TCP_NODELAY, send_all() nguyên tử
│   │   └── http_preview_server.hpp    # Embedded HTTP Server (:8080) phục vụ --mode preview qua Wi-Fi/Ethernet
│   ├── concurrency/
│   │   └── triple_buffer.hpp          # Hàng đợi Triple-Buffer Drop-Stale chống ghi đè khi đang gửi mạng
│   └── config/
│       └── config_loader.hpp          # Đọc tệp cấu hình configs/capture_pi.yaml & CLI arguments
│
├── src/                               # [TẦNG CÀI ĐẶT CHI TIẾT (IMPLEMENTATION)]
│   ├── main.cpp                       # Điểm vào chính: Điều phối 6 chế độ CLI (diag/snapshot/test-imu/preview/stream/test-perf)
│   ├── camera/
│   │   └── v4l2_camera.cpp            # Xử lý media-ctl, VFLIP subdev, poll(POLLIN), DQBUF, NEON de-interleave, QBUF
│   ├── imu/
│   │   └── mpu6050.cpp                # Đọc 14 bytes thanh ghi MPU6050 ở 50Hz & Complementary Filter
│   ├── jpeg/
│   │   └── turbojpeg_encoder.cpp      # Khởi tạo tjInitCompress và gọi tjCompressFromYUV
│   ├── net/
│   │   ├── tcp_streamer.cpp           # Quản lý socket TCP (:9876) qua Wi-Fi / Ethernet Hub Type-C / Jetson
│   │   └── http_preview_server.cpp    # Phục vụ /preview, /stream.mjpg, /snapshot.jpg, /telemetry (:8080)
│   └── config/
│       └── config_loader.cpp          # Phân tích YAML cấu hình và cờ dòng lệnh (--mode, --host, --port)
│
└── tests/                             # [UNIT TESTS VÀ KIỂM THỬ CỤC BỘ]
    ├── test_header_packer.cpp         # Kiểm tra kích thước 40 bytes, std::memcpy float & Big-Endian
    └── test_turbojpeg_synthetic.cpp   # Kiểm tra tách kênh NEON UYVY->YUV422P & nén tjCompressFromYUV
```

---

## 2. Đặc Tả Tệp `CMakeLists.txt` Tối Ưu Cho Raspberry Pi 3

Tệp `CMakeLists.txt` sử dụng `cmake_minimum_required(VERSION 3.18)` để tương thích trực tiếp với cả Raspberry Pi OS Bullseye (CMake 3.18.4) và Bookworm (CMake 3.25+) mà không cần cài đặt trình biên dịch ngoài:

```cmake
cmake_minimum_required(VERSION 3.18)
project(pi_capture_agent_cpp VERSION 1.0.0 LANGUAGES C CXX)

# Bắt buộc chuẩn C++17
set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)

# Cờ biên dịch tối ưu hóa phần cứng ARM Cortex-A53
if(CMAKE_SYSTEM_PROCESSOR MATCHES "aarch64" OR CMAKE_SYSTEM_PROCESSOR MATCHES "arm64")
    # Raspberry Pi OS 64-bit: Tối ưu ARMv8-A + NEON SIMD
    add_compile_options(-O3 -mcpu=cortex-a53 -pipe -Wall -Wextra)
elseif(CMAKE_SYSTEM_PROCESSOR MATCHES "arm.*")
    # Raspberry Pi OS 32-bit: Tối ưu ARMv7-A + NEON VFPv4
    add_compile_options(-O3 -march=armv7-a -mfpu=neon-vfpv4 -mfloat-abi=hard -pipe -Wall -Wextra)
else()
    # Môi trường x86_64 dev/test trên Laptop
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

# Danh sách mã nguồn chính
set(SOURCES
    src/main.cpp
    src/camera/v4l2_camera.cpp
    src/imu/mpu6050.cpp
    src/jpeg/turbojpeg_encoder.cpp
    src/net/tcp_streamer.cpp
    src/net/http_preview_server.cpp
    src/config/config_loader.cpp
)

# Tạo file thực thi binary chính
add_executable(pi_capture_agent_cpp ${SOURCES})

# Liên kết thư viện
target_link_libraries(pi_capture_agent_cpp PRIVATE
    libjpeg-turbo::turbojpeg
    yaml-cpp::yaml-cpp
    nlohmann_json::nlohmann_json
    Threads::Threads
)

# Xuất binary tại cả build/bin/ để đồng nhất mọi kịch bản gọi lệnh
set_target_properties(pi_capture_agent_cpp PROPERTIES
    RUNTIME_OUTPUT_DIRECTORY "${CMAKE_BINARY_DIR}/bin"
)

# Xây dựng Unit Tests
enable_testing()
add_executable(test_header_packer tests/test_header_packer.cpp)
target_link_libraries(test_header_packer PRIVATE Threads::Threads)
add_test(NAME TestHeaderPacker COMMAND test_header_packer)

add_executable(test_turbojpeg_synthetic tests/test_turbojpeg_synthetic.cpp src/jpeg/turbojpeg_encoder.cpp)
target_link_libraries(test_turbojpeg_synthetic PRIVATE libjpeg-turbo::turbojpeg Threads::Threads)
add_test(NAME TestTurboJpegSynthetic COMMAND test_turbojpeg_synthetic)
```

---

## 3. Quy Trình Biên Dịch & Chạy Unit Test

Sau khi đã nạp toolchain từ Conan theo hướng dẫn tại [01-pi3-c-environment-and-conan-setup.md](file:///E:/UIT/monocular-spatial-vision/docs/implementation/release-1c/guidec/01-pi3-c-environment-and-conan-setup.md):

```bash
cd ~/workspaces/monocular-spatial-vision/services/pi_capture_agent_cpp

# 1. Cấu hình build với Conan Toolchain
cmake -B build -DCMAKE_TOOLCHAIN_FILE=build/build/Release/generators/conan_toolchain.cmake -DCMAKE_BUILD_TYPE=Release

# 2. Biên dịch giới hạn 2 luồng (-j2) an toàn cho 1GB RAM của Pi 3
cmake --build build -j2

# 3. Chạy unit test kiểm tra tính toàn vẹn Header 40-byte và bộ nén TurboJPEG
ctest --test-dir build --output-on-failure
```
