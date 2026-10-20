# Release 1c PRD — Pure C/C++ Native Standalone Sandbox

> **Layer:** Implementation Layer (`docs/implementation/release-1c/prd.md`)  
> **Release:** Release 1c (C/C++ Native Edge Capture & Perception Pipeline)  
> **Target Date:** Q4 2026  
> **Status:** Approved Baseline  

---

## 1. Release Goals & Scope Definition

Release 1c là phiên bản tái cấu trúc toàn diện tầng thu nhận và truyền dẫn biên của cụm cảm biến đơn kính (Pcam 5C + IMU MPU6050 trên Raspberry Pi 3) sang **C/C++ thuần túy (C++17/C++20)**. 

Mục tiêu cốt lõi:
1. Giải quyết triệt để vấn đề quá tải CPU, nghẽn GIL và sụt giảm FPS của phiên bản Python trong Release 1.
2. **Khóa cứng độ phân giải chuẩn phần cứng $1280 \times 720 @ 30\text{ FPS}$ (UYVY)**; dẹp bỏ hoàn toàn mọi thao tác resize/downscale trên Pi 3 để loại trừ mọi điểm nghẽn và lỗi phát sinh.
3. Chuyển giao toàn bộ tác vụ tiền xử lý chuẩn hóa kích thước cho mạng AI (như Letterbox $640 \times 640$) về phía GPU của Jetson AGX Xavier.

### 1.1. In-Scope Features (Phạm Vi Thực Hiện)

1. **Native V4L2 Capture Subsystem (Cố định chuẩn 720p gốc):**
   - Trực tiếp tương tác với Linux V4L2 kernel subsystem qua các lệnh `ioctl` chuẩn (`VIDIOC_S_FMT`, `VIDIOC_REQBUFS`, `VIDIOC_QUERYBUF`, `VIDIOC_QBUF`, `VIDIOC_DQBUF`).
   - Hỗ trợ cơ chế Memory Mapping (`V4L2_MEMORY_MMAP`) với 4 bộ đệm xoay vòng (Ring Buffers) cho phép zero-copy trích xuất khung hình từ cảm biến OmniVision OV5640.
   - **Khóa cứng thiết lập phần cứng duy nhất:** Độ phân giải gốc **$1280 \times 720$ định dạng UYVY @ $30\text{ FPS}$**.
   - Tự động kích hoạt Hardware Vertical Flip trên chip cảm biến qua V4L2 Control (`V4L2_CID_VFLIP`) với chi phí 0.0ms CPU.

2. **TurboJPEG ARM NEON SIMD Encoder (720p Native):**
   - Sử dụng trực tiếp C API của `libjpeg-turbo` (`tjInitCompress`, `tjCompress2`).
   - Tận dụng bộ chỉ lệnh 128-bit vectorization ARM NEON trên các nhân ARM Cortex-A53 của Raspberry Pi 3.
   - Nén trực tiếp frame $1280 \times 720$ UYVY sang JPEG với chu kỳ thực thi $\le 10\text{ms}$/frame (nhanh gấp 6 lần so với `cv2.imencode`).

3. **Pure C++ I2C IMU Telemetry Subsystem:**
   - Đọc trực tiếp thanh ghi cảm biến MPU6050 qua Linux I2C device node (`/dev/i2c-1`) bằng lệnh `ioctl(I2C_SLAVE)`.
   - Vòng lặp định thời chuẩn xác $50\text{Hz}$ ($20\text{ms}$), tính toán góc pitch $\theta$, roll $\phi$ bằng toán học số học thực tốc độ cao.

4. **Multi-threaded Producer-Consumer RingBuffer & POSIX Streamer:**
   - Phân tách luồng bắt hình (Capture Thread), luồng xử lý nén (Encode Worker Thread), luồng đọc cảm biến (IMU Thread) và luồng truyền mạng (Socket Streamer Thread) bằng `std::thread` độc lập, không bị khóa toàn cục GIL.
   - Cơ chế tự động thả trôi khung hình cũ (Drop-stale-frame policy): Khi kết nối mạng bị chậm, bộ đệm luôn ưu tiên truyền khung hình mới nhất, triệt tiêu hoàn toàn hiện tượng phình đệm gây lag 2 giây như ở bản Python.
   - Socket client POSIX TCP với cờ `TCP_NODELAY` (vô hiệu hóa thuật toán Nagle), tự động kết nối lại khi đứt kết nối mạng (Exponential Backoff Auto-Reconnect).

