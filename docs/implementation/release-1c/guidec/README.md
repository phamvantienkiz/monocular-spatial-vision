# Release 1c: Bộ Hướng Dẫn Kỹ Thuật Thực Địa C/C++ (Field Guides Index)

> **Layer:** Implementation Layer (`docs/implementation/release-1c/guidec/README.md`)  
> **Release:** Release 1c (C/C++ Native Edge Capture & Perception Pipeline)  
> **Status:** Approved Baseline — Practical Engineering Standard  

---

## 1. Mục Đích & Phạm Vi Áp Dụng

Bộ tài liệu hướng dẫn kỹ thuật thực địa trong thư mục `guidec/` cung cấp toàn bộ quy trình từ thiết lập môi trường, cấu trúc mã nguồn, lập trình driver tầng thấp cho đến kịch bản kiểm thử tích hợp từng bước cho phiên bản **C/C++ thuần túy** chạy trên Raspberry Pi 3, khóa cứng độ phân giải chuẩn phần cứng $1280 \times 720 @ 30\text{ FPS}$ (Zero-Resize on Edge) và kết nối với Jetson AGX Xavier.

---

## 2. Bản Đồ Mục Lục Các Chuyên Đề Hướng Dẫn

| Tệp tài liệu | Tiêu đề chuyên đề | Nội dung trọng tâm |
| :--- | :--- | :--- |
| [00-overview-and-dev-workflow.md](file:///E:/UIT/monocular-spatial-vision/docs/implementation/release-1c/guidec/00-overview-and-dev-workflow.md) | **Quy Trình Phát Triển Thực Chiến & Phân Định Công Cụ** | Phân tách vai trò VS Code (Windows) làm IDE chính $\to$ Git Push $\to$ Pull về Pi 3 $\to$ Native Build trực tiếp bằng `uv` + `Conan`. Khóa cứng chuẩn gốc 720p và loại bỏ hoàn toàn gánh nặng resize trên Pi 3. |
| [01-pi3-c-environment-and-conan-setup.md](file:///E:/UIT/monocular-spatial-vision/docs/implementation/release-1c/guidec/01-pi3-c-environment-and-conan-setup.md) | **Thiết Lập Môi Trường C++ Cô Lập & Swap 2GB Trên Pi 3** | Cấu hình `dphys-swapfile` $2048\text{MB}$ chống tràn RAM, thiết lập `.venv` với `uv`, cài `conan`, đặt `CONAN_HOME=.conan` để cô lập $100\%$ trong workspace. |
| [02-cmake-conan-project-structure.md](file:///E:/UIT/monocular-spatial-vision/docs/implementation/release-1c/guidec/02-cmake-conan-project-structure.md) | **Cấu Trúc Thư Mục Mã Nguồn C++ & Tệp Cấu Hình CMake** | Tổ chức thư mục `services/pi_capture_agent_cpp/`, chi tiết tệp `conanfile.txt`, `CMakeLists.txt` liên kết thư viện `libjpeg-turbo`, `yaml-cpp` và cấu hình compiler flags tối ưu hóa Cortex-A53 (`-O3 -mcpu=cortex-a53`). |
| [03-v4l2-mmap-and-turbojpeg-neon-guide.md](file:///E:/UIT/monocular-spatial-vision/docs/implementation/release-1c/guidec/03-v4l2-mmap-and-turbojpeg-neon-guide.md) | **Lập Trình Bắt Hình V4L2 ioctl & Nén Ảnh TurboJPEG NEON** | Hướng dẫn chi tiết mã C++ gọi Linux V4L2 kernel subsystem (`VIDIOC_REQBUFS`, `mmap`, `VIDIOC_DQBUF` 720p) và kỹ thuật gọi C API `tjCompress2()` tăng tốc SIMD NEON. |
| [04-step-by-step-integration-and-testing-plan.md](file:///E:/UIT/monocular-spatial-vision/docs/implementation/release-1c/guidec/04-step-by-step-integration-and-testing-plan.md) | **Kế Hoạch Kiểm Thử Tích Hợp Từng Bước (5-Step Plan)** | Lộ trình kiểm thử 5 bước: Kiểm tra camera V4L2 720p $\to$ Benchmark nén TurboJPEG $\to$ Đọc IMU I2C $\to$ Stream nhị phân TCP về Laptop/Jetson $\to$ Kiểm toán Zero-Pollution và Memory Leak. |

---

## 3. Quy Tắc Triển Khai Dành Cho Developer

1. **Khóa chuẩn 720p:** Không thêm bất kỳ code resize hoặc downscale nào vào module `pi_capture_agent_cpp`.
2. **Tuân thủ đúng thứ tự tài liệu:** Developer mới bắt đầu nên đọc từ `00` đến `04` để nắm vững tư duy kiến trúc trước khi gõ lệnh.
3. **Không tự ý cài đặt gói toàn cục:** Bắt buộc tuân thủ tài liệu `01` khi cần cài thêm bất kỳ thư viện C++ nào (khai báo vào `conanfile.txt`).
4. **Giới hạn số luồng biên dịch:** Luôn luôn dùng `cmake --build build -j2` trên Pi 3.
