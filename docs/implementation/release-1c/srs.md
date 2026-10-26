# Software Requirements Specification (SRS) — Release 1c

> **Layer:** Implementation Layer (`docs/implementation/release-1c/srs.md`)  
> **Release:** Release 1c (C/C++ Native Edge Capture & Perception Pipeline)  
> **Status:** Approved Baseline (Audited & Revised)  

---

## 1. Functional Requirements (FR)

| Req ID | Yêu cầu kỹ thuật chi tiết | Độ ưu tiên | Phương pháp nghiệm thu |
| :--- | :--- | :---: | :--- |
| **FR-C01** | Module `V4l2CameraDriver` phải tự động đàm phán cấu hình Media Controller (`/dev/media0`) để đặt định dạng pad cảm biến `'ov5640 10-003c':0` thành `UYVY8_1X16/1280x720@1/30`, sau đó mở `/dev/video0` với `O_RDWR \| O_NONBLOCK`, cấu hình `V4L2_PIX_FMT_UYVY` $1280 \times 720$ và cấp phát 4 bộ đệm xoay vòng qua `V4L2_MEMORY_MMAP`. | **Must Have** | Kiểm tra `VIDIOC_S_FMT`, `VIDIOC_REQBUFS`, `VIDIOC_STREAMON` thành công 100%, không xảy ra lỗi `-EPIPE`. |
| **FR-C02** | Hệ thống phải tự động kích hoạt tính năng lật ảnh dọc phần cứng (Hardware Vertical Flip) bằng lệnh `ioctl(subdev_fd, VIDIOC_S_CTRL)` với `V4L2_CID_VFLIP = 1` trực tiếp trên thiết bị subdevice cảm biến (`/dev/v4l-subdev0`, có fallback thử trên `/dev/video0`). | **Must Have** | Ảnh thu được đúng chiều không gian; chi phí lật ảnh trên CPU bằng $0.0\text{ms}$. |
| **FR-C03** | Vòng lặp bắt hình phải sử dụng `poll()` chờ sự kiện `POLLIN` trước khi gọi `ioctl(fd, VIDIOC_DQBUF)`, sau đó dùng chỉ lệnh ARM NEON (`vld2_u8`) tách kênh `UYVY` sang bộ đệm phẳng `YUV422P` trong $\le 1.5\text{ms}$ và gọi ngay `ioctl(fd, VIDIOC_QBUF)` để trả bộ đệm DMA về cho kernel. | **Must Have** | Không bao giờ xảy ra lỗi `EAGAIN` không xử lý hoặc rò rỉ làm cạn kiệt 4 bộ đệm MMAP khi chạy dài hạn. |
| **FR-C04** | Module `TurboJpegEncoder` phải sử dụng C API `tjCompressFromYUV()` của `libjpeg-turbo` (`TJSAMP_422`, cờ `TJFLAG_FASTDCT \| TJFLAG_NOREALLOC`) trên bộ đệm phẳng `YUV422P` để nén khung hình $1280 \times 720$ sang JPEG với thời gian nén tích cực $\le 10.0\text{ms}$/frame. | **Must Have** | Đo thời gian gọi `tjCompressFromYUV()` qua 500 frames liên tục bằng `--mode test-perf`. |
| **FR-C05** | Module `Mpu6050Driver` phải mở `/dev/i2c-1`, gọi `ioctl(fd, I2C_SLAVE, 0x68)`, xác thực thanh ghi `WHO_AM_I (0x75) == 0x68`, cấu hình bộ lọc thông thấp DLPF (`0x1A = 0x03`), duy trì chu kỳ đọc $20\text{ms}$ ($50\text{Hz}$) và tính góc pitch $\theta$, roll $\phi$ chính xác. | **Must Have** | Chạy `--mode diag` và `--mode test-imu`, xác nhận góc nghiêng cập nhật mượt mà ở $50\text{Hz}$. |
| **FR-C06** | Module `BinaryPacker` phải đóng gói dữ liệu vào struct `PackedFrameHeader` 40 bytes (`#pragma pack(push, 1)`, tương đương chuẩn `>HHIQffIIII`: `magic=0x5043`, `version=1`, `frame_id`, `timestamp_ns`, `pitch_deg`, `roll_deg`, `payload_len`, `width`, `height`, `reserved`), sử dụng `std::memcpy` + `htonl()` để chuyển đổi `float` sang Big-Endian an toàn tuyệt đối với Strict Aliasing (`-O3`). | **Must Have** | Unit test `test_header_packing` và kiểm thử giải mã thực tế trên `mock_ingest_server.py` / `IngestService`. |
| **FR-C07** | Hệ thống phải cung cấp đầy đủ **6 chế độ CLI** tương đương hoàn toàn với bản Python: `--mode diag`, `--mode snapshot`, `--mode test-imu`, `--mode preview`, `--mode stream`, và `--mode test-perf`, đọc cấu hình mặc định từ `configs/capture_pi.yaml`. | **Must Have** | Kiểm thử từng cờ CLI trên Raspberry Pi 3, đối chiếu hành vi tương đồng 100% với bản Python. |
| **FR-C08** | Ở chế độ `--mode preview` (cổng mặc định `8080`), hệ thống phải khởi chạy HTTP Server nội bộ phục vụ giao diện HTML HUD (`/`), luồng MJPEG (`/stream.mjpg` có bật `TCP_NODELAY`), ảnh đơn (`/snapshot.jpg`) và JSON (`/telemetry`), hỗ trợ thu nhỏ ảnh preview ($640 \times 360$, $Q=65$) để kiểm thử mượt mà qua mạng **Wi-Fi** hoặc **Ethernet** trên trình duyệt Laptop. | **Must Have** | Mở `http://<pi_ip>:8080/preview` trên Laptop qua Wi-Fi và Ethernet, xác nhận video mượt $18 - 30\text{ FPS}$, không bị trễ tích lũy. |
| **FR-C09** | Ở chế độ `--mode stream`, module `TcpStreamer` phải hỗ trợ truyền luồng nhị phân qua cả **Wi-Fi** lẫn **Cáp Ethernet** (cắm qua Hub Type-C vào Laptop hoặc cắm trực tiếp vào Jetson AGX Xavier), bật cờ `TCP_NODELAY`, sử dụng bộ đệm đôi/ba (Double/Triple Buffer) kèm chính sách `LatestFrameSlot` (hủy frame cũ chưa gửi nếu mạng chậm) và hàm `send_all()` đảm bảo gửi trọn vẹn 100% số byte của mỗi gói tin đã bắt đầu truyền. | **Must Have** | Kiểm thử stream qua Wi-Fi và qua cáp Ethernet (Hub Type-C Laptop / Jetson); rút cáp cắm lại tự động reconnect trong $\le 2\text{s}$, không báo lỗi `Invalid magic number`. |
| **FR-C10** | Toàn bộ thư viện phụ thuộc C++ (`libjpeg-turbo`, `yaml-cpp`, `nlohmann_json`) phải được quản lý bởi `Conan 2.0` trong `.venv` tạo bởi `uv` với `CONAN_HOME` đặt tại `.conan/` trong repo, và cấu hình `CMakeLists.txt` tương thích từ `CMake 3.18+` (hỗ trợ cả Debian Bullseye và Bookworm/Trixie). | **Must Have** | Kiểm toán thư mục sau khi build; không can thiệp `/etc/dphys-swapfile` hay `/usr/local/`. |

