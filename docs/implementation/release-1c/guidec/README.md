# Release 1c: Bộ Hướng Dẫn Kỹ Thuật Thực Địa C/C++ (Field Guides Index)

> **Layer:** Implementation Layer (`docs/implementation/release-1c/guidec/README.md`)  
> **Release:** Release 1c (C/C++ Native Edge Capture & Perception Pipeline)  
> **Status:** Approved Baseline — Practical Engineering Standard (Audit-Remediated)  

---

## 1. Mục Đích & Phạm Vi Áp Dụng

Bộ tài liệu hướng dẫn kỹ thuật thực địa trong thư mục `guidec/` cung cấp toàn bộ quy trình từ thiết lập môi trường cô lập, cấu trúc mã nguồn C++17, lập trình driver tầng thấp (`bcm2835-unicam` Media Controller + V4L2 MMAP + ARM NEON `vld2_u8` + `tjCompressFromYUV`) cho đến kịch bản kiểm thử tích hợp từng bước trên **Raspberry Pi 3**.

Đặc biệt, giải pháp C/C++ trong Release 1c **bảo toàn $100\%$ sự linh hoạt về giao thức truyền dẫn và chế độ kiểm thử như phiên bản Python hiện hành (`services/pi_capture_agent/`)**:
- **Giữ nguyên cả 2 phương thức truyền dẫn vật lý:**
  1. **Wi-Fi (`wlan0`):** Dùng để kiểm thử không dây tiện lợi với Laptop qua cả chế độ xem trực tiếp trên trình duyệt (`--mode preview`, cổng `8080`) lẫn chế độ truyền luồng nhị phân TCP (`--mode stream`, cổng `9876`).
  2. **Cổng Ethernet (`eth0`):** Dùng trong cả quá trình **kiểm thử có dây với Laptop (thông qua Hub chuyển đổi USB Type-C sang RJ45 Ethernet)** lẫn quá trình **tích hợp thực tế với siêu máy tính nhúng Jetson AGX Xavier (`192.168.1.20`)**.
- **Giữ nguyên đủ 6 chế độ CLI (`--mode`):** `diag`, `snapshot`, `test-imu`, `preview`, `stream`, `test-perf`.

---

## 2. Bản Đồ Mục Lục Các Chuyên Đề Hướng Dẫn

| Tệp tài liệu | Tiêu đề chuyên đề | Nội dung trọng tâm |
| :--- | :--- | :--- |
| [00-overview-and-dev-workflow.md](file:///E:/UIT/monocular-spatial-vision/docs/implementation/release-1c/guidec/00-overview-and-dev-workflow.md) | **Quy Trình Phát Triển Thực Chiến & Chế Độ Vận Hành Kép (Wi-Fi + Ethernet)** | Phân tách vai trò VS Code (Windows) $\to$ Git $\to$ Native Build trên Pi 3 bằng `uv` + `Conan`. Bảng ma trận vận hành đầy đủ cho cả Wi-Fi (`preview`/`stream`), dây Ethernet qua Hub Type-C với Laptop và dây Ethernet nối Jetson. |
| [01-pi3-c-environment-and-conan-setup.md](file:///E:/UIT/monocular-spatial-vision/docs/implementation/release-1c/guidec/01-pi3-c-environment-and-conan-setup.md) | **Thiết Lập Môi Trường C++ Cô Lập (`.venv` + `.conan`) Trên Pi 3** | Thiết lập `.venv` với `uv`, cài `conan`, đặt `CONAN_HOME` cục bộ và giới hạn `tools.build:jobs=2` để biên dịch an toàn trong 1GB RAM của Pi 3 mà không làm ô nhiễm hệ điều hành (`/etc/*`). |
| [02-cmake-conan-project-structure.md](file:///E:/UIT/monocular-spatial-vision/docs/implementation/release-1c/guidec/02-cmake-conan-project-structure.md) | **Cấu Trúc Thư Mục Mã Nguồn C++ & Tệp Cấu Hình CMake (`3.18+`)** | Tổ chức thư mục `services/pi_capture_agent_cpp/` (bao gồm `http_preview_server`, `tcp_streamer`, `neon_yuv_convert`, `triple_buffer`) và cấu hình `CMakeLists.txt` tương thích Debian Bullseye/Bookworm. |
| [03-v4l2-mmap-and-turbojpeg-neon-guide.md](file:///E:/UIT/monocular-spatial-vision/docs/implementation/release-1c/guidec/03-v4l2-mmap-and-turbojpeg-neon-guide.md) | **Lập Trình V4L2 (`media-ctl` + `v4l-subdev0`), Tách Kênh NEON `vld2_u8` & `tjCompressFromYUV`** | Mã C++ chuẩn xác cho `bcm2835-unicam`: đồng bộ `/dev/media0`, lật ảnh phần cứng trên `/dev/v4l-subdev0`, gọi `poll(POLLIN)` trước `VIDIOC_DQBUF`, tách kênh `UYVY -> YUV422P` bằng NEON SIMD (trả ngay `VIDIOC_QBUF`) và nén bằng `tjCompressFromYUV()`. |
| [04-step-by-step-integration-and-testing-plan.md](file:///E:/UIT/monocular-spatial-vision/docs/implementation/release-1c/guidec/04-step-by-step-integration-and-testing-plan.md) | **Kế Hoạch Kiểm Thử Tích Hợp Từng Bước (Wi-Fi, Ethernet Type-C Hub & Jetson)** | Lộ trình kiểm thử toàn diện: Unit Test $\to$ Chẩn đoán `diag`/`snapshot` & Benchmark `test-perf` $\to$ `test-imu` $\to$ Test với Laptop qua Wi-Fi & dây Ethernet (Hub Type-C) ở cả `preview` lẫn `stream` $\to$ Tích hợp Jetson AGX Xavier. |

---

## 3. Quy Tắc Triển Khai Dành Cho Developer

1. **Giữ nguyên 2 giao thức vật lý (Wi-Fi & Ethernet) và 6 chế độ CLI:** Mọi tính năng phục vụ kiểm thử với Laptop trên phiên bản Python phải hoạt động tương đương trên bản C++.
2. **Khóa chuẩn $1280 \times 720$ cho `--mode stream`:** Luồng TCP binary luôn giữ nguyên độ phân giải gốc $1280 \times 720$ (Zero-Resize on Edge); riêng chế độ `--mode preview` (HTTP `:8080`) cho phép giảm chiều nhanh bằng chỉ lệnh NEON xuống $640 \times 360$ để xem mượt trên trình duyệt qua Wi-Fi.
3. **Không tự ý cài đặt gói toàn cục hoặc sửa `/etc/*`:** Bắt buộc tuân thủ tài liệu `01` khi quản lý thư viện C++ qua `conanfile.txt`.
4. **Giới hạn số luồng biên dịch:** Luôn luôn dùng `cmake --build build -j2` trên Pi 3.
