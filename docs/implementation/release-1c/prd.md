# Release 1c PRD — Pure C/C++ Native Standalone Sandbox

> **Layer:** Implementation Layer (`docs/implementation/release-1c/prd.md`)  
> **Release:** Release 1c (C/C++ Native Edge Capture & Perception Pipeline)  
> **Target Date:** Q4 2026  
> **Status:** Approved Baseline (Audited & Revised)  

---

## 1. Release Goals & Scope Definition

Release 1c là phiên bản cài đặt tầng thu nhận, chẩn đoán và truyền dẫn biên của cụm cảm biến đơn kính (Pcam 5C + IMU MPU6050 trên Raspberry Pi 3) bằng **C/C++ thuần túy (C++17)**.

Mục tiêu cốt lõi:
1. Giải quyết triệt để chi phí chuyển đổi màu `UYVY -> BGR`, nghẽn khóa GIL và dung lượng RAM lớn của phiên bản Python trong Release 1.
2. **Bảo toàn 100% hai phương thức kết nối truyền dẫn (Wi-Fi và Cáp Ethernet) cùng toàn bộ 6 chế độ vận hành/kiểm thử CLI** giống hệt phiên bản Python hiện tại:
   - Sử dụng **Wi-Fi** để thuận tiện kiểm thử nhanh với Laptop qua cả chế độ xem trực tiếp (`--mode preview` trên trình duyệt) lẫn chế độ truyền luồng nhị phân (`--mode stream` về Laptop).
   - Sử dụng **Cáp Ethernet có dây** kết nối qua **Hub chuyển đổi Type-C vào Laptop** để kiểm thử băng thông tối đa trong quá trình phát triển (không phụ thuộc IP tĩnh), và kết nối trực tiếp qua **cổng Ethernet vào Jetson AGX Xavier** khi tích hợp thực tế trên robot.
3. **Khóa cứng độ phân giải cảm biến ở mức chuẩn phần cứng $1280 \times 720 @ 30\text{ FPS}$ (`UYVY`)** trên đường truyền CSI-2 `bcm2835-unicam`; giữ nguyên khung hình $1280 \times 720$ sắc nét cho luồng `--mode stream` về Laptop/Jetson để đạt độ chính xác đo cự ly 3D IPM cao nhất.

---

### 1.1. In-Scope Features (Phạm Vi Thực Hiện)

1. **Media Controller & Native V4L2 Capture Subsystem (Chuẩn 720p Gốc):**
   - Tự động đàm phán cấu hình Media Controller (`/dev/media0`) đặt định dạng `UYVY8_1X16/1280x720@1/30` cho pad cảm biến `'ov5640 10-003c':0`.
   - Tự động kích hoạt Hardware Vertical Flip (`V4L2_CID_VFLIP = 1`) trực tiếp trên subdevice cảm biến `/dev/v4l-subdev0` với chi phí CPU $0.0\text{ms}$.
   - Giao tiếp trực tiếp với `/dev/video0` qua `poll()` và các lệnh `ioctl` chuẩn (`VIDIOC_S_FMT`, `VIDIOC_REQBUFS`, `VIDIOC_QUERYBUF`, `VIDIOC_QBUF`, `VIDIOC_DQBUF`) với 4 bộ đệm xoay vòng `V4L2_MEMORY_MMAP`.

2. **ARM NEON Planar De-interleave & TurboJPEG SIMD Encoder:**
   - Sử dụng tập lệnh vector 128-bit ARM NEON (`<arm_neon.h>`, `vld2_u8`) để tách nhanh bộ đệm `UYVY` từ `mmap` sang bộ đệm phẳng `YUV422P` (3 mặt phẳng `Y`, `U`, `V`) chỉ trong $\sim 1.2\text{ms}$ và trả ngay buffer `VIDIOC_QBUF` về cho kernel DMA (ngăn chặn hoàn toàn nguy cơ cạn kiệt buffer V4L2).
   - Gọi trực tiếp C API `tjCompressFromYUV()` của `libjpeg-turbo` (`TJSAMP_422`, `TJFLAG_FASTDCT | TJFLAG_NOREALLOC`) để nén khung hình $1280 \times 720$ sang JPEG trong $\sim 7.2 - 8.5\text{ms}$ mà không tốn bước chuyển đổi không gian màu RGB.

3. **Pure C++ I2C IMU Telemetry Subsystem:**
   - Đọc trực tiếp thanh ghi cảm biến MPU6050 qua Linux I2C device node (`/dev/i2c-1`) bằng lệnh `ioctl(I2C_SLAVE, 0x68)`, kiểm tra thanh ghi `WHO_AM_I (0x75) == 0x68`, cấu hình bộ lọc thông thấp DLPF (`44Hz`) và duy trì vòng lặp đọc chuẩn xác $50\text{Hz}$ ($20\text{ms}$) để tính góc pitch $\theta$, roll $\phi$.

