# Software Requirements Specification (SRS) — Release 1c

> **Layer:** Implementation Layer (`docs/implementation/release-1c/srs.md`)  
> **Release:** Release 1c (C/C++ Native Edge Capture & Perception Pipeline)  
> **Status:** Approved Baseline  

---

## 1. Functional Requirements (FR)

| Req ID | Yêu cầu kỹ thuật chi tiết | Độ ưu tiên | Phương pháp nghiệm thu |
| :--- | :--- | :---: | :--- |
| **FR-C01** | Hệ thống C++ phải mở thiết bị `/dev/video0` (cảm biến OV5640) qua Linux V4L2 ioctl, khóa cứng độ phân giải chuẩn gốc $1280 \times 720$ định dạng UYVY @ $30\text{ FPS}$ và cấp phát 4 bộ đệm xoay vòng qua cơ chế `V4L2_MEMORY_MMAP`. Nghiêm cấm thực hiện bất kỳ phép resize/crop nào trên Pi 3. | **Must Have** | Kiểm tra `VIDIOC_S_FMT`, `VIDIOC_REQBUFS` thành công; xác nhận kích thước buffer đúng $1280 \times 720 \times 2$ bytes. |
| **FR-C02** | Hệ thống phải tự động kích hoạt tính năng lật ảnh dọc phần cứng (Hardware Vertical Flip) trên chip cảm biến OV5640 qua `V4L2_CID_VFLIP` với chi phí CPU $0.0\text{ms}$. | **Must Have** | Ảnh thu được đúng chiều không gian; thời gian grab không tăng thêm. |
| **FR-C03** | Module `ImuDriver` phải đọc thanh ghi gia tốc 3 trục từ cảm biến MPU6050 qua file descriptor `/dev/i2c-1` bằng `ioctl(I2C_SLAVE, 0x68)`, duy trì chu kỳ đọc $20\text{ms}$ ($50\text{Hz}$) và tính góc pitch $\theta$, roll $\phi$ chính xác. | **Must Have** | Chạy kiểm thử đọc mẫu telemetry, in liên tục góc nghiêng khi board dao động. |
| **FR-C04** | Module `JpegEncoder` phải sử dụng C API của `libjpeg-turbo` với chỉ lệnh SIMD ARM NEON (`TJSAMP_422`, cờ `TJFLAG_FASTDCT`) để nén frame UYVY $1280 \times 720$ sang JPEG với thời gian xử lý $\le 10\text{ms}$/frame. | **Must Have** | Đo thời gian gọi `tjCompress2()` qua 500 frames liên tục. |
| **FR-C05** | Hệ thống phải đóng gói dữ liệu vào cấu trúc struct C `PackedFrameHeader` (40 bytes, `__attribute__((packed))`, Magic `0x5043`, `width=1280`, `height=720`, `timestamp_ns`, `pitch_deg`, `roll_deg`, `payload_len`), chuyển đổi endianness chuẩn mạng (Big-Endian). | **Must Have** | Hexdump gói tin tại socket server nhận kiểm tra các trường bytes chuẩn xác. |
| **FR-C06** | Hệ thống phải thực thi cơ chế đa luồng tách biệt giữa luồng thu nhận (Capture), luồng nén (Encode), luồng đọc cảm biến (IMU) và luồng truyền socket (Streamer) thông qua hàng đợi đệm RingBuffer thread-safe có cơ chế tự động hủy frame cũ (Drop-stale policy) khi mạng chậm. | **Must Have** | Giả lập nghẽn mạng Wi-Fi; độ trễ hình ảnh quan sát không vượt quá $25\text{ms}$, không bị dồn ứ hàng đợi. |
| **FR-C07** | Module `TcpStreamer` phải tạo POSIX socket, thiết lập cờ `TCP_NODELAY` (vô hiệu hóa thuật toán Nagle), quản lý kết nối bất đồng bộ và tự động kết nối lại (Auto-reconnect với Exponential Backoff từ $500\text{ms}$ đến $3000\text{ms}$) khi đường truyền bị ngắt. | **Must Have** | Rút dây mạng Ethernet hoặc tắt socket server; tiến trình C++ không crash và tự kết nối lại ngay khi server mở lại. |
| **FR-C08** | Toàn bộ các thư viện phụ thuộc của dự án C++ (`libjpeg-turbo`, `nlohmann_json`, `yaml-cpp`) phải được khai báo trong `conanfile.txt` và cài đặt thông qua `Conan 2.0` chạy trong môi trường ảo `.venv` tạo bởi `uv` với biến `CONAN_HOME` nằm trong repo. | **Must Have** | Kiểm tra cấu trúc thư mục sau khi build; biến môi trường hệ thống không bị thay đổi; xóa repo là sạch hoàn toàn. |
| **FR-C09** | Quá trình biên dịch native trên Raspberry Pi 3 phải được điều khiển qua CMake với cờ giới hạn luồng (`-j2` hoặc `-j1`), kiểm tra dung lượng Swap $\ge 2048\text{MB}$ trước khi build nhằm triệt tiêu nguy cơ tràn RAM (OOM). | **Must Have** | Chạy lệnh build native trên Pi 3 hoàn tất 100% không bị kernel OOM Killer ngắt tiến trình. |

---

## 2. Non-Functional Requirements (NFR)

- **NFR-C01 (Thông lượng & Tốc độ Khung hình):** Toàn bộ pipeline bắt hình, nén ảnh 720p và truyền gói tin đạt tốc độ ổn định $\ge 25\text{ FPS}$ (khuyến nghị $30\text{ FPS}$) tại độ phân giải gốc $1280 \times 720$.
- **NFR-C02 (Dấu ấn Bộ nhớ & CPU Tiêu thụ):**
  - Mức chiếm dụng RAM tối đa của tiến trình C++ trên Pi 3 không vượt quá $\mathbf{35\text{ MB}}$ (so với $250\text{ MB}$ của bản Python).
  - Tải CPU trên 4 nhân Cortex-A53 không vượt quá $\mathbf{25\%}$ tổng năng lực tính toán.
- **NFR-C03 (Zero Resize Overhead on Edge):** Thời gian CPU tiêu tốn cho việc thay đổi kích thước khung hình trên Pi 3 là chính xác $\mathbf{0.00\text{ ms}}$.
- **NFR-C04 (Cách ly Môi trường - Zero Global Pollution):** Tuyệt đối không cài đặt bất kỳ file nhị phân, thư viện shared object hay biến môi trường nào vào `/usr/local/`, `/usr/lib/` hoặc `/etc/environment`. Toàn bộ artifacts và cache nằm trong workspace của repo.
- **NFR-C05 (Độ bền Vận hành & Phục hồi):** Hệ thống có khả năng hoạt động liên tục trong ít nhất $24\text{ giờ}$ mà không rò rỉ bộ nhớ (Zero Memory Leak) và tự động hồi phục kết nối trong vòng $\le 2\text{ giây}$ khi xảy ra sự cố mạng.
