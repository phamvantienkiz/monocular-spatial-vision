# Release 1c Master Index — Pure C/C++ Native Standalone Sandbox

> **Layer:** Implementation Layer (`docs/implementation/release-1c/README.md`)  
> **Release:** Release 1c (C/C++ Native Edge Capture & Perception Pipeline)  
> **Target Hardware:** Raspberry Pi 3 Model B/B+ (Broadcom BCM2837, 4x Cortex-A53, 1GB RAM) & Jetson AGX Xavier  
> **Camera Sensor:** Digilent Pcam 5C (OmniVision OV5640 @ Native 1280x720 30 FPS UYVY)  
> **Status:** Active Working Baseline  

---

## 1. Bối Cảnh & Động Lực Kỹ Thuật (Why C/C++ Native & Zero-Resize?)

Trong phiên bản Release 1 ban đầu, cụm thu nhận và xử lý biên trên Raspberry Pi 3 được cài đặt bằng Python (`services/pi_capture_agent/`). Quá trình thực nghiệm thực địa trên phần cứng giới hạn (Broadcom BCM2837, 1GB RAM) đã bộc lộ những điểm nghẽn nghiêm trọng:
1. **Điểm nghẽn GIL (Global Interpreter Lock):** Python đơn luồng không tận dụng được 4 nhân Cortex-A53; khi thử tạo 2 worker nén song song (`4ca25dd`), FPS tụt từ 14 xuống 9.8 do tranh chấp khóa GIL.
2. **Điểm nghẽn Resize cồng kềnh trên Pi 3:** Cảm biến OV5640 có xung nhịp phần cứng PLL cố định tại $1280 \times 720 @ 30\text{ FPS}$. Việc ép CPU Pi 3 gánh hàm `cv2.resize()` làm tốn thêm $5 - 15\text{ms}$ CPU/frame, làm mờ chi tiết vật thể ở xa và gây sụt giảm FPS nghiêm trọng.
3. **Độ trễ nén ảnh phần mềm:** Thao tác nén JPEG bằng OpenCV tốn từ $45 - 65\text{ms}$/frame, kéo tốc độ thực tế tụt xuống và gây phình bộ đệm socket TCP (bufferbloat) làm trễ hình tới $2\text{ giây}$.
4. **Mức tiêu thụ bộ nhớ lớn:** Python runtime chiếm từ $180 - 250\text{MB}$ RAM (chiếm 25% tổng RAM của Pi 3), tiềm ẩn nguy cơ kích hoạt OOM Killer.
5. **Tính tương thích hệ thống:** Hơn 90% firmware và navigation stack của mobile robot đã được viết bằng C/C++ thuần túy (STM32, micro-ROS, ROS 2 C++ nodes).

**Release 1c giải quyết triệt để vấn đề bằng cách:**
- Tái cấu trúc toàn diện sang **C++17/C++20 thuần túy** (không có bất kỳ Python wrapper nào lúc runtime).
- **Khóa cứng độ phân giải chuẩn phần cứng $1280 \times 720 @ 30\text{ FPS}$ (Zero-Resize on Edge):** Dẹp bỏ hoàn toàn mọi thao tác resize trên Pi 3, đẩy toàn bộ việc Letterbox/Resize sang GPU của Jetson AGX Xavier ($< 0.2\text{ms}$ trong VRAM).
- Quản lý thư viện **cô lập tuyệt đối trong workspace (Zero System Pollution)** bằng `uv` + `.venv` + `Conan 2.0` và biên dịch native an toàn trên Pi 3 với bộ nhớ Swap $2048\text{MB}$.

---

## 2. Cấu Trúc Hồ Sơ Tài Liệu Release 1c

Thư mục `docs/implementation/release-1c/` được tổ chức đồng bộ theo tiêu chuẩn Kiến Trúc Tài Liệu 3 Tầng, các thư mục con được định danh với hậu tố `c` để phân biệt rõ ràng với phiên bản Python:

