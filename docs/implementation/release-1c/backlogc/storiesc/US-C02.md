# US-C02: Đọc IMU Qua Linux I2C ioctl & RingBuffer Streamer Đa Luồng

> **Layer:** Implementation Layer (`docs/implementation/release-1c/backlogc/storiesc/US-C02.md`)  
> **Release:** Release 1c (C/C++ Native Edge Capture & Perception Pipeline)  
> **Story ID:** US-C02  
> **Status:** Ready for Development  

---

## 1. User Story

**Là một** Kỹ sư Phần mềm Robot (Robotics Software Engineer),  
**Tôi muốn** hệ thống C++ đọc dữ liệu cảm biến gia tốc MPU6050 trực tiếp qua Linux I2C ioctl ở tần số $50\text{Hz}$, đóng gói cùng khung hình vào cấu trúc struct Header 40 bytes chuẩn mạng và truyền qua TCP socket bằng cơ chế RingBuffer đa luồng có chính sách thả trôi frame cũ (Drop-stale),  
**Để** dữ liệu truyền về phía bộ não Jetson AGX Xavier / Laptop luôn đồng bộ thời gian thực, triệt tiêu hoàn toàn độ trễ $2\text{ giây}$ do nghẽn bộ đệm socket.

---

## 2. Acceptance Criteria (Given-When-Then)

### Kịch bản 1: Giao tiếp I2C không phụ thuộc thư viện Python
- **Given:** Cảm biến MPU6050 được nối vào bus I2C-1 tại địa chỉ `0x68`.
- **When:** Module `Mpu6050Driver` mở file descriptor `/dev/i2c-1` và gọi `ioctl(fd, I2C_SLAVE, 0x68)`.
- **Then:** Module ghi thanh ghi kích hoạt `PWR_MGMT_1 (0x6B) = 0` (đánh thức cảm biến) và đọc liên tục 14 bytes thanh ghi gia tốc, nhiệt độ, con quay hồi chuyển mỗi chu kỳ $20\text{ms}$ mà không làm sụt giảm FPS của camera.

### Kịch bản 2: Đóng gói Header nhị phân 40 bytes chuẩn Network Byte Order
- **Given:** Dữ liệu khung hình JPEG mới nén xong kèm số đo góc pitch $\theta$ và roll $\phi$ tức thời từ IMU.
- **When:** Module `BinaryPacker` điền các giá trị vào `PackedFrameHeader`.
- **Then:**
  1. `magic = 0x5043`, `version = 1`.
  2. Toàn bộ các trường số được hoán vị byte qua `htons()`, `htonl()`, `htobe64()`.
  3. Tổng kích thước Header chính xác $40\text{ bytes}$ (`sizeof(PackedFrameHeader) == 40`).

### Kịch bản 3: Hàng đợi truyền dẫn đa luồng & Chính sách Drop-Stale Frame
- **Given:** Luồng bắt hình và nén ảnh sản sinh 30 khung hình mỗi giây, nhưng mạng Wi-Fi bị nghẽn làm luồng mạng chỉ truyền được 15 khung hình mỗi giây.
- **When:** Luồng nén hoàn tất frame mới và đẩy vào `SafeRingBuffer`.
- **Then:**
  1. Hàng đợi ghi đè frame mới nhất lên vị trí chờ gửi, tự động giải phóng frame cũ đã lỗi thời.
  2. Luồng socket luôn bốc frame mới nhất để gửi đi.
  3. Độ trễ hình ảnh người vận hành nhìn thấy trên màn hình không bao giờ vượt quá $30\text{ms}$ (hoàn toàn không bị delay 2 giây như bản Python).

### Kịch bản 4: Tự động kết nối lại khi đứt socket (Auto-Reconnect)
- **Given:** Server nhận trên Jetson/Laptop bị tắt hoặc rút cáp mạng.
- **When:** Phương thức `send()` trả về lỗi hoặc `EPIPE` / `ECONNRESET`.
- **Then:** Module đóng socket cũ an toàn, chuyển trạng thái sang `DISCONNECTED`, thực hiện thử kết nối lại với chu kỳ Exponential Backoff ($500\text{ms} \to 1000\text{ms} \to 2000\text{ms}$) mà không làm crash tiến trình C++.

---

## 3. ARCHITECTURE GUARDRAILS FOR CODING AGENT

> ⛔ **BẮT BUỘC TUÂN THỦ:** Trước khi viết hoặc sửa đổi mã nguồn, AI Coding Agent phải đối chiếu các ràng buộc kiến trúc sau:

1. **Tuân Thủ Tuyệt Đối Cấu Trúc Header 40 Bytes:**
   - Đối chiếu: [docs/architecture/05-data-architecture.md](file:///E:/UIT/monocular-spatial-vision/docs/architecture/05-data-architecture.md#L1-L25) & [docs/implementation/release-1c/apic/v1.md](file:///E:/UIT/monocular-spatial-vision/docs/implementation/release-1c/apic/v1.md).
   - *Ràng buộc:* Cấm thay đổi thứ tự hay kiểu dữ liệu của các trường trong struct `PackedFrameHeader`.
2. **Kích Hoạt TCP_NODELAY Bắt Buộc:**
   - Đối chiếu: [docs/architecture/08-integration-architecture.md](file:///E:/UIT/monocular-spatial-vision/docs/architecture/08-integration-architecture.md).
   - *Ràng buộc:* Socket client bắt buộc phải gọi `setsockopt(sock_fd, IPPROTO_TCP, TCP_NODELAY, &flag, sizeof(flag))` ngay sau khi kết nối thành công.
3. **An Toàn Đa Luồng (Thread Safety):**
   - Đối chiếu: [docs/architecture/09-design-principles.md](file:///E:/UIT/monocular-spatial-vision/docs/architecture/09-design-principles.md).
   - *Ràng buộc:* Dùng `std::mutex` kết hợp `std::condition_variable` hoặc `std::atomic` cho việc đồng bộ telemetry và con trỏ frame. Tuyệt đối không dùng biến toàn cục trần không có khóa bảo vệ.
