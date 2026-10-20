# US-C02: Đọc IMU I2C, Triple-Buffer Drop-Stale & Truyền Dẫn Kép Wi-Fi / Ethernet (`--mode preview` & `--mode stream`)

> **Layer:** Implementation Layer (`docs/implementation/release-1c/backlogc/storiesc/US-C02.md`)  
> **Release:** Release 1c (C/C++ Native Edge Capture & Perception Pipeline)  
> **Story ID:** US-C02  
> **Status:** Ready for Development (Audit-Remediated)  

---

## 1. User Story

**Là một** Kỹ sư Phần mềm Robot (Robotics Software Engineer),  
**Tôi muốn** hệ thống C++ đọc cảm biến MPU6050 qua Linux I2C ioctl ở tần số $50\text{Hz}$, đồng bộ an toàn với khung hình qua cơ chế **Triple-Buffer Drop-Stale**, đồng thời giữ nguyên cả **2 phương thức truyền dẫn vật lý (Wi-Fi & Ethernet)** lẫn cả **2 chế độ kiểm thử mạng (`--mode preview` qua HTTP MJPEG `:8080` và `--mode stream` qua TCP Binary `:9876`)** như phiên bản Python hiện tại,  
**Để** tôi có thể linh hoạt dùng Wi-Fi hoặc dây Ethernet (qua Hub chuyển đổi USB Type-C sang RJ45) khi test trực quan với Laptop, và dùng cổng Ethernet tốc độ cao khi tích hợp thực tế với Jetson AGX Xavier mà không gặp hiện tượng trễ hình hay lệch khung (`framing desync`).

---

## 2. Acceptance Criteria (Given-When-Then)

### Kịch bản 1: Giao tiếp I2C không phụ thuộc thư viện Python & Hỗ trợ `--mode test-imu`
- **Given:** Cảm biến MPU6050 được nối vào bus I2C-1 tại địa chỉ `0x68`.
- **When:** Module `Mpu6050Driver` mở `/dev/i2c-1`, gọi `ioctl(fd, I2C_SLAVE, 0x68)` hoặc kỹ sư chạy lệnh `./pi_capture_agent_cpp --mode test-imu`.
- **Then:** Module đánh thức cảm biến (`PWR_MGMT_1 = 0`), đọc liên tục 14 bytes thanh ghi mỗi chu kỳ $20\text{ms}$ ($50\text{Hz}$), lọc nhiễu Complementary Filter và xuất góc `pitch_deg`, `roll_deg` chính xác mà không làm giảm FPS của camera.

### Kịch bản 2: Đóng gói Header nhị phân 40 bytes an toàn Strict-Aliasing (`-O3`)
- **Given:** Khung hình JPEG mới nén xong kèm góc `pitch_deg` và `roll_deg` tức thời từ IMU.
- **When:** Hàm `make_packed_header()` đóng gói dữ liệu vào `PackedFrameHeader`.
- **Then:**
  1. `magic_be = htons(0x5043)`, `version_be = htons(1)`.
  2. Các giá trị `float` (`pitch_deg`, `roll_deg`) được sao chép bit qua `std::memcpy(&raw_bits, &val, sizeof(float))` trước khi gọi `htonl(raw_bits)`, đảm bảo không phát sinh Undefined Behavior khi biên dịch với `-O3`.
  3. Tổng kích thước Header chính xác $40\text{ bytes}$ (`sizeof(PackedFrameHeader) == 40`), giải mã khớp $100\%$ với `struct.unpack(">HHIQffIIII", buf)` trên Python Ingest Server.

### Kịch bản 3: Đồng bộ Triple-Buffer Drop-Stale & Gửi nguyên tử `send_all()`
- **Given:** Luồng nén JPEG hoạt động ở $30\text{ FPS}$, nhưng đường truyền mạng bị nghẽn tạm thời chỉ đạt $15\text{ FPS}$.
- **When:** Luồng nén hoàn tất frame mới trong khi luồng mạng đang gửi dở gói tin hiện tại qua hàm `send_all()`.
- **Then:**
  1. Luồng nén ghi vào `write_slot` riêng biệt và hoán đổi `latest_slot` (Drop-Stale) mà **không bao giờ ghi đè** vào `read_slot` đang được `send_all()` truyền đi.
  2. Một khi `send_all()` đã bắt đầu gửi 1 frame (`40 bytes header + payload_len bytes JPEG`), hàm phải dùng `poll(POLLOUT)` gửi trọn vẹn đủ số byte đó (hoặc đóng socket kết nối lại nếu đứt mạng), tuyệt đối không bỏ dở giữa chừng làm hỏng byte đồng bộ `0x5043` phía nhận.