```
docs/implementation/release-1c/
├── README.md                          # [TÀI LIỆU HIỆN TẠI] Master Index cho Release 1c
├── prd.md                             # Release PRD: Mục tiêu, phạm vi in-scope, Acceptance Criteria & KPIs
├── srs.md                             # Software Requirements Specification: FR-C01 -> FR-C09 & NFR-C01 -> NFR-C05
├── technical-design.md                # Thiết kế kỹ thuật: Zero-copy V4L2 mmap 720p, Multi-thread RingBuffer, NEON
├── migration.md                       # Hướng dẫn thiết lập môi trường cô lập uv + Conan, Swap 2GB & Build Native
│
├── apic/                              # [HỒ SƠ GIAO THỨC & GIAO DIỆN C/C++]
│   └── v1.md                          # Đặc tả Binary Frame Header 40 bytes struct C và ROS 2 C++ interfaces
│
├── backlogc/                          # [SỔ CÁI BACKLOG & USER STORIES C/C++]
│   ├── mono-perception-c-story-index.md  # Sổ cái tổng hợp các Story C++ kèm ma trận truy vết
│   └── storiesc/
│       ├── US-C01.md                  # US-C01: Thu nhận V4L2 MMAP trực tiếp 720p & nén TurboJPEG ARM NEON
│       ├── US-C02.md                  # US-C02: Đọc IMU qua Linux I2C ioctl & RingBuffer Streamer đa luồng
│       └── US-C03.md                  # US-C03: Quản lý thư viện cô lập bằng uv + Conan & Build Native
│
├── guidec/                            # [BỘ HƯỚNG DẪN TRIỂN KHAI THỰC ĐỊA CHO DEVELOPER]
│   ├── README.md                      # Mục lục bộ tài liệu hướng dẫn kỹ thuật
│   ├── 00-overview-and-dev-workflow.md# Luồng làm việc VS Code (Windows) -> Git -> Native Build trên Pi 3
│   ├── 01-pi3-c-environment-and-conan-setup.md # Thiết lập uv, .venv, Conan cục bộ và Swap 2GB trên Pi 3
│   ├── 02-cmake-conan-project-structure.md     # Cấu trúc mã nguồn C++, conanfile.txt và CMakeLists.txt
│   ├── 03-v4l2-mmap-and-turbojpeg-neon-guide.md# Chi tiết lập trình V4L2 ioctl và nén SIMD NEON
│   └── 04-step-by-step-integration-and-testing-plan.md # Quy trình kiểm thử 5 bước tuần tự từ cô lập đến E2E
│
├── qac/                               # [KẾ HOẠCH & MA TRẬN KIỂM THỬ CHẤT LƯỢNG]
│   └── test-cases.md                  # Bộ test cases định lượng hiệu năng, bộ nhớ và độ cô lập hệ thống
│
├── reportsc/                          # [NHẬT KÝ & BÁO CÁO THỰC NGHIỆM]
│   └── log_pi_3_cpp_benchmark.md      # Báo cáo đối chuẩn hiệu năng thực nghiệm C++ vs Python trên Pi 3
│
└── solutionsc/                        # [DANH MỤC 4 GIẢI PHÁP TỐI ƯU CỐT LÕI]
    ├── README.md                      # Bản đồ giải pháp tối ưu hóa C++ trên Cortex-A53
    ├── 01-native-v4l2-mmap-zero-copy.md       # Trụ cột 1: Bắt hình trực tiếp kernel V4L2 không qua OpenCV (2.1ms)
    ├── 02-libjpeg-turbo-arm-neon-c-api.md     # Trụ cột 2: Nén TurboJPEG C API kết hợp tập lệnh SIMD NEON (8.4ms)
    ├── 03-lockfree-ringbuffer-streamer.md     # Trụ cột 3: Hàng đợi đệm bất đồng bộ & Drop-stale triệt tiêu lag
    └── 04-zero-resize-edge-and-gpu-offload.md # Trụ cột 4: Khóa cứng 720p gốc, Dẹp bỏ Resize Pi, Đẩy sang GPU Jetson
```

