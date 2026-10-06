# Hướng Dẫn Kỹ Thuật: Raspberry Pi 3 Capture & Network Streaming

> **Layer:** Implementation Layer (`docs/implementation/release-1/guide/01-pi3-capture-and-streaming-guide.md`)  
> **Release:** Release 1 (Phase 1 Sandbox)  
> **Target Hardware:** Raspberry Pi 3 Model B+  

---

## 1. Kết Nối Phần Cứng & Thiết Lập Driver

### 1.1. Sơ đồ kết nối phần cứng (Wiring)
1. **Camera Pcam 5C (Cảm biến OmniVision OV5640):**
   - Cắm cáp dẹt 15-pin FFC vào cổng **MIPI CSI-2** trên Pi 3 (mặt tiếp xúc chân đồng hướng về phía cổng HDMI, mặt xanh hướng về phía cổng Ethernet/USB).
2. **Cảm biến IMU MPU6050 (Giao tiếp I2C):**
   - Chân `VCC` MPU6050 nối với Pin 1 (`3.3V Power`) của Pi 3.
   - Chân `GND` MPU6050 nối với Pin 6 (`Ground`) của Pi 3.
   - Chân `SDA` MPU6050 nối với Pin 3 (`GPIO 2 / I2C1 SDA`) của Pi 3.
   - Chân `SCL` MPU6050 nối với Pin 5 (`GPIO 3 / I2C1 SCL`) của Pi 3.

### 1.2. Kích hoạt giao tiếp hệ điều hành (Raspberry Pi OS)
Chạy trên terminal Pi 3:
```bash
# 1. Kích hoạt giao thức I2C và Camera
sudo raspi-config nonint do_i2c 0
sudo raspi-config nonint do_camera 0

# 2. Cấu hình Device Tree Overlay cho chip OV5640
# Với hệ điều hành Debian Bullseye/Bookworm, mở tệp cấu hình:
sudo nano /boot/firmware/config.txt   # (hoặc /boot/config.txt trên các bản cũ)

# Thêm vào cuối tệp:
dtoverlay=ov5640
dtparam=i2c_arm=on

# 3. Khởi động lại Raspberry Pi
sudo reboot
```

### 1.3. Lệnh kiểm tra phần cứng cấp thấp (Sanity Check)
Sau khi Pi 3 khởi động lại:
```bash
# Kiểm tra driver cảm biến OV5640
dmesg | grep -i ov5640
# Kết quả mong đợi: ov5640 10-003c: OV5640 probed successfully

# Kiểm tra node V4L2
v4l2-ctl --list-devices
# Kết quả mong đợi: xuất hiện /dev/video0 (unicam / ov5640)

# Kiểm tra định dạng hỗ trợ và FPS
v4l2-ctl -d /dev/video0 --list-formats-ext

# Kiểm tra địa chỉ I2C của MPU6050
i2cdetect -y 1
# Kết quả mong đợi: Thấy địa chỉ 68 xuất hiện trên bảng lưới
```

---

## 2. Quy Trình Phát Triển Code: Từ Laptop Sang Pi 3

### 2.1. Không code trực tiếp trên Pi 3
- Toàn bộ mã nguồn module `pi_capture_agent` được viết và quản lý phiên bản trên **Laptop** của developer.
- Đồng bộ mã nguồn sang Pi 3 qua 1 trong 2 cách:
  - **Cách A (Khuyến nghị):** Dùng Git repo chung: Laptop `git push origin dev` -> Pi 3 `git pull`.
  - **Cách B (Test nhanh):** Dùng lệnh rsync qua mạng LAN:
    ```bash
    # Chạy trên Laptop (WSL/macOS/Linux hoặc Git Bash)
    rsync -avz --exclude '.venv' ./services/pi_capture_agent/ pi@192.168.1.50:~/monocular-spatial-vision/services/pi_capture_agent/
    ```