### Kịch bản 4: Giữ nguyên chế độ `--mode preview` (HTTP MJPEG + Telemetry HUD qua Wi-Fi & Ethernet)
- **Given:** Kỹ sư kết nối Pi 3 với Laptop qua Wi-Fi hoặc dây Ethernet (Hub USB Type-C).
- **When:** Chạy lệnh `./pi_capture_agent_cpp --mode preview --port 8080` và mở trình duyệt trên Laptop tại `http://<PI_IP>:8080/preview`.
- **Then:**
  1. Trình duyệt hiển thị mượt mà luồng video MJPEG (`640x360` giảm chiều bằng NEON) kèm thông số IMU (`pitch`, `roll`) và FPS thời gian thực.
  2. Các endpoint `/stream.mjpg`, `/snapshot.jpg`, và `/telemetry` phản hồi đúng chuẩn giống hệt phiên bản Python `preview_server.py`.

### Kịch bản 5: Hỗ trợ `--mode stream` qua cả Wi-Fi, Ethernet Hub Type-C (Laptop) và Ethernet (Jetson)
- **Given:** Kỹ sư cần kiểm thử luồng nhị phân TCP `:9876` trên Laptop (qua Wi-Fi hoặc cáp Ethernet gắn Hub Type-C) hoặc tích hợp thực tế trên Jetson AGX Xavier.
- **When:** Chạy lệnh `./pi_capture_agent_cpp --mode stream --host <TARGET_IP> --port 9876`.
- **Then:**
  1. Khi test qua **Wi-Fi với Laptop**: Hệ thống tự động điều tiết Drop-Stale êm ái ở $15 - 30\text{ FPS}$ mà không gây trễ tích lũy.
  2. Khi test qua **dây Ethernet + Hub chuyển đổi USB Type-C với Laptop**: Hỗ trợ kết nối ngay qua IP APIPA (`169.254.x.x`), mDNS (`raspberrypi.local`), hoặc IP truyền qua `--host` mà không bắt buộc cấu hình Static IP cố định trên Laptop, đạt trọn vẹn $30\text{ FPS}$ ở $1280 \times 720$.
  3. Khi tích hợp thực tế qua **cổng Ethernet với Jetson AGX Xavier (`192.168.1.20`)**: Đạt $30\text{ FPS}$ ổn định và tự động kết nối lại (Exponential Backoff $500\text{ms} \to 2000\text{ms}$) nếu rút/cắm lại dây mạng.

---

## 3. ARCHITECTURE GUARDRAILS FOR CODING AGENT

> ⛔ **BẮT BUỘC TUÂN THỦ:** Trước khi viết hoặc sửa đổi mã nguồn, AI Coding Agent phải đối chiếu các ràng buộc kiến trúc sau:

1. **Tuân Thủ Tuyệt Đối Cấu Trúc Header 40 Bytes & Gửi Nguyên Tử (`send_all`):**
   - Đối chiếu: [docs/architecture/05-data-architecture.md](file:///E:/UIT/monocular-spatial-vision/docs/architecture/05-data-architecture.md) & [docs/implementation/release-1c/apic/v1.md](file:///E:/UIT/monocular-spatial-vision/docs/implementation/release-1c/apic/v1.md).
   - *Ràng buộc:* Cấm thay đổi thứ tự trường trong `PackedFrameHeader`. Không bao giờ được gửi một phần của frame rồi nhảy sang frame mới trên cùng một kết nối TCP.
2. **Kích Hoạt `TCP_NODELAY` & Xử Lý `MSG_NOSIGNAL`:**
   - Đối chiếu: [docs/architecture/08-integration-architecture.md](file:///E:/UIT/monocular-spatial-vision/docs/architecture/08-integration-architecture.md).
   - *Ràng buộc:* Socket client bắt buộc bật `TCP_NODELAY = 1` và truyền cờ `MSG_NOSIGNAL` trong lời gọi `send()` để tiến trình C++ không bị hệ điều hành kết liễu bởi tín hiệu `SIGPIPE` khi phía nhận đóng kết nối đột ngột.
3. **An Toàn Đa Luồng Với Triple-Buffer Pool:**
   - Đối chiếu: [docs/architecture/09-design-principles.md](file:///E:/UIT/monocular-spatial-vision/docs/architecture/09-design-principles.md).
   - *Ràng buộc:* Luồng Encode và luồng Network phải trao đổi dữ liệu qua `TripleBufferPacketPool` có bảo vệ bởi `std::mutex` + `std::condition_variable` với thời gian giữ khóa $< 1\,\mu\text{s}$ (chỉ tráo chỉ số index của slot).
