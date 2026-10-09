# Raspberry Pi 3 Capture Agent (`pi_capture_agent`)

> **Mô tả:** Dịch vụ thu nhận hình ảnh từ Pcam 5C (OV5640) và tư thế IMU (MPU6050), đóng gói nhị phân và stream qua mạng TCP socket.  
> **Hướng dẫn thực hành chi tiết (Step-by-Step):** Xem [06-pi3-step-by-step-bringup-and-verification-guide.md](file:///D:/ASICLAB/monocular-spatial-vision/docs/implementation/release-1/guide/06-pi3-step-by-step-bringup-and-verification-guide.md).

## 1. Cài đặt môi trường trên Pi 3
```bash
cd services/pi_capture_agent
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

## 2. Các Chế Độ Vận Hành (Operating Modes)

Dịch vụ hỗ trợ các chế độ chạy độc lập để kiểm thử từng thành phần:

### 2.1. Kiểm tra phần cứng (Hardware Diagnostic)
Kiểm tra nhanh kết nối I2C (MPU6050) và node V4L2 camera:
```bash
python -m pi_capture_agent.cli --mode check-hardware
# Hoặc chạy script chẩn đoán chuyên sâu:
bash ../../tools/pi/check_hardware.sh
```

### 2.2. Kiểm thử cảm biến IMU MPU6050 liên tục (`--mode test-imu`)
In dữ liệu gia tốc $(a_x, a_y, a_z)$, góc chúc $Pitch$ $(\theta)$, góc nghiêng ngang $Roll$ $(\phi)$, và vận tốc góc $(\omega_x, \omega_y, \omega_z)$ ra console ở tần số $50\text{Hz}$:
```bash
python -m pi_capture_agent.cli --mode test-imu
```
*Hành động kiểm chứng:* Cầm nghiêng camera lên/xuống $\to$ góc Pitch thay đổi tức thời; nghiêng trái/phải $\to$ góc Roll thay đổi tương ứng.

### 2.3. Chụp 1 khung hình thử nghiệm (`--mode snapshot`)
Chụp ảnh 1280x720, đọc tư thế IMU đồng thời và lưu ảnh ra đĩa:
```bash
python -m pi_capture_agent.cli --mode snapshot --output ./data/test_frame.jpg
```

### 2.4. Khởi chạy HTTP Diagnostic HUD (`--mode preview`)
Khi SSH vào Pi 3 không có màn hình HDMI, khởi chạy server HTTP để xem luồng video MJPEG và HUD IMU trực tiếp từ trình duyệt trên Laptop:
```bash
python -m pi_capture_agent.cli --mode preview --preview-port 8080
```
Mở trình duyệt trên máy tính cùng mạng LAN:
- **Web HUD tương tác:** `http://<IP_PI_3>:8080/`
- **Ảnh tĩnh đơn:** `http://<IP_PI_3>:8080/snapshot.jpg`
- **Dữ liệu IMU JSON:** `http://<IP_PI_3>:8080/telemetry`

### 2.5. Luồng truyền nhận TCP Socket (`--mode stream`)
Stream liên tục 30 FPS với Header 36 bytes chuẩn Big-Endian kèm ảnh JPEG nén sang server đích:
```bash
# 1. Trên Laptop (kiểm thử độc lập Phase 3):
python tools/laptop/mock_ingest_server.py --port 9876

# 2. Trên Raspberry Pi 3:
python -m pi_capture_agent.cli --mode stream --host <IP_LAPTOP> --port 9876
```
*(Tự động kích hoạt cơ chế exponential backoff reconnect khi mạng bị ngắt quãng).*

## 3. Cấu Trúc Mã Nguồn Module
- `camera.py`: `CameraDriver` điều khiển V4L2 `/dev/video0`, nén JPEG và đóng dấu `timestamp_ns`.
- `imu.py`: `IMUReader` giao tiếp MPU6050 qua I2C (`smbus2`), tính $Pitch = \arctan2(-a_x, \sqrt{a_y^2 + a_z^2})$, $Roll = \arctan2(a_y, a_z)$ và tích hợp bộ lọc bù Complementary Filter.
- `packer.py`: `BinaryFramePacker` đóng/mở gói nhị phân 36-byte header (`>HHIQffIIII`) + payload ảnh.
- `streamer.py`: `SocketStreamer` TCP client có `TCP_NODELAY` và cơ chế auto-reconnect.
- `cli.py`: Entrypoint hỗ trợ toàn bộ 5 chế độ kiểm thử và vận hành.