### 2.2. Khởi tạo môi trường ảo Python biệt lập trên Pi 3
Theo quy định nghiêm ngặt tại [AGENTS.md](file:///E:/UIT/monocular-spatial-vision/AGENTS.md), **tuyệt đối không cài gói pip vào Python toàn cục**:
```bash
# Đăng nhập SSH vào Pi 3
ssh pi@192.168.1.50

cd ~/monocular-spatial-vision/services/pi_capture_agent

# Khởi tạo môi trường ảo cục bộ
python3 -m venv .venv
source .venv/bin/activate

# Cài đặt các gói phụ thuộc tối thiểu (nhẹ, không cài Torch/TensorRT trên Pi)
pip install --upgrade pip
pip install opencv-python-headless smbus2 pyyaml numpy
```

---

## 3. Các Bước Kiểm Nghiệm Độc Lập Trên Pi 3 (Trước Khi Nối Jetson)

Để đảm bảo không gặp tình trạng "không biết lỗi ở camera, lỗi ở mạng, hay lỗi ở Jetson", dev phải thực hiện kiểm nghiệm theo từng nấc thang:

### Nấc 1: Chụp ảnh đơn ra file và xem lại trên Laptop
Chạy script kiểm tra thu nhận frame:
```bash
python -m pi_capture_agent.cli --mode snapshot --output ./test_frame.jpg
```
**Làm sao xem ảnh khi Pi 3 không cắm màn hình HDMI?**
- **Cách 1 (Kéo file về):** Từ Laptop chạy: `scp pi@192.168.1.50:~/monocular-spatial-vision/services/pi_capture_agent/test_frame.jpg .` rồi mở xem.
- **Cách 2 (HTTP Diagnostic Server):** Bật HTTP server có sẵn trên Pi:
  ```bash
  python3 -m http.server 8080
  ```
  Trên Laptop mở trình duyệt: `http://192.168.1.50:8080/test_frame.jpg`. Xác nhận góc chụp rõ ràng, không bị mờ tiêu cự, không bị ngược màu.

### Nấc 2: Kiểm nghiệm đo đạc IMU thời gian thực
Chạy kiểm tra cảm biến MPU6050:
```bash
python -m pi_capture_agent.cli --mode test-imu
```
Terminal trên Pi 3 in ra liên tục:
```text
[IMU-TEST] Ax: 0.02g, Ay: 0.22g, Az: 0.98g | Pitch (theta): 12.45 deg | Roll (phi): -0.10 deg
[IMU-TEST] Ax: 0.03g, Ay: 0.23g, Az: 0.97g | Pitch (theta): 12.51 deg | Roll (phi): -0.08 deg
```
**Hành động kiểm nghiệm:** Dùng tay nghiêng nhẹ module giá đỡ camera lên/xuống $\to$ xác nhận góc Pitch thay đổi tức thời; nghiêng trái/phải $\to$ góc Roll thay đổi tương ứng.

### Nấc 3: Kiểm chứng Đóng gói & Stream gói tin về Laptop (Mock Ingest)
> [!IMPORTANT]
> **Tuyệt đối không stream thẳng sang Jetson khi chưa kiểm chứng bằng Laptop!**

1. **Trên Laptop của Developer:** Khởi động Mock Ingest Receiver:
   ```bash
   # Chạy trên Laptop (IP ví dụ: 192.168.1.100)
   python tools/laptop/mock_ingest_server.py --port 9876
   ```
   Script này sẽ lắng nghe socket, unpack Header 36 bytes:
   - Kiểm tra Magic bytes: `0x5043` (`PC`).
   - Đọc Timestamp, Frame ID, Pitch, Roll.
   - Giải nén ảnh JPEG và mở cửa sổ `cv2.imshow("Pi 3 Stream on Laptop", frame)` hiển thị lên màn hình máy tính của bạn.
   - In thống kê: `Received Frame #120 | 30.1 FPS | Packet Loss: 0% | Pitch: 12.5°`.

2. **Trên Raspberry Pi 3:** Kích hoạt stream trỏ vào IP Laptop:
   ```bash
   python -m pi_capture_agent.cli --mode stream --host 192.168.1.100 --port 9876
   ```

3. **Tiêu chuẩn hoàn tất kiểm chứng Pi 3:**
   - [x] Stream chạy mượt mà $30\text{ FPS}$ ở độ phân giải $1280 \times 720$.
   - [x] Không rớt gói trong 5 phút chạy liên tục qua mạng Ethernet có dây.
   - [x] Khi rút dây mạng và cắm lại, tiến trình trên Pi tự động reconnect mà không văng lỗi (unhandled crash).

👉 **Khi đạt đủ 3 tiêu chí trên, mã nguồn Pi 3 đã hoàn thiện 100%. Lúc này chỉ cần đổi cấu hình IP đích sang IP của Jetson AGX Xavier!**