5. **Strict Environment & Dependency Isolation (Zero System Pollution):**
   - Quản lý gói thư viện C++ bằng `Conan 2.0` được cài đặt nội bộ trong `.venv` tạo bởi `uv`.
   - Biến môi trường `CONAN_HOME` được trỏ cục bộ vào `.conan/` bên trong workspace.
   - Biên dịch native trực tiếp trên Pi 3 thông qua CMake, đảm bảo không có bất kỳ thư viện hay cấu hình nào can thiệp vào môi trường hệ điều hành global.

---

### 1.2. Out-of-Scope (Ngoài Phạm Vi Release 1c)

1. **Tuyệt đối không resize trên Pi 3:** Mọi tác vụ resize, crop, letterbox bị cấm triệt để trên Pi 3 và được bàn giao $100\%$ cho CUDA Kernel trên Jetson AGX Xavier.
2. **Không thay đổi cấu trúc gói tin mạng:** Header nhị phân 40 bytes (Magic `0x5043`, `timestamp_ns`, `pitch`, `roll`, `width=1280`, `height=720`, `payload_len`) và payload JPEG được giữ nguyên để đảm bảo backend trên Jetson AGX Xavier và Laptop không bị phá vỡ.
3. **Không viết lại mô hình AI trên Jetson:** Quá trình suy luận YOLOv8-seg và Metric Depth trên Jetson AGX Xavier vẫn chạy trên runtime TensorRT hiện có.
4. **Không can thiệp mạch vi sai STM32:** Khung gầm và điều khiển motor bánh xe của robot đã chạy C/C++ ổn định trên STM32, không thuộc phạm vi điều chỉnh của release này.

---

## 2. Release Acceptance Criteria & KPIs

| Tiêu chí | Mô tả chi tiết | Ngưỡng đạt yêu cầu (Pass Target) | Phương pháp kiểm chứng |
| :--- | :--- | :---: | :--- |
| **AC-C01** | Tốc độ khung hình thực tế tại độ phân giải gốc $1280 \times 720$ | $\mathbf{\ge 25.0\text{ FPS}}$ (Target: $30.0\text{ FPS}$) | Đo đạc qua 1000 frames liên tục bằng benchmark CLI |
| **AC-C02** | Tổng thời gian bắt hình và nén ảnh 720p trên Pi 3 (Grab + Encode Latency) | $\mathbf{\le 15.0\text{ ms}}$/frame | Timestamp profiling chi tiết từng chu trình trong C++ |
| **AC-C03** | Mức tiêu thụ CPU trên 4 nhân ARM Cortex-A53 của Raspberry Pi 3 | $\mathbf{\le 25.0\%}$ tổng công suất CPU | Đo bằng công cụ `htop` / `pidstat` trong suốt quá trình stream |
| **AC-C04** | Dung lượng bộ nhớ RAM sử dụng (Resident Set Size - RSS) | $\mathbf{\le 35\text{ MB}}$ RAM | Giám sát qua `/proc/[pid]/status` và `valgrind --tool=massif` |
| **AC-C05** | Độ trễ truyền dẫn luồng hình ảnh tới màn hình quan sát (End-to-End Visual Latency) | $\mathbf{\le 30\text{ ms}}$ | Thử nghiệm đối chiếu đồng hồ bấm giờ kỹ thuật số thời gian thực |
| **AC-C06** | Độ ổn định luồng truyền qua mạng Ethernet có dây trong 60 phút | Tỷ lệ rớt gói $\mathbf{< 0.05\%}$ | Wireshark đếm số thứ tự `frame_id` nhảy cóc |
| **AC-C07** | Mức độ cô lập môi trường phát triển (Zero System Pollution) | $\mathbf{100\%}$ tệp tin nằm trong repo workspace | Kiểm tra `git status --ignored` và xác nhận không có file nào lọt ra ngoài repo |
