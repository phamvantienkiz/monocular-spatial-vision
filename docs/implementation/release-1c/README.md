# Release 1c Master Index — Pure C/C++ Native Standalone Sandbox

> **Layer:** Implementation Layer (`docs/implementation/release-1c/README.md`)  
> **Release:** Release 1c (C/C++ Native Edge Capture & Perception Pipeline)  
> **Target Hardware:** Raspberry Pi 3 Model B/B+ (Broadcom BCM2837, 4x Cortex-A53, 1GB RAM), Developer Laptop & Jetson AGX Xavier  
> **Camera Sensor:** Digilent Pcam 5C (OmniVision OV5640 @ Native 1280x720 30 FPS UYVY)  
> **Status:** Active Working Baseline (Audited & Revised)  

---

## 1. Bối Cảnh & Động Lực Kỹ Thuật (Why C/C++ Native, Dual Transport & Zero-Resize?)

Trong phiên bản Release 1 ban đầu, cụm thu nhận và xử lý biên trên Raspberry Pi 3 được cài đặt bằng Python (`services/pi_capture_agent/`). Qua phân tích thực nghiệm thực địa và kiểm toán mã nguồn ([`counter-argument.md`](file:///E:/UIT/monocular-spatial-vision/docs/implementation/release-1c/reportsc/counter-argument.md)), các điểm nghẽn thực sự trên Pi 3 bao gồm:
1. **Chi phí chuyển đổi không gian màu & cấp phát mảng trong OpenCV Python:** `cv2.VideoCapture` tự động chuyển đổi `UYVY` ($1.84\text{MB}$) sang mảng NumPy `BGR` 3 kênh ($2.76\text{MB}$) trên CPU và khi đặt `CAP_PROP_BUFFERSIZE = 1` dễ làm bộ thu DMA `bcm2835-unicam` bị lỡ nhịp VSYNC ($33.33\text{ms}$), kéo thời gian chờ `read_raw()` lên $41.29\text{ms}$.
2. **Lỗi Silent Fallback khi nén JPEG:** Khi `PyTurboJPEG` thiếu thư viện tương thích hoặc gặp ngoại lệ, code rơi âm thầm về `cv2.imencode()` tốn $60.62\text{ms}$/frame trên 1 nhân Cortex-A53.
3. **Điểm nghẽn GIL (Global Interpreter Lock) & Dấu ấn RAM:** Python runtime chiếm $\sim 180 - 215\text{MB}$ RAM trên tổng số $1\text{GB}$ RAM của Pi 3, và khóa GIL gây cản trở khi cần chạy đồng thời luồng bắt hình 30 FPS, luồng đọc I2C IMU 50Hz, luồng HTTP Preview Server và luồng TCP Streamer.
4. **Tính tương thích hệ thống nhúng:** Hơn 90% firmware điều khiển và navigation stack của mobile robot được viết bằng C/C++ thuần túy (STM32, ROS 2 `rclcpp` nodes).

**Release 1c giải quyết triệt để các vấn đề trên đồng thời giữ nguyên 100% sự tiện lợi vận hành của bản Python:**
- **Tái cấu trúc sang C++17 thuần túy (`services/pi_capture_native/` — tương thích alias `pi_capture_agent_cpp`):** Giao tiếp trực tiếp với Linux Media Controller (`/dev/media0`, `/dev/v4l-subdev0`) và V4L2 MMAP (`/dev/video0`), tự động khóa tốc độ khung hình phần cứng qua `VIDIOC_SUBDEV_S_FRAME_INTERVAL`, hỗ trợ chế độ Anti-Stripe (`720x480` center-crop $\to$ `640x480`), tách kênh `UYVY` $\to$ Planar `YUV422P` bằng chỉ lệnh vector ARM NEON (`vld4_u8` / `vst2_u8`) và nén trực tiếp qua `tjCompressFromYUV()` của `libjpeg-turbo` trong $\le 10\text{ms}$.
- **Bảo toàn 100% 2 phương thức truyền dẫn (Wi-Fi & Ethernet) và 6 chế độ CLI giống hệt bản Python:**
  - **Phương thức 1 (Wi-Fi Không Dây):** Dùng để kiểm thử linh hoạt với Laptop thông qua `--mode preview` (HTTP MJPEG + Telemetry HUD trên cổng `8080`) hoặc `--mode stream` qua Wi-Fi khi di chuyển giá đỡ/robot.
  - **Phương thức 2 (Cáp Ethernet Có Dây):** Dùng dây mạng Ethernet cắm qua **Hub chuyển đổi Type-C vào Laptop** (tự động nhận IP qua APIPA/mDNS hoặc truyền `--host <IP>` động, không cần cấu hình IP tĩnh) trong quá trình dev/test, và cắm trực tiếp qua **cổng Ethernet vào Jetson AGX Xavier** khi tích hợp thực tế trên robot.
  - **Giữ đủ 6 chế độ vận hành CLI:** `--mode diag`, `--mode snapshot`, `--mode test-imu`, `--mode preview`, `--mode stream`, `--mode test-perf`.
- **Khóa cứng độ phân giải chuẩn phần cứng $1280 \times 720 @ 30\text{ FPS}$ cho luồng Stream chính (`--mode stream`):** Không resize/crop luồng stream 720p trên Pi 3 để bảo toàn độ sắc nét quang học cho bài toán đo khoảng cách 3D IPM trên Laptop/Jetson (chỉ hỗ trợ downscale nhẹ bằng NEON cho riêng luồng `--mode preview` qua Wi-Fi khi cần tiết kiệm băng thông).
- **Cô lập môi trường 100% (Zero System Pollution):** Quản lý gói C++ bằng `uv` + `.venv` + `Conan 2.0` (`CONAN_HOME` nằm trong repo), không tự ý sửa đổi cấu hình toàn cục của hệ điều hành (`/etc/dphys-swapfile`).

---

## 2. Cấu Trúc Hồ Sơ Tài Liệu Release 1c

Thư mục `docs/implementation/release-1c/` được tổ chức đồng bộ theo tiêu chuẩn Kiến Trúc Tài Liệu 3 Tầng:

```text
docs/implementation/release-1c/
├── README.md                          # [TÀI LIỆU HIỆN TẠI] Master Index cho Release 1c
├── prd.md                             # Release PRD: Mục tiêu, Dual Wi-Fi/Ethernet, 6 CLI modes, KPIs
├── srs.md                             # Software Requirements Specification: FR-C01 -> FR-C10 & NFR-C01 -> NFR-C05
├── technical-design.md                # Thiết kế kỹ thuật: Media-ctl + V4L2 MMAP, NEON YUV422P, HTTP Preview & TCP Stream
├── migration.md                       # Hướng dẫn thiết lập môi trường cô lập uv + Conan & kết nối Wi-Fi / Ethernet Type-C
│
├── apic/                              # [HỒ SƠ GIAO THỨC & GIAO DIỆN C/C++]
│   └── v1.md                          # Đặc tả Binary Frame Header 40B (Strict-Aliasing safe), HTTP Preview API & ROS 2
│
├── backlogc/                          # [SỔ CÁI BACKLOG & USER STORIES C/C++]
│   ├── mono-perception-c-story-index.md  # Sổ cái tổng hợp các Story C++ kèm ma trận truy vết
│   └── storiesc/
│       ├── US-C01.md                  # US-C01: Media-ctl, V4L2 MMAP 720p & nén TurboJPEG (tjCompressFromYUV + NEON)
│       ├── US-C02.md                  # US-C02: IMU I2C 50Hz, HTTP Preview Server (Wi-Fi) & TCP Streamer (Wi-Fi/Ethernet)
│       └── US-C03.md                  # US-C03: Quản lý phụ thuộc cô lập bằng uv + Conan 2.0 & Build Harness an toàn
│
├── guidec/                            # [BỘ HƯỚNG DẪN TRIỂN KHAI THỰC ĐỊA CHO DEVELOPER]
│   ├── README.md                      # Mục lục bộ tài liệu hướng dẫn kỹ thuật
│   ├── 00-overview-and-dev-workflow.md# Quy trình Dev VS Code -> Pi 3 và 2 kịch bản kết nối Wi-Fi & Ethernet (Hub Type-C / Jetson)
│   ├── 01-pi3-c-environment-and-conan-setup.md # Thiết lập uv, .venv, Conan cục bộ tuân thủ Zero System Pollution
│   ├── 02-cmake-conan-project-structure.md     # Cấu trúc mã nguồn C++, conanfile.txt và CMakeLists.txt chuẩn (CMake >= 3.18)
│   ├── 03-v4l2-mmap-and-turbojpeg-neon-guide.md# Lập trình Media-ctl, V4L2 poll/mmap, NEON UYVY->YUV422P & tjCompressFromYUV
│   └── 04-step-by-step-integration-and-testing-plan.md # Quy trình kiểm thử 6 bước (Unit Test -> Diag/Preview Wi-Fi -> Stream Wi-Fi/Ethernet -> Jetson)
│
├── qac/                               # [KẾ HOẠCH & MA TRẬN KIỂM THỬ CHẤT LƯỢNG]
│   └── test-cases.md                  # Bộ test cases định lượng hiệu năng, Wi-Fi Preview, Ethernet Stream & Zero-Pollution
│
├── reportsc/                          # [NHẬT KÝ KIỂM TOÁN & KỲ VỌNG ĐỐI CHUẨN]
│   ├── counter-argument.md            # Báo cáo phản biện kỹ thuật & kiểm toán kiến trúc Release 1c
│   └── log_pi_3_cpp_benchmark.md      # Phân tích định lượng chu kỳ phần cứng VSYNC & kỳ vọng hiệu năng C++ vs Python
│
└── solutionsc/                        # [DANH MỤC 5 GIẢI PHÁP TỐI ƯU CỐT LÕI]
    ├── README.md                      # Bản đồ giải pháp tối ưu hóa C++ và Dual-Transport trên Cortex-A53
    ├── 01-native-v4l2-mmap-zero-copy.md       # Trụ cột 1: Cấu hình Media-ctl, V4L2 MMAP & RAII Buffer Guard
    ├── 02-libjpeg-turbo-arm-neon-c-api.md     # Trụ cột 2: Tách kênh NEON UYVY->YUV422P & tjCompressFromYUV (8.4ms)
    ├── 03-lockfree-ringbuffer-streamer.md     # Trụ cột 3: Hàng đợi Double/Triple Buffer, Atomic send_all() & Dual Wi-Fi/Ethernet
    ├── 04-zero-resize-edge-and-gpu-offload.md # Trụ cột 4: Khóa cứng 720p cho luồng Stream & lộ trình GPU Offload trên Jetson
    └── 05-cpp-implementation-master-plan.md   # Trụ cột 5: Kế hoạch triển khai mã nguồn C++ 5 giai đoạn đồng bộ 100% với Python
```

---

## 3. Ma Trận So Sánh Chỉ Tiêu Kỹ Thuật (Release 1 Python vs Release 1c C++ Native)

| Chỉ tiêu kỹ thuật | Release 1 (Python Hiện Tại) | Release 1c (C++ Native Mục Tiêu) | Giá trị mang lại |
| :--- | :---: | :---: | :--- |
| **Các chế độ vận hành CLI (`--mode`)** | `diag`, `snapshot`, `test-imu`, `preview`, `stream`, `test-perf` | **`diag`, `snapshot`, `test-imu`, `preview`, `stream`, `test-perf`** | **Giữ nguyên 100% cách thức test & vận hành** |
| **Giao thức & Môi trường truyền dẫn** | Wi-Fi (Preview/Stream) & Ethernet (Type-C Hub Laptop / Jetson) | **Wi-Fi (Preview/Stream) & Ethernet (Type-C Hub Laptop / Jetson)** | **Tương thích hoàn toàn mọi kịch bản thực địa** |
| **Độ phân giải `--mode stream`** | $1280 \times 720$ (Native 720p) | **$1280 \times 720$ (Native 720p)** | Giữ $100\%$ độ nét quang học cho IPM |
| **Độ phân giải `--mode preview` (Wi-Fi)** | $640 \times 360$ (nHD, Q=65) | **$640 \times 360$ (NEON decimation, Q=65) hoặc 720p** | Xem mượt qua Wi-Fi trên trình duyệt Laptop |
| **Thời gian xử lý CPU tích cực / frame (720p)** | $\sim 45 - 65\text{ ms}$ (khi rơi về OpenCV) | **$\mathbf{\le 10.0\text{ ms}}$** ($\sim 1.2\text{ms}$ NEON + $\sim 7.2\text{ms}$ JPEG) | Nhanh hơn $\sim 5 - 6$ lần, dư tải cho 30 FPS |
| **Tốc độ khung hình thực tế (720p Stream)** | $9.8 - 16.5\text{ FPS}$ | **$\mathbf{25.0 - 30.0\text{ FPS}}$** (Khóa theo nhịp VSYNC $33.3\text{ms}$) | Đạt trần tốc độ vật lý cảm biến OV5640 |
| **Mức tiêu thụ CPU (4 nhân Cortex-A53)** | $100\%$ (1 nhân) + GIL contention | **$\mathbf{\le 25\%}$** (chia đều các luồng POSIX) | Giải phóng CPU, giảm nhiệt độ SoC |
| **Mức tiêu thụ RAM (Memory Footprint)** | $180 - 215\text{ MB}$ | **$\mathbf{\le 35\text{ MB}}$** | Tiết kiệm $> 80\%$ bộ nhớ RAM trên Pi 3 |
| **Độ trễ hiển thị (Visual Latency)** | $< 50\text{ ms}$ (sau khi bật `TCP_NODELAY`) | **$\mathbf{< 30\text{ ms}}$** (`TCP_NODELAY` + Latest-Frame Slot) | Phản hồi tức thời khi vẫy tay trước ống kính |
| **Quản lý thư viện & phụ thuộc** | `.venv` + `uv`/`pip` | **`.venv` + `uv` + `Conan 2.0` (`CONAN_HOME` nội bộ)** | Cô lập $100\%$ trong repo, không chạm OS |

---

## 4. Nguyên Tắc Bất Biến Của Phiên Bản C++ (System Invariants)

1. **Dual-Transport & Testing Parity (Bất biến phương thức kết nối & kiểm thử):**
   - Hỗ trợ song song cả **Wi-Fi** (phục vụ kiểm thử nhanh không dây với Laptop qua `--mode preview` port `8080` và `--mode stream` port `9876`) và **Cáp Ethernet có dây** (cắm qua Hub chuyển đổi Type-C vào Laptop để test tốc độ cao không cần gán IP tĩnh, hoặc cắm trực tiếp vào Jetson AGX Xavier khi chạy thực tế).
   - Giữ nguyên đầy đủ 6 chế độ CLI (`diag`, `snapshot`, `test-imu`, `preview`, `stream`, `test-perf`) để kỹ sư sử dụng cùng một quy trình thao tác quen thuộc như bản Python.
2. **Media Controller & V4L2 Subdevice Compliance:**
   - Tự động cấu hình format `UYVY8_1X16/1280x720@1/30` trên `/dev/media0` và bật `V4L2_CID_VFLIP = 1` trực tiếp trên `/dev/v4l-subdev0` trước khi khởi chạy DMA `/dev/video0`.
3. **True NEON SIMD Pipeline & Memory Safety:**
   - Dùng tập lệnh vector ARM NEON (`<arm_neon.h>`, `vld2_u8`) để tách kênh `UYVY` sang Planar `YUV422P` trong $\sim 1.2\text{ms}$, trả ngay buffer `VIDIOC_QBUF` về kernel (tuyệt đối không để rò rỉ buffer DMA khi mạng nghẽn), sau đó nén bằng `tjCompressFromYUV()` vào hệ thống bộ đệm đôi (Double/Triple Buffer) an toàn đa luồng.
4. **Zero-Breaking Interface & Atomic Framing:**
   - Giữ nguyên cấu trúc gói tin mạng 40-byte Binary Header (`>HHIQffIIII`, Magic `0x5043`, đóng gói `float` an toàn qua `std::memcpy`) và dùng hàm `send_all()` đảm bảo không bao giờ gửi thiếu byte giữa chừng gây lệch pha luồng TCP trên `mock_ingest_server.py` và `IngestService`.
5. **Zero System Pollution:**
   - Mọi công cụ và thư viện nằm trọn trong `.venv/`, `.conan/` và `services/pi_capture_agent_cpp/build/`. Tuyệt đối không sửa đổi `/etc/dphys-swapfile` hay cài đặt thư viện vào `/usr/local/`.
