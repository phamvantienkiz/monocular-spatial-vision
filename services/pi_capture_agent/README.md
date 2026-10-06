# Raspberry Pi 3 Capture Agent (`pi_capture_agent`)

> **Mô tả:** Dịch vụ thu nhận hình ảnh từ Pcam 5C (OV5640) và tư thế IMU (MPU6050), đóng gói nhị phân và stream qua mạng TCP socket.

## 1. Cài đặt môi trường trên Pi 3
```bash
cd services/pi_capture_agent
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

## 2. Nhiệm vụ của Sinh viên (Student Implementation Tasks)
1. `camera.py`: Hiện thực hóa lớp `CameraDriver` đọc từ `/dev/video0` bằng OpenCV VideoCapture hoặc V4L2 API.
2. `imu.py`: Hiện thực hóa lớp `IMUReader` đọc dữ liệu gia tốc `[ax, ay, az]` qua I2C (thư viện `smbus2`), chuyển đổi thành góc `pitch` và `roll`.
3. `packer.py`: Hiện thực hóa hàm `pack_frame()` tạo cấu trúc binary header 36-byte chuẩn Big-Endian (`>HHIQffIIII`).
4. `streamer.py`: Hiện thực hóa lớp `SocketStreamer` mở kết nối TCP tới server và cơ chế thử lại (exponential backoff).
5. `cli.py`: Hoàn thiện các chế độ thực thi:
   - `--mode snapshot`: Chụp 1 ảnh lưu ra đĩa để kiểm tra.
   - `--mode preview`: Khởi chạy HTTP snapshot server kiểm tra từ laptop.
   - `--mode test-imu`: In liên tục telemetry IMU ra console.
   - `--mode stream`: Bắt đầu luồng stream liên tục tới server.