4. **Dual-Transport Networking (Wi-Fi & Wired Ethernet) và 6 Chế Độ CLI Tương Thích 100% Với Python:**
   - **`--mode diag`:** Kiểm tra tự động bus I2C MPU6050, subdevice OV5640 và đo tốc độ bắt frame vật lý trên `/dev/video0`.
   - **`--mode snapshot`:** Chụp và lưu 1 khung hình JPEG 720p kèm thông số góc nghiêng IMU ra ổ đĩa.
   - **`--mode test-imu`:** In liên tục gia tốc $[a_x, a_y, a_z]$ và góc nghiêng `Pitch`, `Roll` ở tần số $50\text{Hz}$ ra terminal.
   - **`--mode preview` (Wi-Fi / LAN Diagnostic HTTP Server):** Tích hợp HTTP Server nhẹ trên cổng `8080` phục vụ trang giao diện HUD (`/`), luồng MJPEG trực tiếp (`/stream.mjpg` có bật `TCP_NODELAY`), ảnh tĩnh (`/snapshot.jpg`) và JSON góc nghiêng (`/telemetry`). Hỗ trợ thu nhỏ nhanh về $640 \times 360$ (`preview_width`, `preview_height`, `preview_quality = 65`) bằng chỉ lệnh NEON để xem mượt mà qua sóng Wi-Fi trên trình duyệt Laptop.
   - **`--mode stream` (High-Throughput Binary TCP Streamer qua Wi-Fi hoặc Ethernet):**
     - Đóng gói `PackedFrameHeader` 40 bytes (`>HHIQffIIII`) + JPEG payload 720p và truyền qua POSIX TCP socket (`TCP_NODELAY`, `SO_KEEPALIVE`, hàm `send_all()` đảm bảo tính nguyên vẹn của từng frame, kết hợp bộ đệm `LatestFrameSlot` tự động hủy frame cũ trước khi gửi nếu mạng chậm).
     - Hoạt động linh hoạt trên cả **Wi-Fi** (test không dây với Laptop), **Cáp Ethernet qua Hub chuyển đổi Type-C nối với Laptop** (hỗ trợ APIPA `169.254.x.x` / mDNS / `--host <IP>` động), và **Cáp Ethernet nối trực tiếp với Jetson AGX Xavier**.
   - **`--mode test-perf`:** Đo đạc độc lập thời gian chờ VSYNC, thời gian tách kênh NEON, thời gian nén TurboJPEG và thông lượng FPS thực tế.

5. **Strict Environment & Dependency Isolation (Zero System Pollution):**
   - Quản lý gói thư viện C++ bằng `Conan 2.0` cài đặt nội bộ trong `.venv` tạo bởi `uv`, với `CONAN_HOME` trỏ vào `.conan/` bên trong workspace.
   - Không tự ý thay đổi các tệp cấu hình toàn cục của hệ điều hành như `/etc/dphys-swapfile` hay `/usr/local/`.

---

### 1.2. Out-of-Scope (Ngoài Phạm Vi Release 1c)

1. **Không cắt giảm bất kỳ phương thức kết nối hay chế độ test nào của bản Python:** Nghiêm cấm loại bỏ chế độ Wi-Fi hay chế độ `--mode preview` / `--mode diag`.
2. **Không thay đổi cấu trúc gói tin mạng 40 bytes:** Giữ nguyên định dạng `PackedFrameHeader` 40 bytes (`>HHIQffIIII`) để tương thích 100% với `scripts/mock_ingest_server.py` và `services/backend/app/services/ingest_service.py` trên Laptop và Jetson AGX Xavier.
3. **Không can thiệp mạch vi sai STM32:** Phần điều khiển động cơ bánh xe của robot nằm ngoài phạm vi của release này.

---

## 2. Release Acceptance Criteria & KPIs

| Tiêu chí | Mô tả chi tiết | Ngưỡng đạt yêu cầu (Pass Target) | Phương pháp kiểm chứng |
| :--- | :--- | :---: | :--- |
| **AC-C01** | Tốc độ khung hình thực tế ở chế độ `--mode stream` ($1280 \times 720$ qua cáp Ethernet sang Laptop Type-C Hub hoặc Jetson) | $\mathbf{\ge 25.0\text{ FPS}}$ (Target: $30.0\text{ FPS}$) | Đo qua 1000 frames liên tục trên `mock_ingest_server.py` / `IngestService` |
| **AC-C02** | Tổng thời gian CPU xử lý tích cực mỗi frame 720p trên Pi 3 (NEON De-interleave + TurboJPEG Encode, không tính thời gian ngủ chờ VSYNC cảm biến) | $\mathbf{\le 12.0\text{ ms}}$/frame | Timestamp profiling bằng `std::chrono::steady_clock` trong `--mode test-perf` |
| **AC-C03** | Hoạt động mượt mà ở cả 2 phương thức Wi-Fi và Ethernet (Type-C Hub Laptop & Jetson) cho cả `--mode preview` và `--mode stream` | $15 - 25\text{ FPS}$ (Wi-Fi) và $25 - 30\text{ FPS}$ (Ethernet), độ trễ mắt nhìn $\mathbf{\le 40\text{ ms}}$ | Kiểm thử thực tế trên trình duyệt Laptop (`:8080/preview` và `:8000/hud`) |
| **AC-C04** | Mức tiêu thụ CPU trên 4 nhân ARM Cortex-A53 của Raspberry Pi 3 | $\mathbf{\le 25.0\%}$ tổng công suất CPU | Đo bằng `htop` / `pidstat` trong suốt quá trình stream |
| **AC-C05** | Dung lượng bộ nhớ RAM sử dụng (Resident Set Size - RSS) | $\mathbf{\le 35\text{ MB}}$ RAM | Giám sát qua `/proc/[pid]/status` (`VmRSS`) |
| **AC-C06** | Tính toàn vẹn gói tin TCP & Tự động phục hồi kết nối (Auto-Reconnect) | $\mathbf{0}$ lỗi `Invalid magic number`, tự kết nối lại trong $\mathbf{\le 2.0\text{ s}}$ | Rút/cắm lại cáp Ethernet trên Hub Type-C hoặc ngắt Wi-Fi tạm thời |
| **AC-C07** | Mức độ cô lập môi trường phát triển (Zero System Pollution) | $\mathbf{100\%}$ artifacts nằm trong repo workspace, không chạm cấu hình OS toàn cục | Kiểm tra `git status --ignored` và xác nhận không sửa đổi `/etc/` hay `/usr/local/` |