---

## 3. Ma Trận So Sánh Chỉ Tiêu Kỹ Thuật (Release 1 Python vs Release 1c C++)

| Chỉ tiêu kỹ thuật | Release 1 (Python) | Release 1c (C++ Native) | Cải thiện đạt được |
| :--- | :---: | :---: | :---: |
| **Độ phân giải luồng truyền** | 640x360 (phải resize CPU) | **$1280 \times 720$ (Native Gốc)** | Giữ $100\%$ độ nét quang học |
| **Chi phí Resize trên Pi 3** | $5 - 15\text{ ms}$/frame | $\mathbf{0.00\text{ ms}}$ (Offload sang GPU) | Tiết kiệm $100\%$ thời gian |
| **Thời gian nén ảnh (JPEG Encode)** | $45 - 65\text{ ms}$ | $\mathbf{7 - 9\text{ ms}}$ | Nhanh hơn $\approx 7$ lần |
| **Tốc độ khung hình (720p @ Pi 3)** | $9.8 - 15.1\text{ FPS}$ | $\mathbf{25.0 - 30.0\text{ FPS}}$ | Đạt trần tốc độ cảm biến |
| **Mức tiêu thụ CPU (4 nhân Cortex-A53)** | $100\%$ (1 nhân) + GIL lock | $\mathbf{\le 22\%}$ (chia đều 4 nhân) | Giải phóng CPU cho hệ thống |
| **Mức tiêu thụ RAM (Memory Footprint)** | $180 - 250\text{ MB}$ | $\mathbf{\le 25\text{ MB}}$ | Tiết kiệm $\approx 88\%$ RAM |
| **Hiện tượng trễ khung hình (Lag / Jitter)** | $2.0\text{s}$ (khi giật mạng) | $\mathbf{< 20\text{ ms}}$ (Drop-stale lock-free) | Triệt tiêu hoàn toàn delay |
| **Quản lý thư viện & phụ thuộc** | `.venv` + `uv`/`pip` | `.venv` + `uv` + `Conan 2.0` (`CONAN_HOME`) | Cô lập $100\%$ trong repo |

---

## 4. Nguyên Tắc Bất Biến Của Phiên Bản C++ (Invariants)

1. **Khóa Cứng 720p & Zero Resize on Pi:** Cảm biến OV5640 chạy ở điểm tối ưu nhất $1280 \times 720$ @ $30\text{ FPS}$ (UYVY). Pi 3 không làm bất kỳ thao tác co giãn điểm ảnh nào. Toàn bộ tiền xử lý resize/letterbox cho YOLO do GPU Jetson AGX Xavier đảm nhiệm trong $< 0.2\text{ms}$.
2. **Zero System Pollution (Tuyệt đối không ô nhiễm hệ thống):**
   - Mọi công cụ C++ package manager (`conan`) chạy từ môi trường ảo `.venv` tạo bởi `uv`.
   - Toàn bộ thư viện header và binary đã build (`.a`, `.so`) chỉ được lưu trong `.conan/` và `build/` của repo.
   - Xóa thư mục dự án là máy tính trả về trạng thái sạch sẽ ban đầu.
3. **Zero-Breaking Interface (Không phá vỡ giao tiếp backend):**
   - Giữ nguyên cấu trúc gói tin mạng: 40-byte Binary Header (Magic `0x5043`, `timestamp_ns`, `pitch`, `roll`, `width=1280`, `height=720`, `payload_len`) và payload JPEG.
   - Backend trên Jetson AGX Xavier hoặc Laptop tiếp nhận dữ liệu bình thường mà không cần sửa đổi mã nguồn.
4. **Hardware-Safe Native Compilation:**
   - Biên dịch trực tiếp trên Raspberry Pi 3 bắt buộc cấu hình Swap Memory $2048\text{MB}$ và chỉ dùng cờ `-j2` (hoặc `-j1`) để ngăn ngừa OOM Killer làm treo máy.