---

## 2. Non-Functional Requirements (NFR)

- **NFR-C01 (Thông lượng & Tốc độ Khung hình):**
  - Khi truyền qua **Cáp Ethernet** (nối vào Hub Type-C của Laptop hoặc cổng Ethernet của Jetson AGX Xavier), luồng `--mode stream` ở độ phân giải gốc $1280 \times 720$ đạt tốc độ ổn định $\mathbf{25.0 - 30.0\text{ FPS}}$.
  - Khi truyền qua **Wi-Fi** trong phòng thí nghiệm, luồng `--mode preview` ($640 \times 360$) và `--mode stream` duy trì phản hồi thời gian thực với độ trễ hiển thị $< 40\text{ms}$ (tự động bỏ qua frame cũ khi sóng Wi-Fi dao động, tuyệt đối không để dồn ứ gây lag 2 giây).
- **NFR-C02 (Dấu ấn Bộ nhớ & CPU Tiêu thụ):**
  - Mức chiếm dụng RAM tối đa (RSS) của tiến trình C++ trên Pi 3 không vượt quá $\mathbf{35\text{ MB}}$.
  - Tổng tải CPU trên 4 nhân Cortex-A53 không vượt quá $\mathbf{25\%}$ công suất toàn hệ thống.
- **NFR-C03 (Tính linh hoạt mạng - Zero-Friction Networking):**
  - Không yêu cầu gán IP tĩnh cố định trên Laptop của developer khi cắm cáp Ethernet qua Hub Type-C (tương thích hoàn toàn với địa chỉ tự động APIPA `169.254.x.x`, mDNS `.local` hoặc truyền IP động qua tham số `--host`).
- **NFR-C04 (Cách ly Môi trường - Zero Global Pollution):**
  - Tuyệt đối không cài đặt bất kỳ file nhị phân, thư viện hay sửa đổi cấu hình hệ thống nào ngoài phạm vi thư mục dự án.
- **NFR-C05 (Độ bền Vận hành & An toàn Bộ nhớ):**
  - Hoạt động liên tục mà không rò rỉ bộ nhớ heap (`0 bytes lost` trên Valgrind/ASan) và không làm rò rỉ bộ đệm `V4L2_MEMORY_MMAP`.
